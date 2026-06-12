# Phase 1: Working AI Bot - Research

**Researched:** 2026-06-12
**Domain:** Async Python Telegram bot (long polling) fronting a one-shot OpenAI chat completion
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

The user delegated UX gray areas to Claude ("the PRD is good… let's start"). Recorded defaults:

- **D-01 (Persona):** Minimal system prompt — a single "You are a helpful assistant" style instruction. Friendly, concise, neutral. No elaborate persona for v1 (configurable persona deferred to v2).
- **D-02 (`/start` copy):** Short welcome that tells the user they can just send a message and get an AI reply, and points to `/help`. One or two short lines.
- **D-03 (`/help` copy):** Explains the bot answers any text message using AI, one message at a time, with no memory of past messages yet. Plain, brief.
- **D-04 (Reply length):** Soft-nudge the model toward concise answers via the system prompt. **No hard `max_tokens` cap** — cost controls deliberately deferred. The >4096-char failure remains a documented known limitation for v1.
- **D-05 (Language):** Reply in the same language the user writes in (e.g. Khmer in → Khmer out), via a system-prompt instruction relying on the model's native multilingual ability.

**Project-level locked decisions (PROJECT.md / PRD §11 — override the project STACK.md adapter sketch):**
- **Call the OpenAI (ChatGPT) API directly — NO provider abstraction layer for v1.** Switching providers later is a deliberate code change, not a config flip. (This reverses the earlier `LLMProvider` Protocol / factory plan that appears in `.planning/research/STACK.md` and `CLAUDE.md`. For Phase 1, do NOT build an adapter/factory/Protocol or install `anthropic`.)
- **Model:** configurable via `OPENAI_MODEL` env var, default `gpt-4o-mini`.
- **Delivery:** long polling (`run_polling()`), not webhooks.
- **State:** one-shot replies, no conversation memory.

### Claude's Discretion
- Exact wording of the system prompt and the `/start` / `/help` text.
- Project/module layout, function names, and how config is read/validated.
- Local run mechanism (e.g. `python -m bot` / `.env` loading) and dependency pinning.
- OpenAI call parameters beyond the model (e.g. `temperature`) — pick sensible defaults for a general assistant.

### Deferred Ideas (OUT OF SCOPE)
- **Configurable persona / system prompt** — v2 (CONV-02). v1 uses a fixed minimal prompt.
- **Long-reply splitting (>4096 chars)** — v2 (UX-02). v1 accepts the known limitation.
- **Typing indicator, non-text input guard** — v2 (UX-01, UX-03).
- **Cost controls (`max_tokens` clamp, rate limits, billing cap)** — v2 (COST-*); OpenAI dashboard billing cap recommended operationally.
- **Error/timeout handling + retries + concurrency tuning** — Phase 2 (REL-01, REL-02, REL-03).
- **Docker / droplet / 24/7** — Phase 3. **Tests + CI/CD** — Phase 4.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MSG-01 | Receive text messages from any Telegram user via long polling | PTB `MessageHandler(filters.TEXT & ~filters.COMMAND, ...)` + `Application.run_polling()` (see Pattern 2, Code Examples) |
| MSG-02 | Send each text message to OpenAI as a one-shot prompt (no conversation history) | `messages=[{system}, {user: update.message.text}]` rebuilt per call; no stored history (see Code Examples §2) |
| MSG-03 | Send the LLM's reply back to the user in the same chat | `await update.message.reply_text(reply)` (see Code Examples §3) |
| CMD-01 | `/start` returns a short welcome | `CommandHandler("start", start)`; static text, no LLM call (D-02) |
| CMD-02 | `/help` returns brief usage guidance | `CommandHandler("help", help_cmd)`; static text, no LLM call (D-03) |
| LLM-01 | Call OpenAI directly; model from env var, default `gpt-4o-mini` | `AsyncOpenAI` + `chat.completions.create(model=settings.openai_model, ...)`; `OPENAI_MODEL` env default (see Standard Stack, Config pattern) |

**Phase 1 success criteria (ROADMAP):** user receives an OpenAI reply in-chat; each message is a fresh one-shot prompt; `/start` and `/help` work; model from env var; **fails fast at boot if Telegram token or OpenAI key missing.**
</phase_requirements>

## Summary

This phase wires three well-documented, first-party pieces together: `python-telegram-bot` 22.7 (the async polling loop + handler dispatch), the official `openai` 2.41.1 SDK (`AsyncOpenAI.chat.completions.create`), and a fail-fast environment-variable config layer. There is no novel technical risk here — every component has an official canonical pattern, both library versions are confirmed current on PyPI (latest as of 2026-06-12), and the architecture is stateless (PTB tracks the `getUpdates` offset internally; the bot stores nothing per user). The single most important *scoping* fact is that PROJECT.md and PRD §11 lock in a **direct OpenAI call with no provider-abstraction layer** — this overrides the adapter/factory pattern that appears in the project-level `STACK.md` and the stale `CLAUDE.md` stack block. For Phase 1, do not build a Protocol/factory and do not install `anthropic`.

