# PRD — Telegram AI Bot
**Version 0.1 (Draft) | Last updated: 2026-06-11**

---

## 1. Overview

A public Telegram bot that acts as a general-purpose AI assistant. A user sends a text message; the bot forwards it to the OpenAI (ChatGPT) API and sends the reply straight back into the chat. The bot is stateless (each message answered independently, no memory), runs 24/7 in Docker on a DigitalOcean droplet, and redeploys automatically via GitHub Actions on every push to `main`.

**Core value:** *Send a message in Telegram, get a useful LLM reply back — reliably, 24/7.*

---

## 2. Problem Statement

People increasingly want quick AI answers, but switching to a separate app or website adds friction. Telegram is already open on most users' phones. A bot that lives inside Telegram makes AI assistance a single message away — no new app to install, no account beyond Telegram itself. This project also serves as a deliberately scoped, shippable MVP that exercises the full lifecycle (API integration, reliability, containerization, automated deployment) on real cloud infrastructure.

---

## 3. Goals

| Goal | Success Metric |
|------|----------------|
| Reply to any user message with AI | User sends text and receives an OpenAI-generated reply in the same chat |
| Stateless one-shot answers | Each message answered fresh, with no memory of prior messages |
| Basic command UX | `/start` and `/help` return helpful text |
| Survive errors gracefully | LLM/network failure yields a friendly message, not a crash or silence |
| Handle concurrent users | A slow reply for one user does not block other users |
| Single-poller safety | Exactly one poller per token; no 409 conflicts in logs |
| Run 24/7 | Bot runs continuously on a DO droplet and auto-restarts on crash/reboot |
| Reproducible deploys | Same Docker image runs locally and on the droplet; push to `main` auto-deploys |
| Secret hygiene | No secrets in git history or the built image |
| Cost-aware default | Default model `gpt-4o-mini` keeps per-message cost low |

---

## 4. Scope

### 4.1 In Scope (v1)

- **Core messaging**: receive text via long polling → one-shot OpenAI call → reply in chat
- **Commands**: `/start` (welcome), `/help` (usage)
- **Reliability baseline**: graceful error replies, async/concurrent handling, single-poller safety
- **Deployment**: Dockerized, 24/7 on a DigitalOcean droplet with auto-restart, secrets via env
- **CI/CD**: push to `main` → GitHub Actions builds the image and deploys to the droplet

### 4.2 Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-provider / swappable LLM abstraction | Wired directly to OpenAI for v1 simplicity; switching providers later is a deliberate code change |
| Webhook delivery | Polling is simpler, needs no domain/HTTPS, and matches prior experience |
| Multimodal input (images, voice, files) | Text-only for v1; large surface area, needs vision/transcription |
| Streaming replies | High complexity; conflicts with reply splitting; deferred indefinitely |
| Group-chat support | Cost/abuse multiplier; wait until rate limiting exists |
| Per-user model selection / inline settings | Depends on conversation state, which v1 does not have |

### 4.3 Deferred (v2)

- **Bot UX**: typing indicator with keepalive; split replies over Telegram's 4096-char limit; non-text input guard
- **Cost & abuse controls**: max-token clamp + dashboard billing cap; per-user rate limiting; global daily usage cap
- **Conversation**: multi-turn memory; configurable persona / system prompt

---

## 5. System Architecture

```
Telegram user
   │  text message
   ▼  (long polling — getUpdates)
┌──────────────────────────────┐
│  Telegram Bot (PTB)          │  main.py / handlers.py
│  - /start, /help             │
│  - text handler (async,      │
│    concurrent_updates=True)  │
└──────────────┬───────────────┘
               │  user text → one-shot prompt
               ▼
┌──────────────────────────────┐
│  OpenAI ChatGPT API          │  model = gpt-4o-mini (env var)
│  (chat completions)          │  timeout + error handling
└──────────────┬───────────────┘
               │  reply text
               ▼
┌──────────────────────────────┐
│  Telegram Bot (send)         │ ─────► user
└──────────────────────────────┘

Deployment / delivery
─────────────────────
  push to `main`
        │
        ▼  GitHub Actions: build image → push to GHCR
        │
        ▼  SSH to droplet → docker compose pull && up -d
┌──────────────────────────────┐
│  DigitalOcean Droplet        │
│  Docker container            │  restart: unless-stopped (24/7)
│  secrets via .env (runtime)  │  stop old container before new (no 409)
└──────────────────────────────┘
```

The bot holds **no application state** — the polling library tracks the Telegram update offset internally, and each message triggers a single, independent OpenAI call.

---

## 6. Features & Requirements

Requirement IDs trace to `.planning/REQUIREMENTS.md` and the roadmap (§10).

### F1 — Core Messaging

