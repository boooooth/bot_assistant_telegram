---
phase: 05-ux-polish
reviewed: 2026-06-16T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - bot/handlers.py
  - bot/main.py
  - bot/prompts.py
  - tests/test_handlers.py
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: fixed
fixes_applied:
  - id: CR-01
    commit: f60e9f3
    description: Guard update.message.text against None before passing to LLM
  - id: WR-02
    commit: 145a01a
    description: Wrap ALLOWED_CHAT_IDS parsing to raise ConfigError on non-integer input
  - id: WR-03
    commit: 33db12b
    description: Use max_len-1 for split_text hard-cut to stay below Telegram 4096-char limit
  - id: WR-01
    status: wont-fix
    reason: Locked design decision D-02 — typing indicator fires before auth check by explicit user decision
  - id: IN-01
    status: skipped
    reason: Info finding — not in scope for this fix run
  - id: IN-02
    status: skipped
    reason: Info finding — not in scope for this fix run
---

# Phase 05: Code Review Report

**Reviewed:** 2026-06-16
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed the four files comprising the UX-polish phase deliverable: the message handler, bot entry point, prompt strings, and the handler test suite. The core bot logic is well-structured overall — separation of concerns between `config.py`, `openai_client.py`, and `handlers.py` is clean, the fail-fast config loader is correct, and the split-text algorithm is sound for the common case.

Three issues require attention before shipping:

1. `update.message.text` is accessed without a None-guard, producing a silent `None` passed to the LLM instead of a skip or error.
2. The `send_chat_action` call executes before the authorization check, revealing bot presence to unauthorized users and wasting API calls.
3. `ALLOWED_CHAT_IDS` parsing in `config.py` raises an unhandled `ValueError` on non-integer input, crashing the bot at startup with an uninformative traceback instead of a `ConfigError`.

Additionally, the `split_text` hard-cut fallback (line 22) produces a chunk that is exactly `max_len` characters which is at Telegram's documented limit and will be rejected by the API for any reply where the fallback fires and `max_len` has not been reduced.

---

## Critical Issues

### CR-01: `update.message.text` is not guarded against `None` before being passed to the LLM

**File:** `bot/handlers.py:65`

**Issue:** `update.message` is already verified to be non-None by line 49, but `update.message.text` is `None` for messages that have no text body (e.g., a forwarded sticker caption-less message that still passes the `filters.TEXT` filter edge cases, or a future PTB version change). More practically: the PTB `filters.TEXT` filter allows messages whose `.text` is `None` in some edge cases (entities-only messages). When `update.message.text` is `None`, the `complete()` coroutine receives `None` as `user_text` and silently passes it to LiteLLM rather than returning early. At best the LLM gets the string `"None"`; at worst the LLM SDK raises a type error that is caught by the bare `except Exception` and yields a generic error reply, hiding the root cause entirely.

**Fix:**
```python
user_text = update.message.text
if not user_text:
    return  # nothing to send; PTB filter shouldn't let this through, but guard anyway
reply = await context.bot_data["complete"](user_text)
```

---

## Warnings

### WR-01: Typing indicator sent before authorization check — reveals bot presence to unauthorized users

**File:** `bot/handlers.py:52-62`

**Issue:** `send_chat_action(ChatAction.TYPING)` is called at line 52, before the `allowed_chat_ids` check at line 56. This means every unauthorized user who messages the bot sees a "typing…" indicator before receiving the rejection message. This leaks that the bot is alive and responsive to users who should be silently ignored (or at minimum not visually acknowledged as typing). It also makes an unnecessary Telegram API call for every rejected request.

**Fix:** Move the `send_chat_action` call to after the authorization check:

```python
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_chat is None:
        return
    chat_id = update.effective_chat.id

    allowed_chat_ids = context.bot_data.get("allowed_chat_ids", frozenset())
    if allowed_chat_ids and chat_id not in allowed_chat_ids:
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        logger.info("unauthorized access attempt from chat_id=%s", chat_id)
        return

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    ...
```

