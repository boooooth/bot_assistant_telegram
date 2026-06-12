import logging

from dotenv import load_dotenv
from openai import AsyncOpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from . import openai_client
from .config import load_settings
from .handlers import handle_text, help_cmd, start


def main() -> None:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    settings = load_settings()

    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=60)

    app = ApplicationBuilder().token(settings.telegram_bot_token).build()
    app.bot_data["complete"] = lambda text: openai_client.complete(
        client, settings.openai_model, text
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling(allowed_updates=Update.ALL_TYPES)
