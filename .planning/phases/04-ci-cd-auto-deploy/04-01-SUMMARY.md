---
phase: 04-ci-cd-auto-deploy
plan: 01
subsystem: testing
tags: [pytest, ruff, mypy, ci, handlers]
requires:
  - bot.handlers (start, help_cmd, handle_text)
  - bot.prompts (START_TEXT, HELP_TEXT)
provides:
  - tests/test_handlers.py (handler unit coverage)
  - requirements-dev.txt single-source dev tooling (pinned ruff + mypy)
affects:
  - .github/workflows/ci.yml (Wave 2 can drop ad-hoc 'pip install ruff mypy')
tech-stack:
  added: []
  patterns:
    - "asyncio.run() + AsyncMock/MagicMock handler tests (no pytest-asyncio, no config)"
key-files:
  created:
    - tests/test_handlers.py
  modified:
    - requirements-dev.txt
decisions:
  - "Matched existing asyncio.run() test idiom from test_openai_client.py; skipped pytest-asyncio (zero new config)"
  - "Pinned ruff==0.12.0 and mypy==1.17.1 to the CI/installed versions for local-vs-CI parity"
metrics:
  duration: "~6 min"
  completed: "2026-06-15"
  tasks: 2
  files: 2
---

# Phase 04 Plan 01: Handler Tests + Dev-Tooling Parity Summary

Added `tests/test_handlers.py` with six unit tests covering the three PTB handlers (happy path, friendly LLM-error path, allowlist rejection, no-message no-op, plus /start and /help), and pinned `ruff==0.12.0` + `mypy==1.17.1` into `requirements-dev.txt` so CI installs all dev tooling from one source of truth.

## What Was Built

**Task 1 — tests/test_handlers.py (`test(04-01)`, commit fd92d87)**
- Two local helpers mirroring `test_openai_client.py`'s `_make_mock_response`: `_make_update(text, chat_id)` and `_make_context(reply, allowed)`. `bot_data` is a real dict so the handler's `["complete"]` subscript and `.get("allowed_chat_ids", ...)` work as in production.
- Six tests, all driven by `asyncio.run(...)` with no `@pytest.mark.asyncio` and no new pytest config:
  - `test_handle_text_replies_with_llm_output` — `complete` awaited once with the text only; `reply_text` awaited once with the reply.
  - `test_handle_text_friendly_error_on_llm_failure` — `complete` raises (`side_effect=RuntimeError`); handler swallows it and replies with a message containing "went wrong".
  - `test_handle_text_rejects_unauthorized_chat` — `allowed={123}`, chat 999 → reply contains "not authorized" and `complete` never awaited.
  - `test_handle_text_no_message_is_noop` — `update.message = None` → returns without raising, `complete` never awaited.
  - `test_start_sends_welcome` / `test_help_sends_usage` — assert exact `START_TEXT` / `HELP_TEXT`.

**Task 2 — requirements-dev.txt (`chore(04-01)`, commit fe736c7)**
- Appended `ruff==0.12.0` and `mypy==1.17.1` after the existing `pytest` line. Kept `-r requirements.txt` and `pytest`. Did NOT add `pytest-asyncio` (the suite uses `asyncio.run()`).

## Verification Results

- `pytest tests/test_handlers.py -q` → 6 passed.
- `pytest -q` (full suite) → 16 passed.
- `ruff check .` → All checks passed. `ruff format --check .` → 12 files already formatted.
- `mypy bot/ --ignore-missing-imports` → Success: no issues found in 7 source files.
- `pip install -r requirements-dev.txt --dry-run` → resolves cleanly; two `(ruff|mypy)==` lines present.

## Deviations from Plan

None — plan executed exactly as written.

## TDD Gate Compliance

Task 1 was marked `tdd="true"`, but the code under test (`bot/handlers.py`) already existed and was correct. The tests were therefore characterization/coverage tests written against existing behavior; there was no failing-then-passing RED→GREEN transition to commit separately. The test file was committed as a single `test(04-01)` commit. No production code changed, so no `feat` GREEN commit applies for this plan.

## Notes for Next Plans

- Wave 2 (CI/CD workflow) can now drop the ad-hoc `ruff mypy` arguments from `.github/workflows/ci.yml` line 18 — `pip install -r requirements-dev.txt` alone installs pytest, ruff, and mypy.
- Test files remain intentionally out of mypy scope (`mypy bot/` only), per RESEARCH Pitfall 5.

## Self-Check: PASSED

- FOUND: tests/test_handlers.py
- FOUND: requirements-dev.txt
- FOUND commit: fd92d87 (test)
- FOUND commit: fe736c7 (chore)
