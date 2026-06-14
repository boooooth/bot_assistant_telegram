# Stack Research

**Domain:** Public polling Telegram bot that relays user messages to an LLM (one-shot, swappable provider, Dockerized, deployed to a Linux VPS via GitHub Actions)
**Researched:** 2026-06-11
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12 (3.10+ required) | Implementation language | User already has Python 3.12/3.14 installed and prior polling-bot experience. Python is the dominant ecosystem for both Telegram bots and LLM SDKs — official, mature, first-party SDKs exist for OpenAI, Anthropic, and the Telegram Bot API. 3.12 is the sweet spot in 2026: fully supported by every dependency below, broad wheel availability, and a stable `slim` Docker image. (3.13/3.14 work too, but 3.12 has the widest battle-tested support.) |
| python-telegram-bot (PTB) | 22.7 | Telegram Bot API wrapper + polling loop | The de-facto standard async Telegram library. Built-in `Application.run_polling()` is exactly the locked delivery model — no domain/TLS needed. Handles long-polling, retries, graceful shutdown (SIGTERM/SIGINT, important for Docker), and update dispatch out of the box. Pure-async (asyncio), actively maintained, requires Python 3.10+. |
| openai | 2.41.1 | Default LLM provider SDK | Official first-party OpenAI Python SDK (v2 line). Async client (`AsyncOpenAI`) integrates cleanly with PTB's asyncio loop. Stable `chat.completions.create` / `responses.create` API, typed responses, built-in retries and `x-request-id` surfacing for debugging. This is the default behind the adapter. |
| anthropic | 0.109.1 | Alternative LLM provider SDK | Official first-party Anthropic (Claude) SDK. Installed alongside `openai` so the env-var swap to Claude is genuinely one-line. Async client (`AsyncAnthropic`) mirrors the OpenAI ergonomics. Only the provider name in an env var changes at runtime. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dotenv | 1.x (latest) | Load `.env` in local dev | Local/dev parity only. Read `TELEGRAM_BOT_TOKEN`, `LLM_PROVIDER`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` from a `.env` file locally; in the container these come from real env vars / Docker `--env-file`. Keep it a dev convenience, not a runtime dependency for config. |
| (stdlib) `logging` | builtin | Structured logging | No third-party logging lib needed for v1. Use stdlib `logging` at INFO, log incoming chat IDs (not message bodies, for privacy/cost-debugging) and LLM errors. PTB integrates with it natively. |
| (stdlib) `asyncio` | builtin | Concurrency | PTB and both SDKs are async; the adapter interface should be `async`. No extra concurrency lib required. |

**Deliberately NOT adding for v1:** `httpx` (pulled in transitively by all three SDKs — do not pin it yourself), `pydantic` (overkill for ~4 env vars; a small dataclass/`os.environ` reader suffices), and any rate-limiter/cache extras.

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| ruff | Lint + format | Single fast tool replacing flake8 + black + isort. Add a minimal `ruff.toml`; run in CI before the build step. |
| Docker + docker compose | Packaging & dev/prod parity | Same image runs locally and on the server. A one-service `compose.yaml` on the server makes the deploy step (`docker compose pull && up -d`) trivial and gives you `restart: unless-stopped` for 24/7 uptime. |
| GitHub Actions | CI/CD | Build image, push to GHCR, SSH to server, pull + restart. See workflow sketch below. |

## Installation

```bash
# Core (pin in requirements.txt or pyproject)
pip install "python-telegram-bot==22.7" "openai==2.41.1" "anthropic==0.109.1" "python-dotenv>=1.0"

# Dev dependencies
pip install -U ruff
```

`requirements.txt` (recommended for a simple bot — easy to `pip install` in the Dockerfile):

```
python-telegram-bot==22.7
openai==2.41.1
anthropic==0.109.1
python-dotenv>=1.0,<2
```

## Provider Adapter Structure (the locked "thin hand-rolled adapter")

One internal async interface, one implementation per provider, selected by `LLM_PROVIDER` env var via a tiny factory. No framework.

```python
# llm/base.py
from typing import Protocol

