import logging

from telegram import Update
from telegram.ext import ContextTypes

from .prompts import HELP_TEXT, START_TEXT

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(START_TEXT)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
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