The whole bot is intentionally small: a thin `main.py` composition root, a `config.py` that is the only reader of `os.environ` (validates at boot, fails fast with a clear message if a required var is missing), a `handlers.py` with `/start`, `/help`, and one text handler, and a tiny `openai_client.py` (or inline function) that performs the one-shot completion. Everything is `async` end-to-end (PTB handlers are coroutines; the OpenAI call uses `AsyncOpenAI` + `await`) so the codebase is consistent with the concurrency work that lands in Phase 2 — Phase 1 should write async-correct code even though it does not yet enable `concurrent_updates` or harden errors.

Three things must be gotten right at v1 even though most hardening is deferred: (1) **fail-fast config** — read and validate every required env var once at boot and refuse to start otherwise (this is an explicit Phase 1 success criterion); (2) **secrets via environment only** — `.env` gitignored from the first commit, `.env.example` with blank values, never hardcode a token/key; (3) **async correctness** — never call a blocking SDK method inside an async handler. The 4096-char Telegram limit, OpenAI error/timeout robustness, and concurrency are *acknowledged but deferred* (D-04 / Phase 2) — the plan should note them as known limitations, not solve them.

**Primary recommendation:** Build five small modules under a `bot/` package — `config.py` (fail-fast env settings), `openai_client.py` (direct `AsyncOpenAI` one-shot call), `handlers.py` (`/start`, `/help`, async text handler), `prompts.py` (system prompt + command copy), `main.py` (composition root: build settings → build `AsyncOpenAI` client → `ApplicationBuilder().token(...).build()` → register handlers → `run_polling()`). Use `python-telegram-bot==22.7`, `openai==2.41.1`, `python-dotenv` for local `.env` loading. No adapter, no factory, no `anthropic`, no Docker/CI (later phases).

## Architectural Responsibility Map