| ID | Requirement |
|----|-------------|
| MSG-01 | Receive text messages from any Telegram user via long polling |
| MSG-02 | Send each text message to OpenAI as a one-shot prompt (no conversation history) |
| MSG-03 | Send the LLM's reply back to the user in the same chat |

### F2 — Commands

| ID | Requirement |
|----|-------------|
| CMD-01 | `/start` returns a short welcome explaining what the bot does |
| CMD-02 | `/help` returns brief usage guidance |

### F3 — LLM Integration

| ID | Requirement |
|----|-------------|
| LLM-01 | Call the OpenAI (ChatGPT) API directly to generate each reply; model name configurable via env var, defaulting to `gpt-4o-mini` |

### F4 — Reliability

| ID | Requirement |
|----|-------------|
| REL-01 | On LLM/network error or timeout, reply with a friendly error message instead of going silent or crashing |
| REL-02 | A slow LLM call for one user does not block replies to other users (async / concurrent handling) |
| REL-03 | Exactly one polling instance runs per bot token (no 409 "terminated by other getUpdates" conflicts) |

### F5 — Deployment & Operations

| ID | Requirement |
|----|-------------|
| DEP-01 | Run in a Docker container; the same image runs locally and on the droplet |
| DEP-02 | Run 24/7 on a DigitalOcean droplet and auto-restart on crash or reboot |
| DEP-03 | Provide secrets via environment only — never committed to git or baked into the image |
| DEP-04 | Push to `main` triggers a GitHub Actions pipeline that builds the image and deploys it to the droplet |

---

## 7. Configuration Reference

All configuration is via environment variables (e.g. a `.env` file locally and on the droplet).

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | — | Bot token from @BotFather |
| `OPENAI_API_KEY` | Yes | — | OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | OpenAI model name |
| `OPENAI_REQUEST_TIMEOUT` | No | `60` | Seconds before an LLM call times out |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity |

The bot **fails fast at boot** if a required variable is missing.

---

## 8. Non-Functional Requirements

| NFR | Requirement |
|-----|-------------|
| Reliability | Bot auto-restarts on crash/reboot (Docker `restart: unless-stopped`) |
| Concurrency | Async handling; one slow LLM call does not block other users |
| Security | Secrets via environment only; never in git history or the image |
| Portability | Same Docker image runs locally and on the droplet (Python 3.12 / Linux) |
| Cost control | Low-cost default model (`gpt-4o-mini`); see §9 for the accepted unbounded-cost risk |
| Dependencies | `python-telegram-bot`, `openai` |

---

## 9. Known Limitations & Risks (v1)

Accepted trade-offs of the minimal v1 scope — not defects:

1. **Long replies may fail to send.** Telegram rejects single messages over 4096 characters and v1 does not split replies, so very long answers will fail. *First candidate to fix (v2).*
2. **Unbounded cost.** The bot is public with no rate limits or spend caps. Strangers' messages incur OpenAI token cost with no ceiling. **Recommended near-free mitigation before launch:** set a hard billing cap in the OpenAI dashboard (configuration, not code); the `gpt-4o-mini` default already keeps per-message cost low.
3. **No conversation memory.** Each message is independent; the bot cannot follow up on prior context. *Intentional for v1 (v2).*

---

## 10. Delivery Plan (Roadmap)

Structured as a **Vertical MVP**: deliver a working bot first, then harden, then deploy, then automate. All 13 requirements are mapped; coverage is complete. Execution order: 1 → 2 → 3 → 4.

### Phase 1 — Working AI Bot
**Goal:** Anyone on Telegram can send a text message and get a ChatGPT reply, including `/start` and `/help`.
**Requirements:** MSG-01, MSG-02, MSG-03, CMD-01, CMD-02, LLM-01
**Success criteria:** user receives an OpenAI reply in-chat; each message is a fresh one-shot prompt; `/start` and `/help` work; model from env var; fails fast at boot if token/key missing.

### Phase 2 — Reliability Hardening
**Goal:** The working bot survives real public traffic.
**Requirements:** REL-01, REL-02, REL-03
**Success criteria:** friendly error on OpenAI failure; a slow reply doesn't delay other users; only one poller per token (no 409 in logs).

### Phase 3 — Containerize & Run 24/7
**Goal:** Same image local + droplet, always up, secrets at runtime.
**Requirements:** DEP-01, DEP-02, DEP-03
**Success criteria:** identical image local and on droplet; runs continuously and auto-restarts; secrets via env, absent from git and image.

### Phase 4 — CI/CD Auto-Deploy
**Goal:** Push to `main` builds and deploys automatically.
**Requirements:** DEP-04
**Success criteria:** push triggers build + droplet deploy; droplet runs the new version; old container stops before new starts (no 409 during release).

---

## 11. Key Decisions

