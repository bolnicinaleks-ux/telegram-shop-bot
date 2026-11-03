import re
from datetime import datetime
from html import escape

from bot.config import Config

DT_FMT = "%Y-%m-%d %H:%M"

STATUSES = {
    "new": "🆕 Новый",
    "confirmed": "👍 Подтверждён",
    "shipped": "📦 Отправлен",
    "done": "✅ Выполнен",
    "cancelled": "❌ Отменён",
}
STATUS_PLAIN = {
    "new": "Новый", "confirmed": "Подтверждён", "shipped": "Отправлен", "done": "Выполнен", "cancelled": "Отменён",
}


def client_status_text(status: str, delivery: str) -> str | None:
    if status == "shipped":
        return "передан в доставку" if delivery == "delivery" else "готов к выдаче"
    return {"confirmed": "подтверждён", "done": "выполнен. Спасибо за покупку!", "cancelled": "отменён"}.get(status)


def now_local(cfg: Config) -> datetime:
    return datetime.now(cfg.tz).replace(tzinfo=None, second=0, microsecond=0)


def dt_to_str(dt: datetime) -> str:
    return dt.strftime(DT_FMT)


def fmt_created(value: str) -> str:
    return datetime.strptime(value, DT_FMT).strftime("%d.%m.%Y %H:%M")


def fmt_price(amount: int, currency: str) -> str:
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
        text += "\n\n❗ Нет в наличии"
    return text


def admin_caption(p, cfg: Config) -> str:
    flags = []
    if p["deleted"]:
        flags.append("🗑 удалён")
    if p["hidden"]:
        flags.append("🙈 скрыт")
    flags.append("✅ в наличии" if p["in_stock"] else "❌ нет в наличии")
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
    lines = [f"Товары: {fmt_price(items_total, cfg.currency)}"]
    if delivery == "delivery":
        lines.append("Доставка: " + (fmt_price(delivery_price, cfg.currency) if delivery_price else "бесплатно"))
    lines.append(f"<b>Итого: {fmt_price(items_total + delivery_price, cfg.currency)}</b>")
    return "\n".join(lines)


def delivery_line(delivery: str, address: str | None, cfg: Config) -> str:
    if delivery == "delivery":
        return f"🚚 Доставка: {escape(address or '')}"
    return "🚶 Самовывоз" + (f": {escape(cfg.pickup_address)}" if cfg.pickup_address else "")


def tg_contact(order) -> str:
    if order["username"]:
        return f"@{order['username']}"
    return f'<a href="tg://user?id={order["user_id"]}">{escape(order["full_name"])}</a>'


def order_card(order, items, cfg: Config) -> str:
    parts = [
        f"<b>Заказ #{order['id']}</b> · {STATUSES[order['status']]}",
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