This bot is a single-process application — there is no browser/CDN/database tier. "Tier" here maps to the in-process modules and the two external services.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Receive user text via long polling | Telegram service ↔ Polling loop (PTB `Application`) | — | PTB owns `getUpdates`, offset, retries, graceful shutdown — never hand-rolled |
| Route updates to the right handler | Message Router (PTB handlers) | — | `CommandHandler` / `MessageHandler` + `filters` dispatch; framework-owned |
| `/start`, `/help` responses | Command handlers (`handlers.py`) | Prompt/copy module (`prompts.py`) | Static text, no LLM call — cheap, instant, no token cost |
| Build the one-shot prompt | Text handler (`handlers.py`) | Prompt module (system prompt) | Rebuild `messages` per call → guarantees no memory (MSG-02) |
| Call OpenAI, get reply text | OpenAI client (`openai_client.py`) | OpenAI service (HTTPS) | The only module that imports `openai` and holds the API key |
| Send reply to chat | Text handler (`reply_text`) | Telegram service (`sendMessage`) | PTB convenience method on the inbound message |
| Load + validate config / secrets | Config (`config.py`) | OS environment | The only reader of `os.environ`; fail-fast at boot |
| Structured logging | Logging setup (`main.py` / `logging`) | stdout | stdlib `logging`; log chat IDs + errors, never message bodies |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12 | Implementation language | Locked in STACK.md; widest battle-tested wheel support; required ≥3.10 by PTB 22.7 |
| python-telegram-bot | 22.7 | Async Telegram Bot API wrapper + polling loop | De-facto standard async PTB; `Application.run_polling()` is exactly the locked delivery model; owns offset/retries/graceful shutdown `[VERIFIED: PyPI — latest version 22.7 confirmed via pip index]` |
| openai | 2.41.1 | OpenAI (ChatGPT) SDK | Official first-party SDK; `AsyncOpenAI.chat.completions.create` integrates with PTB's asyncio loop `[VERIFIED: PyPI — latest version 2.41.1 confirmed via pip index]` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dotenv | >=1.0,<2 | Load `.env` in local dev | Local dev convenience only; reads `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`, `OPENAI_MODEL` from a `.env` file. In Docker (Phase 3) these come from real env vars `[CITED: STACK.md]` |
| `logging` (stdlib) | builtin | Structured logging to stdout | Configure once at startup; INFO level; log chat IDs + errors, not message bodies `[CITED: ARCHITECTURE.md anti-pattern 5]` |
| `asyncio` (stdlib) | builtin | Async runtime | PTB and the OpenAI async client are both async; no extra concurrency lib needed `[ASSUMED]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| python-telegram-bot | aiogram 3.x | Equally valid; PTB chosen for `run_polling()` simplicity + user's prior familiarity (locked) |
| Direct OpenAI call | `LLMProvider` Protocol + factory (adapter) | **Explicitly rejected for v1** by PROJECT.md/PRD §11. Do NOT build it this phase, despite the project STACK.md/CLAUDE.md sketch |
| python-dotenv | Manual `os.environ` only | dotenv is a dev convenience; production reads real env vars either way. Fine to skip if planner prefers |

**Installation:**
```bash
pip install "python-telegram-bot==22.7" "openai==2.41.1" "python-dotenv>=1.0,<2"
```

`requirements.txt` (recommended — Phase 3 Docker will `pip install -r` it):
```
python-telegram-bot==22.7
openai==2.41.1
python-dotenv>=1.0,<2
```

**Version verification (run 2026-06-12):**
- `pip index versions python-telegram-bot` → latest **22.7** ✓ (matches locked stack)
- `pip index versions openai` → latest **2.41.1** ✓ (matches locked stack)

> Note: `anthropic` appears in the project-level STACK.md but is **out of scope for Phase 1** (direct-OpenAI decision). Do not add it.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| python-telegram-bot | PyPI | ~10 yrs (v22.7 current) | very high (millions/mo) | github.com/python-telegram-bot/python-telegram-bot | OK | Approved — official, verified via official docs + PyPI |
| openai | PyPI | est. since 2020 (v2.41.1 current) | very high | github.com/openai/openai-python | OK | Approved — official first-party SDK, verified via GitHub + PyPI |
| python-dotenv | PyPI | mature, widely used | very high | github.com/theskumar/python-dotenv | OK | Approved — long-established standard |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

> Note: `gsd-tools` is not on PATH in this environment and all configured search MCP providers (brave/exa/firecrawl/tavily/ref/perplexity/jina) are disabled in `.planning/config.json`, so the automated `package-legitimacy check` seam could not run. All three packages were instead verified directly: existence + latest version confirmed via `pip index versions` against PyPI, and each is the canonical official package referenced in its own official documentation (PTB docs, openai GitHub). These are among the most-downloaded packages in the Python ecosystem with no slopsquatting ambiguity. Confidence: HIGH.

## Architecture Patterns

### System Architecture Diagram

```
        Telegram user
            │  types text message
            ▼  (Telegram cloud stores it)
   ┌──────────────────────────────────────────────┐
   │  Telegram Bot API (cloud)                      │
   │   getUpdates  ◄── long-poll (pull)             │
   │   sendMessage ──► reply (push)                 │
   └──────┬───────────────────────────▲────────────┘
          │ Update                     │ reply text
          ▼                            │
   ┌──────────────────────────────────┴────────────┐
   │  Bot Process (single async event loop)         │
   │                                                │
   │  Application.run_polling()  ── owns the loop   │
   │          │                                     │
   │          ▼  dispatch by handler                │
   │   ┌──────────────┐   ┌──────────────────────┐  │
   │   │ /start /help │   │ text handler (async) │  │
   │   │ (static copy)│   │  update.message.text │  │
   │   └──────────────┘   └──────────┬───────────┘  │
   │                                 │ build messages│
   │   ┌──────────────┐              ▼  [sys,user]   │
   │   │ config.py    │──► settings  ┌─────────────┐ │
   │   │ (env, boot)  │   (key,model)│ openai_client│ │
   │   └──────────────┘              │ (AsyncOpenAI)│ │
   │                                 └──────┬──────┘ │
   └────────────────────────────────────────┼───────┘
                                             │ HTTPS await
                                             ▼
                              ┌───────────────────────────┐
                              │ OpenAI Chat Completions API │
                              │ model = OPENAI_MODEL        │
                              └───────────────────────────┘
```

Data flow for the core use case: user text → `getUpdates` (PTB) → text handler extracts `update.message.text` → builds a fresh `[system, user]` message list → `await client.chat.completions.create(...)` → `resp.choices[0].message.content` → `await update.message.reply_text(reply)` → `sendMessage` → user. No state is stored between messages.

### Recommended Project Structure
```
telegram_bot_ai/
├── bot/
│   ├── __init__.py
│   ├── __main__.py        # enables `python -m bot` -> calls main()
│   ├── main.py            # composition root: settings -> client -> Application -> handlers -> run_polling()
│   ├── config.py          # ONLY reader of os.environ; Settings dataclass; fail-fast validation at boot
│   ├── openai_client.py   # direct AsyncOpenAI one-shot call; the only module importing `openai`
│   ├── handlers.py        # start(), help_cmd(), handle_text() — async PTB handlers
│   └── prompts.py         # SYSTEM_PROMPT, START_TEXT, HELP_TEXT (copy lives in one place)
├── .env.example           # documents required vars; blank values; committed
├── .gitignore             # MUST include .env from commit #1
├── requirements.txt
└── README.md              # how to run locally (python -m bot)
```

**Why this layout:** `config.py` as the single env reader means missing secrets fail loudly at startup, not mid-request (Phase 1 success criterion). `main.py` is thin — it only wires components, so it stays trivially correct. `openai_client.py` isolates the one SDK that touches the API key. `prompts.py` centralizes all user-facing copy (D-01..D-05) so wording changes touch one file. This is flat-not-layered: no services/repositories/DTOs for a one-shot bot. **No `llm/` package, no `base.py`/`factory.py`** — that adapter structure is explicitly out of scope (direct-call decision).

### Pattern 1: Fail-fast config at boot
**What:** Read and validate every required env var once at startup into a typed `Settings` object; raise (or `sys.exit(1)` with a clear log) if any required var is missing or blank. Optional vars get documented defaults (`OPENAI_MODEL` → `gpt-4o-mini`).
**When to use:** Always — it is an explicit Phase 1 success criterion ("fails fast at boot if token/key missing").
**Example:**
```python
# bot/config.py
import os
from dataclasses import dataclass

