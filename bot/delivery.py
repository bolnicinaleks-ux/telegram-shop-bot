import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message

from bot import keyboards as kb
from bot.config import Config
from bot.db import Database
from bot.utils import order_card

log = logging.getLogger(__name__)


async def send_order_card(bot: Bot, db: Database, cfg: Config, order, chat_id: int) -> bool:
    try:
        msg = await bot.send_message(
            chat_id,
            order_card(order, await db.order_items(order["id"]), cfg),
            reply_markup=kb.order_status_kb(order["id"], order["status"]),
        )
    except TelegramAPIError as e:
        log.warning("Не удалось отправить заказ #%s в чат %s: %s", order["id"], chat_id, e)
        return False
    await db.add_message(order["id"], chat_id, msg.message_id)
    return True


async def deliver_order(bot: Bot, db: Database, cfg: Config, order) -> None:
    for chat_id in cfg.order_targets:
        await send_order_card(bot, db, cfg, order, chat_id)


async def refresh_order_cards(bot: Bot, db: Database, cfg: Config, order) -> None:
    text = order_card(order, await db.order_items(order["id"]), cfg)
    markup = kb.order_status_kb(order["id"], order["status"])
    for m in await db.order_messages(order["id"]):
        try:
            await bot.edit_message_text(text=text, chat_id=m["chat_id"], message_id=m["message_id"], reply_markup=markup)
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                log.info("Карточка %s/%s не обновлена: %s", m["chat_id"], m["message_id"], e)
        except TelegramAPIError as e:
            log.warning("Карточка %s/%s не обновлена: %s", m["chat_id"], m["message_id"], e)


async def notify_user(bot: Bot, user_id: int, text: str) -> bool:
    try:
        await bot.send_message(user_id, text)
        return True
    except TelegramAPIError as e:
        log.warning("Не удалось написать пользователю %s: %s", user_id, e)
        return False


async def notify_admins(bot: Bot, cfg: Config, text: str) -> None:
    for chat_id in cfg.order_targets:
        try:
            await bot.send_message(chat_id, text)
        except TelegramAPIError as e:
            log.warning("Не удалось уведомить %s: %s", chat_id, e)


async def edit_card(message: Message, text: str, markup: InlineKeyboardMarkup | None) -> None:
    """Редактирует карточку — фото с подписью или обычный текст."""
    try:
        if message.photo:
            await message.edit_caption(caption=text, reply_markup=markup)
        else:
            await message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


async def safe_delete(message: Message) -> None:
    try:
        await message.delete()
    except TelegramAPIError:
        pass
