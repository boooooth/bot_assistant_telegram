---
phase: 02-reliability-hardening
plan: 01
status: complete
completed: 2026-06-14
---

# Summary: Add LiteLLM Timeout

## What Was Built

Added `timeout=30` to the `litellm.acompletion()` call in `bot/openai_client.py`.

If OpenAI does not respond within 30 seconds, LiteLLM raises an exception. The existing `except Exception` block in `handlers.py` catches it and sends the user a friendly error message instead of waiting forever.

## Requirements Met

- **REL-01** — friendly error on LLM failure: already handled by `try/except` in `handlers.py`; timeout ensures it triggers within 30s maximum
- **REL-02** — slow calls don't block other users: satisfied for free by PTB's async architecture and Python's asyncio event loop
- **REL-03** — single poller, no 409 conflicts: deployment concern; addressed by Phase 3 Docker/Compose setup