class ConfigError(RuntimeError):
    pass

@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    openai_api_key: str
    openai_model: str

def load_settings() -> Settings:
    missing = [k for k in ("TELEGRAM_BOT_TOKEN", "OPENAI_API_KEY") if not os.environ.get(k)]
    if missing:
        raise ConfigError(f"Missing required environment variable(s): {', '.join(missing)}")
    return Settings(
        telegram_bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        openai_api_key=os.environ["OPENAI_API_KEY"],
        openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
    )
```
`main.py` calls `load_settings()` first thing; a missing var crashes before the Application is built, with a message that names the missing key.

### Pattern 2: Framework-owned polling loop (PTB 22.x)
**What:** Let `Application.run_polling()` own the `getUpdates` loop, offset bookkeeping, retries, and graceful shutdown. Register handlers on the `Application`.
**When to use:** Always for polling bots — never hand-roll `getUpdates`.
**Example:**
```python
# Source: https://docs.python-telegram-bot.org/en/v22.7/  (echobot example, v22)
from telegram import Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

app = ApplicationBuilder().token(settings.telegram_bot_token).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_cmd))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.run_polling(allowed_updates=Update.ALL_TYPES)  # blocking; owns SIGINT/SIGTERM shutdown
```
`[VERIFIED: docs.python-telegram-bot.org v22.7 + official echobot example]`

### Pattern 3: Async handler with a one-shot OpenAI call
**What:** PTB handlers are coroutines `async def h(update, context)`. The OpenAI call uses `AsyncOpenAI` + `await` so the event loop is never blocked.
**When to use:** The text handler (MSG-01→MSG-03 + LLM-01).
**Example:**
```python
# bot/handlers.py
from telegram import Update
from telegram.ext import ContextTypes

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_text = update.message.text
    reply = await context.bot_data["complete"](user_text)   # injected from main.py
    await update.message.reply_text(reply)
