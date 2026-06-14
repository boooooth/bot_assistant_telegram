# Architecture Research

**Domain:** Public polling Telegram bot fronting a one-shot LLM call (general-purpose AI assistant)
**Researched:** 2026-06-11
**Confidence:** HIGH

> Language note: PROJECT.md does not lock a language, but every locked decision (OpenAI default,
> hand-rolled adapter, Docker, droplet, polling, user's prior self-hosted polling bot) points at the
> mainstream choice for this shape of bot: **Python + `python-telegram-bot` v21 + the official `openai` SDK**.
> This document recommends that stack and structures the architecture around it. If the roadmap chooses
> Node.js instead (`telegraf`/`grammY` + `openai`), the component boundaries and data flow below are
> identical — only file names change.

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                      Telegram Bot API (cloud)                      │
│            getUpdates  ───────────►   sendMessage                  │
└───────────────┬──────────────────────────────▲────────────────────┘
                │ long-poll (pull)              │ reply (push)
┌───────────────▼──────────────────────────────┴────────────────────┐
│                  Bot Process (single container)                    │
│                                                                    │
│  ┌────────────────────┐   update    ┌────────────────────────┐    │
│  │  Polling / Update  │────────────►│   Message Router       │    │
│  │  Handler           │             │   (handler dispatch)   │    │
│  │  (PTB Application,  │◄────────────│                        │    │
│  │   run_polling)     │  reply text └───────────┬────────────┘    │
│  └────────────────────┘                         │ prompt          │
│                                                  ▼                 │
│  ┌────────────────────┐         ┌──────────────────────────────┐  │
│  │  Config / Secrets  │────────►│  LLMProvider (interface)     │  │
│  │  (env vars)        │ select  │  ── OpenAIProvider (default) │  │
│  └────────────────────┘ provider│  ── (future: ClaudeProvider) │  │
│                                  └───────────────┬──────────────┘  │
│  ┌────────────────────┐                          │ HTTPS           │
│  │  Logging           │◄─── all components log    │                │
│  └────────────────────┘                          ▼                 │
└──────────────────────────────────────────────────┼────────────────┘
                                                    ▼
                                       ┌─────────────────────────┐
                                       │  OpenAI API (chat)      │
                                       └─────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Polling / Update Handler | Long-poll Telegram for updates, manage the run loop, graceful shutdown | `python-telegram-bot` `Application.run_polling()` — owns the `getUpdates` loop so you never hand-write it |
| Message Router | Match incoming updates to a handler; ignore non-text; extract the user's text | PTB `MessageHandler(filters.TEXT & ~filters.COMMAND, handle)` + a `CommandHandler("start", ...)` |
| LLMProvider (interface) | Define one method the bot calls regardless of provider | Abstract base class / `Protocol`: `complete(prompt: str) -> str` |
| OpenAIProvider (concrete) | Translate `complete()` into an OpenAI Chat Completions call, return text | Official `openai` SDK, `chat.completions.create` |
| Provider factory | Read `LLM_PROVIDER` env var, return the matching provider instance | Small `get_provider()` dict-dispatch function |
| Config / Secrets | Load and validate `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`, `LLM_PROVIDER`, `OPENAI_MODEL` from env; fail fast if missing | `os.environ` + a typed settings object (e.g. `pydantic-settings` or a plain dataclass) |
| Logging | Structured, leveled logs to stdout (so Docker/journald capture them) | stdlib `logging` configured once at startup |
| Container | Reproducible runtime, same image local and on server | `Dockerfile` + `docker-compose.yml` |
| CI/CD | Build image, push to registry, SSH to server, pull + restart | GitHub Actions + GHCR + `appleboy/ssh-action` |

## Recommended Project Structure

```
telegram_bot_ai/
├── bot/
│   ├── __init__.py
│   ├── main.py             # entrypoint: build Application, register handlers, run_polling()
│   ├── config.py           # load + validate env vars into a Settings object
│   ├── handlers.py         # message router: /start, text handler -> provider.complete()
│   ├── logging_setup.py    # configure stdlib logging once
│   └── llm/
│       ├── __init__.py
│       ├── base.py         # LLMProvider interface (ABC / Protocol)
│       ├── openai_provider.py   # concrete OpenAI implementation
│       └── factory.py      # get_provider(settings) -> LLMProvider
├── tests/
│   └── test_provider.py    # provider returns text; factory selects by env var
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .env.example            # documents required vars, never the real .env
├── requirements.txt        # or pyproject.toml
└── .github/workflows/
    └── deploy.yml          # build -> push GHCR -> ssh deploy on push to main
```

### Structure Rationale

- **`bot/llm/`:** isolates the swap point. Adding a provider = one new file + one line in `factory.py`. Nothing in `handlers.py` ever imports a concrete provider.
- **`config.py` as the only reader of `os.environ`:** the rest of the code receives a validated `Settings` object, so missing secrets fail loudly at startup, not mid-request.
- **`main.py` is thin:** it wires components together (build settings → build provider → build Application → register handlers → run). All logic lives in the modules it imports, which keeps it testable.
- **Flat, not layered-to-death:** a one-shot bot does not need services/repositories/DTOs. Five small modules plus an `llm/` package is the right size.

## Architectural Patterns

### Pattern 1: Adapter (provider abstraction) selected by factory

**What:** A single `LLMProvider` interface with one method; concrete classes per vendor; a factory that picks one from an env var.
**When to use:** Whenever PROJECT.md calls for "swappable provider via env var" without a heavy framework — exactly this case.
**Trade-offs:** Tiny amount of indirection now buys a one-line provider switch later. No LiteLLM dependency (respects the locked "hand-rolled adapter" decision).

**Example:**
```python
# bot/llm/base.py
from typing import Protocol

class LLMProvider(Protocol):
    def complete(self, prompt: str) -> str: ...

# bot/llm/openai_provider.py
from openai import OpenAI

class OpenAIProvider:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def complete(self, prompt: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or ""

# bot/llm/factory.py
def get_provider(settings) -> LLMProvider:
    if settings.llm_provider == "openai":
        return OpenAIProvider(settings.openai_api_key, settings.openai_model)
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider}")
```
A future `ClaudeProvider` implements the same `complete()` and gets one new `elif` — the handler code is untouched.

### Pattern 2: Framework-owned polling loop

**What:** Let `python-telegram-bot`'s `Application.run_polling()` own the `getUpdates` loop, retries, backoff, and graceful shutdown instead of hand-rolling HTTP calls.
**When to use:** Always, for polling bots. Hand-rolling `getUpdates`/offset bookkeeping is a classic source of dropped/duplicate updates.
**Trade-offs:** You accept the library's conventions (handlers, `ContextTypes`) in exchange for correct offset management and signal handling for free.

**Example:**
```python
# bot/main.py
app = ApplicationBuilder().token(settings.telegram_bot_token).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.run_polling()  # owns the loop + graceful shutdown on SIGTERM/SIGINT
```

### Pattern 3: Config-as-startup-gate (fail fast)

**What:** Read and validate every required env var once at boot; refuse to start if any is missing.
**When to use:** Any container that depends on secrets. A bot that boots without `OPENAI_API_KEY` and only fails on the first user message wastes a deploy cycle to discover it.
**Trade-offs:** A few lines of validation; payoff is that a bad deploy crashes immediately and visibly in CI/CD logs.

## Data Flow

### Request Flow (the core loop)

```
User types message in Telegram
        ↓ (Telegram stores it)
PTB Application long-polls getUpdates  ──► receives Update
        ↓
Message Router matches MessageHandler (text, non-command)
        ↓  extracts update.message.text
handle_message(update, context)
        ↓  provider.complete(text)
LLMProvider (OpenAIProvider) ──HTTPS──► OpenAI Chat Completions
        ↓  reply text
        ↓  await update.message.reply_text(reply)
PTB calls sendMessage ──► Telegram ──► user sees reply
```

One message in, one synchronous LLM call, one reply out. No history, no queue, no DB — matches the locked "one-shot, no memory" decision.

### State Management

There is effectively **no application state**. The only "state" is Telegram's `getUpdates` offset, which PTB manages internally in memory. No database, no session store, no per-user context for v1. (When conversation memory returns post-v1, it slots in as a store the handler reads/writes before/after `complete()`.)

### Key Data Flows

1. **Inbound update:** Telegram cloud → long-poll → Application → Router → handler. Pull-based; the bot initiates every fetch.
2. **LLM round-trip:** handler → provider interface → concrete provider → vendor HTTPS API → text back. The only place an API key is used.
3. **Outbound reply:** handler → `reply_text` → PTB → Telegram `sendMessage`. Push-based response on the same chat.
4. **Secrets at boot:** environment → `config.py` → validated Settings → injected into provider + Application. Read once, never re-read per message.

## Suggested Build Order

The components depend on each other in this order; build and prove each locally before adding the next. This is the dependency chain the roadmap should mirror in phase structure.

```
1. Config + Logging        (no deps — everything else needs validated settings)
        ↓
2. LLM adapter             (depends on config; testable in isolation with a script)
   - base.py interface
   - openai_provider.py
   - factory.py (env-var select)
        ↓
3. Polling + Router        (depends on config + adapter; this is the working bot, run locally)
   - main.py, handlers.py
        ↓
4. Containerize            (depends on a working bot; Dockerfile + compose, run same image locally)
        ↓
5. CI/CD deploy            (depends on a working image; GitHub Actions -> GHCR -> droplet)
```

Rationale for this order:
- **Config first** because every other component consumes validated settings; getting fail-fast right early prevents debugging "works locally, dies on droplet" later.
- **Adapter before the bot loop** because the adapter is the riskiest custom piece (the swap design) and is the easiest to test standalone — call `provider.complete("hello")` from a throwaway script, no Telegram needed.
- **Polling loop after the adapter** so the first time you run the real bot, the LLM path already works — you're only debugging Telegram wiring, not two unknowns at once.
- **Containerize only once the bot runs on the host** so a container failure is unambiguously a packaging issue, not a code issue. Docker gives local/prod parity (a locked decision), so the same `docker compose up` you run locally is what runs on the droplet.
- **CI/CD last** because it's pure plumbing around an already-working image; build it when there is something proven worth deploying.

## Container & Deploy Topology

### Dockerfile shape
- Single-stage `python:3.12-slim` base; copy `requirements.txt`, `pip install`, copy `bot/`, `CMD ["python", "-m", "bot.main"]`.
- No exposed ports — polling needs no inbound port, no domain, no TLS (a locked decision; this is the main reason droplet+polling is cheap and simple).
- Run as a non-root user.

### docker-compose.yml shape
- One service `bot`, `restart: unless-stopped` (this is what keeps it up 24/7), `env_file: .env` for secrets on the droplet, image pinned to the GHCR tag.

### CI/CD pipeline (GitHub Actions, on push to `main`)
```
build job:
  - checkout
  - docker/login-action  -> ghcr.io (GITHUB_TOKEN)
  - docker/build-push-action -> push ghcr.io/<owner>/telegram_bot_ai:latest (+ sha tag)
deploy job (needs: build):
  - appleboy/ssh-action -> droplet:
      docker compose pull && docker compose up -d && docker image prune -f
```
Secrets in GitHub: `DROPLET_HOST`, `DROPLET_USER`, `SSH_PRIVATE_KEY`. App secrets (`TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`) live in the droplet's `.env`, never in the image or repo. This GHCR + `appleboy/ssh-action` + `compose pull && up -d` flow is the verified-standard droplet deploy pattern.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0–1k messages/day | Single container, single droplet. No changes. This is v1's home and is comfortable. |
| 1k–100k messages/day | OpenAI call latency dominates. Ensure async handling so one slow LLM call doesn't block others (PTB's async handlers already do this). Add the deliberately-deferred rate limiting / usage caps here — the unbounded-cost risk noted in PROJECT.md bites at this scale. |
| 100k+ messages/day | Move off the synchronous-per-update model: enqueue prompts, scale worker count, consider webhook for lower-overhead delivery. Out of scope for v1 and likely never needed for a personal bot. |

