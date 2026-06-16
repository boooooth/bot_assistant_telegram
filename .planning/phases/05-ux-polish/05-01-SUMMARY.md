---
phase: 05-ux-polish
plan: 01
subsystem: bot-handlers
tags: [ux, telegram, handlers, typing-indicator, reply-splitting]
requires:
  - bot/handlers.py:handle_text
  - bot/prompts.py
provides:
  - bot/handlers.py:split_text
  - bot/prompts.py:TRUNCATION_NOTE
  - typing-indicator in handle_text
  - reply-split loop in handle_text
affects:
  - bot/handlers.py
  - bot/prompts.py
  - tests/test_handlers.py
tech-stack:
  added: []
  patterns:
    - "ChatAction.TYPING imported from telegram.constants (PTB 22.x canonical location)"
    - "Pure synchronous helper (split_text) kept separate from async handler for testability"
    - "asyncio.run() test idiom (no pytest-asyncio)"
key-files:
  created: []
  modified:
    - bot/prompts.py
    - bot/handlers.py
    - tests/test_handlers.py
decisions:
  - "ChatAction imported from telegram.constants rather than telegram (PTB 22.x canonical)"
  - "send_chat_action made AsyncMock in shared _make_context fixture so all handle_text callers stay awaitable"
metrics:
  duration: ~12m
  completed: 2026-06-16
---

# Phase 05 Plan 01: Typing Indicator + Long-Reply Splitting Summary

Typing indicator and 3-chunk newline-boundary reply splitting added to `handle_text`, with a standalone testable `split_text` helper and a `TRUNCATION_NOTE` constant.

## What Was Built

- **`bot/prompts.py`** — Added `TRUNCATION_NOTE = "\n\n...(truncated — reply was too long)"`, the note appended to the final chunk when a reply exceeds the 3-message cap (D-04). Follows the existing `START_TEXT` / `HELP_TEXT` constant style.
- **`bot/handlers.py`**
  - New pure helper `split_text(text, max_len=4096, max_chunks=3) -> list[str]`: splits at the last newline before `max_len` (falling back to a hard cut when no newline exists), caps at 3 chunks, and appends `TRUNCATION_NOTE` to the last chunk if text still remains at the cap (D-03, D-04).
  - Typing indicator: `await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)` fired once, immediately after the `None` guard and **before** the `allowed_chat_ids` auth check, so every user (authorized or not) sees instant feedback (D-01 fire-once, D-02 pre-auth).
  - The single `reply_text(reply)` call replaced with `for chunk in split_text(reply): await update.message.reply_text(chunk)`, inside the unchanged try/except (D-05 — default `reply_text` quoting satisfies visual threading).
  - Imports: `ChatAction` from `telegram.constants`, `TRUNCATION_NOTE` from `.prompts`.
- **`tests/test_handlers.py`** — 7 new tests (typing action fired once, single-message short reply, multi-message long-reply split, 3-chunk cap with truncation note, and three `split_text` unit tests). Added `context.bot.send_chat_action = AsyncMock()` to the shared `_make_context` fixture.

## How It Works

`handle_text` flow: None guard → fire TYPING action → auth check → LLM call → `split_text(reply)` loop → per-chunk `reply_text`. `split_text` accumulates chunks while text remains and `len(chunks) < max_chunks`; each iteration either appends the remainder (when it fits) and breaks, or splits at `rfind("\n", 0, max_len)` (hard cut at `max_len` when none found). The loop terminates because each iteration consumes ≥1 char or breaks (bounds T-05-01 DoS).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `ChatAction` import source**
- **Found during:** Task 2 implementation
- **Issue:** Plan said add `ChatAction` to `from telegram import ...`. In PTB 22.x, `ChatAction` lives in `telegram.constants`, not the top-level `telegram` namespace.
- **Fix:** Imported via `from telegram.constants import ChatAction`. Functionally equivalent; mypy/runtime clean.
- **Files modified:** bot/handlers.py
- **Commit:** 0b1c0e3

**2. [Rule 3 - Blocking] `send_chat_action` not awaitable in existing test fixture**
- **Found during:** Task 2 GREEN run
- **Issue:** Firing the typing action made all `handle_text` tests await `context.bot.send_chat_action`, which was a plain `MagicMock` in the shared `_make_context` helper → `TypeError: object MagicMock can't be used in 'await' expression`. Broke 6 existing/new tests.
- **Fix:** Added `context.bot.send_chat_action = AsyncMock()` to `_make_context` so every `handle_text` caller stays awaitable. The plan's inline assignment in the typing test remains (harmless re-assignment).
- **Files modified:** tests/test_handlers.py
- **Commit:** 0b1c0e3

**3. [Rule 3 - Blocking] Unused `TRUNCATION_NOTE` import flagged by ruff**
- **Found during:** Task 2 verification
- **Issue:** Plan instructed importing `TRUNCATION_NOTE` into the test file, but the test bodies asserted on the literal `"truncated"` substring, leaving the import unused (ruff F401).
- **Fix:** Added `assert chunks[-1].endswith(TRUNCATION_NOTE)` to `test_split_text_caps_at_max_chunks_and_appends_truncation_note` — a stronger assertion that genuinely uses the import.
- **Files modified:** tests/test_handlers.py
- **Commit:** 0b1c0e3

## TDD Gate Compliance

- RED gate: `test(05-01)` commit `44622be` — tests failed on `ImportError: cannot import name 'split_text'`.
- GREEN gate: `feat(05-01)` commit `0b1c0e3` — 13/13 tests pass.
- REFACTOR: not needed; implementation already minimal.

## Verification Results

- `python -m pytest tests/test_handlers.py -q` → 13 passed
- `ruff check bot/ tests/` → All checks passed
- `ruff format --check bot/ tests/` → 12 files already formatted
- `mypy bot/ --ignore-missing-imports` → Success: no issues found in 7 source files
- `send_chat_action` (line 46) precedes `allowed_chat_ids` (line 50) — typing fires before auth (D-02)

## Notes for Downstream

- Plan 05-02 adds the non-text guard handler (`handle_non_text`), `NON_TEXT_REPLY` constant, and the inverted-filter registration in `bot/main.py`. `NON_TEXT_REPLY` was intentionally NOT added in this plan.
- ruff and mypy are not in the project `.venv`; they resolve via the anaconda toolchain on this machine. CI uses its own pinned tooling.

## Self-Check: PASSED

- FOUND: bot/prompts.py, bot/handlers.py, tests/test_handlers.py
- FOUND commits: edd6735, 44622be, 0b1c0e3
