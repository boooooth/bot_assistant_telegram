# Telegram AI Bot

A public Telegram bot that sends your messages to OpenAI (ChatGPT) and replies in the same chat.

## Run locally

1. Copy `.env.example` to `.env` and fill in your credentials:

```
TELEGRAM_BOT_TOKEN=   # from BotFather → /newbot
OPENAI_API_KEY=       # from platform.openai.com → API keys
OPENAI_MODEL=         # optional, defaults to gpt-4o-mini
ALLOWED_CHAT_IDS=     # optional, comma-separated chat IDs to whitelist (empty = allow all)
```

2. Install deps and run:

```bash
pip install -r requirements.txt
python -m bot
```

Use a **separate dev bot token** (not your production token) to avoid 409 polling conflicts.

## Run with Docker

```bash
docker compose up --build
```

Secrets are read from `.env` at runtime — never baked into the image.

## Known limitations (v1)

- Replies longer than 4096 characters may fail (Telegram limit) — no splitting yet.
- Slow or failing OpenAI calls time out after 30 seconds and return a friendly error message.
- No conversation memory — each message is answered fresh.
- No rate limits or cost caps — set a billing cap in the OpenAI dashboard before going public.
