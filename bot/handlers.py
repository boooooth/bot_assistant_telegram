import logging

from telegram import Update
from telegram.ext import ContextTypes

from .prompts import HELP_TEXT, START_TEXT

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(START_TEXT)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(HELP_TEXT)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_chat is None:
        return
    chat_id = update.effective_chat.id
    allowed_chat_ids = context.bot_data.get("allowed_chat_ids", frozenset())
    if allowed_chat_ids and chat_id not in allowed_chat_ids:
        await update.message.reply_text(
            "Sorry, you are not authorized to use this bot."
        )
        logger.info("unauthorized access attempt from chat_id=%s", chat_id)
        return
    logger.info("message from chat_id=%s", chat_id)
    try:
        reply = await context.bot_data["complete"](update.message.text)
        await update.message.reply_text(reply)
        logger.info("replied to chat_id=%s", chat_id)
    except Exception:
        logger.exception("OpenAI call failed for chat_id=%s", chat_id)
        await update.message.reply_text(
            "Sorry, something went wrong. Please try again in a moment."
        )