### Scaling Priorities

1. **First bottleneck (cost, not compute):** public access + no caps = unbounded OpenAI spend. PROJECT.md accepts this for v1; the very first scaling action is adding caps/rate limiting, not more servers.
2. **Second bottleneck (concurrency):** a long OpenAI response holds a coroutine. PTB handles updates concurrently by default, so this is fine until very high volume; only then consider a queue/worker split.

## Anti-Patterns

### Anti-Pattern 1: Hand-rolling the getUpdates loop

**What people do:** Write a `while True` loop calling `getUpdates` with manual offset tracking instead of using the library.
**Why it's wrong:** Off-by-one offset bugs cause dropped or infinitely-redelivered messages; you also reimplement backoff and graceful shutdown badly.
**Do this instead:** Use `Application.run_polling()` and register handlers. The library owns offset, retries, and SIGTERM handling.

### Anti-Pattern 2: Importing the concrete provider in the handler

**What people do:** `from bot.llm.openai_provider import OpenAIProvider` inside `handlers.py` and instantiate it there.
**Why it's wrong:** It defeats the swap design — switching providers now means editing handler code, not flipping an env var.
**Do this instead:** Handlers depend only on the `LLMProvider` interface; `main.py` builds the concrete one via the factory and passes it in (e.g. via `bot_data`/closure).

