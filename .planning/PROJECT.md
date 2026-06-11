# Telegram AI Bot

## What This Is

A public Telegram bot that acts as a general-purpose AI assistant. A user sends a text message, the bot forwards it to an LLM, and the LLM's reply is sent straight back in the chat. It's for anyone on Telegram who wants quick AI answers without leaving the app.

## Core Value

Send a message in Telegram, get a useful LLM reply back — reliably, 24/7.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

(None yet — ship to validate)

### Active

<!-- Current scope. Building toward these. -->

- [ ] Bot receives text messages from Telegram users via polling
- [ ] Each user message is sent to an LLM and the reply is returned in Telegram (one-shot, no history)
- [ ] LLM provider is swappable via an env var through a hand-rolled adapter, defaulting to OpenAI (ChatGPT)
- [ ] Bot runs containerized with Docker and stays up 24/7 on a DigitalOcean droplet
- [ ] CI/CD pipeline (GitHub Actions) builds the image and deploys to the droplet on push to `main`

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Conversation memory / multi-turn context — one-shot replies only for v1; keeps it simple
- Rate limiting, usage caps, abuse protection — deliberately omitted for v1 (known cost risk; revisit before scaling)
- Webhook delivery — polling is simpler, needs no domain/HTTPS, and matches prior experience
- Specialized persona / fixed system prompt — general assistant for v1
- Non-text inputs (images, voice, files) — text only for v1

## Context

- The user has previously self-hosted a "normal" (polling) Telegram bot, so the polling model is already familiar — no new delivery concepts to learn.
- Provider-swap is an explicit priority: OpenAI is the default now, but switching to Claude or another provider should be a one-line env-var change plus an API key. This drives the adapter design.
- The bot is public with no guardrails, so messages from strangers incur OpenAI token cost. This is an accepted, known risk for v1.
- Deployment target is a DigitalOcean droplet (a Linux VPS) running the bot in Docker; the same container runs locally for dev/prod parity.

## Constraints

- **Architecture**: LLM access sits behind a thin, hand-rolled adapter (one internal interface, per-provider implementations selected by env var). No heavy multi-provider framework (e.g. LiteLLM) for v1.
- **Packaging**: Docker-containerized so the same image runs locally and on the droplet.
- **Hosting**: DigitalOcean droplet using polling — no public URL, HTTPS, or domain required.
- **Delivery**: CI/CD via GitHub Actions deploying to the droplet on push to `main`.
- **Dependencies**: Telegram Bot API token; OpenAI API key (provider-swappable).
- **Cost**: Public access + no usage caps = unbounded LLM spend risk; accepted for v1.

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project lifecycle. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| LLM provider = OpenAI (ChatGPT) | User's choice; mainstream, well-documented API | — Pending |
| Provider behind a hand-rolled adapter (not LiteLLM) | Fewer dependencies for a small bot; still swappable via env var | — Pending |
| One-shot replies, no conversation memory | Simplicity for v1 | — Pending |
| Public access with no guardrails | User wants a lean v1 | — Pending (cost risk) |
| Polling over webhook | No domain/TLS needed; matches user's prior self-hosting experience | — Pending |
| DigitalOcean droplet + Docker over App Platform | Cheap (~$4–6/mo), portable, full control | — Pending |
| CI/CD via GitHub Actions in v1 | Push-button deploys to the droplet on push to `main` | — Pending |

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
*Last updated: 2026-06-11 after initialization*
