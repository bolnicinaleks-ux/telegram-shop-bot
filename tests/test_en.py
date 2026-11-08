"""Английская версия (BOT_LANG=en): основной сценарий проходит, и ни одно сообщение или кнопка не содержит кириллицы.

Запуск: python -m tests.test_en
"""
import os

os.environ["BOT_LANG"] = "en"

import asyncio  # noqa: E402
import csv  # noqa: E402
import dataclasses  # noqa: E402
import io  # noqa: E402
import re  # noqa: E402
import tempfile  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

from aiogram import Bot  # noqa: E402
from aiogram.methods import (  # noqa: E402
    AnswerCallbackQuery,
    EditMessageCaption,
    EditMessageReplyMarkup,
    EditMessageText,
    SendDocument,
    SendMessage,
    SendPhoto,
)

from bot.__main__ import ADMIN_COMMANDS, build_dispatcher  # noqa: E402
from bot.config import Config  # noqa: E402
from bot.db import Database  # noqa: E402
from tests.test_flow import PHOTO, FakeSession, msg, press  # noqa: E402

ADMIN, CLIENT = 1000, 2000
CYR = re.compile(r"[А-Яа-яЁё]")


def outgoing_texts(session: FakeSession) -> list[str]:
    texts = []
    for c in session.calls:
        if isinstance(c, (SendMessage, EditMessageText, AnswerCallbackQuery, SendPhoto, EditMessageCaption, SendDocument)):
            texts += [v for v in (getattr(c, "text", None), getattr(c, "caption", None)) if isinstance(v, str)]
        if isinstance(c, (SendMessage, EditMessageText, SendPhoto, EditMessageCaption, EditMessageReplyMarkup)):
            markup = c.reply_markup
            for row in getattr(markup, "inline_keyboard", None) or getattr(markup, "keyboard", None) or []:
                texts += [b.text for b in row]
    return texts


