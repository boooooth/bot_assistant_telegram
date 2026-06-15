# Phase 3: Containerize & Run 24/7 - Pattern Map

**Mapped:** 2026-06-14
**Files analyzed:** 5 (Dockerfile, compose.yaml, requirements.txt, .dockerignore [new], .env.example)
**Analogs found:** 4 / 5 (all existing files read directly; .dockerignore has no analog — use Python convention)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `Dockerfile` | config | build-time | existing `Dockerfile` (self) | exact — modify in place |
| `compose.yaml` | config | request-response | existing `compose.yaml` (self) | exact — modify in place |
| `requirements.txt` | config | N/A | existing `requirements.txt` (self) | exact — modify in place |
| `.dockerignore` | config | build-time | none in codebase | no analog — use Python project convention |
| `.env.example` | config | N/A | existing `.env.example` (self) | exact — modify in place |

---

## Pattern Assignments

### `Dockerfile` (config, build-time)

**Analog:** `Dockerfile` (current state, self)

**Current state** (lines 1-13):
```dockerfile
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ bot/

CMD ["python", "-m", "bot"]
```

**Change required — add non-root user (D-08):**

Insert after `WORKDIR /app`, before the first `COPY`:
```dockerfile
# Run as non-root for security (D-08)
RUN addgroup --system botuser && adduser --system --ingroup botuser botuser

WORKDIR /app
```
Then add `USER botuser` after the final `COPY`, before `CMD`:
```dockerfile
USER botuser

CMD ["python", "-m", "bot"]
```

**Full target state after modification:**
```dockerfile
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

RUN addgroup --system botuser && adduser --system --ingroup botuser botuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ bot/

USER botuser

CMD ["python", "-m", "bot"]
```

**Notes:**
- Do NOT add a `HEALTHCHECK` instruction (D-10 — deferred).
- `addgroup --system` / `adduser --system` are the `debian-slim` / `busybox`-compatible commands. UID/GID assigned automatically by the system; no explicit UID needed.
- `PYTHONUNBUFFERED=1` stays as-is — already set.
- Base image `python:3.12-slim` stays as-is — already correct.

---

### `compose.yaml` (config, request-response)

**Analog:** `compose.yaml` (current state, self)

**Current state** (lines 1-6):
```yaml
services:
  bot:
    image: ghcr.io/${GITHUB_REPOSITORY:-telegram-bot-ai}/bot:latest
    env_file: .env
    restart: unless-stopped
```

**Change required — add `build: .` (D-11):**

Add `build: .` alongside the existing `image:` key. With both keys present:
- `docker compose up --build` builds locally from source.
- `docker compose pull && docker compose up -d` pulls from GHCR (production / Phase 4 CI path).

**Full target state after modification:**
```yaml
services:
  bot:
    build: .
    image: ghcr.io/${GITHUB_REPOSITORY:-telegram-bot-ai}/bot:latest
    env_file: .env
    restart: unless-stopped
```

**Notes:**
- `env_file: .env` pattern is the established secret injection mechanism (DEP-03) — keep as-is.
- `restart: unless-stopped` is already present — keep as-is.
- No `ports:` needed — polling bot, no inbound connections.

---

### `requirements.txt` (config, N/A)

**Analog:** `requirements.txt` (current state, self)

**Current state** (lines 1-3):
```
python-telegram-bot==22.7
litellm
python-dotenv>=1.0,<2
```

**Change required — pin litellm (D-03):**

`litellm` is currently unpinned. Pin to the installed version discovered via `pip show litellm`:

```
python-telegram-bot==22.7
litellm==1.88.1
python-dotenv>=1.0,<2
```

**Notes:**
- Do NOT add an explicit `openai` pin — LiteLLM pulls it in as a transitive dep. Manual pin causes resolver conflicts (CLAUDE.md "What NOT to Use").
- Do NOT add an explicit `httpx` pin — same reason.
- `python-telegram-bot==22.7` is already pinned — keep as-is.

---

### `.dockerignore` (config, build-time)

**Analog:** None in codebase. Use Python project convention.

**New file — full content:**
```
# Version control
.git/
.gitignore

# Virtual environment
.venv/

# Tests
tests/
.pytest_cache/
.ruff_cache/

# Planning & docs
.planning/
*.md

# Secrets — never send to Docker daemon
.env

# Python cache
__pycache__/
*.pyc
*.pyo

# Editor / OS
.claude/
*.DS_Store
```

