# Roadmap: Telegram AI Bot

## Overview

This roadmap delivers a public Telegram bot that turns any user's text message into a one-shot OpenAI (ChatGPT) reply, running reliably 24/7. As a Vertical MVP, the journey front-loads a working, demonstrable bot: Phase 1 gets a real bot replying in Telegram end-to-end (config, direct OpenAI call, polling, `/start` + `/help`). Phase 2 hardens that working bot so it survives real public traffic (graceful errors, concurrent handling, single-poller safety). Phase 3 packages it in Docker and stands it up 24/7 on a DigitalOcean droplet with auto-restart. Phase 4 wraps push-button CI/CD around the proven image so every push to `main` redeploys. Each phase leaves the bot demonstrably more capable than the last.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Working AI Bot** - A real Telegram bot replies to messages via OpenAI, end-to-end
- [ ] **Phase 2: Reliability Hardening** - Bot stays responsive and stable under real public traffic
- [ ] **Phase 3: Containerize & Run 24/7** - Bot runs in Docker on a DigitalOcean droplet, always up
- [ ] **Phase 4: CI/CD Auto-Deploy** - Pushing to `main` builds and deploys the bot automatically

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
  5. The OpenAI model name is read from an environment variable, and the bot fails fast at boot if the Telegram token or OpenAI key is missing
**Plans**: TBD

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
**Goal**: The bot runs as the same Docker image locally and on a DigitalOcean droplet, stays up 24/7, and auto-restarts on crash or reboot — with secrets injected at runtime, never committed or baked into the image.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: DEP-01, DEP-02, DEP-03
**Success Criteria** (what must be TRUE):
  1. The same Docker image runs the bot identically on a local machine and on the droplet
  2. The bot runs continuously on the droplet and comes back automatically after a crash or droplet reboot
  3. The Telegram token and OpenAI key are supplied via environment at runtime, and neither appears in git history nor inside the built image
**Plans**: TBD

### Phase 4: CI/CD Auto-Deploy
**Goal**: A push to `main` automatically builds the image and deploys the new version to the droplet, with no manual SSH or Docker steps.
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: DEP-04
**Success Criteria** (what must be TRUE):
  1. Pushing to `main` triggers a GitHub Actions pipeline that builds the image and deploys it to the droplet
  2. After a successful pipeline run, the droplet is running the newly built version of the bot
  3. The deploy stops the old container before starting the new one, so no 409 polling conflict occurs during release
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Working AI Bot | 0/TBD | Not started | - |
| 2. Reliability Hardening | 0/TBD | Not started | - |
| 3. Containerize & Run 24/7 | 0/TBD | Not started | - |
| 4. CI/CD Auto-Deploy | 0/TBD | Not started | - |
