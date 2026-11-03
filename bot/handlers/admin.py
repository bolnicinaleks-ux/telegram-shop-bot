import csv
import io
from datetime import datetime, time, timedelta
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import BaseFilter, Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot import keyboards as kb
from bot.config import Config
from bot.db import Database
from bot.delivery import edit_card, notify_user, refresh_order_cards, send_order_card
from bot.states import AddProduct, EditPrice
from bot.utils import (
    STATUS_PLAIN,
    STATUSES,
    admin_caption,
    chunk_lines,
    client_status_text,
    fmt_created,
    fmt_price,
    now_local,
    order_short,
    parse_price,
)

HELP = (
    "<b>Админ-панель</b>\n\n"
    "<b>Каталог</b>\n"
    "/add — добавить товар\n"
    "/products — все товары\n"
    "/p ID — управление товаром (цена, наличие, скрыть, удалить)\n\n"
    "<b>Заказы</b>\n"
    "/orders — последние 10\n"
    "/orders new|confirmed|shipped|done|cancelled — по статусу\n"
    "/order ID — карточка заказа\n"
    "/export — все заказы в CSV (Excel)\n"
    "/stats — продажи и топ товаров"
)


class IsAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery, cfg: Config) -> bool:
        return event.from_user is not None and event.from_user.id in cfg.admin_ids


router = Router(name="admin")
router.message.filter(IsAdmin())


async def _send_admin_card(message: Message, cfg: Config, p) -> None:
    markup = None if p["deleted"] else kb.admin_product_kb(p)
    if p["photo_id"]:
        await message.answer_photo(p["photo_id"], caption=admin_caption(p, cfg), reply_markup=markup)
    else:
        await message.answer(admin_caption(p, cfg), reply_markup=markup)


# --- Отмена мастера (кнопкой «Отмена» или любой кнопкой меню) ---

@router.message(StateFilter(AddProduct, EditPrice), F.text.in_(kb.MENU_BUTTONS | {kb.BTN_CANCEL}))
async def wizard_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.", reply_markup=kb.main_menu())


@router.message(StateFilter(AddProduct, EditPrice), F.text.startswith("/"))
async def wizard_command(message: Message) -> None:
    await message.answer("Сначала закончите добавление или нажмите «✖️ Отмена».")


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    await message.answer(HELP)


# --- Добавление товара ---

@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    await state.set_state(AddProduct.category)
    await message.answer("<b>Новый товар</b>", reply_markup=kb.input_kb())
    await message.answer("Выберите категорию:", reply_markup=kb.admin_categories_kb(await db.all_categories()))


@router.callback_query(AddProduct.category, kb.AdmCatCb.filter(), IsAdmin())
async def add_pick_category(cb: CallbackQuery, callback_data: kb.AdmCatCb, state: FSMContext, db: Database) -> None:
    await cb.answer()
    if callback_data.id == 0:
        await state.set_state(AddProduct.new_category)
        await cb.message.answer("Название новой категории:")
        return
    category = await db.get_category(callback_data.id)
    if category is None:
        await cb.message.answer("Категория не найдена, выберите снова.")
        return
    await state.update_data(category_id=category["id"])
    await state.set_state(AddProduct.name)
    await cb.message.edit_text(f"Категория: <b>{escape(category['name'])}</b>")
    await cb.message.answer("Название товара:")


@router.message(AddProduct.new_category, F.text)
async def add_new_category(message: Message, state: FSMContext, db: Database) -> None:
    name = " ".join(message.text.split())
    if not 1 <= len(name) <= 40:
        await message.answer("Название категории — от 1 до 40 символов.")
        return
    await state.update_data(category_id=await db.get_or_create_category(name))
    await state.set_state(AddProduct.name)
    await message.answer(f"Категория: <b>{escape(name)}</b>\n\nНазвание товара:")


@router.message(AddProduct.name, F.text)
async def add_name(message: Message, state: FSMContext) -> None:
    name = " ".join(message.text.split())
    if not 1 <= len(name) <= 64:
        await message.answer("Название — от 1 до 64 символов.")
        return
    await state.update_data(name=name)
    await state.set_state(AddProduct.description)
    await message.answer("Описание товара:", reply_markup=kb.input_kb(skip=True))


@router.message(AddProduct.description, F.text)
async def add_description(message: Message, state: FSMContext) -> None:
    description = "" if message.text == kb.BTN_SKIP else message.text.strip()
    if len(description) > 700:
        await message.answer("Описание — не длиннее 700 символов.")
        return
    await state.update_data(description=description)
    await state.set_state(AddProduct.price)
    await message.answer("Цена (целое число):", reply_markup=kb.input_kb())