**Notes:**
- Excludes `.env` to prevent accidental bake-in of secrets (DEP-03).
- Excludes `.git/`, `.venv/`, `tests/`, `.planning/`, `*.md` per D-09.
- Keeps `requirements.txt` and `bot/` reachable — those are the only paths referenced in `COPY` instructions in `Dockerfile`.

---

### `.env.example` (config, N/A)

**Analog:** `.env.example` (current state, self)

**Current state** (read via shell):
```
# Copy to .env and fill in real values. .env is gitignored - never commit secrets.
# Required: Telegram Bot API token from BotFather.
TELEGRAM_BOT_TOKEN=
# Required: API key for whichever provider you use.
#   OpenAI   key from platform.openai.com
#   Anthropic  key from console.anthropic.com
OPENAI_API_KEY=
# Optional: model name passed to LiteLLM. Defaults to gpt-4o-mini if unset.
...
OPENAI_MODEL=
# Optional: comma-separated Telegram chat IDs allowed to use the bot.
ALLOWED_CHAT_IDS=
```

**Problem found:** `.env.example` still uses the OLD variable names `OPENAI_API_KEY` and `OPENAI_MODEL`. These were renamed to `LLM_API_KEY` and `LLM_MODEL` in the PR before Phase 3 (D-02). The code in `bot/config.py` already reads `LLM_API_KEY` / `LLM_MODEL` (confirmed at lines 12 and 57). `.env.example` was missed in that rename.

**Change required — rename env vars:**
```
# Copy to .env and fill in real values. .env is gitignored - never commit secrets.
# Required: Telegram Bot API token from BotFather.
TELEGRAM_BOT_TOKEN=
# Required: API key for whichever LLM provider you use.
#   OpenAI    → key from platform.openai.com
#   Anthropic → key from console.anthropic.com
LLM_API_KEY=
# Optional: model name passed to LiteLLM. Defaults to gpt-4o-mini if unset.
# Examples:
#   gpt-4o-mini                      (OpenAI)
#   gpt-4o                           (OpenAI)
#   claude-haiku-4-5-20251001        (Anthropic)
#   claude-sonnet-4-6                (Anthropic)
LLM_MODEL=
# Optional: comma-separated Telegram chat IDs allowed to use the bot. If unset, everyone is allowed.
ALLOWED_CHAT_IDS=
```

---

## Shared Patterns

### Secret injection pattern
**Source:** `compose.yaml` line 4 + `bot/config.py` lines 12, 39-45
**Apply to:** `compose.yaml`, `.env.example`, deployment runbook
```yaml
# compose.yaml — secrets come from .env file on the server, never baked into image
env_file: .env
```
```python
# bot/config.py — validated at boot, loud failure on missing vars
REQUIRED_VARS = ("TELEGRAM_BOT_TOKEN", "LLM_API_KEY")
missing = [
    name for name in REQUIRED_VARS if not (os.environ.get(name) or "").strip()
]
if missing:
    raise ConfigError(
        f"Missing required environment variable(s): {', '.join(missing)}"
    )
```

### Non-root user (Dockerfile convention)
**Source:** Debian-slim convention (no codebase analog — first time in this project)
**Apply to:** `Dockerfile`
```dockerfile
RUN addgroup --system botuser && adduser --system --ingroup botuser botuser
...
USER botuser
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `.dockerignore` | config | build-time | No existing `.dockerignore` in the repo. Use standard Python project convention (documented above in pattern assignment). |

---

## Pre-flight Finding

**`.env.example` uses stale variable names.** `OPENAI_API_KEY` and `OPENAI_MODEL` must be renamed to `LLM_API_KEY` and `LLM_MODEL` to match what `bot/config.py` actually reads. This is a correctness bug — a developer copying `.env.example` to `.env` would get a boot-time `ConfigError` because `LLM_API_KEY` would be unset. The planner must include this fix in the Phase 3 plan.

---

## Metadata

**Analog search scope:** Repository root + `bot/` directory
**Files read:** `Dockerfile`, `compose.yaml`, `requirements.txt`, `.env.example` (via shell), `bot/config.py`
**LiteLLM version confirmed:** 1.88.1 (via `pip show litellm` in active `.venv`)
**Pattern extraction date:** 2026-06-14
