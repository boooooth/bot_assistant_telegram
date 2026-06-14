# Project Research Summary

**Project:** Telegram AI Bot
**Domain:** Public Telegram bot fronting a one-shot LLM (general-purpose AI assistant, polling, Dockerized on a Linux VPS)
**Researched:** 2026-06-11
**Confidence:** HIGH

## Executive Summary

This is a public Telegram polling bot that proxies user text messages to an LLM and returns the reply — a well-understood, widely-built class of project. Research is unambiguous about the recommended stack: Python 3.12, `python-telegram-bot` 22.7 for the polling loop, the official `openai` and `anthropic` SDKs behind a thin hand-rolled adapter interface, Dockerized with `python:3.12-slim`, and deployed via GitHub Actions → GHCR → DigitalOcean droplet over SSH. All locked decisions in PROJECT.md are correct and consistent with expert practice. Nothing needs to be revisited before building.

The architecture is intentionally minimal: five modules plus an `llm/` package. The one structural non-negotiable is the `LLMProvider` Protocol + factory pattern — handlers must never import a concrete SDK directly; swapping providers must be a single env-var change. Config must be read once at boot and fail fast if missing. The polling loop must be fully async (PTB + `AsyncOpenAI`) with `concurrent_updates=True` so a slow LLM call for user A does not block users B and C.

The two highest-impact risks are cost and secrets. The bot is public with no rate limiting — a single bad actor or a shared link can spike the OpenAI bill in minutes. Setting a hard billing cap in the OpenAI dashboard costs zero code and must be done before the bot goes live. Secrets (Telegram token, OpenAI key) must never touch the image or git history; they are injected at runtime only. Both risks are fully preventable with known, cheap mitigations.

## Key Findings

### Recommended Stack

The stack is well-established, with official first-party SDKs for all external services and no exotic dependencies. Python 3.12 is the compatibility sweet spot — fully supported by PTB, openai, and anthropic with no edge cases. The entire bot fits in a single-stage `python:3.12-slim` Docker image. The GitHub Actions → GHCR → `appleboy/ssh-action` → `docker compose pull && up -d` pipeline is the canonical pattern for this class of deployment.

**Core technologies:**
- **Python 3.12**: Implementation language — dominant ecosystem for Telegram bots and LLM SDKs; 3.12 has widest battle-tested wheel support
- **python-telegram-bot 22.7**: Polling loop + handler dispatch — owns `getUpdates`, offset management, retries, and graceful SIGTERM shutdown; no hand-rolled loop needed
- **openai 2.41.1**: Default LLM provider SDK — `AsyncOpenAI` integrates cleanly with PTB's asyncio loop
- **anthropic 0.109.1**: Alternative provider SDK — `AsyncAnthropic` mirrors openai ergonomics; swap is one env-var change
- **python:3.12-slim**: Docker base — glibc compatibility, prebuilt wheels, ~40MB base, active security patches
- **GitHub Actions + GHCR + appleboy/ssh-action**: CI/CD — standard, well-documented pattern for GHCR push + SSH deploy

### Expected Features

The v1 MVP is deliberately minimal — a "lightweight" tier bot matching the locked scope. Every table-stakes item is achievable in a single build phase. The most technically subtle items are the typing-indicator keepalive (must be cancelled on completion or it sticks on forever) and long-reply chunking (must split on safe boundaries, not mid-entity, and count by encoded byte length near the 4096 limit).

**Must have (table stakes):**
- `/start` and `/help` commands — Telegram convention; bot looks dead without them
- Text message → LLM (one-shot) → reply — core value; locked
- Typing indicator with keepalive loop + cancel on completion — essential UX given 5–30s LLM latency
- Long-reply splitting at 4096-char limit — LLM frequently exceeds this; API rejects oversized `sendMessage` calls
- Graceful error reply on LLM/network failure — public bot hits these constantly; silence looks broken
- Safe output formatting (plain text or HTML with plain-text fallback) — raw LLM Markdown breaks Telegram MarkdownV2 constantly
- Non-text input guard ("text only" reply) — strangers send photos/stickers; must not crash

**Should have (post-validation):**
- Rate limiting / usage caps — first thing to add before any real traffic; cost risk materializes fast
- Conversation memory (multi-turn) — biggest quality jump; drives state/storage architecture
- Configurable persona / system prompt — cheap once adapter exists; add when a use-case niche emerges

**Defer (v2+):**
- Streaming replies — high complexity, conflicts with reply splitting, reintroduces formatting fragility
- Multimodal input (images, voice, files) — large surface, needs vision/transcription; out of scope
- Per-user model selection and inline settings — depends on state; only useful after memory exists
- Group-chat support — cost/abuse multiplier; wait until rate limiting exists

### Architecture Approach

The architecture is flat and explicit: a composition root (`main.py`) wires validated config → provider factory → PTB Application → handlers. The `llm/` sub-package is the only swap point in the system; everything outside it depends only on the `LLMProvider` Protocol. There is no application state in v1 — PTB manages the `getUpdates` offset internally; the bot is stateless per message. When memory is added post-v1, it slots in as a store the handler reads/writes before/after `complete()`, without touching the adapter or polling logic.