```
Passing the OpenAI call in via `application.bot_data` (a dict PTB provides) keeps `handlers.py` free of module-level globals and SDK imports.

### Anti-Patterns to Avoid
- **Hand-rolling the `getUpdates` loop:** off-by-one offset bugs drop/duplicate messages. Use `run_polling()`.
- **Building a provider adapter/factory/Protocol this phase:** explicitly rejected by the direct-OpenAI decision. Call `openai` directly.
- **Blocking SDK call inside an async handler:** using the sync `OpenAI` client (not `AsyncOpenAI`) inside `async def` stalls the whole event loop. Always `await` the async client.
- **Reading `os.environ` in multiple modules:** scattered reads make missing-var failures inconsistent. One `config.py` reads everything once.
- **Hardcoding the model or copy in the handler:** model comes from `OPENAI_MODEL`; copy lives in `prompts.py`.
- **Logging full prompts/replies at INFO:** public bot = logging strangers' content. Log chat id + status only.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Long-poll `getUpdates` loop, offset tracking, retries, graceful shutdown | A `while True` HTTP loop | `Application.run_polling()` | Offset/backoff/SIGTERM handling is fiddly and a classic bug source |
| Telegram API HTTP calls (`sendMessage`, etc.) | Raw `httpx`/`requests` to api.telegram.org | PTB `update.message.reply_text()` | PTB handles formatting, retries, connection pooling |
| OpenAI HTTP, auth, retry, JSON parsing | Raw HTTP to api.openai.com | `openai` SDK `AsyncOpenAI` | Official SDK handles auth headers, request IDs, typed responses, built-in retries |
| Env-var parsing/validation framework | A config DSL or pydantic-settings | A small dataclass + `os.environ` reads | ~3 vars; a dataclass is plenty (pydantic is overkill here) |
| Command argument parsing | A custom `/command` parser | PTB `CommandHandler` | PTB already splits commands from text via `filters` |

**Key insight:** For Phase 1 essentially everything hard is already owned by PTB and the OpenAI SDK. The only code you actually write is glue: read config, build one message list, make one awaited call, reply. Resist adding structure (adapters, settings frameworks, retry libraries) the locked scope rejects or defers.

## Common Pitfalls

### Pitfall 1: Config that fails late instead of at boot
**What goes wrong:** Bot starts fine with a missing `OPENAI_API_KEY` and only errors on the first user message — wasting a deploy cycle and looking like a runtime bug.
**Why it happens:** Reading env vars lazily, scattered through handlers, instead of validating once at startup.
**How to avoid:** `load_settings()` (Pattern 1) is the first call in `main()`; raise `ConfigError` naming the missing var(s) before the Application is built. This is a Phase 1 success criterion, not optional.
**Warning signs:** Bot boots green but first message returns an auth error; `KeyError: 'OPENAI_API_KEY'` deep in a handler traceback.

### Pitfall 2: Secrets leaked into git
**What goes wrong:** `TELEGRAM_BOT_TOKEN` / `OPENAI_API_KEY` committed in a `.env`, hardcoded in source, or printed in logs. Public-repo key leaks get scraped within minutes.
**Why it happens:** "I'll move it to env later"; `.env` not gitignored from the start.
**How to avoid:** `.env` in `.gitignore` from commit #1; ship `.env.example` with blank values; never hardcode. If a key ever touches git history, rotate it (BotFather / OpenAI dashboard) — removing the commit is not enough.
**Warning signs:** `git status` shows `.env` tracked; `git log -p` reveals a token; GitHub secret-scanning alert.

### Pitfall 3: Blocking the event loop with a sync OpenAI call
**What goes wrong:** Using the synchronous `OpenAI` client inside an `async def` handler blocks the entire event loop — including the poller — for the full 5–30s of the LLM call. Even single-user testing can feel laggy; under any concurrency the bot appears dead.
**Why it happens:** Copy-pasting a sync `client.chat.completions.create(...)` example into an async handler without `await` / `AsyncOpenAI`.
**How to avoid:** Use `AsyncOpenAI` and `await` the call. Write async-correct code now even though `concurrent_updates` and full error handling are Phase 2 — the async shape must be right from the start so Phase 2 only flips a flag.
**Warning signs:** `RuntimeWarning: coroutine ... was never awaited`; bot stops responding while one request is in flight; type checker flags a coroutine used as a value.

### Pitfall 4 (DEFERRED — document, don't fix): 4096-char reply limit
**What goes wrong:** Telegram `sendMessage` rejects text over 4096 UTF-8 chars with a 400; the user gets nothing on the longest (most useful) answers.
**Why it happens:** Short test prompts never hit the limit.
**Phase 1 stance:** **Accepted known limitation per D-04** (no `max_tokens` cap, no splitting in v1). The plan should note it as a documented v1 limitation, not solve it. Reply splitting is v2 (UX-02).

### Pitfall 5 (DEFERRED — Phase 2): No OpenAI error/timeout handling
**What goes wrong:** OpenAI calls fail (429, 5xx, hangs). Without a timeout a stuck call wedges a handler; without a friendly fallback the user gets silence.
**Phase 1 stance:** Full retry/typed-error handling is **Phase 2 (REL-01)**. *However*, the SDK's default read timeout is 600s, so for hygiene the plan may set a modest client-level timeout (`AsyncOpenAI(timeout=...)`, the PRD references `OPENAI_REQUEST_TIMEOUT` default 60) and let any exception propagate for now. Do **not** build retry/backoff logic this phase — that's Phase 2.

## Code Examples

Verified patterns from official sources.

### 1. Composition root (`main.py`)
```python
# bot/main.py
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from openai import AsyncOpenAI
from .config import load_settings
from .handlers import start, help_cmd, handle_text
from . import openai_client

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = load_settings()  # fail-fast: raises before anything else if a required var is missing

    client = AsyncOpenAI(api_key=settings.openai_api_key)  # optionally timeout=settings.openai_timeout

    app = ApplicationBuilder().token(settings.telegram_bot_token).build()
    # inject the bound completion function so handlers stay free of SDK imports
    app.bot_data["complete"] = lambda text: openai_client.complete(client, settings.openai_model, text)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
```

### 2. Direct one-shot OpenAI call (`openai_client.py`) — no memory
```python
# bot/openai_client.py
# Source: https://github.com/openai/openai-python  (AsyncOpenAI + chat.completions.create)
from openai import AsyncOpenAI
from .prompts import SYSTEM_PROMPT

async def complete(client: AsyncOpenAI, model: str, user_text: str) -> str:
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},   # D-01, D-04, D-05 live here
            {"role": "user", "content": user_text},          # fresh each call => no history (MSG-02)
        ],
    )
    return resp.choices[0].message.content or ""
