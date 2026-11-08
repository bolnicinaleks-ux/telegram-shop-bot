from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.i18n import _
from bot.utils import STATUSES, is_available

BTN_CATALOG = _("🛍 Каталог")
BTN_CART = _("🛒 Корзина")
BTN_ORDERS = _("📦 Мои заказы")
BTN_CANCEL = _("✖️ Отмена")
BTN_SKIP = _("⏭ Пропустить")
BTN_CONTACT = _("📱 Отправить мой номер")
BTN_PICKUP = _("🚶 Самовывоз")
BTN_DELIVERY = _("🚚 Доставка")
MENU_BUTTONS = {BTN_CATALOG, BTN_CART, BTN_ORDERS}


class CatCb(CallbackData, prefix="cat"):
    id: int


class BrowseCb(CallbackData, prefix="br"):
    c: int  # категория
    i: int  # индекс товара в категории


class CardCb(CallbackData, prefix="pc"):
    a: str  # add | inc | dec
    p: int
    c: int
    i: int


class CartCb(CallbackData, prefix="ct"):
    a: str  # show | inc | dec | del | clear | checkout
    p: int = 0


class MenuCb(CallbackData, prefix="mn"):
    to: str  # cats


class NoopCb(CallbackData, prefix="noop"):
    pass


class ConfirmCb(CallbackData, prefix="co"):
    a: str  # place | cancel


class MyOrderCb(CallbackData, prefix="mo"):
    a: str  # cancel | cancel_yes | back
    id: int


class OrderCb(CallbackData, prefix="or"):
    id: int
    s: str


class AdmCatCb(CallbackData, prefix="ac"):
    id: int  # 0 — новая категория


class AdmProdCb(CallbackData, prefix="ap"):
    a: str  # price | stock | hide | del | del_yes | del_no
    id: int


def _btn(text: str, cb: CallbackData) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=cb.pack())


NOOP = NoopCb()


# --- Reply-клавиатуры ---

def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_CATALOG), KeyboardButton(text=BTN_CART)], [KeyboardButton(text=BTN_ORDERS)]],
        resize_keyboard=True,
    )


def reply_kb(*rows: list[str], contact: bool = False) -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton(text=t) for t in row] for row in rows if row]
    if contact:
        keyboard.insert(0, [KeyboardButton(text=BTN_CONTACT, request_contact=True)])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, is_persistent=True)


def input_kb(prev: str | None = None, skip: bool = False, contact: bool = False) -> ReplyKeyboardMarkup:
    rows = []
    if prev:
        rows.append([prev[:64]])
    rows.append(([BTN_SKIP] if skip else []) + [BTN_CANCEL])
    return reply_kb(*rows, contact=contact)


def delivery_kb() -> ReplyKeyboardMarkup:
    return reply_kb([BTN_PICKUP, BTN_DELIVERY], [BTN_CANCEL])


# --- Каталог и корзина ---

def categories_kb(categories) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for c in categories:
        b.button(text=f"{c['name']} ({c['cnt']})", callback_data=CatCb(id=c["id"]))
    b.adjust(1)
    b.row(_btn(BTN_CART, CartCb(a="show")))
    return b.as_markup()


def product_kb(p, qty: int, cat_id: int, i: int, n: int) -> InlineKeyboardMarkup:
    rows = []
    if n > 1:
        rows.append([
            _btn("◀️", BrowseCb(c=cat_id, i=(i - 1) % n)),
            _btn(f"{i + 1} / {n}", NOOP),
            _btn("▶️", BrowseCb(c=cat_id, i=(i + 1) % n)),
        ])
    if not p["in_stock"]:
        rows.append([_btn(_("Нет в наличии"), NOOP)])
    elif qty == 0:
        rows.append([_btn(_("🛒 В корзину"), CardCb(a="add", p=p["id"], c=cat_id, i=i))])
    else:
        rows.append([
            _btn("➖", CardCb(a="dec", p=p["id"], c=cat_id, i=i)),
            _btn(_("{n} шт", n=qty), NOOP),
            _btn("➕", CardCb(a="inc", p=p["id"], c=cat_id, i=i)),
        ])
    rows.append([_btn(_("⬅️ Категории"), MenuCb(to="cats")), _btn(BTN_CART, CartCb(a="show"))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cart_kb(items) -> InlineKeyboardMarkup:
    rows = []
    for item in items:
        name = item["name"][:18]
        if is_available(item):
            rows.append([
                _btn("➖", CartCb(a="dec", p=item["product_id"])),
                _btn(f"{name} × {item['qty']}", NOOP),
                _btn("➕", CartCb(a="inc", p=item["product_id"])),
            ])
        else:
            rows.append([_btn(_("🗑 {name} (недоступен)", name=name), CartCb(a="del", p=item["product_id"]))])
    rows.append([_btn(_("🗑 Очистить"), CartCb(a="clear")), _btn(_("✅ Оформить"), CartCb(a="checkout"))])
    rows.append([_btn(_("⬅️ Каталог"), MenuCb(to="cats"))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(_("✅ Подтвердить заказ"), ConfirmCb(a="place"))],
        [_btn(BTN_CANCEL, ConfirmCb(a="cancel"))],
    ])


def my_orders_kb(orders) -> InlineKeyboardMarkup | None:
    b = InlineKeyboardBuilder()
    for o in orders:
        if o["status"] == "new":
            b.button(text=_("❌ Отменить заказ #{id}", id=o["id"]), callback_data=MyOrderCb(a="cancel", id=o["id"]))
    b.adjust(1)
    markup = b.as_markup()
    return markup if markup.inline_keyboard else None


def my_cancel_confirm_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        _btn(_("Да, отменить"), MyOrderCb(a="cancel_yes", id=order_id)),
        _btn(_("Нет"), MyOrderCb(a="back", id=order_id)),
    ]])


# --- Админ ---

def order_status_kb(order_id: int, current: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for status in ("confirmed", "shipped", "done", "cancelled"):
        label = STATUSES[status]
        b.button(text=f"• {label} •" if status == current else label, callback_data=OrderCb(id=order_id, s=status))
    b.adjust(2)
    return b.as_markup()


def admin_categories_kb(categories) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for c in categories:
        b.button(text=c["name"], callback_data=AdmCatCb(id=c["id"]))
    b.button(text=_("➕ Новая категория"), callback_data=AdmCatCb(id=0))
    b.adjust(2)
    return b.as_markup()


def admin_product_kb(p) -> InlineKeyboardMarkup:
    pid = p["id"]
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            _btn(_("💰 Цена"), AdmProdCb(a="price", id=pid)),
            _btn(_("❌ Нет в наличии") if p["in_stock"] else _("✅ В наличии"), AdmProdCb(a="stock", id=pid)),
        ],
        [
            _btn(_("👁 Показать") if p["hidden"] else _("🙈 Скрыть"), AdmProdCb(a="hide", id=pid)),
            _btn(_("🗑 Удалить"), AdmProdCb(a="del", id=pid)),
        ],
    ])


def admin_delete_kb(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        _btn(_("Да, удалить"), AdmProdCb(a="del_yes", id=product_id)),
        _btn(_("Нет"), AdmProdCb(a="del_no", id=product_id)),
    ]])