### Anti-Pattern 3: Reading env vars scattered through the code

**What people do:** `os.environ["OPENAI_API_KEY"]` in three different modules.
**Why it's wrong:** Missing-var failures surface late and inconsistently; hard to see the full required config; easy to typo a key name.
**Do this instead:** One `config.py` reads and validates everything once at boot; everyone else takes a `Settings` object.

### Anti-Pattern 4: Baking secrets into the image

**What people do:** `COPY .env` into the Docker image or `ENV OPENAI_API_KEY=...` in the Dockerfile.
**Why it's wrong:** Secrets leak into the registry/image layers and CI logs.
**Do this instead:** `.env` on the droplet via `env_file` in compose; GitHub Actions injects only deploy SSH secrets, never app secrets.

### Anti-Pattern 5: Logging the full prompt/response at INFO

**What people do:** Log every user message and LLM reply.
**Why it's wrong:** Public bot = logging strangers' content; noisy and a privacy footgun.
**Do this instead:** Log metadata (chat id, latency, token usage, errors) at INFO; gate content behind DEBUG only.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Telegram Bot API | `python-telegram-bot`, long polling via `run_polling()` | No inbound port/domain/TLS needed — the reason polling was chosen. Token from env. |
| OpenAI API | Official `openai` SDK behind `OpenAIProvider`, Chat Completions | Only the provider touches it. Network/timeout/auth errors must be caught and turned into a friendly reply, not a crash. |
| GHCR (registry) | `docker/build-push-action`, auth via `GITHUB_TOKEN` | Image storage between CI and droplet. |
| DigitalOcean droplet | `appleboy/ssh-action` over SSH key | Runs `docker compose pull && up -d`. Docker + compose pre-installed on the droplet. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Router ↔ LLMProvider | Direct call to `complete(prompt) -> str` | The interface seam. Router never knows which vendor answers. |
| Factory ↔ concrete providers | Dict/`if` dispatch on `LLM_PROVIDER` | The single place that names concrete classes. |
| Config ↔ everything | Inject validated `Settings` object | One-way: config is read at boot and passed down; nothing reads env directly. |
| main.py ↔ components | Composition root: builds + wires all parts | Keeps modules decoupled and unit-testable. |

## Sources

- [Application — python-telegram-bot v21.10](https://docs.python-telegram-bot.org/en/v21.10/telegram.ext.application.html) — `run_polling()` owns the loop, init, and graceful shutdown (HIGH, curated/official)
- [ApplicationBuilder — python-telegram-bot v21.9](https://docs.python-telegram-bot.org/en/v21.9/telegram.ext.applicationbuilder.html) — handler registration / builder pattern (HIGH, curated/official)
- [Deploying to DigitalOcean via GitHub Actions and SSH](https://docs.servicestack.net/do-github-action-mix-deployment) — build/push + SSH deploy pattern (MEDIUM, web)
- [How to deploy an app to droplet via SSH action — DigitalOcean Community](https://www.digitalocean.com/community/questions/how-to-deploy-an-app-to-droplet-via-ssh-action) — `appleboy/ssh-action` + `compose pull && up -d` (MEDIUM, web)

---
*Architecture research for: public polling Telegram bot + one-shot LLM (general AI assistant)*
*Researched: 2026-06-11*
