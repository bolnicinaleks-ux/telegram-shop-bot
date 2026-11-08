import re
from datetime import datetime
from html import escape

from bot.config import Config
from bot.i18n import LANG, _

DT_FMT = "%Y-%m-%d %H:%M"
MONTHS_SHORT_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

STATUSES = {
    "new": _("🆕 Новый"),
    "confirmed": _("👍 Подтверждён"),
    "shipped": _("📦 Отправлен"),
    "done": _("✅ Выполнен"),
    "cancelled": _("❌ Отменён"),
}
STATUS_PLAIN = {
    "new": _("Новый"), "confirmed": _("Подтверждён"), "shipped": _("Отправлен"), "done": _("Выполнен"),
    "cancelled": _("Отменён"),
}


def client_status_text(status: str, delivery: str) -> str | None:
    if status == "shipped":
        return _("передан в доставку") if delivery == "delivery" else _("готов к выдаче")
    return {"confirmed": _("подтверждён"), "done": _("выполнен. Спасибо за покупку!"), "cancelled": _("отменён")}.get(status)


def now_local(cfg: Config) -> datetime:
    return datetime.now(cfg.tz).replace(tzinfo=None, second=0, microsecond=0)


def dt_to_str(dt: datetime) -> str:
    return dt.strftime(DT_FMT)


def fmt_created(value: str) -> str:
    dt = datetime.strptime(value, DT_FMT)
    if LANG == "en":
        return f"{MONTHS_SHORT_EN[dt.month - 1]} {dt.day}, {dt:%Y %H:%M}"
    return dt.strftime("%d.%m.%Y %H:%M")


def fmt_price(amount: int, currency: str) -> str:
    if LANG == "en":
        return f"{currency}{amount:,}" if currency in ("$", "€", "£") else f"{amount:,} {currency}"
    return f"{amount:,}".replace(",", " ") + f" {currency}"


def normalize_phone(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if not 10 <= len(digits) <= 15:
        return None
    return "+" + digits


def parse_price(raw: str) -> int | None:
    digits = raw.replace(" ", "").replace(" ", "")
    if not digits.isdigit():
        return None
    value = int(digits)
    return value if 0 < value <= 100_000_000 else None


def is_available(item) -> bool:
    return bool(item["in_stock"]) and not item["hidden"] and not item["deleted"]


def product_caption(p, cfg: Config) -> str:
    text = f"<b>{escape(p['name'])}</b>\n{fmt_price(p['price'], cfg.currency)}"
    if p["description"]:
        text += f"\n\n{escape(p['description'])}"
    if not p["in_stock"]:
        text += "\n\n" + _("❗ Нет в наличии")
    return text


def admin_caption(p, cfg: Config) -> str:
    flags = []
    if p["deleted"]:
        flags.append(_("🗑 удалён"))
    if p["hidden"]:
        flags.append(_("🙈 скрыт"))
    flags.append(_("✅ в наличии") if p["in_stock"] else _("❌ нет в наличии"))
    return (
        f"<b>#{p['id']}</b> · {escape(p['category_name'])}\n"
        f"{product_caption(p, cfg)}\n\n"
        f"{' · '.join(flags)}"
    )


def cart_totals(items, cfg: Config) -> tuple[int, int]:
    """(сумма товаров, число недоступных позиций)"""
    total = sum(i["price"] * i["qty"] for i in items if is_available(i))
    unavailable = sum(1 for i in items if not is_available(i))
    return total, unavailable


def items_lines(items, cfg: Config) -> str:
    return "\n".join(
        f"• {escape(i['name'])} × {i['qty']} — {fmt_price(i['price'] * i['qty'], cfg.currency)}" for i in items
    )


def totals_lines(items_total: int, delivery_price: int, delivery: str, cfg: Config) -> str:
    lines = [_("Товары: {sum}", sum=fmt_price(items_total, cfg.currency))]
    if delivery == "delivery":
        lines.append(_("Доставка: {sum}", sum=fmt_price(delivery_price, cfg.currency) if delivery_price else _("бесплатно")))
    lines.append(_("<b>Итого: {sum}</b>", sum=fmt_price(items_total + delivery_price, cfg.currency)))
    return "\n".join(lines)


def delivery_line(delivery: str, address: str | None, cfg: Config) -> str:
    if delivery == "delivery":
        return _("🚚 Доставка: {address}", address=escape(address or ""))
    return _("🚶 Самовывоз") + (f": {escape(cfg.pickup_address)}" if cfg.pickup_address else "")


def tg_contact(order) -> str:
    if order["username"]:
        return f"@{order['username']}"
    return f'<a href="tg://user?id={order["user_id"]}">{escape(order["full_name"])}</a>'


def order_card(order, items, cfg: Config) -> str:
    parts = [
        _("<b>Заказ #{id}</b>", id=order["id"]) + f" · {STATUSES[order['status']]}",
        f"{fmt_created(order['created_at'])} · {tg_contact(order)}",
        "",
        f"👤 {escape(order['client_name'])}, {escape(order['phone'])}",
        delivery_line(order["delivery"], order["address"], cfg),
    ]
    if order["comment"]:
        parts.append(f"💬 {escape(order['comment'])}")
    parts += ["", items_lines(items, cfg), "", totals_lines(order["items_total"], order["delivery_price"], order["delivery"], cfg)]
    return "\n".join(parts)


def order_short(order, cfg: Config) -> str:
    return (
        f"#{order['id']} · {fmt_created(order['created_at'])} · {STATUSES[order['status']]} · "
        f"{fmt_price(order['total'], cfg.currency)}"
    )


def chunk_lines(lines: list[str], limit: int = 3500) -> list[str]:
    chunks, current = [], ""
    for line in lines:
        if current and len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = ""
        current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks
