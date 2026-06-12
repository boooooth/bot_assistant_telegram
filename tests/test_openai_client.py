import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.openai_client import complete
from bot.prompts import SYSTEM_PROMPT


def _make_mock_client(content: str = "hello back"):
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = content
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=mock_resp)
    return client


def test_calls_create_once():
    client = _make_mock_client()
    asyncio.run(complete(client, "gpt-4o-mini", "hello"))
    client.chat.completions.create.assert_called_once()


def test_messages_are_system_then_user():
    client = _make_mock_client()
    asyncio.run(complete(client, "gpt-4o-mini", "hello"))
    _, kwargs = client.chat.completions.create.call_args
    messages = kwargs["messages"]
    assert len(messages) == 2
    assert messages[0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert messages[1] == {"role": "user", "content": "hello"}


def test_model_is_passed_through():
    client = _make_mock_client()
    asyncio.run(complete(client, "gpt-4o-mini", "hello"))
    _, kwargs = client.chat.completions.create.call_args
    assert kwargs["model"] == "gpt-4o-mini"


def test_returns_content():
    client = _make_mock_client("the answer")
    result = asyncio.run(complete(client, "gpt-4o-mini", "q"))
    assert result == "the answer"


def test_none_content_returns_empty_string():
    client = _make_mock_client(None)
    result = asyncio.run(complete(client, "gpt-4o-mini", "q"))
    assert result == ""
