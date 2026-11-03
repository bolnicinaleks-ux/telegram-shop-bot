import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


def _parse_ints(value: str) -> frozenset[int]:
    return frozenset(int(v) for v in value.replace(" ", "").split(",") if v)


@dataclass(frozen=True, slots=True)
class Config:
    bot_token: str
    admin_ids: frozenset[int]
    orders_chat_id: int | None
    db_path: str
    tz: ZoneInfo
    currency: str
    shop_name: str
    payment_info: str
    pickup_address: str
    delivery_enabled: bool
    delivery_price: int
    free_delivery_from: int
    min_order: int
    max_orders_per_hour: int
    demo_mode: bool = False

    @property
    def order_targets(self) -> list[int]:
        """Куда отправлять заказы: рабочая группа или каждый админ в личку."""
        return [self.orders_chat_id] if self.orders_chat_id else sorted(self.admin_ids)

    def delivery_cost(self, items_total: int) -> int:
        if self.free_delivery_from and items_total >= self.free_delivery_from:
            return 0
        return self.delivery_price


def load_config() -> Config:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN не задан (см. .env.example)")
    orders_chat = os.getenv("ORDERS_CHAT_ID", "").strip()

    cfg = Config(
        bot_token=token,
        admin_ids=_parse_ints(os.getenv("ADMIN_IDS", "")),
        orders_chat_id=int(orders_chat) if orders_chat else None,
        db_path=os.getenv("DB_PATH", "data/bot.db"),
        tz=ZoneInfo(os.getenv("TIMEZONE", "Asia/Almaty")),
        currency=os.getenv("CURRENCY", "₸"),
        shop_name=os.getenv("SHOP_NAME", "Магазин"),
        payment_info=os.getenv("PAYMENT_INFO", "").replace("\\n", "\n"),
        pickup_address=os.getenv("PICKUP_ADDRESS", ""),
        delivery_enabled=os.getenv("DELIVERY_ENABLED", "1").strip() not in ("0", "", "false", "no"),
        delivery_price=int(os.getenv("DELIVERY_PRICE", "0")),
        free_delivery_from=int(os.getenv("FREE_DELIVERY_FROM", "0")),
        min_order=int(os.getenv("MIN_ORDER", "0")),
        max_orders_per_hour=int(os.getenv("MAX_ORDERS_PER_HOUR", "5")),
        demo_mode=os.getenv("DEMO_MODE", "0").strip().lower() in ("1", "true", "yes"),
    )
    if not cfg.admin_ids:
        raise RuntimeError("ADMIN_IDS пуст — некому управлять каталогом")
    return cfg