```
Rebuilding `messages` on every call — with only the system prompt and the current user message — is what makes each reply a one-shot prompt with no memory (MSG-02). `[VERIFIED: github.com/openai/openai-python — AsyncOpenAI.chat.completions.create signature]`

### 3. Handlers (`handlers.py`)
```python
# bot/handlers.py
from telegram import Update
from telegram.ext import ContextTypes
from .prompts import START_TEXT, HELP_TEXT

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(START_TEXT)   # CMD-01, static (no LLM call, no token cost)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT)    # CMD-02, static

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_text = update.message.text                       # MSG-01
    reply = await context.bot_data["complete"](user_text) # MSG-02 + LLM-01
    await update.message.reply_text(reply)                # MSG-03
```
`[VERIFIED: docs.python-telegram-bot.org v22.7 echobot — async handler signature (update, context: ContextTypes.DEFAULT_TYPE)]`

### 4. Prompt + copy (`prompts.py`) — Claude's discretion (D-01..D-05)
```python
# bot/prompts.py
SYSTEM_PROMPT = (
    "You are a helpful, friendly, concise assistant. "          # D-01 minimal persona
    "Keep answers reasonably brief unless the user asks for detail. "  # D-04 soft-nudge concise
    "Always reply in the same language the user writes in."      # D-05 mirror language
)
START_TEXT = "Hi! Send me any message and I'll reply with an AI-generated answer. Type /help for more."  # D-02
HELP_TEXT = (
    "I answer any text message you send using AI, one message at a time. "
    "I don't remember previous messages yet — each question is answered on its own."  # D-03
)
```

### 5. `__main__.py` to enable `python -m bot`
```python
# bot/__main__.py
from .main import main
main()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| PTB v13 sync `Updater`/`Dispatcher`, decorator handlers | PTB v20+ async `Application` + `ApplicationBuilder` + `run_polling()` | v20 (2023) | All handlers are `async def`; the v21 sync examples in the project ARCHITECTURE.md must be treated as async in 22.x `[VERIFIED: docs v22.7]` |
| openai v0.x `openai.ChatCompletion.create()` module-level | openai v1/v2 client-based `OpenAI()` / `AsyncOpenAI().chat.completions.create()` | v1 (late 2023), v2 (2025) | Module-level `openai.ChatCompletion` is removed; use a client instance `[VERIFIED: github.com/openai/openai-python]` |

**Deprecated/outdated:**
- `openai.ChatCompletion.create(...)` (pre-v1 module API) — removed; use `AsyncOpenAI().chat.completions.create(...)`.
- PTB `Updater(token).dispatcher` decorator style (v13) — replaced by `ApplicationBuilder` in v20+.
- The `LLMProvider` Protocol/factory adapter in the project STACK.md/CLAUDE.md — not deprecated generally, but **out of scope for this project's v1** per the direct-OpenAI decision.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `gpt-4o-mini` is a valid, currently-available OpenAI model name (default) | Standard Stack / config | LOW — locked by PROJECT.md/PRD as the project default; if renamed/retired, `OPENAI_MODEL` env var lets the user override without code change. Could not live-verify model availability (no OpenAI API access this session). |
| A2 | `python-dotenv` is the chosen `.env` loader (vs. manual env) | Supporting stack | LOW — Claude's discretion (D); either works. Trivially swappable. |
| A3 | Injecting the completion fn via `application.bot_data` is the cleanest wiring | Code Examples §1/§3 | LOW — a closure, module global, or `context.application` access are equivalent; pure style choice for the planner. |
| A4 | A modest client-level timeout is acceptable hygiene in Phase 1 | Pitfall 5 | LOW — does not constitute the deferred Phase 2 error handling; just avoids the 600s default hang. Planner may omit and defer entirely to Phase 2. |
| A5 | stdlib `asyncio`/`logging` suffice; no extra runtime deps | Supporting stack | LOW — standard for this bot class. |

**Note:** No compliance/retention/security-standard assumptions are made here — the only genuinely unverifiable item is A1 (model name), which is a locked project default with an env-var escape hatch.

## Open Questions

1. **Exact `temperature` / sampling params for the OpenAI call**
   - What we know: Claude's discretion (CONTEXT.md). A general assistant typically uses the API default (often ~1.0) or a slightly lower value (~0.7) for steadier answers.
   - What's unclear: No user preference stated.
   - Recommendation: Omit `temperature` (use the API default) for v1 simplicity; it's trivially added later. Do not over-tune.

2. **Whether to set a client-level OpenAI timeout in Phase 1**
   - What we know: PRD §7 documents `OPENAI_REQUEST_TIMEOUT` default 60; full timeout/retry handling is Phase 2 (REL-01). SDK default read timeout is 600s.
   - What's unclear: Whether to introduce the timeout now or defer entirely.
   - Recommendation: Setting `AsyncOpenAI(timeout=60)` is a one-liner that avoids a 600s hang and matches the PRD config table; acceptable in Phase 1. Building retry/backoff is **not** — defer to Phase 2.

