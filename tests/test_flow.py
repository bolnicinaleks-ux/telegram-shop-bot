"""Сквозной прогон бота без Telegram: апдейты подаются в Dispatcher, ответы перехватывает фейковая сессия.

Запуск: python -m tests.test_flow
"""
import os

os.environ.setdefault("BOT_LANG", "ru")  # тест проверяет русские тексты (test_en ставит en)

import asyncio  # noqa: E402
import csv
import dataclasses
import io
import itertools
import os
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import (
    AnswerCallbackQuery,
    EditMessageCaption,
    EditMessageReplyMarkup,
    EditMessageText,
    SendDocument,
    SendMessage,
    SendPhoto,
)
from aiogram.types import CallbackQuery, Chat, Contact, Message, PhotoSize, Update, User

from bot.__main__ import build_dispatcher
from bot.config import Config
from bot.db import Database

ADMIN, CLIENT, CLIENT2, STRANGER, GROUP = 1000, 2000, 3000, 4000, -100500
PHOTO = [PhotoSize(file_id="small", file_unique_id="s", width=90, height=90),
         PhotoSize(file_id="big", file_unique_id="b", width=800, height=800)]
_ids = itertools.count(1)
TEXT_METHODS = (SendMessage, EditMessageText, SendPhoto, EditMessageCaption)


class FakeSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list = []

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if isinstance(method, (SendMessage, EditMessageText, SendPhoto, SendDocument, EditMessageCaption)):
            return Message(
                message_id=getattr(method, "message_id", None) or next(_ids),
                date=datetime.now(),
                chat=Chat(id=method.chat_id or 0, type="private"),
                text=getattr(method, "text", None),
            )
        return True

    async def close(self) -> None:
        pass

    async def stream_content(self, *args, **kwargs):
        yield b""

    def of(self, *types, chat_id=None):
        return [c for c in self.calls if isinstance(c, types) and (chat_id is None or c.chat_id == chat_id)]

    def last(self, chat_id: int):
        return self.of(*TEXT_METHODS, chat_id=chat_id)[-1]

    def last_text(self, chat_id: int) -> str:
        m = self.last(chat_id)
        return getattr(m, "text", None) or getattr(m, "caption", None) or ""

    def alerts(self) -> list[str]:
        return [c.text for c in self.of(AnswerCallbackQuery) if c.text]

    def last_buttons(self, chat_id: int) -> list[tuple[str, str]]:
        for c in reversed(self.of(*TEXT_METHODS, EditMessageReplyMarkup, chat_id=chat_id)):
            markup = getattr(c, "reply_markup", None)
            if markup is not None and hasattr(markup, "inline_keyboard"):
                return [(b.text, b.callback_data) for row in markup.inline_keyboard for b in row]
        return []


def user(uid: int) -> User:
    return User(id=uid, is_bot=False, first_name=f"U{uid}", username="anya" if uid == CLIENT else None)


def msg(uid: int, text: str | None = None, **extra) -> Update:
    return Update(update_id=next(_ids), message=Message(
        message_id=next(_ids), date=datetime.now(), chat=Chat(id=uid, type="private"),
        from_user=user(uid), text=text, **extra,
    ))


def press(uid: int, data: str, *, chat: int | None = None, photo: bool = False) -> Update:
    return Update(update_id=next(_ids), callback_query=CallbackQuery(
        id=str(next(_ids)), from_user=user(uid), chat_instance="ci", data=data,
        message=Message(message_id=next(_ids), date=datetime.now(), chat=Chat(id=chat or uid, type="private"),
                        photo=PHOTO if photo else None, text=None if photo else "-", caption="-" if photo else None),
    ))