**Major components:**
1. **Config / Secrets (`config.py`)** — reads and validates all env vars at boot; fails fast with a clear log if any are missing; everything else receives a typed `Settings` object, never raw `os.environ`
2. **LLM Adapter (`bot/llm/`)** — `base.py` defines the `LLMProvider` Protocol; `openai_provider.py` and `anthropic_provider.py` implement it; `factory.py` selects by `LLM_PROVIDER` env var; handlers never import a concrete SDK
3. **Polling / Message Router (`main.py`, `handlers.py`)** — `Application.run_polling()` owns the loop; `MessageHandler` + `CommandHandler` dispatch to typed handlers; `concurrent_updates=True` enables parallel LLM calls
4. **Container + CI/CD (`Dockerfile`, `docker-compose.yml`, `.github/workflows/deploy.yml`)** — single-stage slim image, `restart: unless-stopped`, secrets injected at runtime via `env_file`, deploy stops old container before starting new one

### Critical Pitfalls

1. **Unbounded cost on public bot** — set a hard billing cap in the OpenAI dashboard before going live (zero code; converts "unbounded" to a chosen ceiling); use a small/cheap model (gpt-4o-mini class); clamp `max_tokens` in the adapter. Per-user throttling is explicitly deferred but the adapter/dispatch layer must leave a seam for it.

2. **409 Conflict — two pollers on the same token** — exactly one polling process per token, always. Use a separate BotFather token for local dev. The CI/CD deploy must stop the old container before starting the new one. Treat a 409 in logs as a critical alert, not noise.

3. **Slow LLM call blocks all users** — `concurrent_updates(True)` must be set from day one on a public bot. Use `AsyncOpenAI` + `await` throughout; never mix a synchronous SDK call into an async handler. Raise `connection_pool_size` to match the concurrency cap.

4. **Secrets leaked into git or Docker image** — `.env` in `.gitignore` from commit #1; never `COPY .env` in Dockerfile; secrets injected at runtime only via `env_file` in compose. If a key ever touches git history, rotate it immediately.

5. **No error/timeout handling on OpenAI calls** — always set an explicit request timeout (30–60s). Retry rate-limit and 5xx errors with exponential backoff + jitter. Do NOT retry `insufficient_quota` or auth errors. On final failure, send a friendly reply rather than silence.

## Implications for Roadmap

Based on combined research, the architecture's own suggested build order (config → adapter → polling + handlers → containerize → CI/CD) is the correct phase structure. Each phase produces a testable artifact with no unresolved unknowns carried forward.

### Phase 1: Foundation — Config, Secrets, Project Structure

**Rationale:** Every other component depends on validated config; secrets hygiene must be established before any secret is created. This phase has zero external API dependencies — nothing can go wrong except a misconfigured `.gitignore`, so catch that here.
**Delivers:** Repo with correct `.gitignore`, `.env.example`, `config.py` with fail-fast env-var validation, stdlib logging setup, `requirements.txt`, and basic Dockerfile skeleton.
**Addresses:** Settings object consumed by all subsequent phases.
**Avoids:** Secrets-in-git pitfall; missing-var failures discovered mid-request rather than at boot.

### Phase 2: LLM Adapter

**Rationale:** The adapter is the single riskiest custom piece (the swap design is project-defining) and the easiest to test standalone — `provider.complete("hello")` from a throwaway script, no Telegram needed. Proving the adapter in isolation means when the Telegram wiring is added, only one unknown remains.
**Delivers:** `bot/llm/base.py` (Protocol), `openai_provider.py` (async client, explicit timeout, typed error handling, retry policy, `max_tokens` clamp), `anthropic_provider.py` (same contract), `factory.py` (env-var select). OpenAI billing cap set as a configuration action (not code).
**Uses:** `openai 2.41.1` (`AsyncOpenAI`), `anthropic 0.109.1` (`AsyncAnthropic`)
**Avoids:** OpenAI error/timeout pitfall; unbounded cost (cheap model, max_tokens, billing cap); concrete provider imported in handler (anti-pattern).

### Phase 3: Telegram Bot — Polling, Handlers, UX Polish

**Rationale:** With a proven adapter, the Telegram wiring introduces only one unknown. This phase builds the full working bot: polling loop, message routing, typing indicator, reply chunking, graceful error messages, and non-text guard. Run locally against a dev bot token.
**Delivers:** `main.py` (`Application` + handler registration + `run_polling()` with `concurrent_updates=True`), `handlers.py` (`/start`, `/help`, text handler with typing keepalive + cancel, reply chunking at 4096 chars on safe boundaries, safe plain-text/HTML formatting with fallback, graceful error reply), non-text input guard.
**Implements:** All v1 table-stakes features.
**Avoids:** Sequential-update blocking (concurrent_updates=True from day one); typing-indicator stuck-on bug; 4096-char 400 errors; silence on errors.

### Phase 4: Containerize — Docker + Local Parity

