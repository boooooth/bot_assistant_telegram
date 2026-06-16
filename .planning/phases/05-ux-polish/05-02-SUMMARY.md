---
phase: 05-ux-polish
plan: 02
subsystem: bot-handlers
tags: [ux, telegram, handlers, non-text-guard, message-filter]
requires:
  - bot/handlers.py
  - bot/main.py
  - bot/prompts.py
provides:
  - bot/prompts.py:NON_TEXT_REPLY
  - bot/handlers.py:handle_non_text
  - non-text guard registration in bot/main.py
affects:
  - bot/prompts.py
  - bot/handlers.py
  - bot/main.py
  - tests/test_handlers.py
tech-stack:
  added: []
  patterns:
    - "Single inverted-filter MessageHandler (~filters.TEXT & ~filters.COMMAND) catches all non-text types with no per-type branching (D-06)"
    - "Guard handler follows the minimal start/help_cmd pattern: None-message early return then reply_text"
    - "asyncio.run() test idiom (no pytest-asyncio)"
key-files:
  created: []
  modified:
    - bot/prompts.py
    - bot/handlers.py
    - bot/main.py
    - tests/test_handlers.py
decisions:
  - "handle_non_text performs NO allowed_chat_ids check — it replies for every user including unauthorized ones (D-08)"
  - "Inverted filter registered AFTER the text handler so text still routes to handle_text"
  - "NON_TEXT_REPLY collapsed to a single-line assignment per ruff format (fits within line length)"
metrics:
  duration: ~6m
  completed: 2026-06-16
---

# Phase 05 Plan 02: Non-Text Message Guard Summary

A single inverted-filter `MessageHandler` now catches every non-text, non-command message (photo, voice, sticker, video, document) and replies with the friendly `NON_TEXT_REPLY` nudge for all users — no more silent drops.

## What Was Built

- **`bot/prompts.py`** — Added `NON_TEXT_REPLY = "I only understand text messages — send me a question and I'll reply!"` (helpful-nudge tone per D-07). Existing constants (`SYSTEM_PROMPT`, `START_TEXT`, `HELP_TEXT`, `TRUNCATION_NOTE`) left untouched.
- **`bot/handlers.py`**
  - Added `NON_TEXT_REPLY` to the `from .prompts import ...` line.
  - New handler `async def handle_non_text(update, context) -> None`: early-return guard `if update.message is None: return`, then `await update.message.reply_text(NON_TEXT_REPLY)`. Follows the exact minimal pattern of `start` / `help_cmd`. No `allowed_chat_ids` check — per D-08 the guard fires for every user. Never reads `message.text` or any media payload (T-05-04 mitigation).
- **`bot/main.py`**
  - Added `handle_non_text` to the `from .handlers import ...` import.
  - Registered `app.add_handler(MessageHandler(~filters.TEXT & ~filters.COMMAND, handle_non_text))` immediately after the existing `handle_text` registration. The inverted filter (D-06) catches all non-text types with no per-type branching; placement after the text handler preserves text routing.
- **`tests/test_handlers.py`** — Added `handle_non_text` to handler imports and `NON_TEXT_REPLY` to prompt imports. Two new tests using the `asyncio.run()` idiom:
  - `test_handle_non_text_sends_guard_message` — asserts `reply_text` awaited once with `NON_TEXT_REPLY`.
  - `test_handle_non_text_no_message_is_noop` — sets `update.message = None`, asserts the handler returns without raising.

## How It Works

PTB dispatches each incoming update to the first matching handler. Text/command messages match `filters.TEXT & ~filters.COMMAND` → `handle_text`. Everything else that is not a command (photo, voice, sticker, video, document) matches the new `~filters.TEXT & ~filters.COMMAND` filter → `handle_non_text`, which sends the fixed `NON_TEXT_REPLY` and nothing else. Because the guard runs no auth check and makes no LLM call, unauthorized users also get the nudge (D-08) at zero LLM cost (T-05-05 accepted).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `ruff format` collapsed NON_TEXT_REPLY to one line**
- **Found during:** Task 2 verification (`ruff format --check`)
- **Issue:** The plan/pattern specified a parenthesized multi-line assignment for `NON_TEXT_REPLY`, but the single-string value fits within the line-length limit, so `ruff format --check` flagged `bot/prompts.py` as needing reformatting.
- **Fix:** Ran `ruff format bot/prompts.py`, collapsing it to `NON_TEXT_REPLY = "..."`. Value unchanged; the Task 1 assertion (`NON_TEXT_REPLY == "..."`) still holds. The format change was folded into the GREEN commit.
- **Files modified:** bot/prompts.py
- **Commit:** 478f79f

### Environment Note

- pytest resolves via the project `.venv` (`.venv/Scripts/python.exe -m pytest`); ruff and mypy resolve via the anaconda toolchain on this machine (consistent with the 05-01 SUMMARY note). CI uses its own pinned tooling.

## TDD Gate Compliance

- RED gate: `test(05-02)` commit `824c9be` — collection failed on `ImportError: cannot import name 'handle_non_text'`.
- GREEN gate: `feat(05-02)` commit `478f79f` — 15/15 tests pass.
- REFACTOR: not needed; the guard handler is already minimal.

## Verification Results

- `.venv/Scripts/python.exe -m pytest tests/test_handlers.py -q` → 15 passed
- `ruff check bot/ tests/` → All checks passed!
- `ruff format --check bot/ tests/` → 12 files already formatted
- `mypy bot/ --ignore-missing-imports` → Success: no issues found in 7 source files
- `grep allowed_chat_ids bot/handlers.py` → only lines 56–57 (inside `handle_text`); `handle_non_text` has no auth check (D-08 confirmed)
- `bot/main.py` registers `MessageHandler(~filters.TEXT & ~filters.COMMAND, handle_non_text)` after the `handle_text` registration

## Threat Surface

No new threat surface beyond the plan's `<threat_model>`. The guard reads no user content, makes no LLM call, sends a static constant with no `parse_mode`, and adds no dependencies.

## Notes for Downstream

- Phase 05 (UX Polish) feature work is complete across plans 05-01 (typing indicator + reply splitting) and 05-02 (non-text guard). All three phase UX behaviors are now live in the handler layer.

## Self-Check: PASSED

- FOUND: bot/prompts.py (NON_TEXT_REPLY), bot/handlers.py (handle_non_text), bot/main.py (registration), tests/test_handlers.py (2 new tests)
- FOUND commits: 5c6953b, 824c9be, 478f79f
