---
phase: 04-ci-cd-auto-deploy
plan: 03
subsystem: ci-cd
tags: [deferred, vps, ghcr, end-to-end-validation]
requires:
  - .github/workflows/deploy.yml (gated deploy from Plan 02)
  - Linux VPS with SSH access (not yet provisioned)
provides: []
affects: []
tech-stack:
  added: []
  patterns: []
key-files:
  created: []
  modified: []
decisions:
  - "Deferred: no VPS available at time of Phase 4 completion"
  - "Task 1 (GHCR pull credential) and Task 2 (live end-to-end run) require a live server — skipped"
metrics:
  duration: "n/a"
  completed: "2026-06-16"
  tasks: 0
  files: 0
---

# Phase 04 Plan 03: End-to-End Pipeline Validation — DEFERRED

This plan was deferred because no VPS server is available. All code-side work for Phase 4 is complete (Plans 01 and 02); this plan is purely operational verification on live infrastructure.

## What Was Planned

**Task 1 — Durable GHCR pull credential**
Decide and apply how the server authenticates to GHCR for automated pulls (make the package public, or set up a one-time read-only PAT login on the VPS). Recommended: make the GHCR package public.

**Task 2 — Live end-to-end pipeline run**
Push to `main`, verify in GitHub Actions that CI runs first and deploy fires only after CI goes green. SSH into the VPS to confirm the bot container was replaced with the newly built image, the bot responds in Telegram, and no 409 conflict appears in logs.

## Why Deferred

No Linux VPS is provisioned. The plan requires `SERVER_HOST`, `SERVER_USER`, and `SERVER_SSH_KEY` GitHub secrets pointing to a live server, plus a working `compose.yaml` + `.env` on that server.

## Resume When

A VPS is provisioned. Steps to complete:
1. Set the 3 GitHub secrets (`SERVER_HOST`, `SERVER_USER`, `SERVER_SSH_KEY`)
2. Copy `compose.yaml` and `.env` (with `TELEGRAM_BOT_TOKEN` and `LLM_API_KEY`) to `~/telegram-ai-bot/` on the server
3. Make the GHCR package public (GitHub → Packages → bot → Settings → visibility)
4. Push any small change to `main` and follow the verification steps in `04-03-PLAN.md` Task 2

## Self-Check: DEFERRED

- NOT DONE: Live pipeline run (no VPS)
- NOT DONE: GHCR pull credential decision (no VPS)
- Code pipeline (ci.yml + deploy.yml) is complete and correct — awaiting infrastructure
