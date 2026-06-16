import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from .prompts import HELP_TEXT, NON_TEXT_REPLY, START_TEXT, TRUNCATION_NOTE

logger = logging.getLogger(__name__)


def split_text(text: str, max_len: int = 4096, max_chunks: int = 3) -> list[str]:
    """Split text at newline boundaries; cap at max_chunks."""
    chunks: list[str] = []
    remaining = text
    while remaining and len(chunks) < max_chunks:
        if len(remaining) <= max_len:
            chunks.append(remaining)
            break
        split_at = remaining.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len - 1  # stay one char inside Telegram's 4096-char limit
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip("\n")
    if remaining and len(chunks) == max_chunks:
        chunks[-1] += TRUNCATION_NOTE
    return chunks


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(START_TEXT)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(HELP_TEXT)


async def handle_non_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(NON_TEXT_REPLY)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_chat is None:
        return
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(
        chat_id=chat_id,
        action=ChatAction.TYPING,
    )
    allowed_chat_ids = context.bot_data.get("allowed_chat_ids", frozenset())
    if allowed_chat_ids and chat_id not in allowed_chat_ids:
        await update.message.reply_text(
            "Sorry, you are not authorized to use this bot."
        )
        logger.info("unauthorized access attempt from chat_id=%s", chat_id)
        return
    logger.info("message from chat_id=%s", chat_id)
    user_text = update.message.text
    if not user_text:
        return  # nothing to send; PTB filter shouldn't let this through, but guard anyway
    try:
        reply = await context.bot_data["complete"](user_text)
        for chunk in split_text(reply):
            await update.message.reply_text(chunk, do_quote=True)
        logger.info("replied to chat_id=%s", chat_id)
    except Exception:
        logger.exception("OpenAI call failed for chat_id=%s", chat_id)
        await update.message.reply_text(
            "Sorry, something went wrong. Please try again in a moment."
        )
