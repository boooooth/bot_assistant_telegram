---
phase: 01-working-ai-bot
plan: 02
status: complete
completed: 2026-06-12
---

# Summary: End-to-End Slice — Prompts, LLM Client, Handlers, Composition Root

## What Was Built

Complete walking-skeleton vertical slice: a user sends a text message and gets a real LLM reply back in the same chat, with `/start` and `/help` commands working.

- `bot/prompts.py` — `SYSTEM_PROMPT` (sarcastic persona), `START_TEXT`, `HELP_TEXT`
- `bot/openai_client.py` — `async def complete(model, api_key, user_text)` using `litellm.acompletion`; one-shot `[system, user]` messages list every call
- `bot/handlers.py` — `start`, `help_cmd`, `handle_text` PTB handlers; includes allowlist check via `ALLOWED_CHAT_IDS`
- `bot/main.py` — composition root: `load_settings` → inject `complete` into `bot_data` → register handlers → `run_polling`
- `bot/__main__.py` — `python -m bot` entrypoint
- `tests/test_openai_client.py` — MSG-02 one-shot test proving `[system, user]` only, no history
- `README.md` — local run guide with env var setup

## Deviations from Plan

- **LiteLLM instead of `AsyncOpenAI`** — plan specified `AsyncOpenAI.chat.completions.create`; LiteLLM's `litellm.acompletion` was used instead, enabling provider switching via `OPENAI_MODEL`.
- **Sarcastic persona** — plan called for a minimal helpful-assistant prompt; a sarcastic persona was added instead (shipped via PR #2).
- **User allowlist** — `ALLOWED_CHAT_IDS` allowlist added to `handle_text`, blocking unauthorized users (shipped via PR #3). Not in original plan scope.
- **CI/CD workflows added** — `.github/workflows/ci.yml` and `.github/workflows/deploy.yml` were created during this phase, pulling forward Phase 4 scope.

## Success Criteria Met

- Text message → LLM reply end-to-end (MSG-01, MSG-02, MSG-03, LLM-01)
- `/start` and `/help` return correct copy (CMD-01, CMD-02)
- One-shot behavior — no conversation history
- `pytest` passes
- Live smoke test approved (human checkpoint)