| Decision | Rationale |
|----------|-----------|
| LLM provider = OpenAI (ChatGPT) | Mainstream, well-documented API |
| Call OpenAI directly (no provider abstraction) | Simplicity for v1; switching providers later is a deliberate code change |
| Default model = `gpt-4o-mini` | Low cost / fast; mitigates the public-bot cost risk |
| One-shot replies, no memory | Simplicity for v1 |
| Public access, no guardrails | Lean v1 (accepted cost risk; see §9) |
| Polling over webhook | No domain/TLS needed; matches prior self-hosting experience |
| DigitalOcean droplet + Docker | Cheap, portable, full control |
| CI/CD via GitHub Actions | Push-button deploys to the droplet on push to `main` |
| Vertical MVP phase structure | Working bot first, then harden and deploy |

---

## 12. Deployment

### 12.1 Local development (manual)

Run the bot on your own machine to develop and test. This is **not** how it reaches production — it's just the local dev loop.

```bash
# Configure environment
cp .env.example .env
# set TELEGRAM_BOT_TOKEN and OPENAI_API_KEY (OPENAI_MODEL optional)

# Build and run locally with Docker
docker compose up --build
```

> Use a **separate BotFather token** for local testing so the laptop instance and the droplet never share a token (avoids a 409 polling conflict — see REL-03).

### 12.2 Production deployment (automated CI/CD)

Production deploys are **automatic** — no manual SSH or build steps. On every push to `main`, GitHub Actions:

1. Builds the Docker image
2. Pushes it to GHCR (GitHub Container Registry)
3. SSHes into the DigitalOcean droplet
4. Runs `docker compose pull && up -d`, **stopping the old container before starting the new one** (avoids a 409 conflict during release)

The droplet runs the container with `restart: unless-stopped` for 24/7 uptime. App secrets (`TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`) live in the droplet's `.env`; only SSH/registry credentials live in GitHub encrypted secrets.

> One-time droplet setup (install Docker, clone repo / place `docker-compose.yml`, create `.env`) is manual; **every deploy after that is automatic** via the pipeline above.

---

## 13. CI/CD Pipeline

The pipeline lives in `.github/workflows/deploy.yml` and runs on GitHub-hosted runners. It turns a `git push` into a live deploy with no manual steps.

### 13.1 Trigger

- Runs on **push to `main`** only.
- (Optional, recommended) also allow **manual run** via `workflow_dispatch` so you can redeploy without a code change.

### 13.2 Workflow steps

**Job 1 — Build & publish image**
1. **Checkout** the repository (`actions/checkout`).
2. **Log in to GHCR** using the built-in `GITHUB_TOKEN` (no extra secret needed).
3. **Build the Docker image** from the `Dockerfile`.
4. **Tag** the image (e.g. `ghcr.io/<owner>/telegram-ai-bot:latest` and the commit SHA).
5. **Push** the image to GHCR.

**Job 2 — Deploy to droplet** *(runs after Job 1 succeeds)*
6. **SSH into the droplet** (`appleboy/ssh-action`) using stored SSH secrets.
7. **Pull the new image**: `docker compose pull`.
8. **Restart cleanly**: `docker compose up -d` — Compose **stops the old container before starting the new one**, so only one poller runs at a time (avoids the 409 conflict, REL-03).
9. **(Optional) prune** old images to reclaim disk: `docker image prune -f`.

### 13.3 Secrets

| Secret (GitHub repo) | Purpose |
|----------------------|---------|
| `GITHUB_TOKEN` (built-in) | Push image to GHCR |
| `DROPLET_HOST` | Droplet IP / hostname |
| `DROPLET_USER` | SSH user |
| `DROPLET_SSH_KEY` | Private SSH deploy key (ED25519) |

> **App secrets are not in CI.** `TELEGRAM_BOT_TOKEN` and `OPENAI_API_KEY` live only in the droplet's `.env`. The pipeline never sees them — it only moves and restarts the image.

### 13.4 Sketch of `deploy.yml`

```yaml
name: deploy
on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        with:
          push: true
          tags: ghcr.io/${{ github.repository }}:latest

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.DROPLET_HOST }}
          username: ${{ secrets.DROPLET_USER }}
          key: ${{ secrets.DROPLET_SSH_KEY }}
          script: |
            cd ~/telegram-ai-bot
            docker compose pull
            docker compose up -d
            docker image prune -f
```

> This is an illustrative sketch for the PRD, not the final file — exact action versions and paths are finalized during Phase 4.

---

## 14. Open Questions / Pre-Build Checklist

- **OpenAI billing cap value** — operational decision; set in the OpenAI dashboard before going live (Phase 3/4).
- **Concurrency tuning** — `concurrent_updates` and connection-pool sizing for the small droplet should be validated empirically during Phase 1/2.
- **Sign-off** — approval of this PRD is the gate before implementation starts.

---

*Source artifacts: `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/research/`. This PRD is a synthesis for review; the planning files remain the working source of truth.*
