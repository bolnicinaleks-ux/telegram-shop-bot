from datetime import timedelta
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot import keyboards as kb
from bot.config import Config
from bot.db import Database
from bot.delivery import deliver_order, notify_admins, refresh_order_cards, safe_delete
from bot.states import Checkout
from bot.utils import (
    cart_totals,
    delivery_line,
    fmt_price,
    is_available,
    items_lines,
    normalize_phone,
    now_local,
    order_short,
    product_caption,
    totals_lines,
)

router = Router(name="client")

EMPTY_CART_KB = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text=kb.BTN_CATALOG, callback_data=kb.MenuCb(to="cats").pack())]]
)


# --- Отрисовка ---

async def _send_categories(message: Message, db: Database) -> None:
    categories = await db.visible_categories()
    if not categories:
        await message.answer("Каталог пока пуст.", reply_markup=kb.main_menu())
        return
    await message.answer("Выберите категорию:", reply_markup=kb.categories_kb(categories))


async def _send_product(message: Message, db: Database, cfg: Config, user_id: int, cat_id: int, i: int) -> None:
    products = await db.category_products(cat_id)
    if not products:
        await _send_categories(message, db)
        return
    i %= len(products)
    p = products[i]
    markup = kb.product_kb(p, await db.cart_qty(user_id, p["id"]), cat_id, i, len(products))
    if p["photo_id"]:
        await message.answer_photo(p["photo_id"], caption=product_caption(p, cfg), reply_markup=markup)
    else:
        await message.answer(product_caption(p, cfg), reply_markup=markup)


async def _cart_view(db: Database, cfg: Config, user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    items = await db.cart_items(user_id)
    if not items:
        return "🛒 Корзина пуста.", EMPTY_CART_KB
    total, unavailable = cart_totals(items, cfg)
    lines = []
    for it in items:
        if is_available(it):
            lines.append(
                f"• {escape(it['name'])} — {fmt_price(it['price'], cfg.currency)} × {it['qty']} = "
                f"{fmt_price(it['price'] * it['qty'], cfg.currency)}"
            )
        else:
            lines.append(f"• <s>{escape(it['name'])}</s> — недоступен")
    text = "<b>Корзина</b>\n\n" + "\n".join(lines) + f"\n\n<b>Сумма: {fmt_price(total, cfg.currency)}</b>"
    if cfg.delivery_enabled and cfg.free_delivery_from:
        text += f"\nБесплатная доставка от {fmt_price(cfg.free_delivery_from, cfg.currency)}"
    if cfg.min_order and total < cfg.min_order:
        text += f"\n❗ Минимальная сумма заказа — {fmt_price(cfg.min_order, cfg.currency)}"
    if unavailable:
        text += "\n❗ Уберите недоступные товары, чтобы оформить заказ."
    return text, kb.cart_kb(items)


async def _edit_cart(message: Message, db: Database, cfg: Config, user_id: int) -> None:
    text, markup = await _cart_view(db, cfg, user_id)
    try:
        await message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


async def _my_orders_view(db: Database, cfg: Config, user_id: int) -> tuple[str, InlineKeyboardMarkup | None]:
    orders = await db.user_orders(user_id)
    if not orders:
        return "У вас пока нет заказов.", None
    blocks = []
    for o in orders:
        items = await db.order_items(o["id"])
        blocks.append(order_short(o, cfg) + "\n" + escape(", ".join(f"{i['name']} × {i['qty']}" for i in items)))
    return "<b>Ваши заказы</b>\n\n" + "\n\n".join(blocks), kb.my_orders_kb(orders)


async def _checkout_problem(db: Database, cfg: Config, user_id: int) -> str | None:
    """Почему нельзя оформить корзину (или None, если можно)."""
    items = await db.cart_items(user_id)
    if not items:
        return "Корзина пуста."
    total, unavailable = cart_totals(items, cfg)
    if unavailable:
        return "В корзине есть недоступные товары — уберите их."
    if cfg.min_order and total < cfg.min_order:
        return f"Минимальная сумма заказа — {fmt_price(cfg.min_order, cfg.currency)}."
    since = now_local(cfg) - timedelta(hours=1)
    if await db.count_orders_since(user_id, since) >= cfg.max_orders_per_hour:
        return "Слишком много заказов за последний час. Попробуйте позже."
    return None


def _checkout_text(data: dict, items, items_total: int, delivery_price: int, cfg: Config) -> str:
    parts = [
        "<b>Ваш заказ</b>",
        "",
        items_lines(items, cfg),
        "",
        totals_lines(items_total, delivery_price, data["delivery"], cfg),
        "",
        f"👤 {escape(data['client_name'])}, {escape(data['phone'])}",
        delivery_line(data["delivery"], data.get("address"), cfg),
    ]
    if data.get("comment"):
        parts.append(f"💬 {escape(data['comment'])}")
    if cfg.payment_info:
        parts += ["", f"💳 {escape(cfg.payment_info)}"]
    return "\n".join(parts)


async def _calc(db: Database, cfg: Config, user_id: int, delivery: str):
    items = await db.cart_items(user_id)
    items_total, _ = cart_totals(items, cfg)
    delivery_price = cfg.delivery_cost(items_total) if delivery == "delivery" else 0
    return items, items_total, delivery_price


# --- Меню ---

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, cfg: Config) -> None:
    await state.clear()
    await message.answer(
        f"Добро пожаловать в <b>{escape(cfg.shop_name)}</b>!\n\n"
        f"{kb.BTN_CATALOG} — товары\n{kb.BTN_CART} — ваша корзина\n{kb.BTN_ORDERS} — статусы заказов",
        reply_markup=kb.main_menu(),
    )