async def main() -> None:
    tmp = tempfile.mkdtemp()
    cfg = Config(
        bot_token="123456:" + "A" * 35,
        admin_ids=frozenset({ADMIN}),
        orders_chat_id=None,
        db_path=os.path.join(tmp, "test.db"),
        tz=ZoneInfo("Asia/Almaty"),
        currency="₸",
        shop_name="Тест-шоп",
        payment_info="Kaspi: +7 700 000 00 00",
        pickup_address="ул. Абая, 1",
        delivery_enabled=True,
        delivery_price=1000,
        free_delivery_from=20000,
        min_order=0,
        max_orders_per_hour=5,
    )
    db = Database(cfg.db_path)
    await db.connect()
    try:
        await scenario(cfg, db)
    finally:
        await db.close()
    print("\nВСЕ ПРОВЕРКИ ПРОЙДЕНЫ")


async def scenario(cfg: Config, db: Database) -> None:
    s = FakeSession()
    bot = Bot(cfg.bot_token, session=s)
    dp = build_dispatcher(db, cfg)

    async def feed(upd: Update, **overrides) -> None:
        await dp.feed_update(bot, upd, **({"cfg": dataclasses.replace(cfg, **overrides)} if overrides else {}))

    # 1. Админ наполняет каталог
    await feed(msg(ADMIN, "/add"))
    await feed(press(ADMIN, "ac:0"))
    await feed(msg(ADMIN, "Электроника"))
    await feed(msg(ADMIN, "Наушники"))
    await feed(msg(ADMIN, "Беспроводные, 30 часов"))
    await feed(msg(ADMIN, "дорого"))
    assert "целым числом" in s.last_text(ADMIN)
    await feed(msg(ADMIN, "12 990"))
    await feed(msg(ADMIN, "не фото"))
    assert "Пришлите фото" in s.last_text(ADMIN)
    await feed(msg(ADMIN, photo=PHOTO))
    card = s.of(SendPhoto, chat_id=ADMIN)[-1]
    assert card.photo == "big" and "12 990 ₸" in card.caption and "#1" in card.caption

    await feed(msg(ADMIN, "/add"))
    await feed(press(ADMIN, "ac:1"))
    await feed(msg(ADMIN, "Чехол"))
    await feed(msg(ADMIN, "⏭ Пропустить"))
    await feed(msg(ADMIN, "3000"))
    await feed(msg(ADMIN, "⏭ Пропустить"))
    assert "#2" in s.last_text(ADMIN)

    await feed(msg(ADMIN, "/add"))
    await feed(press(ADMIN, "ac:0"))
    await feed(msg(ADMIN, "Книги"))
    await feed(msg(ADMIN, "Роман"))
    await feed(msg(ADMIN, "/products"))
    assert "Сначала закончите" in s.last_text(ADMIN)
    await feed(msg(ADMIN, "⏭ Пропустить"))
    await feed(msg(ADMIN, "5000"))
    await feed(msg(ADMIN, "⏭ Пропустить"))
    assert len(await db.all_products()) == 3

    await feed(msg(ADMIN, "/add"))
    await feed(msg(ADMIN, "🛍 Каталог"))
    assert "Отменено" in s.last_text(ADMIN)
    await feed(msg(CLIENT, "/add"))
    assert not s.of(SendMessage, chat_id=CLIENT)
    print("✔ админ: мастер добавления товара, новая/существующая категория, отмена, защита от команд")

    # 2. Клиент листает каталог и кладёт в корзину
    await feed(msg(CLIENT, "/start"))
    assert "Тест-шоп" in s.last_text(CLIENT)
    await feed(msg(CLIENT, "🛍 Каталог"))
    cats = s.last_buttons(CLIENT)
    assert cats[0] == ("Книги (1)", "cat:2") and cats[1] == ("Электроника (2)", "cat:1")
    await feed(press(CLIENT, "cat:1"))
    photo_card = s.of(SendPhoto, chat_id=CLIENT)[-1]
    assert photo_card.photo == "big" and "Наушники" in photo_card.caption
    assert ("1 / 2", "noop") in s.last_buttons(CLIENT)
    await feed(press(CLIENT, "pc:add:1:1:0", photo=True))
    await feed(press(CLIENT, "pc:inc:1:1:0", photo=True))
    assert ("2 шт", "noop") in s.last_buttons(CLIENT)
    assert s.alerts()[-1] == "В корзине: 2 шт"
    await feed(press(CLIENT, "br:1:1", photo=True))
    assert "Чехол" in s.last_text(CLIENT)
    await feed(press(CLIENT, "pc:add:2:1:1"))
    await feed(msg(CLIENT, "🛒 Корзина"))
    cart = s.last_text(CLIENT)
    assert "Наушники — 12 990 ₸ × 2 = 25 980 ₸" in cart and "Сумма: 28 980 ₸" in cart
    await feed(press(CLIENT, "ct:dec:2"))
    assert "Чехол" not in s.last_text(CLIENT) and "Сумма: 25 980 ₸" in s.last_text(CLIENT)
    print("✔ каталог: категории, фото-карточка, листание, корзина +/−")

    # 3. Товар закончился — оформить нельзя
    await feed(press(ADMIN, "ap:stock:1", photo=True))
    assert "нет в наличии" in s.last_text(ADMIN)
    await feed(press(CLIENT, "ct:checkout:0"))
    assert "недоступные" in s.alerts()[-1]
    await feed(press(CLIENT, "ct:inc:1"))
    assert s.alerts()[-1] == "Товар недоступен"
    await feed(press(ADMIN, "ap:stock:1", photo=True))
    print("✔ нет в наличии: блокировка оформления и добавления")

    # 4. Оформление с доставкой; цена меняется до подтверждения
    await feed(press(CLIENT, "ct:checkout:0"))
    await feed(msg(CLIENT, "А"))
    assert "от 2 до 50" in s.last_text(CLIENT)
    await feed(msg(CLIENT, "Аня"))
    await feed(msg(CLIENT, contact=Contact(phone_number="87011234567", first_name="Аня", user_id=CLIENT)))
    await feed(msg(CLIENT, "на такси"))
    assert "кнопкой" in s.last_text(CLIENT)
    await feed(msg(CLIENT, "🚚 Доставка"))
    await feed(msg(CLIENT, "ул. Абая 10, кв 5"))
    await feed(msg(CLIENT, "⏭ Пропустить"))
    summary = s.last_text(CLIENT)
    assert "Доставка: бесплатно" in summary and "Итого: 25 980 ₸" in summary and "+77011234567" in summary
    assert "Kaspi" in summary

    await feed(press(ADMIN, "ap:price:1", photo=True))
    await feed(msg(ADMIN, "13990"))
    assert "13 990" in s.last_text(ADMIN)
    await feed(press(CLIENT, "co:place"))
    assert s.alerts()[-1] == "Сумма изменилась" and "Итого: 27 980 ₸" in s.last_text(CLIENT)
    await feed(press(CLIENT, "co:place"))
    assert "Заказ #1 оформлен" in s.last_text(CLIENT)
    assert await db.cart_items(CLIENT) == []
    order = await db.get_order(1)
    assert order["total"] == 27980 and order["delivery_price"] == 0 and order["address"] == "ул. Абая 10, кв 5"
    admin_card = s.last_text(ADMIN)
    assert "Заказ #1" in admin_card and "@anya" in admin_card and "Наушники × 2" in admin_card
    print("✔ оформление: валидация, доставка, бесплатная доставка, пересчёт при смене цены")

    # 5. Статусы
    await feed(press(STRANGER, "or:1:shipped"))
    assert s.alerts()[-1] == "Нет доступа"
    await feed(press(ADMIN, "or:1:shipped"))
    assert "📦 Отправлен" in s.of(EditMessageText, chat_id=ADMIN)[-1].text
    assert s.last_text(CLIENT) == "Ваш заказ #1 передан в доставку"
    print("✔ статусы: доступ, обновление карточки, уведомление клиента")

    # 6. Самовывоз; доставка платная ниже порога; отмена клиентом
    await feed(msg(CLIENT2, "/catalog"))
    await feed(press(CLIENT2, "cat:2"))
    await feed(press(CLIENT2, "pc:add:3:2:0"))
    await feed(press(CLIENT2, "ct:checkout:0"))
    await feed(msg(CLIENT2, "Борис"))
    await feed(msg(CLIENT2, "+7 777 111 22 33"))
    await feed(msg(CLIENT2, "🚶 Самовывоз"))
    await feed(msg(CLIENT2, "Позвоню заранее"))
    assert "Самовывоз: ул. Абая, 1" in s.last_text(CLIENT2)
    await feed(press(CLIENT2, "co:place"))
    assert (await db.get_order(2))["total"] == 5000
    await feed(press(ADMIN, "or:2:shipped"))
    assert s.last_text(CLIENT2) == "Ваш заказ #2 готов к выдаче"

    await feed(msg(CLIENT2, "/catalog"))
    await feed(press(CLIENT2, "cat:1"))
    await feed(press(CLIENT2, "pc:add:2:1:1"))
    await feed(press(CLIENT2, "ct:checkout:0"))
    await feed(msg(CLIENT2, "Борис"))  # имя/телефон подставлены кнопками из прошлого заказа
    await feed(msg(CLIENT2, "+77771112233"))
    await feed(msg(CLIENT2, "🚚 Доставка"))
    await feed(msg(CLIENT2, "мкр Самал 2, д 5"))
    await feed(msg(CLIENT2, "⏭ Пропустить"))
    assert "Доставка: 1 000 ₸" in s.last_text(CLIENT2) and "Итого: 4 000 ₸" in s.last_text(CLIENT2)
    await feed(press(CLIENT2, "co:place"))
    await feed(msg(CLIENT2, "📦 Мои заказы"))
    my = s.last_text(CLIENT2)
    assert "#3" in my and "#2" in my and s.last_buttons(CLIENT2) == [("❌ Отменить заказ #3", "mo:cancel:3")]
    await feed(press(CLIENT, "mo:cancel_yes:3"))  # чужой
    assert (await db.get_order(3))["status"] == "new"
    await feed(press(CLIENT2, "mo:cancel:3"))
    await feed(press(CLIENT2, "mo:cancel_yes:3"))
    assert (await db.get_order(3))["status"] == "cancelled"
    assert "Клиент отменил заказ #3" in s.last_text(ADMIN)
    print("✔ самовывоз, платная доставка ниже порога, отмена заказа клиентом")

    # 7. Скрытие и удаление товаров
    await feed(press(ADMIN, "ap:hide:2"))
    await feed(press(ADMIN, "ap:del:3"))
    await feed(press(ADMIN, "ap:del_yes:3"))
    await feed(msg(CLIENT, "🛍 Каталог"))
    assert s.last_buttons(CLIENT)[0] == ("Электроника (1)", "cat:1")
    await feed(press(CLIENT, "pc:add:3:2:0"))
    assert s.alerts()[-1] == "Товар больше недоступен"
    await feed(msg(ADMIN, "/p3"))
    assert "удалён" in s.last_text(ADMIN)
    await feed(msg(ADMIN, "/p 2"))
    assert "скрыт" in s.last_text(ADMIN)
    await feed(msg(ADMIN, "/p 99"))
    assert "не найден" in s.last_text(ADMIN)
    await feed(msg(ADMIN, "/products"))
    assert "/p1" in s.last_text(ADMIN) and "/p3" not in s.last_text(ADMIN)
    print("✔ скрытие, удаление, /p, /products")

    # 8. Заказы, экспорт, статистика
    await feed(msg(ADMIN, "/admin"))
    assert "Админ-панель" in s.last_text(ADMIN)
    await feed(msg(ADMIN, "/orders"))
    assert all(f"#{n}" in s.last_text(ADMIN) for n in (1, 2, 3))
    await feed(msg(ADMIN, "/orders cancelled"))
    assert "#3" in s.last_text(ADMIN) and "#1" not in s.last_text(ADMIN)
    await feed(msg(ADMIN, "/order 1"))
    assert "Заказ #1" in s.last_text(ADMIN) and len(await db.order_messages(1)) == 2
    await feed(msg(ADMIN, "/export"))
    rows = list(csv.reader(io.StringIO(s.of(SendDocument)[-1].document.data.decode("utf-8-sig")), delimiter=";"))
    assert len(rows) == 4 and rows[1][9] == "Наушники × 2" and rows[1][12] == "27980"
    await feed(msg(ADMIN, "/stats"))
    stats = s.last_text(ADMIN)
    assert "Сегодня: 2 зак. · 32 980 ₸" in stats and "1. Наушники — 2 шт" in stats
    print("✔ /orders, /order, /export, /stats")

    # 9. Ограничения и рабочая группа
    await feed(press(CLIENT, "pc:add:1:1:0", photo=True))
    await feed(press(CLIENT, "ct:checkout:0"), min_order=100000)
    assert "Минимальная сумма" in s.alerts()[-1]
    await feed(press(CLIENT, "ct:checkout:0"), max_orders_per_hour=1)
    assert "Слишком много заказов" in s.alerts()[-1]
    await feed(press(STRANGER, "or:2:done", chat=GROUP), orders_chat_id=GROUP)
    assert (await db.get_order(2))["status"] == "done"
    await feed(press(CLIENT, "co:place"))
    assert "устарела" in s.alerts()[-1]
    print("✔ минимальная сумма, лимит заказов, рабочая группа, устаревшие кнопки")

    # 10. Демо-режим: копия карточки владельца, статус только своего заказа, без реквизитов оплаты
    await feed(msg(CLIENT2, "/start"), demo_mode=True)
    assert "демо-магазин" in s.last_text(CLIENT2)
    await feed(press(CLIENT2, "pc:add:1:1:0", photo=True), demo_mode=True)
    await feed(press(CLIENT2, "ct:checkout:0"), demo_mode=True)
    for text in ("Борис", "+77771112233", "🚶 Самовывоз", "⏭ Пропустить"):
        await feed(msg(CLIENT2, text), demo_mode=True)
    summary = s.last_text(CLIENT2)
    assert "оплачивать ничего не нужно" in summary and "Kaspi" not in summary
    await feed(press(CLIENT2, "co:place"), demo_mode=True)
    demo_id = (await db.all_orders())[-1]["id"]
    assert f"Заказ #{demo_id}" in s.last_text(CLIENT2)
    assert any("увидит владелец" in m.text for m in s.of(SendMessage, chat_id=CLIENT2)[-3:])
    await feed(press(CLIENT2, f"or:{demo_id}:confirmed"))
    assert s.alerts()[-1] == "Нет доступа"  # без демо-режима
    await feed(press(STRANGER, f"or:{demo_id}:confirmed"), demo_mode=True)
    assert s.alerts()[-1] == "Нет доступа"  # чужой заказ
    await feed(press(CLIENT2, "or:1:cancelled"), demo_mode=True)
    assert s.alerts()[-1] == "Нет доступа"
    await feed(press(CLIENT2, f"or:{demo_id}:shipped"), demo_mode=True)
    assert s.last_text(CLIENT2) == f"Ваш заказ #{demo_id} готов к выдаче"
    assert len(await db.order_messages(demo_id)) == 2
    await feed(msg(CLIENT2, "/add"), demo_mode=True)
    assert "Новый товар" not in s.last_text(CLIENT2)
    print("✔ демо-режим: копия карточки владельца, статус только своего заказа, без реквизитов")


if __name__ == "__main__":
    asyncio.run(main())
