# Product Requirements Document — Telegram AI Bot

**Status:** Draft
**Date:** 2026-06-11

> This PRD consolidates the project's vision, scope, requirements, technical approach, and phased delivery plan into a single document **for review before implementation begins**. It is derived from the detailed planning artifacts in `.planning/` (PROJECT.md, REQUIREMENTS.md, ROADMAP.md, and domain research).

---

## 1. Summary

A **public Telegram bot** that acts as a general-purpose AI assistant. A user sends a text message in Telegram; the bot forwards it to the **OpenAI (ChatGPT) API**, and the reply is sent straight back into the chat. The bot is stateless (each message answered independently), runs **24/7 in Docker on a DigitalOcean droplet**, and redeploys automatically via a CI/CD pipeline on every push to `main`.

**Core value:** *Send a message in Telegram, get a useful LLM reply back — reliably, 24/7.*

---

## 2. Problem & Motivation

People increasingly want quick AI answers, but switching to a separate app or website adds friction. Telegram is already open on most users' phones. A bot that lives inside Telegram makes AI assistance a single message away, with no new app to install and no account to create beyond Telegram itself.

This project is also a deliberately **scoped, shippable MVP** — small enough to build and deploy end-to-end, while exercising the full lifecycle (API integration, reliability, containerization, automated deployment) on real cloud infrastructure.

---

## 3. Target Users

- **Primary:** Any Telegram user who messages the bot. The bot is **public** — anyone who finds it can use it.
- **Operator:** The project owner, who runs and pays for the bot.

There are no user accounts, roles, or onboarding beyond Telegram itself.

---

## 4. Scope

### 4.1 In scope (v1)

- Receiving text messages and replying with an OpenAI-generated answer (one-shot, no memory)
- `/start` and `/help` commands
- Baseline reliability: graceful error handling, concurrent request handling, single-poller safety
- Dockerized deployment to a DigitalOcean droplet, running 24/7
- Automated CI/CD deployment on push to `main`

### 4.2 Out of scope (explicitly excluded)

| Excluded | Reason |
|----------|--------|
| Multi-provider / swappable LLM abstraction | Wired directly to OpenAI for v1 simplicity; switching providers later is a deliberate code change |
| Webhook delivery | Polling is simpler, needs no domain/HTTPS, and matches prior experience |
| Multimodal input (images, voice, files) | Text-only for v1; large surface area, needs vision/transcription |
| Streaming replies | High complexity; conflicts with reply splitting; deferred indefinitely |
| Group-chat support | Cost/abuse multiplier; wait until rate limiting exists |
| Per-user model selection / inline settings | Depends on conversation state, which v1 does not have |

### 4.3 Deferred to a later release (v2)

- **Bot UX:** typing indicator with keepalive; splitting replies over Telegram's 4096-char limit; non-text input guard
- **Cost & abuse controls:** cheap-model default + max-token clamp + billing cap; per-user rate limiting; global daily usage cap
- **Conversation:** multi-turn memory; configurable persona / system prompt

---

## 5. Functional Requirements

Each requirement is user-centric, atomic, and testable. IDs are referenced by the roadmap (Section 9).

### Core Messaging
- **MSG-01** — Bot receives text messages from any Telegram user via long polling.
- **MSG-02** — Each text message is sent to OpenAI as a one-shot prompt (no conversation history).
- **MSG-03** — The LLM's reply is sent back to the user in the same chat.

### Commands
- **CMD-01** — `/start` returns a short welcome explaining what the bot does.
- **CMD-02** — `/help` returns brief usage guidance.

### LLM Integration
- **LLM-01** — Bot calls the OpenAI (ChatGPT) API directly to generate each reply; the model name is configurable via an environment variable, defaulting to `gpt-4o-mini`.