class LLMProvider(Protocol):
    async def complete(self, prompt: str) -> str: ...

# llm/openai_provider.py
from openai import AsyncOpenAI
class OpenAIProvider:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
    async def complete(self, prompt: str) -> str:
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or ""

# llm/anthropic_provider.py
from anthropic import AsyncAnthropic
class AnthropicProvider:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5"):
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model
    async def complete(self, prompt: str) -> str:
        msg = await self._client.messages.create(
            model=self._model, max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in msg.content if b.type == "text")

# llm/factory.py
def make_provider() -> LLMProvider:
    name = os.environ["LLM_PROVIDER"].lower()  # "openai" | "anthropic"
    if name == "openai":
        return OpenAIProvider(os.environ["OPENAI_API_KEY"])
    if name == "anthropic":
        return AnthropicProvider(os.environ["ANTHROPIC_API_KEY"])
    raise ValueError(f"Unknown LLM_PROVIDER: {name}")
```

The Telegram message handler depends only on the `LLMProvider` Protocol — it never imports a vendor SDK directly. Swapping providers = change `LLM_PROVIDER` and the corresponding API key. This is the single most important structural decision and it is intentionally tiny.

## Docker Base Image

**Recommendation: `python:3.12-slim` (Debian bookworm/trixie slim), single or simple multi-stage build.**

```dockerfile
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "-m", "bot"]
```

- `slim` gives glibc compatibility (prebuilt wheels for httpx/cryptography "just work"), active security patches, and a ~40MB base — the documented default choice for Python apps in 2026.
- `PYTHONUNBUFFERED=1` so logs reach Docker/journald immediately.
- Rely on PTB's built-in signal handling for graceful shutdown; pair with `restart: unless-stopped` in compose for 24/7 uptime.

## GitHub Actions → Linux VPS (push to `main`)

Standard, well-trodden pattern: **build → push to GHCR → SSH to server → pull + restart**.

```yaml
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions: { contents: read, packages: write }
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        with:
          push: true
          tags: ghcr.io/${{ github.repository }}:latest
      - uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SERVER_SSH_KEY }}
          script: |
            cd /opt/telegram-bot
            docker compose pull
            docker compose up -d