3. **Local run mechanism — `python -m bot` vs. a `main.py` script**
   - What we know: Claude's discretion. `python -m bot` (package + `__main__.py`) matches the Phase 3 Docker `CMD ["python", "-m", "bot"]` pattern in STACK.md.
   - Recommendation: Use the `bot/` package + `__main__.py` so local and (future) container entrypoints are identical.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | Whole bot | Assumed ✓ | user has 3.12/3.14 (per STACK.md) | — |
| pip | Install deps | ✓ | present (used to verify versions) | — |
| python-telegram-bot 22.7 | Polling/handlers | Installable ✓ | 22.7 on PyPI | — |
| openai 2.41.1 | LLM call | Installable ✓ | 2.41.1 on PyPI | — |
| Telegram bot token | MSG-01, run | User-supplied (runtime) | — | None — bot cannot run without it (fail-fast catches absence) |
| OpenAI API key | LLM-01, run | User-supplied (runtime) | — | None — bot cannot answer without it (fail-fast catches absence) |
| Internet egress to api.telegram.org + api.openai.com | Both services | Assumed ✓ | — | None |

**Missing dependencies with no fallback:** Telegram token and OpenAI key are runtime secrets the user provides; their absence is *handled* by the fail-fast config (Pattern 1), which is the correct behavior, not a blocker to building.
**Missing dependencies with fallback:** None.

> Note: a separate BotFather token for local dev (vs. production) is recommended (CONTEXT.md specifics) to avoid future 409 conflicts, but the 409/single-poller concern itself is Phase 2 (REL-03).

## Validation Architecture

