# Roadmap: Telegram AI Bot

## Overview

This roadmap delivers a public Telegram bot that turns any user's text message into a one-shot OpenAI (ChatGPT) reply, running reliably 24/7. As a Vertical MVP, the journey front-loads a working, demonstrable bot: Phase 1 gets a real bot replying in Telegram end-to-end (config, direct OpenAI call, polling, `/start` + `/help`). Phase 2 hardens that working bot so it survives real public traffic (graceful errors, concurrent handling, single-poller safety). Phase 3 packages it in Docker and stands it up 24/7 on a Linux VPS with auto-restart. Phase 4 wraps push-button CI/CD around the proven image so every push to `main` redeploys. Each phase leaves the bot demonstrably more capable than the last.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Working AI Bot** - A real Telegram bot replies to messages via OpenAI, end-to-end
- [x] **Phase 2: Reliability Hardening** - Bot stays responsive and stable under real public traffic
- [x] **Phase 3: Containerize & Run 24/7** - Bot runs in Docker on a Linux VPS, always up
- [ ] **Phase 4: CI/CD Auto-Deploy** - Pushing to `main` runs CI checks, then builds and deploys the bot automatically

## Phase Details

### Phase 1: Working AI Bot

**Goal**: Anyone on Telegram can send the bot a text message and get a useful ChatGPT-generated reply back in the same chat, including basic `/start` and `/help` commands.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: MSG-01, MSG-02, MSG-03, CMD-01, CMD-02, LLM-01
**Success Criteria** (what must be TRUE):

  1. A user sends a text message to the bot and receives an OpenAI-generated reply in the same chat
  2. The bot answers each message as a fresh one-shot prompt (no memory of prior messages)
  3. Sending `/start` returns a short welcome explaining what the bot does
  4. Sending `/help` returns brief usage guidance
  5. The OpenAI model name is read from an environment variable, and the bot fails fast at boot if the Telegram token or OpenAI key is missing**Plans**: 2 plans

**Wave 1**

- [ ] 01-01-PLAN.md — Walking-skeleton scaffold + fail-fast config loader + Wave 0 config tests

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 01-02-PLAN.md — End-to-end slice: prompts, direct OpenAI client (MSG-02 test), handlers, composition root, live smoke checkpoint

### Phase 2: Reliability Hardening

**Goal**: The working bot survives real public traffic — it stays responsive when an LLM call is slow, recovers gracefully from errors, and never runs as duplicate pollers.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: REL-01, REL-02, REL-03
**Success Criteria** (what must be TRUE):

  1. When the OpenAI call errors or times out, the user gets a friendly error message instead of silence or a crash
  2. A slow reply for one user does not delay replies to other users sending messages at the same time
  3. Only one polling instance ever runs per bot token, with no 409 "terminated by other getUpdates" conflicts in the logs

**Plans**: TBD

### Phase 3: Containerize & Run 24/7

**Goal**: The bot runs as the same Docker image locally and on a Linux VPS, stays up 24/7, and auto-restarts on crash or reboot — with secrets injected at runtime, never committed or baked into the image.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: DEP-01, DEP-02, DEP-03
**Success Criteria** (what must be TRUE):

  1. The same Docker image runs the bot identically on a local machine and on the server
  2. The bot runs continuously on the server and comes back automatically after a crash or server reboot
  3. The Telegram token and OpenAI key are supplied via environment at runtime, and neither appears in git history nor inside the built image

**Plans**: 2 plans

**Wave 1**

- [x] 03-01-PLAN.md — Buildable hardened image: pin litellm, add .dockerignore, non-root botuser, compose build, fix .env.example env names (DEP-01, DEP-03)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 03-02-PLAN.md — VPS deploy runbook in README: GHCR push, server bootstrap, pull+run, auto-restart/reboot recovery (DEP-01, DEP-02)

### Phase 4: CI/CD Auto-Deploy

**Goal**: A push to `main` runs automated checks (lint, type-check, tests, build) and, when they pass, automatically builds the image and deploys the new version to the server — with no manual SSH or Docker steps.
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: DEP-04, QA-01, QA-02
**Success Criteria** (what must be TRUE):

  1. An automated test suite (`pytest`) covers core message handling and the OpenAI call path
  2. A CI workflow runs lint (`ruff`), type-check (`mypy`), tests, and a Docker build check on every push and pull request, and fails the run if any check fails
  3. Pushing to `main` triggers the pipeline that builds the image and deploys it to the server only when CI passes
  4. After a successful pipeline run, the server is running the newly built version of the bot
  5. The deploy stops the old container before starting the new one, so no 409 polling conflict occurs during release

**Plans**: 3 plans

**Wave 1**

- [x] 04-01-PLAN.md — QA-01 handler tests (tests/test_handlers.py) + pin ruff/mypy in requirements-dev.txt (QA-01, QA-02)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 04-02-PLAN.md — Gate deploy.yml on CI via workflow_run [CI] + if conclusion==success; --pull always --force-recreate; checkout pinned to verified SHA; drop in-script token (DEP-04, QA-02)

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 04-03-PLAN.md — Live pipeline checkpoint: GHCR pull-credential decision + end-to-end verify (CI gate, new version on server, no 409) (DEP-04, QA-02)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Working AI Bot | 2/2 | Complete | 2026-06-12 |
| 2. Reliability Hardening | 1/1 | Complete | 2026-06-14 |
| 3. Containerize & Run 24/7 | 2/2 | Complete | 2026-06-15 |
| 4. CI/CD Auto-Deploy | 2/3 | In Progress|  |
