# Walking Skeleton — Telegram AI Bot

**Phase:** 1
**Generated:** 2026-06-12

## Capability Proven End-to-End

A Telegram user sends a text message to the running bot and receives a real OpenAI (ChatGPT) generated reply in the same chat, with `/start` and `/help` returning static copy — all driven by a single `python -m bot` process that reads its secrets and model name from the environment and refuses to start if a required secret is missing.

This is the thinnest slice that exercises the entire pipeline: **project scaffold → env config load (fail-fast) → one real Telegram long-poll round-trip → one real OpenAI chat completion → reply back to the same chat.**

## Architectural Decisions

These decisions are a contract. Phases 2–4 build on them and MUST NOT renegotiate them without an explicit roadmap change.

| Decision | Choice | Rationale |
|---|---|---|
| Language / runtime | Python 3.12 (async end-to-end) | Locked in STACK.md; widest battle-tested wheel support; PTB 22.7 requires ≥3.10. Async shape set now so Phase 2 only flips `concurrent_updates`. |
| Telegram library | python-telegram-bot 22.7, long polling via `Application.run_polling()` | De-facto standard async PTB; framework owns `getUpdates`/offset/retries/graceful shutdown. Polling locked over webhook (no domain/TLS needed). |
| LLM access | **Direct** `openai` 2.41.1 `AsyncOpenAI.chat.completions.create` — NO provider abstraction | PRD §11 / PROJECT.md lock a direct OpenAI call for v1. The `LLMProvider` Protocol/factory + `anthropic` in CLAUDE.md/STACK.md is STALE and explicitly out of scope this phase. |
| Model selection | `OPENAI_MODEL` env var, default `gpt-4o-mini` | LLM-01. Switching model is a config change, not a code change. |
| State | Stateless — one-shot prompt rebuilt per message, no conversation memory | MSG-02. Bot stores nothing per user; PTB tracks the poll offset internally. |
| Config / secrets | Single `bot/config.py` reads `os.environ` once at boot into a frozen `Settings` dataclass; fail-fast `ConfigError` if a required var is missing | Phase 1 success criterion + Security V14. The only module that reads `os.environ`. |
| Secrets hygiene | Env-only; `.env` gitignored from commit #1; `.env.example` with blank values; never logged | Security V14 (primary control). Token/key leaks on public repos are scraped within minutes. |
| Local-run mechanism | `bot/` package + `bot/__main__.py` → `python -m bot`; local `.env` loaded via `python-dotenv` | Matches the future Phase 3 Docker entrypoint `CMD ["python", "-m", "bot"]` so local and container entrypoints are identical. |
| Directory layout | Flat `bot/` package (config, openai_client, handlers, prompts, main) — no services/repositories/DTOs, no `llm/` package | A one-shot bot needs glue, not layers. Centralizes the one SDK that holds the API key and the one module that reads env. |
| Logging | stdlib `logging` at INFO to stdout; log chat id + status only, never message bodies/secrets | Security V7 (privacy) + Phase 3 (Docker reads stdout). |

## Stack Touched in Phase 1

- [x] Project scaffold — `bot/` package, `requirements.txt`, `requirements-dev.txt`, `.gitignore`, `.env.example`, `README.md`
- [x] Routing — PTB handler dispatch: `CommandHandler("start")`, `CommandHandler("help")`, `MessageHandler(filters.TEXT & ~filters.COMMAND)`
- [x] "Database" (external state) — one real read (Telegram `getUpdates` long-poll) AND one real write (OpenAI `chat.completions.create` + Telegram `sendMessage` reply). No persistent DB exists in this product (stateless by design).
- [x] UI — the Telegram chat itself: a user sends a message and an interactive reply comes back, plus `/start` / `/help`.
- [x] Deployment — documented local full-stack run command: `python -m bot` with a populated `.env` against a dev BotFather token (the canonical walking-skeleton demo). Docker/droplet is Phase 3.

## Out of Scope (Deferred to Later Slices)

Explicit — prevents later phases from re-litigating Phase 1's minimalism.

- **Provider abstraction / `anthropic` / `LLMProvider` Protocol + factory** — out of scope v1 (direct OpenAI call only). Do NOT build it or install `anthropic` this phase.
- **Error / timeout handling, retries, friendly error replies, concurrency tuning (`concurrent_updates`), single-poller / 409 safety** — Phase 2 (REL-01, REL-02, REL-03).
- **Docker image, DigitalOcean droplet, 24/7 auto-restart, runtime secret injection** — Phase 3 (DEP-01..03).
- **CI/CD (GitHub Actions: ruff lint, mypy type-check, pytest, Docker build, deploy on push to `main`)** — Phase 4 (DEP-04, QA-01, QA-02). The formal automated test suite is Phase 4; Phase 1 adds only two cheap pure-function tests as Wave 0.
- **Cost controls** — `max_tokens` clamp, per-user rate limiting, global daily cap, OpenAI dashboard billing cap (v2 / operational; COST-*). No hard `max_tokens` cap in v1 (D-04).
- **Conversation memory, configurable persona/system prompt** — v2 (CONV-01, CONV-02). v1 uses a fixed minimal system prompt (D-01).
- **Long-reply splitting (>4096 chars), typing indicator, non-text input guard** — v2 (UX-02, UX-01, UX-03). The >4096-char reply failure is an accepted, documented v1 limitation (D-04).

## Subsequent Slice Plan

Each later phase adds a vertical slice on top of this skeleton without altering its architectural decisions:

- **Phase 2 (Reliability Hardening):** wrap the existing OpenAI call with timeout + friendly error reply (REL-01), enable concurrent update handling so one slow call doesn't block others (REL-02), and guarantee a single poller per token (REL-03).
- **Phase 3 (Containerize & Run 24/7):** package the same `python -m bot` entrypoint into a `python:3.12-slim` Docker image, run it on a DigitalOcean droplet with `restart: unless-stopped`, secrets injected at runtime via env (DEP-01..03).
- **Phase 4 (CI/CD Auto-Deploy):** GitHub Actions runs ruff + mypy + pytest + Docker build on every push/PR, and deploys the built image to the droplet on push to `main` (DEP-04, QA-01, QA-02).