@router.message(AddProduct.price, F.text)
async def add_price(message: Message, state: FSMContext) -> None:
    price = parse_price(message.text)
    if price is None:
        await message.answer("Введите цену целым числом больше нуля, например 4990.")
        return
    await state.update_data(price=price)
    await state.set_state(AddProduct.photo)
    await message.answer("Фото товара:", reply_markup=kb.input_kb(skip=True))


@router.message(AddProduct.photo, F.photo | (F.text == kb.BTN_SKIP))
async def add_photo(message: Message, state: FSMContext, db: Database, cfg: Config) -> None:
    data = await state.get_data()
    product_id = await db.add_product(
        category_id=data["category_id"],
        name=data["name"],
        description=data["description"],
        price=data["price"],
        photo_id=message.photo[-1].file_id if message.photo else None,
    )
    await state.clear()
    await message.answer("✅ Товар добавлен.", reply_markup=kb.main_menu())
    await _send_admin_card(message, cfg, await db.get_product(product_id))


@router.message(StateFilter(AddProduct))
async def add_wrong_input(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current == AddProduct.photo.state:
        await message.answer("Пришлите фото или нажмите «⏭ Пропустить».")
    elif current == AddProduct.category.state:
        await message.answer("Выберите категорию кнопкой выше.")
    else:
        await message.answer("Ответьте текстом.")


# --- Управление товарами ---

@router.message(Command("products"))
async def cmd_products(message: Message, db: Database, cfg: Config) -> None:
    products = await db.all_products()
    if not products:
        await message.answer("Товаров нет. Добавьте: /add")
        return
    lines, current = [], None
    for p in products:
        if p["category_name"] != current:
            current = p["category_name"]
            lines.append(f"\n<b>{escape(current)}</b>")
        flags = ("🙈" if p["hidden"] else "") + ("" if p["in_stock"] else "❌")
        lines.append(f"/p{p['id']} · {escape(p['name'])} — {fmt_price(p['price'], cfg.currency)} {flags}".rstrip())
    for chunk in chunk_lines(lines + ["", "🙈 скрыт · ❌ нет в наличии"]):
        await message.answer(chunk.strip())


@router.message(F.text.regexp(r"^/p(\d+)(@\w+)?$").as_("match"))
@router.message(Command("p"))
async def cmd_product(message: Message, db: Database, cfg: Config, command: CommandObject | None = None, match=None) -> None:
    if match:
        raw = match.group(1)
    else:
        raw = (command.args or "").strip().lstrip("#") if command else ""
    if not raw.isdigit():
        await message.answer("Формат: /p 12 или /p12")
        return
    p = await db.get_product(int(raw))
    if p is None:
        await message.answer("Товар не найден.")
        return
    await _send_admin_card(message, cfg, p)


@router.callback_query(kb.AdmProdCb.filter(), IsAdmin())
async def product_action(
    cb: CallbackQuery, callback_data: kb.AdmProdCb, state: FSMContext, db: Database, cfg: Config
) -> None:
    p = await db.get_product(callback_data.id)
    if p is None or p["deleted"]:
        await cb.answer("Товар удалён", show_alert=True)
        return
    a = callback_data.a
    if a == "price":
        await state.set_state(EditPrice.price)
        await state.update_data(product_id=p["id"])
        await cb.message.answer(
            f"Новая цена для «{escape(p['name'])}» (сейчас {fmt_price(p['price'], cfg.currency)}):",
            reply_markup=kb.input_kb(),
        )
        await cb.answer()
        return
    if a == "del":
        await cb.message.edit_reply_markup(reply_markup=kb.admin_delete_kb(p["id"]))
        await cb.answer()
        return
    if a == "del_no":
        await cb.message.edit_reply_markup(reply_markup=kb.admin_product_kb(p))
        await cb.answer()
        return

    if a == "stock":
        await db.set_product(p["id"], "in_stock", 0 if p["in_stock"] else 1)
    elif a == "hide":
        await db.set_product(p["id"], "hidden", 0 if p["hidden"] else 1)
    elif a == "del_yes":
        await db.delete_product(p["id"])
    p = await db.get_product(p["id"])
    await edit_card(cb.message, admin_caption(p, cfg), None if p["deleted"] else kb.admin_product_kb(p))
    await cb.answer("Готово")


@router.message(EditPrice.price, F.text)
async def edit_price(message: Message, state: FSMContext, db: Database, cfg: Config) -> None:
    price = parse_price(message.text)
    if price is None:
        await message.answer("Введите цену целым числом больше нуля.")
        return
    data = await state.get_data()
    await state.clear()
    await db.set_product(data["product_id"], "price", price)
    await message.answer(f"Цена обновлена: {fmt_price(price, cfg.currency)}", reply_markup=kb.main_menu())
    await _send_admin_card(message, cfg, await db.get_product(data["product_id"]))


# --- Заказы ---

@router.message(Command("orders"))
async def cmd_orders(message: Message, command: CommandObject, db: Database, cfg: Config) -> None:
    status = (command.args or "").strip() or None
    if status and status not in STATUSES:
        await message.answer("Статусы: " + ", ".join(STATUSES))
        return
    orders = await db.recent_orders(10, status)
    if not orders:
        await message.answer("Заказов нет.")
        return
    await message.answer("\n".join(order_short(o, cfg) for o in orders) + "\n\nПодробнее: /order ID")


@router.message(Command("order"))
async def cmd_order(message: Message, command: CommandObject, db: Database, cfg: Config, bot: Bot) -> None:
    raw = (command.args or "").strip().lstrip("#")
    order = await db.get_order(int(raw)) if raw.isdigit() else None
    if order is None:
        await message.answer("Формат: /order 12 (заказ должен существовать)")
        return
    await send_order_card(bot, db, cfg, order, message.chat.id)


@router.message(Command("export"))
async def cmd_export(message: Message, db: Database, cfg: Config) -> None:
    orders = await db.all_orders()
    if not orders:
        await message.answer("Заказов нет.")
        return
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["ID", "Создан", "Статус", "Клиент", "Телефон", "Telegram", "Получение", "Адрес",
                "Комментарий", "Состав", "Товары", "Доставка", "Итого"])
    for o in orders:
        items = await db.order_items(o["id"])
        w.writerow([
            o["id"], fmt_created(o["created_at"]), STATUS_PLAIN[o["status"]], o["client_name"], o["phone"],
            f"@{o['username']}" if o["username"] else f"id {o['user_id']}",
            "Доставка" if o["delivery"] == "delivery" else "Самовывоз", o["address"] or "", o["comment"] or "",
            ", ".join(f"{i['name']} × {i['qty']}" for i in items),
            o["items_total"], o["delivery_price"], o["total"],
        ])
    await message.answer_document(
        BufferedInputFile(buf.getvalue().encode("utf-8-sig"), filename=f"orders-{now_local(cfg):%Y%m%d-%H%M}.csv"),
        caption=f"Заказов: {len(orders)}",
    )


