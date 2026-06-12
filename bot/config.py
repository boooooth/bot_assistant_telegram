"""Fail-fast configuration loader.

This is the ONLY module that reads ``os.environ``. Every other module receives a
``Settings`` instance from the composition root (``main.py``). Reading secrets in
one place means a missing/blank required variable fails loudly at boot — a Phase 1
success criterion and the primary Security V14 control — instead of mid-request.
"""

import os
from dataclasses import dataclass

REQUIRED_VARS = ("TELEGRAM_BOT_TOKEN", "OPENAI_API_KEY")
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


class ConfigError(RuntimeError):
    """Raised at boot when required configuration is missing or blank.

    The message names the missing variable KEYS only — never their values — so a
    misconfiguration cannot leak a partially-set secret into logs.
    """


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    openai_api_key: str
    openai_model: str


def load_settings() -> Settings:
    """Read and validate config from the environment once, at startup.

    Treats unset and blank/whitespace-only required variables as missing.
    ``OPENAI_MODEL`` is optional and defaults to ``gpt-4o-mini`` (LLM-01).
    """
    missing = [
        name for name in REQUIRED_VARS if not (os.environ.get(name) or "").strip()
    ]
    if missing:
        raise ConfigError(
            f"Missing required environment variable(s): {', '.join(missing)}"
        )

    return Settings(
        telegram_bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        openai_api_key=os.environ["OPENAI_API_KEY"],
        openai_model=os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
    )