```

- **Registry: GHCR (`ghcr.io`)** — free for the repo, authenticated with the built-in `GITHUB_TOKEN`, no extra cloud-specific container registry billing. The server pulls with a read-only PAT/`GITHUB_TOKEN`.
- **SSH: `appleboy/ssh-action@v1`** — the standard action for "run these commands on my server." Use an **ED25519** deploy key (RSA is rejected on some modern sshd configs).
- Secrets needed: `SERVER_HOST`, `SERVER_USER`, `SERVER_SSH_KEY`. Provider/API keys live in an `.env` file on the server referenced by `compose.yaml` (never baked into the image).

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| python-telegram-bot 22.7 | aiogram 3.x | aiogram is excellent and slightly more modern in API; choose it if you prefer its router/filter style. PTB wins here on the user's prior familiarity and `run_polling()` simplicity. Either is a defensible standard. |
| python-telegram-bot 22.7 | pyTelegramBotAPI (telebot) | Simpler but largely sync; weaker fit for async LLM calls. Use only for trivial sync scripts. |
| Hand-rolled adapter | LiteLLM | LiteLLM is the right call when you need 5+ providers, unified streaming, fallbacks, and budget tracking. For two providers and one-shot calls it adds a heavy dependency and abstraction the project explicitly rejected. Revisit only if provider count or routing complexity grows. |
| GHCR | Cloud-specific container registry | Use a provider registry if you want registry and server in one vendor/VPC or hit GHCR rate/visibility limits. GHCR is cheaper and simpler for a single private repo. |
| `appleboy/ssh-action` + compose | Managed platform (PaaS) | A managed platform removes server management but costs more and was explicitly declined in favor of a Linux VPS with full control. |
| `python:3.12-slim` | `python:3.12-alpine` | Alpine only if image size is critical AND you have no glibc-only wheels. For Python it routinely breaks/recompiles wheels (musl libc) — not worth it here. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| LiteLLM (or any multi-provider framework) for v1 | Explicitly out of scope; heavy dependency for a 2-provider one-shot bot; obscures the simple adapter | Hand-rolled `LLMProvider` Protocol + per-provider class |
| Webhook mode / Flask/FastAPI front | Requires public URL, TLS, domain; contradicts locked polling decision | PTB `Application.run_polling()` |
| `python:3.12-alpine` | musl libc breaks/recompiles many Python wheels; slow, fragile builds | `python:3.12-slim` |
| Conversation/history storage (Redis, DB) | One-shot replies are locked scope; adds infra | Stateless handler; no persistence |
| Pinning `httpx` yourself | All three SDKs bring a compatible `httpx`; manual pins cause resolver conflicts | Let SDKs manage it transitively |
| Baking API keys into the Docker image | Leaks secrets into image layers/registry | `.env` on droplet via compose `env_file`; GH Actions secrets for SSH only |
| `latest` floating Python tag in Dockerfile | Non-reproducible builds | Pin `python:3.12-slim` |

## Stack Patterns by Variant

**If you later add a 3rd/4th LLM provider or need fallback/streaming/budgets:**
- Reconsider LiteLLM at that point; the Protocol-based adapter makes migration localized to the `llm/` package.

**If cost risk materializes (public bot, no caps):**
- Add PTB's `[rate-limiter]` extra (aiolimiter) and/or a per-user throttle in the handler. Out of scope for v1 but the cleanest place to add it is the handler layer, not the adapter.

**If you outgrow long-polling reliability or want instant delivery:**
- Switch to webhook mode — PTB supports it via the `[webhooks]` extra (tornado), but this then requires the domain/TLS the project deliberately avoided.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| python-telegram-bot 22.7 | Python 3.10–3.14 | Async; needs 3.10+. 3.12 recommended. |
| openai 2.41.1 | Python 3.9–3.14 | v2 SDK line; `AsyncOpenAI` for asyncio. |
| anthropic 0.109.1 | Python 3.9–3.14 | `AsyncAnthropic` for asyncio. |
| PTB + openai + anthropic | shared `httpx`/`anyio` | All three depend on `httpx`; do not pin `httpx` manually to avoid resolver conflicts. |
| docker/build-push-action | docker/login-action@v3 | v6 is current-stable and widely used; v7 + login-action@v4 also released in 2026. Either works; v6/v3 are the conservative, documented pairing. |

## Sources

- https://pypi.org/pypi/python-telegram-bot/json — confirmed v22.7, Python 3.10+, available extras (HIGH)
- https://pypi.org/pypi/openai/json — confirmed v2.41.1, Python 3.9–3.14 (HIGH)
- https://pypi.org/pypi/anthropic/json — confirmed v0.109.1 (2026-06-09), Python 3.9+ (HIGH)
- https://docs.python-telegram-bot.org/ — `Application.run_polling()` behavior, signal handling (HIGH)
- https://pythonspeed.com/articles/base-image-python-docker-images/ — slim vs alpine vs distroless guidance, Feb 2026 (MEDIUM-HIGH, cross-checked)
- https://oneuptime.com/blog/post/2026-02-08-how-to-choose-the-right-docker-base-image-for-your-application/view — base image selection (MEDIUM, cross-checked)
- https://www.digitalocean.com/community/questions/github-action-to-deploy-docker-image-from-github-packages — GHCR + appleboy/ssh-action deploy pattern (MEDIUM, cross-checked)
- https://github.com/docker/build-push-action — current action versions v6/v7 (MEDIUM)

---
*Stack research for: public polling Telegram → LLM bot*
*Researched: 2026-06-11*
