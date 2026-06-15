# Telegram AI Bot

A public Telegram bot that sends your messages to OpenAI (ChatGPT) and replies in the same chat.

## Run locally

1. Copy `.env.example` to `.env` and fill in your credentials:

```
TELEGRAM_BOT_TOKEN=   # from BotFather → /newbot
LLM_API_KEY=          # from platform.openai.com → API keys (OpenAI by default)
LLM_MODEL=            # optional, defaults to gpt-4o-mini
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

## Deploy to a Linux VPS (manual, Phase 3)

This is the one-time manual runbook to take the locally-built image to a Linux VPS and run
it 24/7. CI/CD automation comes later (Phase 4) — for now you push and deploy by hand.

The image name comes from `compose.yaml`:
`ghcr.io/${GITHUB_REPOSITORY:-telegram-bot-ai}/bot:latest`. When `GITHUB_REPOSITORY` is unset
it resolves to `telegram-bot-ai`, which is **not** a valid GHCR namespace. Export it so the
pushed tag matches your GHCR account:

```bash
export GITHUB_REPOSITORY=<owner>/telegram_bot_ai   # e.g. boooooth/telegram_bot_ai
```

### 1. Log in to GHCR on your machine (one-time)

Create a **classic Personal Access Token (PAT)** with the `write:packages` scope:
GitHub → Settings → Developer settings → Personal access tokens (classic) → Generate new token.
Then log in with it:

```bash
echo $GHCR_PAT | docker login ghcr.io -u <github-username> --password-stdin
# expected: Login Succeeded
```

The PAT lives **only on your local machine**, used by `docker login` — it is never committed
to the repo and never baked into the image.

### 2. Build and push the image

With `GITHUB_REPOSITORY` exported (step above), build the hardened image and push it to GHCR:

```bash
docker compose build
docker compose push          # pushes ghcr.io/<owner>/telegram_bot_ai/bot:latest
```

The **server never builds** — it only pulls this exact image. Building once locally and pushing
guarantees the server runs the identical artifact you built and tested.

### 3. Bootstrap the server (one-time)

SSH into the VPS and install Docker Engine plus the `docker compose` plugin (see
https://docs.docker.com/engine/install/ for your distro):

```bash
ssh <user>@<server-host>
# install Docker Engine + docker compose plugin per your distro's instructions
```

Copy `compose.yaml` to the server (the only repo file the server needs), then create the
runtime `.env` **directly on the server** from the `.env.example` template:

```bash
# from your machine:
scp compose.yaml <user>@<server-host>:~/telegram-bot/compose.yaml

# on the server, in ~/telegram-bot:
nano .env
```

Fill the server `.env` with:

```
TELEGRAM_BOT_TOKEN=   # from BotFather — MUST be a different token than your local dev bot
LLM_API_KEY=          # your LLM provider key (OpenAI by default)
LLM_MODEL=            # optional, defaults to gpt-4o-mini
ALLOWED_CHAT_IDS=     # optional, comma-separated chat IDs to whitelist (empty = allow all)
```

The server `.env` is **created on the server and never committed** — secrets are injected at
runtime via compose's `env_file`, never stored in git or baked into the image. Use a
**production bot token that differs from any local dev token**, otherwise both pollers fight
over `getUpdates` and Telegram returns 409 conflicts.

### 4. Log in to GHCR on the server, then pull and run

On the server, authenticate to GHCR with a read-capable token, then pull and start the bot:

```bash
echo $GHCR_PAT | docker login ghcr.io -u <github-username> --password-stdin
docker compose pull
docker compose up -d
```

This runs the **exact image you built locally** — the server pulled it, it never rebuilt.

### 5. Verify 24/7 auto-restart

Confirm the bot is running:

```bash
docker compose ps        # the bot service should show state "Up"
```

The container uses `restart: unless-stopped` (see `compose.yaml`), which is the recovery
mechanism — there is **no `HEALTHCHECK`** by design; the restart policy is enough for a
polling bot. Verify it actually recovers:

```bash
# (a) crash recovery: kill the container process and confirm Docker brings it back
docker kill $(docker compose ps -q bot)
docker compose ps        # after a moment the bot is "Up" again — Docker restarted it

# (b) reboot recovery: the same policy returns the bot after a full server reboot,
#     because the Docker daemon starts on boot and re-launches unless-stopped containers
sudo reboot
# after the server comes back:
docker compose ps        # the bot is "Up" without any manual start
```

With `restart: unless-stopped`, the bot survives both a crashed process and a server reboot —
satisfying the 24/7 requirement.

## Known limitations (v1)

- Replies longer than 4096 characters may fail (Telegram limit) — no splitting yet.
- Slow or failing OpenAI calls time out after 30 seconds and return a friendly error message.
- No conversation memory — each message is answered fresh.
- No rate limits or cost caps — set a billing cap in the OpenAI dashboard before going public.