**Rationale:** Containerize only after the bot runs cleanly on the host so a container failure is unambiguously a packaging issue, not a code issue. This phase also establishes the `restart: unless-stopped` policy for 24/7 uptime.
**Delivers:** Production-ready `Dockerfile` (`python:3.12-slim`, non-root user, `PYTHONUNBUFFERED=1`), `docker-compose.yml` (one service, `restart: unless-stopped`, `env_file: .env`), `.dockerignore`. Bot runs identically via `docker compose up` locally.
**Avoids:** Secrets-in-image pitfall; bot-down-after-reboot (restart policy).

### Phase 5: CI/CD — GitHub Actions Deploy Pipeline

**Rationale:** CI/CD is pure plumbing around an already-working, already-containerized bot. Build it last so there is something proven worth deploying. This phase also resolves the stop-old-before-new ordering (409 prevention).
**Delivers:** `.github/workflows/deploy.yml` — build + push to GHCR on push to `main`, SSH to server via `appleboy/ssh-action`, `docker compose pull && up -d`. GitHub encrypted secrets for SSH credentials. Server's `.env` holds app secrets (never in workflow).
**Avoids:** 409 Conflict from deploy overlap; secrets in CI logs.

### Phase Ordering Rationale

- Config first because every component consumes validated settings; fail-fast early prevents "works locally, dies on server" mystery failures.
- Adapter before the bot loop because it is the riskiest custom design (provider swap) and tests in complete isolation with no Telegram dependency.
- Polling after the adapter so the first time the real bot runs, the LLM path is already proven; only Telegram wiring is new.
- Containerize after the bot works on the host so container failures are unambiguously packaging issues.
- CI/CD last because it wraps a proven image; build it when there is something worth deploying.

### Research Flags

Phases with standard patterns (skip research-phase):
- **Phase 1 (Foundation):** Well-documented; `.gitignore`, `logging`, env-var validation are standard Python patterns with no ambiguity.
- **Phase 2 (LLM Adapter):** Official SDK docs are comprehensive; Protocol + factory pattern is standard Python; error handling sourced from OpenAI's own cookbook.
- **Phase 3 (Telegram Bot):** PTB official docs are thorough; typing keepalive and reply chunking are well-documented in community issues and official API references.
- **Phase 4 (Docker):** Standard single-stage Python slim image; no unusual base image or build steps.
- **Phase 5 (CI/CD):** GHCR + `appleboy/ssh-action` + `docker compose pull && up -d` is the canonical server deploy pattern with multiple verified examples.

No phase needs a `--research-phase` flag. All patterns are well-documented with high-confidence sources.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions confirmed against PyPI JSON APIs; official SDK docs; `python:3.12-slim` recommendation cross-checked across multiple independent sources |
| Features | HIGH (table stakes + anti-features), MEDIUM (differentiator complexity estimates) | Table stakes sourced from official Telegram Bot API; typing keepalive bug corroborated across multiple library issue trackers |
| Architecture | HIGH | Component boundaries and patterns sourced from official PTB docs; deploy pattern corroborated across multiple independent community guides |
| Pitfalls | HIGH | Critical pitfalls cross-checked against official docs (Telegram, OpenAI, PTB, Docker); operational patterns are well-established community knowledge |

**Overall confidence:** HIGH

### Gaps to Address

- **Typing-indicator keepalive implementation detail:** the exact PTB async pattern for a cancellable keepalive loop (`asyncio.create_task` + `task.cancel()`) should be prototyped early in Phase 3 — it is the most subtle v1 implementation detail.
- **Connection pool sizing:** `connection_pool_size` tuning for `concurrent_updates(True)` depends on the concurrency cap chosen; the right value should be validated empirically rather than set arbitrarily.
- **OpenAI billing cap value:** the cap amount is an operational decision (not a code decision) but must be set before Phase 5 goes live. Flag this as a required pre-deploy checklist item.

## Sources

### Primary (HIGH confidence)
- https://pypi.org/pypi/python-telegram-bot/json — version 22.7, Python 3.10+ requirement
- https://pypi.org/pypi/openai/json — version 2.41.1, Python 3.9–3.14
- https://pypi.org/pypi/anthropic/json — version 0.109.1, Python 3.9+
- https://docs.python-telegram-bot.org/ — `run_polling()`, `concurrent_updates`, `ApplicationBuilder`, signal handling
- https://core.telegram.org/bots/api — `sendMessage` 4096 limit, `sendChatAction`, getUpdates 409 constraint
- https://cookbook.openai.com/examples/how_to_handle_rate_limits — 429 handling, backoff, quota vs rate-limit distinction
- https://platform.openai.com/docs/guides/rate-limits — rate limit categories and retry guidance

### Secondary (MEDIUM confidence)
- https://pythonspeed.com/articles/base-image-python-docker-images/ — slim vs alpine vs distroless (Feb 2026)
- https://www.digitalocean.com/community/questions/github-action-to-deploy-docker-image-from-github-packages — GHCR + appleboy/ssh-action deploy pattern
- github.com/father-bot/chatgpt_telegram_bot — competitor feature set (memory, streaming, multimodal)
- github.com/DoctorLai/llm-telegram-bot — lightweight competitor (no memory, plain text)

---
*Research completed: 2026-06-11*
*Ready for roadmap: yes*
