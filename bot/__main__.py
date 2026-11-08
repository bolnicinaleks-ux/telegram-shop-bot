import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat

from bot.config import Config, load_config
from bot.db import Database
from bot.i18n import _
from bot.handlers import admin, client

CLIENT_COMMANDS = [
    BotCommand(command="catalog", description=_("Каталог")),
    BotCommand(command="cart", description=_("Корзина")),
    BotCommand(command="myorders", description=_("Мои заказы")),
]
ADMIN_COMMANDS = CLIENT_COMMANDS + [
    BotCommand(command="admin", description=_("Админ-панель")),
    BotCommand(command="add", description=_("Добавить товар")),
    BotCommand(command="products", description=_("Товары")),
    BotCommand(command="orders", description=_("Заказы")),
    BotCommand(command="stats", description=_("Статистика")),
]


def build_dispatcher(db: Database, cfg: Config) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage(), db=db, cfg=cfg)
    dp.include_routers(admin.router, client.router)
    return dp


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = load_config()
    os.makedirs(os.path.dirname(cfg.db_path) or ".", exist_ok=True)
    db = Database(cfg.db_path)
    await db.connect()

    bot = Bot(cfg.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher(db, cfg)
    # Всё, что может упасть (например, нет сети при старте), — внутри try:
    # иначе открытая БД не даст процессу завершиться и супервизор не перезапустит бота.
    try:
        await bot.set_my_commands(CLIENT_COMMANDS)
        for admin_id in cfg.admin_ids:
            try:
                await bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=admin_id))
            except Exception as e:  # админ ещё не писал боту
                logging.warning("Меню команд для админа %s не установлено: %s", admin_id, e)
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