---

### WR-02: `ALLOWED_CHAT_IDS` parsing crashes the bot at startup with an unhandled `ValueError`

**File:** `bot/config.py:49`

**Issue:** `int(i.strip())` inside the generator expression at line 49 raises `ValueError` if any value in the comma-separated `ALLOWED_CHAT_IDS` env var is not a valid integer (e.g., `"123,abc,456"`). This exception propagates out of `load_settings()` as a bare `ValueError`, not as a `ConfigError`. The `main()` function has no handler for `ValueError`, so the bot process exits with a raw Python traceback rather than the clean `ConfigError` message that signals a configuration problem. This contradicts the documented intent of `ConfigError` ("raised at boot when required configuration is missing or blank") and makes the failure mode significantly harder to diagnose.

**Fix:**
```python
try:
    allowed_chat_ids: frozenset[int] = (
        frozenset(int(i.strip()) for i in raw_ids.split(",") if i.strip())
        if raw_ids
        else frozenset()
    )
except ValueError as exc:
    raise ConfigError(
        f"ALLOWED_CHAT_IDS contains a non-integer value: {exc}"
    ) from exc
```

---

### WR-03: `split_text` hard-cut fallback produces a chunk of exactly `max_len` bytes — at Telegram's limit

**File:** `bot/handlers.py:22-23`

**Issue:** When `rfind("\n", 0, max_len)` returns `-1` (no newline found in the first `max_len` characters), `split_at` is set to `max_len` (4096 by default) and the chunk `remaining[:4096]` is appended. Telegram's Bot API maximum message length is 4096 characters. A chunk of exactly 4096 characters sits at the boundary; multi-byte Unicode characters (emoji, CJK, Cyrillic) mean the byte length can exceed 4096 even when the character count is exactly 4096, causing Telegram to reject the message with a `BadRequest` error. This fallback also does not strip the leading newline from `remaining[split_at:]` (only `lstrip("\n")` is applied, which is correct), but the chunk itself is never trimmed.

**Fix:** Reduce the hard-cut to one character below the limit so the boundary is safe, and add a test covering the all-ASCII no-newline hard-cut case:

```python
split_at = max_len - 1  # stay one char inside Telegram's 4096-char limit
```

---

## Info

### IN-01: Test `test_handle_text_no_message_is_noop` does not also set `effective_chat = None`

**File:** `tests/test_handlers.py:52-57`

**Issue:** The guard condition in `handle_text` is `if update.message is None or update.effective_chat is None`. The test exercises only the `update.message = None` branch. There is no test for the `update.effective_chat is None` branch. If the guard on `effective_chat` were accidentally removed, this coverage gap would not catch it.

**Fix:** Add a companion test:
```python
def test_handle_text_no_effective_chat_is_noop():
    update = _make_update()
    update.effective_chat = None
    context = _make_context()
    asyncio.run(handle_text(update, context))
    context.bot_data["complete"].assert_not_awaited()
```

---

### IN-02: `send_chat_action` test re-assigns `context.bot.send_chat_action` redundantly

**File:** `tests/test_handlers.py:75`

**Issue:** `test_handle_text_sends_typing_action` calls `_make_context()` which already sets `context.bot.send_chat_action = AsyncMock()` at line 18. Line 75 immediately re-assigns the same attribute to a new `AsyncMock()`, making the first assignment dead. This is harmless but indicates the test was written without awareness of what `_make_context` initializes, which could lead to subtle assertion mismatches if the two mocks diverge.

**Fix:** Remove the redundant assignment on line 75:
```python
def test_handle_text_sends_typing_action():
    update = _make_update("hello")
    context = _make_context(reply="ok")
    # context.bot.send_chat_action is already an AsyncMock from _make_context
    asyncio.run(handle_text(update, context))
    context.bot.send_chat_action.assert_awaited_once()
```

---

_Reviewed: 2026-06-16_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
