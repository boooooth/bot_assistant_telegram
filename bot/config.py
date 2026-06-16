"""Fail-fast configuration loader.

This is the ONLY module that reads ``os.environ``. Every other module receives a
``Settings`` instance from the composition root (``main.py``). Reading secrets in
one place means a missing/blank required variable fails loudly at boot — a Phase 1
success criterion and the primary Security V14 control — instead of mid-request.
"""

import os
from dataclasses import dataclass

REQUIRED_VARS = ("TELEGRAM_BOT_TOKEN", "LLM_API_KEY")
DEFAULT_LLM_MODEL = "gpt-4o-mini"


class ConfigError(RuntimeError):
    """Raised at boot when required configuration is missing or blank.

    The message names the missing variable KEYS only — never their values — so a
    misconfiguration cannot leak a partially-set secret into logs.
    """


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    llm_api_key: str
    llm_model: str
    allowed_chat_ids: frozenset[int]


def load_settings() -> Settings:
    """Read and validate config from the environment once, at startup.

    Treats unset and blank/whitespace-only required variables as missing.
    ``LLM_MODEL`` is optional and defaults to ``gpt-4o-mini`` (LLM-01).
    ``ALLOWED_CHAT_IDS`` is optional; when unset, all users are allowed.
    """
    missing = [
        name for name in REQUIRED_VARS if not (os.environ.get(name) or "").strip()
    ]
    if missing:
        raise ConfigError(
            f"Missing required environment variable(s): {', '.join(missing)}"
        )

    raw_ids = os.environ.get("ALLOWED_CHAT_IDS", "").strip()
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

    return Settings(
        telegram_bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        llm_api_key=os.environ["LLM_API_KEY"],
        llm_model=os.environ.get("LLM_MODEL", DEFAULT_LLM_MODEL),
        allowed_chat_ids=allowed_chat_ids,
    )