@router.message(Command("catalog"))
@router.message(F.text == kb.BTN_CATALOG)
async def cmd_catalog(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    await _send_categories(message, db)


@router.message(Command("cart"))
@router.message(F.text == kb.BTN_CART)
async def cmd_cart(message: Message, state: FSMContext, db: Database, cfg: Config) -> None:
    await state.clear()
    text, markup = await _cart_view(db, cfg, message.from_user.id)
    await message.answer(text, reply_markup=markup)


@router.message(Command("myorders"))
@router.message(F.text == kb.BTN_ORDERS)
async def cmd_my_orders(message: Message, state: FSMContext, db: Database, cfg: Config) -> None:
    await state.clear()
    text, markup = await _my_orders_view(db, cfg, message.from_user.id)
    await message.answer(text, reply_markup=markup or kb.main_menu())


# --- Каталог ---

@router.callback_query(kb.NoopCb.filter())
async def noop(cb: CallbackQuery) -> None:
    await cb.answer()


@router.callback_query(kb.MenuCb.filter(F.to == "cats"))
async def to_categories(cb: CallbackQuery, db: Database) -> None:
    await cb.answer()
    await safe_delete(cb.message)
    await _send_categories(cb.message, db)


@router.callback_query(kb.CatCb.filter())
async def open_category(cb: CallbackQuery, callback_data: kb.CatCb, db: Database, cfg: Config) -> None:
    await cb.answer()
    await safe_delete(cb.message)
    await _send_product(cb.message, db, cfg, cb.from_user.id, callback_data.id, 0)


@router.callback_query(kb.BrowseCb.filter())
async def browse(cb: CallbackQuery, callback_data: kb.BrowseCb, db: Database, cfg: Config) -> None:
    await cb.answer()
    await safe_delete(cb.message)
    await _send_product(cb.message, db, cfg, cb.from_user.id, callback_data.c, callback_data.i)


@router.callback_query(kb.CardCb.filter())
async def card_cart(cb: CallbackQuery, callback_data: kb.CardCb, db: Database) -> None:
    p = await db.get_product(callback_data.p)
    if p is None or p["hidden"] or p["deleted"]:
        await cb.answer("Товар больше недоступен", show_alert=True)
        return
    adding = callback_data.a in ("add", "inc")
    if adding and not p["in_stock"]:
        await cb.answer("Нет в наличии", show_alert=True)
        return
    qty = await db.cart_change(cb.from_user.id, p["id"], 1 if adding else -1)

    products = await db.category_products(callback_data.c)
    ids = [x["id"] for x in products]
    i = ids.index(p["id"]) if p["id"] in ids else callback_data.i
    try:
        await cb.message.edit_reply_markup(reply_markup=kb.product_kb(p, qty, callback_data.c, i, len(products)))
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await cb.answer(f"В корзине: {qty} шт" if qty else "Убрано из корзины")


# --- Корзина ---

@router.callback_query(kb.CartCb.filter(F.a == "show"))
async def cart_show(cb: CallbackQuery, state: FSMContext, db: Database, cfg: Config) -> None:
    await state.clear()
    text, markup = await _cart_view(db, cfg, cb.from_user.id)
    await cb.message.answer(text, reply_markup=markup)
    await cb.answer()


@router.callback_query(kb.CartCb.filter(F.a.in_({"inc", "dec", "del", "clear"})))
async def cart_edit(cb: CallbackQuery, callback_data: kb.CartCb, db: Database, cfg: Config) -> None:
    uid, a = cb.from_user.id, callback_data.a
    if a == "clear":
        await db.cart_clear(uid)
    elif a == "del":
        await db.cart_remove(uid, callback_data.p)
    elif a == "dec":
        await db.cart_change(uid, callback_data.p, -1)
    else:
        p = await db.get_product(callback_data.p)
        if p is None or not is_available(p):
            await cb.answer("Товар недоступен", show_alert=True)
            await _edit_cart(cb.message, db, cfg, uid)
            return
        await db.cart_change(uid, p["id"], 1)
    await _edit_cart(cb.message, db, cfg, uid)
    await cb.answer()


@router.callback_query(kb.CartCb.filter(F.a == "checkout"))
async def checkout_start(cb: CallbackQuery, state: FSMContext, db: Database, cfg: Config) -> None:
    problem = await _checkout_problem(db, cfg, cb.from_user.id)
    if problem:
        await cb.answer(problem, show_alert=True)
        return
    await cb.answer()
    await state.clear()
    await state.set_state(Checkout.name)
    last = await db.last_contact(cb.from_user.id)
    await cb.message.answer(
        "<b>Оформление заказа</b>\n\nКак к вам обращаться?",
        reply_markup=kb.input_kb(last["client_name"] if last else None),
    )


# --- Оформление ---

@router.message(StateFilter(Checkout), F.text == kb.BTN_CANCEL)
async def checkout_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Оформление отменено. Товары остались в корзине.", reply_markup=kb.main_menu())


@router.message(Checkout.name, F.text)
async def checkout_name(message: Message, state: FSMContext, db: Database) -> None:
    name = " ".join(message.text.split())
    if not 2 <= len(name) <= 50 or name.startswith("/"):
        await message.answer("Имя должно быть от 2 до 50 символов.")
        return
    await state.update_data(client_name=name)
    await state.set_state(Checkout.phone)
    last = await db.last_contact(message.from_user.id)
    await message.answer(
        "Номер телефона — кнопкой ниже или текстом:",
        reply_markup=kb.input_kb(last["phone"] if last else None, contact=True),
    )


async def _after_phone(message: Message, state: FSMContext, db: Database, cfg: Config) -> None:
    if cfg.delivery_enabled:
        await state.set_state(Checkout.delivery)
        await message.answer("Как получить заказ?", reply_markup=kb.delivery_kb())
    else:
        await state.update_data(delivery="pickup", address=None)
        await _ask_comment(message, state)


async def _ask_comment(message: Message, state: FSMContext) -> None:
    await state.set_state(Checkout.comment)
    await message.answer("Комментарий к заказу (необязательно):", reply_markup=kb.input_kb(skip=True))


@router.message(Checkout.phone, F.contact | F.text)
async def checkout_phone(message: Message, state: FSMContext, db: Database, cfg: Config) -> None:
    phone = normalize_phone(message.contact.phone_number if message.contact else message.text)
    if phone is None:
        await message.answer("Не похоже на номер телефона. Пример: +7 701 123 45 67")
        return
    await state.update_data(phone=phone)
    await _after_phone(message, state, db, cfg)


@router.message(Checkout.delivery, F.text)
async def checkout_delivery(message: Message, state: FSMContext, db: Database) -> None:
    if message.text == kb.BTN_PICKUP:
        await state.update_data(delivery="pickup", address=None)
        await _ask_comment(message, state)
    elif message.text == kb.BTN_DELIVERY:
        await state.update_data(delivery="delivery")
        await state.set_state(Checkout.address)
        last = await db.last_contact(message.from_user.id)
        await message.answer(
            "Адрес доставки (город, улица, дом, квартира):",
            reply_markup=kb.input_kb(last["address"] if last and last["address"] else None),
        )
    else:
        await message.answer("Выберите способ получения кнопкой ниже.")


@router.message(Checkout.address, F.text)
async def checkout_address(message: Message, state: FSMContext) -> None:
    address = message.text.strip()
    if not 5 <= len(address) <= 300:
        await message.answer("Адрес должен быть от 5 до 300 символов.")
        return
    await state.update_data(address=address)
    await _ask_comment(message, state)


@router.message(Checkout.comment, F.text)
async def checkout_comment(message: Message, state: FSMContext, db: Database, cfg: Config) -> None:
    if message.text == kb.BTN_SKIP:
        comment = None
    else:
        comment = message.text.strip()
        if len(comment) > 500:
            await message.answer("Комментарий — не длиннее 500 символов.")
            return
    await state.update_data(comment=comment)

    data = await state.get_data()
    problem = await _checkout_problem(db, cfg, message.from_user.id)
    if problem:
        await state.clear()
        await message.answer(problem, reply_markup=kb.main_menu())
        return
    items, items_total, delivery_price = await _calc(db, cfg, message.from_user.id, data["delivery"])
    await state.update_data(expected_total=items_total + delivery_price)
    await state.set_state(Checkout.confirm)
    await message.answer("Проверьте заказ 👇", reply_markup=kb.main_menu())
    await message.answer(_checkout_text(data, items, items_total, delivery_price, cfg), reply_markup=kb.confirm_kb())


@router.message(Checkout.confirm)
async def checkout_confirm_hint(message: Message) -> None:
    await message.answer("Нажмите «✅ Подтвердить заказ» под сводкой.")


@router.message(StateFilter(Checkout))
async def checkout_wrong_input(message: Message) -> None:
    await message.answer("Ответьте текстом или нажмите «✖️ Отмена».")


@router.callback_query(Checkout.confirm, kb.ConfirmCb.filter(F.a == "place"))
async def place_order(cb: CallbackQuery, state: FSMContext, db: Database, cfg: Config, bot: Bot) -> None:
    user = cb.from_user
    problem = await _checkout_problem(db, cfg, user.id)
    if problem:
        await state.clear()
        await cb.message.edit_text(f"Заказ не оформлен: {problem}")
        await cb.answer()
        return

    data = await state.get_data()
    items, items_total, delivery_price = await _calc(db, cfg, user.id, data["delivery"])
    text = _checkout_text(data, items, items_total, delivery_price, cfg)
    if items_total + delivery_price != data["expected_total"]:
        await state.update_data(expected_total=items_total + delivery_price)
        await cb.message.edit_text(f"{text}\n\n❗ <b>Сумма изменилась</b> — проверьте заказ ещё раз.", reply_markup=kb.confirm_kb())
        await cb.answer("Сумма изменилась", show_alert=True)
        return

    order_id = await db.create_order(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        client_name=data["client_name"],
        phone=data["phone"],
        delivery=data["delivery"],
        address=data.get("address"),
        comment=data.get("comment"),
        items=items,
        items_total=items_total,
        delivery_price=delivery_price,
        now=now_local(cfg),
    )
    await state.clear()
    await cb.message.edit_text(
        f"✅ <b>Заказ #{order_id} оформлен!</b>\n\n{text}\n\nМы свяжемся с вами для подтверждения."
    )
    await cb.answer()
    await deliver_order(bot, db, cfg, await db.get_order(order_id))


@router.callback_query(kb.ConfirmCb.filter(F.a == "cancel"))
async def cancel_checkout(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.message.edit_text("Оформление отменено. Товары остались в корзине.")
    await cb.answer()


# --- Мои заказы ---

async def _own_new_order(db: Database, user_id: int, order_id: int):
    order = await db.get_order(order_id)
    if order is None or order["user_id"] != user_id or order["status"] != "new":
        return None
    return order


@router.callback_query(kb.MyOrderCb.filter(F.a == "cancel"))
async def my_order_cancel(cb: CallbackQuery, callback_data: kb.MyOrderCb, db: Database) -> None:
    if await _own_new_order(db, cb.from_user.id, callback_data.id) is None:
        await cb.answer("Заказ уже нельзя отменить — напишите нам", show_alert=True)
        return
    await cb.message.edit_text(f"Отменить заказ #{callback_data.id}?", reply_markup=kb.my_cancel_confirm_kb(callback_data.id))
    await cb.answer()


@router.callback_query(kb.MyOrderCb.filter(F.a == "cancel_yes"))
async def my_order_cancel_yes(
    cb: CallbackQuery, callback_data: kb.MyOrderCb, db: Database, cfg: Config, bot: Bot
) -> None:
    order = await _own_new_order(db, cb.from_user.id, callback_data.id)
    if order is None or not await db.set_status(order["id"], "cancelled", now_local(cfg), only_from="new"):
        await cb.answer("Заказ уже нельзя отменить — напишите нам", show_alert=True)
        return
    await cb.message.edit_text(f"Заказ #{order['id']} отменён.")
    await cb.answer()
    await refresh_order_cards(bot, db, cfg, await db.get_order(order["id"]))
    await notify_admins(bot, cfg, f"❌ Клиент отменил заказ #{order['id']}")


@router.callback_query(kb.MyOrderCb.filter(F.a == "back"))
async def my_orders_back(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    text, markup = await _my_orders_view(db, cfg, cb.from_user.id)
    await cb.message.edit_text(text, reply_markup=markup)
    await cb.answer()


@router.callback_query()
async def stale_callback(cb: CallbackQuery) -> None:
    await cb.answer("Кнопка устарела. Откройте /catalog", show_alert=True)