@router.message(Command("stats"))
async def cmd_stats(message: Message, db: Database, cfg: Config) -> None:
    now = now_local(cfg)
    today = datetime.combine(now.date(), time.min)
    lines = ["<b>Продажи</b> (без отменённых)\n"]
    for title, since in (("Сегодня", today), ("7 дней", today - timedelta(days=6)), ("30 дней", today - timedelta(days=29))):
        count, revenue = await db.stats_since(since)
        lines.append(f"{title}: {count} зак. · {fmt_price(revenue, cfg.currency)}")
    top = await db.top_products(today - timedelta(days=29))
    if top:
        lines.append("\n<b>Топ товаров за 30 дней</b>")
        lines += [f"{n}. {escape(t['name'])} — {t['qty']} шт · {fmt_price(t['revenue'], cfg.currency)}"
                  for n, t in enumerate(top, 1)]
    await message.answer("\n".join(lines))


# Кнопки статуса работают у админов, у участников рабочей группы и (в демо-режиме) у автора заказа
@router.callback_query(kb.OrderCb.filter())
async def change_status(cb: CallbackQuery, callback_data: kb.OrderCb, db: Database, cfg: Config, bot: Bot) -> None:
    in_orders_chat = (
        cfg.orders_chat_id is not None and cb.message is not None and cb.message.chat.id == cfg.orders_chat_id
    )
    current = await db.get_order(callback_data.id)
    own_demo = cfg.demo_mode and current is not None and current["user_id"] == cb.from_user.id
    if cb.from_user.id not in cfg.admin_ids and not in_orders_chat and not own_demo:
        await cb.answer("Нет доступа", show_alert=True)
        return
    if callback_data.s not in STATUSES:
        await cb.answer()
        return
    if not await db.set_status(callback_data.id, callback_data.s, now_local(cfg)):
        await cb.answer("Статус уже установлен" if await db.get_order(callback_data.id) else "Заказ не найден")
        return
    order = await db.get_order(callback_data.id)
    await refresh_order_cards(bot, db, cfg, order)
    await cb.answer(f"Статус: {STATUSES[order['status']]}")
    text = client_status_text(order["status"], order["delivery"])
    if text:
        await notify_user(bot, order["user_id"], f"Ваш заказ #{order['id']} {text}")
