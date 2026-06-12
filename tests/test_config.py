"""Wave 0 unit tests for the fail-fast config loader (bot/config.py).

Locks the Phase 1 boot acceptance criterion: the bot refuses to start when the
Telegram token or OpenAI key is missing, and OPENAI_MODEL defaults to
gpt-4o-mini (LLM-01).
"""

import pytest

from bot.config import ConfigError, Settings, load_settings


def test_missing_both_required_vars_raises_naming_both(clean_env):
    with pytest.raises(ConfigError) as excinfo:
        load_settings()
    message = str(excinfo.value)
    assert "TELEGRAM_BOT_TOKEN" in message
    assert "OPENAI_API_KEY" in message


def test_missing_only_openai_key_raises_naming_only_it(set_env):
    set_env("TELEGRAM_BOT_TOKEN", "tg-token")
    with pytest.raises(ConfigError) as excinfo:
        load_settings()
    message = str(excinfo.value)
    assert "OPENAI_API_KEY" in message
    assert "TELEGRAM_BOT_TOKEN" not in message


def test_model_defaults_to_gpt_4o_mini_when_unset(set_env):
    set_env("TELEGRAM_BOT_TOKEN", "tg-token")
    set_env("OPENAI_API_KEY", "sk-key")
    settings = load_settings()
    assert isinstance(settings, Settings)
    assert settings.openai_model == "gpt-4o-mini"
    assert settings.telegram_bot_token == "tg-token"
    assert settings.openai_api_key == "sk-key"


def test_model_env_override_is_respected(set_env):
    set_env("TELEGRAM_BOT_TOKEN", "tg-token")
    set_env("OPENAI_API_KEY", "sk-key")
    set_env("OPENAI_MODEL", "gpt-4o")
    settings = load_settings()
    assert settings.openai_model == "gpt-4o"


def test_blank_token_treated_as_missing(set_env):
    set_env("TELEGRAM_BOT_TOKEN", "   ")
    set_env("OPENAI_API_KEY", "sk-key")
    with pytest.raises(ConfigError) as excinfo:
        load_settings()
    assert "TELEGRAM_BOT_TOKEN" in str(excinfo.value)
