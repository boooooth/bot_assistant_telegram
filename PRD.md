# PRD — Telegram AI Bot
**Version 0.1 (Draft) | Last updated: 2026-06-11**

---

## 1. Overview

A public Telegram bot that acts as a general-purpose AI assistant. A user sends a text message; the bot forwards it to the OpenAI (ChatGPT) API and sends the reply straight back into the chat. The bot is stateless (each message answered independently, no memory), runs 24/7 in Docker on a Linux VPS, and redeploys automatically via GitHub Actions on every push to `main`.

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
| Run 24/7 | Bot runs continuously on a Linux VPS and auto-restarts on crash/reboot |
| Reproducible deploys | Same Docker image runs locally and on the server; push to `main` auto-deploys |
| Secret hygiene | No secrets in git history or the built image |
| Cost-aware default | Default model `gpt-4o-mini` keeps per-message cost low |

---

## 4. Scope

### 4.1 In Scope (v1)

- **Core messaging**: receive text via long polling → one-shot OpenAI call → reply in chat
- **Commands**: `/start` (welcome), `/help` (usage)
- **Reliability baseline**: graceful error replies, async/concurrent handling, single-poller safety
- **Deployment**: Dockerized, 24/7 on a Linux VPS with auto-restart, secrets via env
- **CI/CD**: CI checks (lint, type-check, tests, build) on every push/PR; push to `main` → GitHub Actions builds the image and deploys to the server when CI passes
- **Quality**: automated test suite + lint/type-check gating deployment

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
        ▼  SSH to server → docker compose pull && up -d
┌──────────────────────────────┐
│  Linux VPS (any provider)    │
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
| DEP-01 | Run in a Docker container; the same image runs locally and on the server |
| DEP-02 | Run 24/7 on a Linux VPS and auto-restart on crash or reboot |
| DEP-03 | Provide secrets via environment only — never committed to git or baked into the image |
| DEP-04 | Push to `main` triggers a GitHub Actions pipeline that builds the image and deploys it to the server |

### F6 — Quality & CI

| ID | Requirement |
|----|-------------|
| QA-01 | An automated test suite (`pytest`) covers core message handling and the OpenAI call path |
| QA-02 | A GitHub Actions CI workflow runs lint (`ruff`), type-check (`mypy`), tests, and a Docker build check on every push and pull request; deployment proceeds only when CI passes |

---

## 7. Configuration Reference

All configuration is via environment variables (e.g. a `.env` file locally and on the server).

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
| Portability | Same Docker image runs locally and on the server (Python 3.12 / Linux) |
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
**Goal:** Same image local + server, always up, secrets at runtime.
**Requirements:** DEP-01, DEP-02, DEP-03
**Success criteria:** identical image local and on server; runs continuously and auto-restarts; secrets via env, absent from git and image.

### Phase 4 — CI/CD Auto-Deploy
**Goal:** Push to `main` runs CI checks, then builds and deploys automatically when they pass.
**Requirements:** DEP-04, QA-01, QA-02
**Success criteria:** `pytest` suite covers core handling and the OpenAI path; CI runs lint/type-check/tests/build on every push & PR and fails on any error; push to `main` builds + deploys only when CI is green; server runs the new version; old container stops before new starts (no 409 during release).

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
| Linux VPS + Docker | Portable, full control; any provider works |
| CI/CD via GitHub Actions | Push-button deploys to the server on push to `main` |
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

> Use a **separate BotFather token** for local testing so the laptop instance and the server never share a token (avoids a 409 polling conflict — see REL-03).

### 12.2 Production deployment (automated CI/CD)

Production deploys are **automatic** — no manual SSH or build steps. On every push to `main`, GitHub Actions:

1. Builds the Docker image
2. Pushes it to GHCR (GitHub Container Registry)
3. SSHes into the Linux VPS
4. Runs `docker compose pull && up -d`, **stopping the old container before starting the new one** (avoids a 409 conflict during release)

The server runs the container with `restart: unless-stopped` for 24/7 uptime. App secrets (`TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`) live in the server's `.env`; only SSH/registry credentials live in GitHub encrypted secrets.

> One-time server setup (install Docker, clone repo / place `docker-compose.yml`, create `.env`) is manual; **every deploy after that is automatic** via the pipeline above.

---

## 13. CI/CD Pipeline

CI and CD are split into **two GitHub Actions workflow files** under `.github/workflows/`:

| File | Pipeline | Runs on | Purpose |
|------|----------|---------|---------|
| `ci.yml` | **CI** — Continuous Integration | every push + pull request | Quality gate: lint, type-check, run tests, verify the image builds |
| `deploy.yml` | **CD** — Continuous Deployment | push to `main` | Build the image, push to GHCR, deploy to the server |

The split reflects their jobs: **CI proves the code is good; CD ships it.** CD runs only on `main` and is gated so it deploys only when CI is green.

### 13.1 CI — `ci.yml`

**Trigger:** every push and every pull request, so problems are caught before code reaches `main`.

**Steps (the checks most projects run):**
1. **Checkout** the repo (`actions/checkout`).
2. **Set up Python 3.12** (`actions/setup-python`).
3. **Install dependencies** (`pip install -r requirements.txt` plus dev tools).
4. **Lint** — `ruff` (style and common-error checks).
5. **Type-check** — `mypy` (catches type mistakes before runtime).
6. **Run tests** — `pytest` (unit tests for handlers and the OpenAI call).
7. **Build check** — `docker build` to confirm the image still builds.

If any step fails the run goes red and, for pull requests, blocks the merge.

Sketch of `ci.yml`:
```yaml
name: ci
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt ruff mypy pytest
      - run: ruff check .
      - run: mypy .
      - run: pytest
      - run: docker build -t telegram-ai-bot:ci .
```

### 13.2 CD — `deploy.yml`

**Trigger:** push to `main` (optionally also a manual run via `workflow_dispatch`). Gated on CI passing.

**Job 1 — Build & publish image**
1. **Checkout** the repository.
2. **Log in to GHCR** using the built-in `GITHUB_TOKEN` (no extra secret needed).
3. **Build the Docker image** from the `Dockerfile`.
4. **Tag** the image (`:latest` + commit SHA).
5. **Push** the image to GHCR.

**Job 2 — Deploy to server** *(runs after Job 1 succeeds)*
6. **SSH into the server** (`appleboy/ssh-action`) using stored SSH secrets.
7. **Pull the new image**: `docker compose pull`.
8. **Restart cleanly**: `docker compose up -d` — Compose **stops the old container before starting the new one**, so only one poller runs at a time (avoids the 409 conflict, REL-03).
9. **(Optional) prune** old images: `docker image prune -f`.

Sketch of `deploy.yml`:
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
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SERVER_SSH_KEY }}
          script: |
            cd ~/telegram-ai-bot
            docker compose pull
            docker compose up -d
            docker image prune -f
```

### 13.3 Secrets

| Secret (GitHub repo) | Used by | Purpose |
|----------------------|---------|---------|
| `GITHUB_TOKEN` (built-in) | `deploy.yml` | Push image to GHCR |
| `SERVER_HOST` | `deploy.yml` | Server IP / hostname |
| `SERVER_USER` | `deploy.yml` | SSH user |
| `SERVER_SSH_KEY` | `deploy.yml` | Private SSH deploy key (ED25519) |

`ci.yml` needs **no secrets** — it only checks code. App secrets (`TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`) live only in the server's `.env`; **neither pipeline ever sees them**.

### 13.4 How CI gates CD

CD should run only when CI is green. Two common ways:
- **Two files (shown above)** — `deploy.yml` is triggered after `ci.yml` succeeds via a `workflow_run` trigger, or branch protection on `main` requires CI to pass before merge.
- **One file** — fold the CI checks into `deploy.yml` as a first `test` job that the `build`/`deploy` jobs declare with `needs: test`.

> These are illustrative sketches for the PRD, not the final files — exact action versions, the gating mechanism, and paths are finalized during Phase 4. CI assumes a test suite and lint/type tooling exist (see §14).

---

## 14. Open Questions / Pre-Build Checklist

- **OpenAI billing cap value** — operational decision; set in the OpenAI dashboard before going live (Phase 3/4).
- **Concurrency tuning** — `concurrent_updates` and connection-pool sizing for the server should be validated empirically during Phase 1/2.
- **CI tooling choices.** CI (QA-01, QA-02, now in v1 scope under Phase 4) commits the project to a `pytest` test suite and `ruff`/`mypy` tooling. The exact lint/type-check strictness and the minimum test coverage to enforce are finalized during Phase 4.
- **Sign-off** — approval of this PRD is the gate before implementation starts.

---

*Source artifacts: `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/research/`. This PRD is a synthesis for review; the planning files remain the working source of truth.*
