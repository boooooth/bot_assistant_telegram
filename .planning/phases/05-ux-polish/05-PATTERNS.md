# Phase 5: UX Polish - Pattern Map

**Mapped:** 2026-06-16
**Files analyzed:** 4 (handlers.py, main.py, prompts.py, tests/test_handlers.py)
**Analogs found:** 4 / 4 — all are in-place modifications of existing files; the files themselves are their own analogs.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `bot/handlers.py` | handler (controller) | request-response | `bot/handlers.py` itself — `handle_text` and command handlers | exact (in-place modification) |
| `bot/main.py` | config / wiring | request-response | `bot/main.py` itself — existing `add_handler` registrations | exact (in-place modification) |
| `bot/prompts.py` | constants / config | — | `bot/prompts.py` itself — `START_TEXT`, `HELP_TEXT` | exact (in-place modification) |
| `tests/test_handlers.py` | test | request-response | `tests/test_handlers.py` itself — existing `asyncio.run()` tests | exact (in-place modification) |

---

## Pattern Assignments

### `bot/handlers.py` — typing indicator, reply splitting, non-text guard

**Analog:** `bot/handlers.py` (existing file, lines 1–44)

**Imports pattern** (lines 1–8):
```python
import logging

from telegram import Update
from telegram.ext import ContextTypes

from .prompts import HELP_TEXT, START_TEXT

logger = logging.getLogger(__name__)
```
New additions: import `ChatAction` from `telegram`, import new prompt constants (`NON_TEXT_REPLY`, `TRUNCATION_NOTE`) from `.prompts`.

**Handler signature pattern** (lines 11–13, 17–19, 23–25):
```python
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(START_TEXT)
```
Every handler is `async def (update, context) -> None` with an early-return guard on `update.message is None`. The new `handle_non_text` guard handler follows this exact signature and guard structure.

**Typing indicator placement** — fire before the auth check (D-02). Insert immediately after the `update.message is None` guard, before line 27 (`allowed_chat_ids` check):
```python
await context.bot.send_chat_action(
    chat_id=update.effective_chat.id,
    action=ChatAction.TYPING,
)
```

**Core reply pattern** (lines 35–43) — the block to modify for reply splitting:
```python
try:
    reply = await context.bot_data["complete"](update.message.text)
    await update.message.reply_text(reply)          # <-- replace this line
    logger.info("replied to chat_id=%s", chat_id)
except Exception:
    logger.exception("OpenAI call failed for chat_id=%s", chat_id)
    await update.message.reply_text(
        "Sorry, something went wrong. Please try again in a moment."
    )
```
Replace the single `reply_text(reply)` call with a loop over `split_text(reply)` chunks, each sent with `reply_text`. Same `except Exception` / `logger.exception` pattern wraps everything.

**Reply split helper — new standalone function** (add above `handle_text`):
```python
def split_text(text: str, max_len: int = 4096, max_chunks: int = 3) -> list[str]:
    """Split text at newline boundaries; cap at max_chunks."""
    chunks: list[str] = []
    remaining = text
    while remaining and len(chunks) < max_chunks:
        if len(remaining) <= max_len:
            chunks.append(remaining)
            break
        split_at = remaining.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip("\n")
    if remaining and len(chunks) == max_chunks:
        chunks[-1] += TRUNCATION_NOTE
    return chunks
```
This is a pure function — independently testable, keeps `handle_text` readable (D-03, D-04).

**Non-text guard handler — new function** (pattern copied from `start` / `help_cmd`):
```python
async def handle_non_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(NON_TEXT_REPLY)
```
Follows the same minimal pattern as `start` and `help_cmd` (lines 11–20). No auth check needed — D-08 says the guard applies to all users.

---

### `bot/main.py` — add non-text guard handler registration

**Analog:** `bot/main.py` (existing file, lines 1–31)

**Imports pattern** (lines 1–9):
```python
from .handlers import handle_text, help_cmd, start
```
Add `handle_non_text` to this import.

**Handler registration pattern** (lines 27–29):
```python
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_cmd))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
```
Add one more `add_handler` call after the existing text handler:
```python
app.add_handler(MessageHandler(~filters.TEXT & ~filters.COMMAND, handle_non_text))
```
The inverted filter `~filters.TEXT & ~filters.COMMAND` mirrors the existing pattern (D-06).

---

### `bot/prompts.py` — add NON_TEXT_REPLY and TRUNCATION_NOTE constants

**Analog:** `bot/prompts.py` (existing file, lines 8–15)

**Existing constant pattern** (lines 8–15):
```python
START_TEXT = (
    "Hi! Send me any message and I'll answer using AI.\nType /help for usage info."
)

HELP_TEXT = (
    "Just send me any text message and I'll reply using AI.\n"
    "Each message is answered on its own — I don't remember past messages yet."
)
```
New constants follow the same pattern — module-level string assignments using parenthesized string concatenation for multi-line values, no trailing newline, consistent tone:
```python
NON_TEXT_REPLY = (
    "I only understand text messages — send me a question and I'll reply!"
)

TRUNCATION_NOTE = "\n\n...(truncated — reply was too long)"
```

---

### `tests/test_handlers.py` — new tests for typing indicator, reply splitting, non-text guard

**Analog:** `tests/test_handlers.py` (existing file, lines 1–68)

**Imports pattern** (lines 1–5):
```python
import asyncio
from unittest.mock import AsyncMock, MagicMock

from bot.handlers import handle_text, help_cmd, start
from bot.prompts import HELP_TEXT, START_TEXT
```
Add `handle_non_text`, `split_text` to handler imports; add `NON_TEXT_REPLY`, `TRUNCATION_NOTE` to prompt imports.