> `workflow.nyquist_validation` is `true` in `.planning/config.json` → this section is included. Note: the project's **automated test suite is formally Phase 4 (QA-01/QA-02)**. Phase 1 therefore has minimal-to-no automated test infrastructure, and most Phase 1 validation is **manual smoke testing against a live dev bot** plus a couple of cheap pure-function unit checks the planner may add as Wave 0.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest` (project standard per PRD §13 / QA-01) — **not yet installed in Phase 1** |
| Config file | none yet — see Wave 0 (formal suite is Phase 4) |
| Quick run command | `pytest -q` (once a `tests/` dir + dev dep exist) |
| Full suite command | `pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LLM-01 / config | Missing `TELEGRAM_BOT_TOKEN` or `OPENAI_API_KEY` raises `ConfigError` at boot; `OPENAI_MODEL` defaults to `gpt-4o-mini` | unit (pure) | `pytest tests/test_config.py -x` | ❌ Wave 0 |
| MSG-02 | One-shot `messages` list is `[system, user]` only (no history) — verify the builder/`complete` constructs exactly two messages with a mocked client | unit (mock `AsyncOpenAI`) | `pytest tests/test_openai_client.py -x` | ❌ Wave 0 |
| MSG-01/MSG-03 | Bot receives a text message and replies in the same chat | manual smoke | send a message to the dev bot via Telegram; observe reply | manual-only |
| CMD-01 | `/start` returns the welcome copy | manual smoke (or unit on the static text) | send `/start`; observe | manual-only |
| CMD-02 | `/help` returns usage copy | manual smoke | send `/help`; observe | manual-only |
| LLM-01 (live) | Reply is OpenAI-generated, model from env | manual smoke | set `OPENAI_MODEL`, send message, confirm sensible reply | manual-only |

**Manual-only justification:** MSG-01/MSG-03 and the command round-trips require a live Telegram connection and a live OpenAI call; they are not meaningfully unit-testable without mocking the entire transport, which is the Phase 4 integration-test concern. Phase 1 validates these by running the bot locally against a dev BotFather token (the canonical "walking skeleton" demo).

### Sampling Rate
- **Per task commit:** `pytest -q` (the two pure unit tests, if Wave 0 adds them) — sub-second.
- **Per wave merge:** `pytest` + one manual smoke run against the dev bot.
- **Phase gate:** Manual end-to-end demo — send a message, get an AI reply; `/start` and `/help` work; deleting a required env var crashes at boot.

### Wave 0 Gaps
- [ ] `tests/test_config.py` — covers config fail-fast (missing var → `ConfigError`) and `OPENAI_MODEL` default. *(Optional in Phase 1; formal suite is Phase 4 — but config fail-fast is a Phase 1 success criterion and is cheap to unit-test.)*
- [ ] `tests/test_openai_client.py` — covers MSG-02 one-shot message construction with a mocked `AsyncOpenAI` client.
- [ ] Framework install: `pip install pytest` (dev-only; add to a `requirements-dev.txt` so it doesn't bloat the runtime image).
- [ ] `tests/conftest.py` — fixture providing a fake env / mocked client (only if the two tests above are added).

*If the planner chooses to keep Phase 1 a pure walking-skeleton with zero automated tests (deferring all of QA to Phase 4), that is consistent with the roadmap — in that case Wave 0 is "None" and validation is the manual phase-gate demo above. Recommended: add the two cheap pure-function tests, since config fail-fast is a Phase 1 acceptance criterion.*

## Security Domain

> `workflow.security_enforcement` is `true`, `security_asvs_level` 1 → this section is included.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No user accounts; Telegram identifies users. Bot auth is the bot token (a secret, see V6/V14). |
| V3 Session Management | no | Stateless; no sessions. |
| V4 Access Control | no (v1) | Public bot by design (PROJECT.md). No per-user authz in v1. |
| V5 Input Validation | partial | User text is passed to OpenAI as a chat message — no injection into a shell/SQL/eval. The only validation is "is it text" (PTB `filters.TEXT`). Prompt-injection of the LLM is possible but low-impact for a stateless general assistant (no tools, no data access). |
| V6 Cryptography | no (don't hand-roll) | No crypto implemented. TLS to Telegram/OpenAI is handled by the SDKs' `httpx`. Never hand-roll. |
| V7 Error Handling & Logging | partial | Log metadata (chat id, status), **never message bodies or secrets**. Don't print tokens/keys. |
| V8 Data Protection | partial | User messages are sent to OpenAI (third party) — inherent to the product. Don't persist messages (stateless v1 stores nothing). |
| V14 Configuration | **yes** | **Secrets via environment only**; `.env` gitignored; never baked into source/image. This is the primary security control for Phase 1. |

### Known Threat Patterns for {Python async Telegram→OpenAI bot, polling}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Telegram bot token leaked (git/source/logs) → bot hijack | Spoofing / Elevation | Env-only secrets; `.gitignore` `.env` from commit #1; rotate via BotFather if leaked |
| OpenAI API key leaked → financial theft (scraped within minutes on public repos) | Information Disclosure | Same: env-only, gitignored; rotate via OpenAI dashboard if leaked; (billing cap is the operational backstop, deferred) |
| Logging strangers' message content | Information Disclosure (privacy) | Log chat id + status/latency only; gate content behind DEBUG |
| Prompt injection of the LLM by a user | Tampering | LOW impact in v1 — no tools, no memory, no data access; the model can only produce text. No mitigation needed beyond the fixed system prompt. Revisit if tools/memory are added (v2). |
| Unbounded cost from public abuse | (Availability / financial) | **Accepted v1 risk** (PROJECT.md). Operational mitigation = OpenAI dashboard billing cap (deferred, pre-launch). Not a Phase 1 code task. |
| Denial via flooding the bot | Denial of Service | Out of scope v1 (no rate limiting — COST-02, deferred). |

**Security bottom line for Phase 1:** the entire security surface that this phase must actively get right is **V14 Configuration / secrets hygiene** — env-only secrets, `.env` gitignored from the first commit, `.env.example` with blank values, no secrets in logs. Everything else is either handled by the SDKs (TLS) or deliberately deferred (access control, rate limiting, billing cap).

## Sources

### Primary (HIGH confidence)
- https://docs.python-telegram-bot.org/en/v22.7/telegram.ext.applicationbuilder.html — `ApplicationBuilder` API, `token()`, `concurrent_updates()`, `run_polling()` (verified this session)
- https://github.com/python-telegram-bot/python-telegram-bot (examples/echobot.py) — canonical v22 async handler signatures + handler registration (verified this session)
- https://github.com/openai/openai-python — `AsyncOpenAI` instantiation, client/per-request timeout, `chat.completions.create` async usage (verified this session)
- PyPI via `pip index versions` — confirmed `python-telegram-bot` latest 22.7 and `openai` latest 2.41.1 (verified this session, 2026-06-12)

### Secondary (MEDIUM confidence)
- WebSearch on OpenAI SDK v2 timeout behavior — confirmed default `Timeout(connect=5, read=600, write=600, pool=600)` and per-request `timeout=` override (community + GitHub issues, cross-checked against the official repo)

### Tertiary (project artifacts, treated as locked input)
- `.planning/PROJECT.md`, `PRD.md` (§5,6,7,11), `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md` — locked decisions, requirement IDs, config reference
- `.planning/research/{STACK,ARCHITECTURE,PITFALLS,SUMMARY}.md` — project-level research (note: their adapter/factory recommendation is superseded by the direct-OpenAI decision for v1)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — both core versions confirmed current on PyPI; both are official first-party packages
- Architecture: HIGH — PTB 22.x and openai 2.x canonical patterns verified against official docs/repo this session; layout is a deliberately minimal, standard composition-root shape
- Pitfalls: HIGH — config fail-fast, secrets hygiene, and async-correctness are well-established and cross-checked against the project's own PITFALLS.md and official docs
- Model name (`gpt-4o-mini`): MEDIUM — locked project default, not live-verified against the OpenAI model list this session (A1); env-var override mitigates risk

**Research date:** 2026-06-12
**Valid until:** ~2026-07-12 (30 days — stable stack; re-check PTB/openai versions if planning slips, both are actively released)
