import asyncio
from unittest.mock import AsyncMock, MagicMock

from bot.handlers import handle_non_text, handle_text, help_cmd, split_text, start
from bot.prompts import HELP_TEXT, NON_TEXT_REPLY, START_TEXT, TRUNCATION_NOTE


def _make_update(text="hello", chat_id=123):
    update = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.effective_chat.id = chat_id
    return update


def _make_context(reply="hi back", allowed=frozenset()):
    context = MagicMock()
    context.bot.send_chat_action = AsyncMock()
    context.bot_data = {
        "complete": AsyncMock(return_value=reply),
        "allowed_chat_ids": allowed,
    }
    return context


def test_handle_text_replies_with_llm_output():
    update = _make_update("hello")
    context = _make_context(reply="the answer")
    asyncio.run(handle_text(update, context))
    context.bot_data["complete"].assert_awaited_once_with("hello")
    update.message.reply_text.assert_awaited_once_with("the answer")


def test_handle_text_friendly_error_on_llm_failure():
    update = _make_update("boom")
    context = _make_context()
    context.bot_data["complete"].side_effect = RuntimeError("llm down")
    asyncio.run(handle_text(update, context))
    update.message.reply_text.assert_awaited_once()
    assert "went wrong" in update.message.reply_text.call_args.args[0]


def test_handle_text_rejects_unauthorized_chat():
    update = _make_update(chat_id=999)
    context = _make_context(allowed=frozenset({123}))
    asyncio.run(handle_text(update, context))
    update.message.reply_text.assert_awaited_once()
    assert "not authorized" in update.message.reply_text.call_args.args[0]
    context.bot_data["complete"].assert_not_awaited()


def test_handle_text_no_message_is_noop():
    update = _make_update()
    update.message = None
    context = _make_context()
    asyncio.run(handle_text(update, context))  # must not raise
    context.bot_data["complete"].assert_not_awaited()


def test_start_sends_welcome():
    update = _make_update()
    asyncio.run(start(update, MagicMock()))
    update.message.reply_text.assert_awaited_once_with(START_TEXT)


def test_help_sends_usage():
    update = _make_update()
    asyncio.run(help_cmd(update, MagicMock()))
    update.message.reply_text.assert_awaited_once_with(HELP_TEXT)


def test_handle_text_sends_typing_action():
    update = _make_update("hello")
    context = _make_context(reply="ok")
    context.bot.send_chat_action = AsyncMock()
    asyncio.run(handle_text(update, context))
    context.bot.send_chat_action.assert_awaited_once()


def test_handle_text_short_reply_single_message():
    update = _make_update("q")
    context = _make_context(reply="short answer")
    asyncio.run(handle_text(update, context))
    assert update.message.reply_text.await_count == 1


def test_handle_text_long_reply_splits_into_multiple_messages():
    long_reply = ("A" * 4000 + "\n") * 2  # >4096 chars with newline boundary
    update = _make_update("q")
    context = _make_context(reply=long_reply)
    asyncio.run(handle_text(update, context))
    assert update.message.reply_text.await_count > 1


def test_handle_text_caps_at_3_chunks_with_truncation_note():
    huge_reply = ("B" * 4000 + "\n") * 10  # forces >3 chunks
    update = _make_update("q")
    context = _make_context(reply=huge_reply)
    asyncio.run(handle_text(update, context))
    assert update.message.reply_text.await_count == 3
    last_call_text = update.message.reply_text.call_args_list[-1].args[0]
    assert "truncated" in last_call_text


def test_split_text_short_string_returns_single_chunk():
    assert split_text("hello") == ["hello"]


def test_split_text_splits_at_newline_boundary():
    text = "A" * 4000 + "\n" + "B" * 4000
    chunks = split_text(text)
    assert len(chunks) == 2
    assert all(len(c) <= 4096 for c in chunks)


def test_split_text_caps_at_max_chunks_and_appends_truncation_note():
    text = ("C" * 4000 + "\n") * 10
    chunks = split_text(text)
    assert len(chunks) == 3
    assert "truncated" in chunks[-1]
    assert chunks[-1].endswith(TRUNCATION_NOTE)


def test_handle_non_text_sends_guard_message():
    update = _make_update()
    asyncio.run(handle_non_text(update, MagicMock()))
    update.message.reply_text.assert_awaited_once_with(NON_TEXT_REPLY)


def test_handle_non_text_no_message_is_noop():
    update = _make_update()
    update.message = None
    asyncio.run(handle_non_text(update, MagicMock()))  # must not raise