async def main() -> None:
    cfg = Config(
        bot_token="123456:" + "A" * 35, admin_ids=frozenset({ADMIN}), orders_chat_id=None,
        db_path=os.path.join(tempfile.mkdtemp(), "en.db"), tz=ZoneInfo("Asia/Almaty"), currency="$",
        shop_name="Demo Shop", payment_info="Card or cash on delivery", pickup_address="1 Main St",
        delivery_enabled=True, delivery_price=5, free_delivery_from=100, min_order=0, max_orders_per_hour=5,
    )
    db = Database(cfg.db_path)
    await db.connect()
    try:
        s = FakeSession()
        bot = Bot(cfg.bot_token, session=s)
        dp = build_dispatcher(db, cfg)

        async def feed(update, **overrides):
            await dp.feed_update(bot, update, **({"cfg": dataclasses.replace(cfg, **overrides)} if overrides else {}))

        assert not any(CYR.search(c.description) for c in ADMIN_COMMANDS)

        # Админ: товары
        await feed(msg(ADMIN, "/add"))
        await feed(press(ADMIN, "ac:0"))
        await feed(msg(ADMIN, "Electronics"))
        for text in ("Headphones", "Wireless, 30 hours", "cheap"):
            await feed(msg(ADMIN, text))
        assert "whole number above zero" in s.last_text(ADMIN)
        await feed(msg(ADMIN, "60"))
        await feed(msg(ADMIN, photo=PHOTO))
        assert "Product added" in s.of(SendMessage, chat_id=ADMIN)[-1].text
        assert "$60" in s.of(SendPhoto, chat_id=ADMIN)[-1].caption and "in stock" in s.of(SendPhoto, chat_id=ADMIN)[-1].caption
        await feed(msg(ADMIN, "/add"))
        await feed(press(ADMIN, "ac:1"))
        for text in ("Case", "⏭ Skip", "20", "⏭ Skip"):
            await feed(msg(ADMIN, text))

        # Клиент: каталог, корзина, оформление
        await feed(msg(CLIENT, "/start"))
        assert "Welcome to <b>Demo Shop</b>" in s.last_text(CLIENT)
        await feed(msg(CLIENT, "🛍 Catalog"))
        assert s.last_buttons(CLIENT)[0] == ("Electronics (2)", "cat:1")
        await feed(press(CLIENT, "cat:1"))
        await feed(press(CLIENT, "pc:add:1:1:0", photo=True))
        await feed(press(CLIENT, "pc:inc:1:1:0", photo=True))
        assert s.alerts()[-1] == "In cart: 2 pcs"
        await feed(msg(CLIENT, "🛒 Cart"))
        assert "Subtotal: $120" in s.last_text(CLIENT) and "Free delivery from $100" in s.last_text(CLIENT)
        await feed(press(CLIENT, "ct:checkout:0"))
        for text in ("Anna Lee", "+1 555 123 4567", "🚚 Delivery", "12 Oak Street, apt 4", "⏭ Skip"):
            await feed(msg(CLIENT, text))
        summary = s.last_text(CLIENT)
        assert "Delivery: free" in summary and "Total: $120" in summary and "Card or cash" in summary
        await feed(press(CLIENT, "co:place"))
        assert "Order #1 placed!" in s.last_text(CLIENT)
        assert "Order #1" in s.last_text(ADMIN) and "Headphones × 2" in s.last_text(ADMIN)
        await feed(press(ADMIN, "or:1:shipped"))
        assert s.last_text(CLIENT) == "Your order #1 is on its way"

        # Демо-режим и отмена
        await feed(msg(CLIENT, "/start"), demo_mode=True)
        assert "demo shop" in s.last_text(CLIENT)
        await feed(press(CLIENT, "pc:add:2:1:1"), demo_mode=True)
        await feed(press(CLIENT, "ct:checkout:0"), demo_mode=True)
        for text in ("Anna Lee", "+15551234567", "🚶 Pickup", "Call me"):
            await feed(msg(CLIENT, text), demo_mode=True)
        assert "no payment needed" in s.last_text(CLIENT) and "Pickup: 1 Main St" in s.last_text(CLIENT)
        await feed(press(CLIENT, "co:place"), demo_mode=True)
        assert any("what the owner sees" in m.text for m in s.of(SendMessage, chat_id=CLIENT)[-3:])
        await feed(press(CLIENT, "or:2:shipped"), demo_mode=True)
        assert s.last_text(CLIENT) == "Your order #2 is ready for pickup"
        await feed(msg(CLIENT, "📦 My orders"))
        assert "Your orders" in s.last_text(CLIENT)

        # Админ-команды
        for cmd in ("/admin", "/products", "/p1", "/p 99", "/orders", "/orders bad", "/order 1", "/stats"):
            await feed(msg(ADMIN, cmd))
        await feed(press(ADMIN, "ap:stock:2"))
        await feed(press(ADMIN, "ap:del:2"))
        await feed(press(ADMIN, "ap:del_yes:2"))
        await feed(msg(ADMIN, "/export"))
        rows = list(csv.reader(io.StringIO(s.of(SendDocument)[-1].document.data.decode("utf-8-sig")), delimiter=";"))
        assert rows[0][1] == "Created" and rows[1][6] == "Delivery" and rows[2][6] == "Pickup"
        await feed(press(CLIENT, "co:place"))
        assert "outdated" in s.alerts()[-1]

        leaks = [t for t in outgoing_texts(s) if CYR.search(t)]
        assert not leaks, "Кириллица в английской версии:\n" + "\n".join(leaks)
        print(f"✔ английская версия: {len(outgoing_texts(s))} текстов и кнопок, кириллицы нет")
    finally:
        await db.close()
    print("\nВСЕ ПРОВЕРКИ ПРОЙДЕНЫ")


if __name__ == "__main__":
    asyncio.run(main())
