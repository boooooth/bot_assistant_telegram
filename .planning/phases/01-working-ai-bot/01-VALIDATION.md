---
phase: 1
slug: working-ai-bot
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-12
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
>
> **Context:** The formal automated test suite is Phase 4 (QA-01/QA-02). Phase 1 is a
> walking skeleton, so most validation is **manual smoke testing against a live dev bot**,
> plus two cheap pure-function unit tests the planner should add as Wave 0 (config
> fail-fast is a Phase 1 acceptance criterion and is cheap to cover).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (project standard per PRD §13 / QA-01) — not yet installed; Wave 0 installs dev-only |
| **Config file** | none yet — formal suite is Phase 4 |
| **Quick run command** | `pytest -q` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~1 second (two pure-function unit tests) |

---

## Sampling Rate

- **After every task commit:** Run `pytest -q` (the two pure unit tests once Wave 0 adds them) — sub-second
- **After every plan wave:** Run `pytest` plus one manual smoke run against the dev bot
- **Before `/gsd-verify-work`:** Full suite green + manual end-to-end demo passes
- **Max feedback latency:** ~5 seconds (unit); manual demo for transport-bound behaviors

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| (config fail-fast) | TBD | 0 | LLM-01 / config | V14 (config/secrets) | Missing `TELEGRAM_BOT_TOKEN` or `OPENAI_API_KEY` raises `ConfigError` at boot; `OPENAI_MODEL` defaults to `gpt-4o-mini`; secrets read from env only | unit (pure) | `pytest tests/test_config.py -x` | ❌ W0 | ⬜ pending |
| (one-shot messages) | TBD | 0 | MSG-02 | — | — | unit (mock `AsyncOpenAI`) | `pytest tests/test_openai_client.py -x` | ❌ W0 | ⬜ pending |
| (text round-trip) | TBD | 1 | MSG-01 / MSG-03 | — | — | manual smoke | send message to dev bot; observe reply in same chat | N/A | ⬜ pending |
| (start command) | TBD | 1 | CMD-01 | — | — | manual smoke | send `/start`; observe welcome copy | N/A | ⬜ pending |
| (help command) | TBD | 1 | CMD-02 | — | — | manual smoke | send `/help`; observe usage copy | N/A | ⬜ pending |
| (live LLM reply) | TBD | 1 | LLM-01 (live) | — | — | manual smoke | set `OPENAI_MODEL`, send message, confirm sensible AI reply | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs finalized by the planner; rows above reflect the RESEARCH.md req → test map.*

---

## Wave 0 Requirements

- [ ] `tests/test_config.py` — config fail-fast (missing required var → `ConfigError`) and `OPENAI_MODEL` default (LLM-01 / config)
- [ ] `tests/test_openai_client.py` — one-shot `messages` is `[system, user]` only, no history (MSG-02), with mocked `AsyncOpenAI`
- [ ] `tests/conftest.py` — fixture providing a fake env / mocked client
- [ ] `pip install pytest` — dev-only; add to `requirements-dev.txt` so it does not bloat the runtime image

*Optional but recommended: config fail-fast is a Phase 1 acceptance criterion and is cheap to cover. If the planner keeps Phase 1 a pure walking skeleton with zero automated tests (deferring all QA to Phase 4), Wave 0 is "None" and validation is the manual phase-gate demo below.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Bot receives text and replies in same chat | MSG-01 / MSG-03 | Requires live Telegram connection + live OpenAI call; not meaningfully unit-testable without mocking the entire transport (Phase 4 concern) | Run the bot locally against a dev BotFather token; send a text message; observe an AI reply in the same chat |
| `/start` returns welcome copy | CMD-01 | Round-trip needs a live Telegram connection | Send `/start` to the dev bot; observe the welcome message |
| `/help` returns usage copy | CMD-02 | Round-trip needs a live Telegram connection | Send `/help` to the dev bot; observe the usage message |
| Reply is OpenAI-generated, model from env | LLM-01 (live) | Requires a live OpenAI call | Set `OPENAI_MODEL`, send a message, confirm a sensible model-generated reply |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (or are listed Manual-Only with justification)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s (unit)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
