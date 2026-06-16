# Telegram AI Bot

## What This Is

A public Telegram bot that acts as a general-purpose AI assistant. A user sends a text message, the bot forwards it to the OpenAI (ChatGPT) API via LiteLLM, and the reply is sent straight back in the chat. It runs 24/7 in Docker on a Linux VPS with CI-gated auto-deploy on push to `main`.

## Core Value

Send a message in Telegram, get a useful LLM reply back — reliably, 24/7.

## Requirements

### Validated

- ✓ Bot receives text messages from Telegram users via polling — v1.0
- ✓ Each user message sent to OpenAI as a one-shot prompt; reply returned in Telegram — v1.0
- ✓ `/start` and `/help` commands work — v1.0
- ✓ Friendly error message on LLM failure/timeout — v1.0
- ✓ Slow LLM call does not block other users (async PTB) — v1.0
- ✓ Single polling instance; no 409 conflicts (Compose `--force-recreate`) — v1.0
- ✓ Bot runs in Docker; same image locally and on server — v1.0
- ✓ Bot runs 24/7, auto-restarts on crash or reboot (`restart: unless-stopped`) — v1.0
- ✓ Secrets via environment only; never in git or image (`.dockerignore`) — v1.0
- ✓ Automated `pytest` suite covers message handling and LLM call path — v1.0
- ✓ CI workflow (ruff, mypy, pytest, Docker build) gates every push/PR — v1.0
- ✓ CI-gated auto-deploy pipeline wired (`workflow_run` gate) — v1.0 code-complete; live validation pending VPS

### Active

- [ ] Live pipeline validation on real VPS (04-03 deferred — no server at v1.0 close)
- [ ] OpenAI dashboard billing cap — recommended before public traffic; zero code, one config click

### Out of Scope

- Conversation memory / multi-turn context — one-shot replies only for v1; keeps it simple
- Rate limiting, usage caps, abuse protection — deliberately omitted for v1 (known cost risk; revisit before scaling)
- Webhook delivery — polling is simpler, needs no domain/HTTPS
- Specialized persona / fixed system prompt — general assistant for v1 (sarcastic persona in prompts.py is a flavor choice, not a configurable system)
- Non-text inputs (images, voice, files) — text only for v1
- SHA-pinning of GitHub Actions — tag pins only for now; supply-chain hardening deferred

## Context

- **Shipped v1.0** — 4 phases, 8 plans over 5 days (2026-06-11 → 2026-06-16)
- **Stack:** Python 3.12, python-telegram-bot 22.7, LiteLLM (pinned to 1.88.1), Docker (`python:3.12-slim`), GitHub Actions (GHCR + appleboy/ssh-action)
- **Runtime:** Docker container on a Linux VPS; `restart: unless-stopped` for 24/7 uptime
- **CI/CD:** `ci.yml` gates quality; `deploy.yml` fires via `workflow_run` only after CI passes on `main`
- **Deferred:** Live end-to-end pipeline validation (04-03) pending VPS provisioning. Code pipeline is correct and ready.
- **Cost risk:** Public bot with no rate limits or spend caps. Setting an OpenAI dashboard billing cap is the recommended near-free backstop.
- The user has prior Telegram polling bot experience; polling model is already familiar.
- LiteLLM chosen for provider flexibility: switching to Anthropic/Gemini is a `LLM_MODEL`/`LLM_API_KEY` config change, not a code change.

## Constraints

- **Architecture**: Bot calls LLM via LiteLLM; model and API key configurable via `LLM_MODEL` and `LLM_API_KEY` env vars; default `gpt-4o-mini`.
- **Packaging**: Docker-containerized; same image runs locally and on the server.
- **Hosting**: Linux VPS using polling — no public URL, HTTPS, or domain required.
- **Delivery**: CI/CD via GitHub Actions; deploy gated on green CI.
- **Dependencies**: Telegram Bot API token; LLM API key (OpenAI by default).
- **Cost**: Public access + no usage caps = unbounded LLM spend risk; accepted for v1.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| LLM provider = OpenAI (ChatGPT) by default via LiteLLM | Provider flexibility via config; avoids code changes to switch | ✓ Good — LiteLLM `LLM_MODEL`/`LLM_API_KEY` worked cleanly |
| One-shot replies, no conversation memory | Simplicity for v1 | ✓ Good — correct scope for MVP |
| Public access with no guardrails | Lean v1 | — Pending (cost risk; billing cap recommended) |
| Polling over webhook | No domain/TLS; matches prior experience | ✓ Good — zero infra complexity |
| Linux VPS + Docker over managed platform | Portable, full control | ✓ Good — straightforward deploy |
| `python:3.12-slim` Docker base | glibc + broad wheel support vs Alpine complexity | ✓ Good — wheels installed cleanly |
| Non-root `botuser` in Docker | Security hardening (T-03-02) | ✓ Good — confirmed `uid=100(botuser)` |
| `.dockerignore` as DEP-03 control | Secrets never enter build context | ✓ Good — `.env` confirmed absent from image |
| Pin `litellm==1.88.1`; no transitive pins | Reproducible builds; avoid resolver conflicts | ✓ Good — local and server resolve identically |
| CI/CD: two-file `workflow_run` structure | PLAN was authoritative over RESEARCH single-file suggestion | ✓ Good — `ci.yml` unchanged; `deploy.yml` gated cleanly |
| Deploy: `--pull always --force-recreate` | Guards Compose bug #9259 (stale `:latest`) | ✓ Good — serial stop-old-then-start-new preserved |
| Remove in-script `GITHUB_TOKEN` server login | Revoked at job end; leaks into remote process list | ✓ Good — server-side auth deferred to 04-03 |
| Handler tests use `asyncio.run()` (not pytest-asyncio) | Matches existing test idiom; zero new config | ✓ Good — consistent test style |

## Evolution

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-16 after v1.0 milestone*