### Reliability (non-functional baseline)
- **REL-01** — On LLM/network error or timeout, the bot replies with a friendly error message instead of going silent or crashing.
- **REL-02** — A slow LLM call for one user does not block replies to other users (async / concurrent handling).
- **REL-03** — Exactly one polling instance runs per bot token (no 409 "terminated by other getUpdates" conflicts).

### Deployment & Operations
- **DEP-01** — The bot runs in a Docker container; the same image runs locally and on the droplet.
- **DEP-02** — The bot runs 24/7 on a DigitalOcean droplet and auto-restarts on crash or reboot.
- **DEP-03** — Secrets (Telegram token, OpenAI key) are provided via environment only — never committed to git or baked into the image.
- **DEP-04** — Pushing to `main` triggers a GitHub Actions pipeline that builds the image and deploys it to the droplet.

**Total: 13 v1 requirements.**

---

## 6. Technical Approach

The recommended stack and architecture below are backed by domain research (full findings in `.planning/research/`, overall confidence: **HIGH**).

### 6.1 Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | **Python 3.12** | Dominant ecosystem for Telegram bots + LLM SDKs; widest battle-tested library support |
| Telegram | **python-telegram-bot 22.7** | Owns the polling loop (`getUpdates`, offset tracking, retries, graceful shutdown); built-in `run_polling()` matches the polling decision exactly |
| LLM | **openai 2.41.1** (`AsyncOpenAI`), default model **`gpt-4o-mini`** | Official async SDK; integrates cleanly with the bot's asyncio loop. Cheap, fast default keeps per-message cost low (changeable via env var) |
| Packaging | **Docker** (`python:3.12-slim`) | Same image runs locally and in production; glibc compatibility, prebuilt wheels |
| Hosting | **DigitalOcean droplet** (~$4–6/mo) | Cheap, full control; `restart: unless-stopped` for 24/7 uptime |
| CI/CD | **GitHub Actions → GHCR → SSH deploy** | Build + push image to GitHub Container Registry, then deploy to droplet via SSH; canonical pattern |

### 6.2 How it works (data flow)

```
Telegram user → (long polling) → Bot handler → OpenAI ChatGPT API → reply text → Telegram user
```

The bot is **stateless per message**: it holds no conversation history. The polling library manages the connection to Telegram; each incoming message triggers a single OpenAI API call whose response is returned to the user.

### 6.3 Reliability design

- **Async throughout** with concurrent update handling, so one slow OpenAI call (2–30s) does not block other users (REL-02).
- **Typed error handling** on the OpenAI call: explicit request timeout, retry on transient/rate-limit errors with backoff, friendly fallback reply on final failure (REL-01).
- **Single-instance discipline:** exactly one poller per token; a separate bot token for local development; deploys stop the old container before starting the new one (REL-03).

### 6.4 Deployment & operations

- Single-stage `python:3.12-slim` image; secrets injected at runtime via environment (never in git or the image) (DEP-03).
- `docker compose` with `restart: unless-stopped` for crash/reboot survival (DEP-02).
- GitHub Actions builds on push to `main`, pushes to GHCR, and deploys to the droplet over SSH, stopping the old container before starting the new (DEP-04, and avoids REL-03 conflicts during release).

---

## 7. Known Limitations & Risks (v1)

These are **accepted trade-offs** of the minimal v1 scope, not defects:

1. **Long replies may fail to send.** Telegram rejects single messages over 4096 characters, and v1 does not split replies. Very long answers will fail. *First candidate to fix (v2: UX-02).*
2. **Unbounded cost.** The bot is public with no rate limits or spend caps. Strangers' messages incur OpenAI token cost with no ceiling. **Recommended near-free mitigation before launch:** set a hard billing cap in the OpenAI dashboard (configuration, not code) and use a low-cost model by default.
3. **No conversation memory.** Each message is independent; the bot cannot follow up on prior context. *Intentional for v1 (v2: CONV-01).*

---

## 8. Success Metrics (Definition of Done for v1)

The v1 release is "done" when:

- A real Telegram user can message the public bot and reliably receive a correct OpenAI-generated reply.
- The bot runs unattended 24/7 on the droplet and recovers automatically from crashes/reboots.
- A push to `main` deploys the new version with no manual server steps.
- No secrets appear in git history or the built image.

---

## 9. Phased Delivery Plan (Roadmap)

Structured as a **Vertical MVP**: deliver a working bot first, then harden, then deploy, then automate. Each phase leaves the bot demonstrably more capable. All 13 requirements are mapped; coverage is complete.

### Phase 1 — Working AI Bot
**Goal:** Anyone on Telegram can send a text message and get a useful ChatGPT reply, including `/start` and `/help`.
**Requirements:** MSG-01, MSG-02, MSG-03, CMD-01, CMD-02, LLM-01
**Success criteria:**
1. A user sends a text message and receives an OpenAI-generated reply in the same chat.
2. Each message is answered as a fresh one-shot prompt (no memory).
3. `/start` returns a welcome; `/help` returns usage guidance.
4. The model name is read from an env var; the bot fails fast at boot if the token or key is missing.

### Phase 2 — Reliability Hardening
**Goal:** The working bot survives real public traffic — responsive under slow calls, recovers from errors, never runs duplicate pollers.
**Requirements:** REL-01, REL-02, REL-03
**Success criteria:**
1. On OpenAI error/timeout, the user gets a friendly message instead of silence or a crash.
2. A slow reply for one user does not delay other users.
3. Only one poller runs per token — no 409 conflicts in the logs.

### Phase 3 — Containerize & Run 24/7
**Goal:** The same Docker image runs locally and on the droplet, stays up 24/7, auto-restarts, with secrets injected at runtime.
**Requirements:** DEP-01, DEP-02, DEP-03
**Success criteria:**
1. The same image runs identically locally and on the droplet.
2. The bot runs continuously and auto-restarts after crash/reboot.
3. Secrets are supplied via env at runtime and appear neither in git history nor in the image.

### Phase 4 — CI/CD Auto-Deploy
**Goal:** A push to `main` automatically builds and deploys the new version, no manual SSH/Docker steps.
**Requirements:** DEP-04
**Success criteria:**
1. Pushing to `main` triggers a GitHub Actions build + droplet deploy.
2. After a successful run, the droplet runs the newly built version.
3. The old container stops before the new one starts (no 409 during release).

**Execution order:** 1 → 2 → 3 → 4.

---

## 10. Key Decisions

| Decision | Rationale |
|----------|-----------|
| LLM provider = OpenAI (ChatGPT) | Owner's choice; mainstream, well-documented API |
| Call OpenAI API directly (no provider abstraction) | Simplicity for v1; reverses an earlier adapter plan. Swapping providers later is a deliberate code change |
| One-shot replies, no conversation memory | Simplicity for v1 |
| Public access with no guardrails | Owner wants a lean v1 (accepted cost risk; see §7) |
| Polling over webhook | No domain/TLS needed; matches owner's prior self-hosting experience |
| DigitalOcean droplet + Docker over App Platform | Cheap, portable, full control |
| CI/CD via GitHub Actions in v1 | Push-button deploys to the droplet on push to `main` |
| Vertical MVP phase structure | Get a working bot first, then harden and deploy |

---

## 11. Open Questions / Pre-Build Checklist

- **OpenAI billing cap value** — operational decision; should be set in the OpenAI dashboard before the bot goes live (Phase 3/4).
- **Default model** — decided: `gpt-4o-mini` (low cost/fast), set via env var; revisit if answer quality proves insufficient.
- **Concurrency tuning** — `concurrent_updates` and connection-pool sizing for the small droplet should be validated empirically during Phase 1/2.
- **Sign-off** — approval of this PRD is the gate before implementation starts.

---

*Source artifacts: `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/research/`. This PRD is a synthesis for review; the planning files remain the working source of truth.*
