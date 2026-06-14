# Telegram AI Bot

## What This Is

A public Telegram bot that acts as a general-purpose AI assistant. A user sends a text message, the bot forwards it to the OpenAI (ChatGPT) API, and the reply is sent straight back in the chat. It's for anyone on Telegram who wants quick AI answers without leaving the app.

## Core Value

Send a message in Telegram, get a useful LLM reply back — reliably, 24/7.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

(None yet — ship to validate)

### Active

<!-- Current scope. Building toward these. -->

- [ ] Bot receives text messages from Telegram users via polling
- [ ] Each user message is sent to an LLM (OpenAI by default, via LiteLLM) and the reply is returned in Telegram (one-shot, no history)
- [ ] Bot runs containerized with Docker and stays up 24/7 on a Linux VPS
- [ ] Automated tests (`pytest`) plus a CI workflow (lint, type-check, tests, build) gate every push/PR
- [ ] CI/CD pipeline (GitHub Actions) builds the image and deploys to the server on push to `main` when CI passes

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Conversation memory / multi-turn context — one-shot replies only for v1; keeps it simple
- Rate limiting, usage caps, abuse protection — deliberately omitted for v1 (known cost risk; revisit before scaling)
- Webhook delivery — polling is simpler, needs no domain/HTTPS, and matches prior experience
- Specialized persona / fixed system prompt — general assistant for v1
- Non-text inputs (images, voice, files) — text only for v1

## Context

- The user has previously self-hosted a "normal" (polling) Telegram bot, so the polling model is already familiar — no new delivery concepts to learn.
- The bot calls OpenAI (ChatGPT) via LiteLLM. LiteLLM was chosen so that switching providers is a config change (`LLM_MODEL`, `LLM_API_KEY`), not a code change — while keeping the call site simple and self-contained.
- The bot is public with no guardrails, so messages from strangers incur OpenAI token cost. This is an accepted, known risk for v1.
- Deployment target is a Linux VPS (any provider: Oracle Cloud, DigitalOcean, etc.) running the bot in Docker; the same container runs locally for dev/prod parity.

## Constraints

- **Architecture**: Bot calls an LLM provider (OpenAI by default) via LiteLLM. Model and API key configurable via `LLM_MODEL` and `LLM_API_KEY` env vars; default model `gpt-4o-mini` (low cost/fast).
- **Packaging**: Docker-containerized so the same image runs locally and on the server.
- **Hosting**: Linux VPS using polling — no public URL, HTTPS, or domain required.
- **Delivery**: CI/CD via GitHub Actions deploying to the server on push to `main`.
- **Dependencies**: Telegram Bot API token; LLM API key (OpenAI by default).
- **Cost**: Public access + no usage caps = unbounded LLM spend risk; accepted for v1.

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project lifecycle. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| LLM provider = OpenAI (ChatGPT) by default | User's choice; mainstream, well-documented API. Configurable via `LLM_MODEL` env var. | — Pending |
| Use LiteLLM to call the LLM | Enables provider switching via config (`LLM_MODEL`, `LLM_API_KEY`) without code changes. Pinned to a specific version for reproducible builds. | — Pending |
| One-shot replies, no conversation memory | Simplicity for v1 | — Pending |
| Public access with no guardrails | User wants a lean v1 | — Pending (cost risk) |
| Polling over webhook | No domain/TLS needed; matches user's prior self-hosting experience | — Pending |
| Linux VPS + Docker over managed platform | Portable, full control; any provider works (Oracle Cloud, DigitalOcean, etc.) | — Pending |
| CI/CD via GitHub Actions in v1 | Push-button deploys to the server on push to `main` | — Pending |
| Add tests + CI gate (pytest, ruff, mypy) in v1 | Catch breakage before it deploys; CI must pass before release | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-11 — added tests + CI gate to v1 scope*