**Test helper pattern** (lines 8–21):
```python
def _make_update(text="hello", chat_id=123):
    update = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.effective_chat.id = chat_id
    return update

def _make_context(reply="hi back", allowed=frozenset()):
    context = MagicMock()
    context.bot_data = {
        "complete": AsyncMock(return_value=reply),
        "allowed_chat_ids": allowed,
    }
    return context
```
For typing indicator tests, add `context.bot.send_chat_action = AsyncMock()` to `_make_context` (or add inline in the test). For non-text guard tests, `_make_update` needs no `text` — the guard handler never reads `message.text`.

**asyncio.run() test idiom** (lines 25–30):
```python
def test_handle_text_replies_with_llm_output():
    update = _make_update("hello")
    context = _make_context(reply="the answer")
    asyncio.run(handle_text(update, context))
    context.bot_data["complete"].assert_awaited_once_with("hello")
    update.message.reply_text.assert_awaited_once_with("the answer")
```
All new tests use `asyncio.run()` — no pytest-asyncio, no `@pytest.mark.asyncio`, no `async def test_*`. Plain `def test_*` calling `asyncio.run(handler(...))`.

**New tests to add (following the idiom):**

*Typing indicator:*
```python
def test_handle_text_sends_typing_action():
    update = _make_update("hello")
    context = _make_context(reply="ok")
    context.bot.send_chat_action = AsyncMock()
    asyncio.run(handle_text(update, context))
    context.bot.send_chat_action.assert_awaited_once()
```

*Reply splitting — short reply (no split):*
```python
def test_handle_text_short_reply_single_message():
    update = _make_update("q")
    context = _make_context(reply="short answer")
    asyncio.run(handle_text(update, context))
    assert update.message.reply_text.await_count == 1
```

*Reply splitting — long reply splits into multiple messages:*
```python
def test_handle_text_long_reply_splits_into_multiple_messages():
    long_reply = ("A" * 4000 + "\n") * 2  # >4096 chars with newline boundary
    update = _make_update("q")
    context = _make_context(reply=long_reply)
    asyncio.run(handle_text(update, context))
    assert update.message.reply_text.await_count > 1
```

*Reply splitting — cap at 3 chunks with truncation note:*
```python
def test_handle_text_caps_at_3_chunks_with_truncation_note():
    huge_reply = ("B" * 4000 + "\n") * 10  # forces >3 chunks
    update = _make_update("q")
    context = _make_context(reply=huge_reply)
    asyncio.run(handle_text(update, context))
    assert update.message.reply_text.await_count == 3
    last_call_text = update.message.reply_text.call_args_list[-1].args[0]
    assert "truncated" in last_call_text
```

*split_text unit tests (pure function, no asyncio.run needed):*
```python
def test_split_text_short_string_returns_single_chunk():
    from bot.handlers import split_text
    assert split_text("hello") == ["hello"]

def test_split_text_splits_at_newline_boundary():
    from bot.handlers import split_text
    text = "A" * 4000 + "\n" + "B" * 4000
    chunks = split_text(text)
    assert len(chunks) == 2
    assert all(len(c) <= 4096 for c in chunks)

def test_split_text_caps_at_max_chunks_and_appends_truncation_note():
    from bot.handlers import split_text
    text = ("C" * 4000 + "\n") * 10
    chunks = split_text(text)
    assert len(chunks) == 3
    assert "truncated" in chunks[-1]
```

*Non-text guard:*
```python
def test_handle_non_text_sends_guard_message():
    update = _make_update()
    asyncio.run(handle_non_text(update, MagicMock()))
    update.message.reply_text.assert_awaited_once_with(NON_TEXT_REPLY)

def test_handle_non_text_no_message_is_noop():
    update = _make_update()
    update.message = None
    asyncio.run(handle_non_text(update, MagicMock()))  # must not raise
```

---

## Shared Patterns

### Guard pattern (early return on None message)
**Source:** `bot/handlers.py` lines 12–13, 18–19, 24–25
**Apply to:** all handlers including new `handle_non_text`
```python
if update.message is None:
    return
```

### reply_text call pattern
**Source:** `bot/handlers.py` lines 14, 20, 37
**Apply to:** typing indicator, all split chunks, non-text guard response
```python
await update.message.reply_text(<text>)
```
No kwargs needed — PTB defaults are appropriate for all cases in this phase.

### Error handling pattern
**Source:** `bot/handlers.py` lines 39–43
**Apply to:** the try/except block wrapping the LLM call and reply loop in `handle_text`
```python
except Exception:
    logger.exception("OpenAI call failed for chat_id=%s", chat_id)
    await update.message.reply_text(
        "Sorry, something went wrong. Please try again in a moment."
    )
```
The bare `except Exception` + `logger.exception` pattern is intentional — preserves the full traceback in logs.

### Prompt constant pattern
**Source:** `bot/prompts.py` lines 8–15
**Apply to:** `NON_TEXT_REPLY` and `TRUNCATION_NOTE` in `bot/prompts.py`
```python
CONSTANT_NAME = (
    "String value here."
)
```

### asyncio.run() test idiom
**Source:** `tests/test_handlers.py` lines 28, 37, 43, 50, 61, 67
**Apply to:** all new async handler tests
```python
def test_<name>():
    update = _make_update(...)
    context = _make_context(...)
    asyncio.run(handler(update, context))
    # assert on update.message.reply_text or context mocks
```

---

## No Analog Found

None — all four files exist and are the direct integration targets.

---

## Metadata

**Analog search scope:** `bot/`, `tests/`
**Files scanned:** 4 source files (handlers.py, main.py, prompts.py, test_handlers.py)
**Pattern extraction date:** 2026-06-16
