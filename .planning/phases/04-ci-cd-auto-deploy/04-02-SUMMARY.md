---
phase: 04-ci-cd-auto-deploy
plan: 02
subsystem: ci-cd
tags: [github-actions, workflow_run, deploy, docker-compose, ghcr, ssh]
requires:
  - .github/workflows/ci.yml (name: CI — the gating workflow, unchanged)
  - compose.yaml (server-side service `bot`, restart: unless-stopped)
provides:
  - .github/workflows/deploy.yml gated on CI completion via workflow_run
  - CI-verified-commit deploy (checkout pinned to workflow_run.head_sha)
  - safe release semantics (--pull always --force-recreate; image prune)
affects:
  - VPS docker compose deploy (appleboy/ssh-action)
tech-stack:
  added: []
  patterns:
    - "workflow_run [CI] types:[completed] branches:[main] gate with if: conclusion == 'success'"
    - "checkout ref pinned to github.event.workflow_run.head_sha || github.sha"
    - "docker compose up -d --pull always --force-recreate (compose #9259 remedy)"
key-files:
  created: []
  modified:
    - .github/workflows/deploy.yml
decisions:
  - "Kept the two-file structure (ci.yml unchanged + deploy.yml workflow_run) per PLAN frontmatter, not the single-file ci-cd.yml mentioned in RESEARCH summary — the PLAN tasks/must_haves are authoritative"
  - "Used `cd ~/telegram-ai-bot` as the server deploy dir per Phase 3 runbook (A4); Plan 03 checkpoint confirms/corrects if it differs"
  - "Removed in-script GITHUB_TOKEN login; server-side GHCR auth handled durably out-of-band (Plan 03 checkpoint)"
metrics:
  duration: "~5 min"
  completed: "2026-06-15"
  tasks: 1
  files: 1
---

# Phase 04 Plan 02: Gate Deploy on CI via workflow_run Summary

Rewrote `.github/workflows/deploy.yml` so the deploy job fires only after the `CI` workflow completes successfully on `main` (or on manual `workflow_dispatch`), builds the image from the exact CI-verified commit SHA, and deploys with safe Compose release semantics. `ci.yml` is untouched. This closes the headline DEP-04/QA-02 gap where the old `deploy.yml` had `needs: []` and triggered simultaneously with CI on every push to `main`, shipping even when CI failed.

## What Was Built

**Task 1 — deploy.yml gated on CI (`fix(04-02)`, commit b2b5f3f)**

Trigger and gating:
- Trigger changed from `on: push: branches: [main]` to:
  ```yaml
  on:
    workflow_run:
      workflows: [CI]
      types: [completed]
      branches: [main]
    workflow_dispatch:
  ```
  (`CI` matches the `name:` field in `ci.yml` exactly — `workflow_run` references workflows by name, not filename.)
- Added job-level condition `if: github.event.workflow_run.conclusion == 'success' || github.event_name == 'workflow_dispatch'` so the deploy only runs on a green CI run, while still permitting manual redeploys.
- Removed `needs: []` (single job; not required).

Build from the verified commit:
- `actions/checkout@v4` now pins `ref: ${{ github.event.workflow_run.head_sha || github.sha }}`, so the built image matches the commit CI actually ran on rather than whatever HEAD is at trigger time.

Three deploy-script fixes (appleboy/ssh-action@v1):
1. Removed the `echo ${{ secrets.GITHUB_TOKEN }} | docker login ghcr.io ...` line entirely (T-04-02): the job token is revoked at job end and interpolating it into the remote shell leaks it into the server process list. Server-side GHCR auth is handled durably out-of-band (Plan 03 checkpoint).
2. Replaced `docker compose pull` + `docker compose up -d` with the single `docker compose up -d --pull always --force-recreate` (T-04-05 / compose #9259) — guarantees a fresh pull and serial stop-old-then-start-new container replacement, avoiding a 409 dual-poller during release.
3. Appended `docker image prune -f` to remove the now-dangling old image layer.

Preserved as specified: job name `deploy`, `permissions: { contents: read, packages: write }`, action versions `login-action@v3` / `build-push-action@v6` / `ssh-action@v1`, build tag `ghcr.io/${{ github.repository }}/bot:latest`, and the build-side GHCR login keeping `password: ${{ secrets.GITHUB_TOKEN }}` (correct on the runner). Server deploy dir is `~/telegram-ai-bot`.

## Verification Results

Automated YAML + acceptance checks (all pass):
- `deploy.yml` parses as valid YAML.
- `workflow_run.workflows == ['CI']`, `types` contains `completed`, `branches` contains `main`.
- `workflow_dispatch` present.
- deploy job has no `needs`; `if` contains `github.event.workflow_run.conclusion`.
- checkout step contains `ref: ${{ github.event.workflow_run.head_sha || github.sha }}`.
- script contains `docker compose up -d --pull always --force-recreate` and `docker image prune -f`.
- SSH script block does NOT contain `secrets.GITHUB_TOKEN` (build-side login retains it, as intended).
- No standalone `docker compose pull` line.
- `ci.yml` has `name: CI` and shows no git diff — confirmed unchanged.

Note: the plan's verification snippet accessed `d['on']`, but PyYAML (YAML 1.1) coerces the bare key `on:` to the boolean `True`. This is a test-harness artifact, not a file defect — the YAML is valid and GitHub Actions reads `on` correctly. The verification was run with a `d.get('on', d.get(True))` fallback and all assertions passed.

## Deviations from Plan

None — plan executed exactly as written. (The RESEARCH summary references a single-file `ci-cd.yml`; the PLAN frontmatter and tasks specify the two-file `workflow_run` approach, which is authoritative and was followed.)

## Operational Prerequisites (carried forward, not blocking this plan)

These are verified by humans at deploy time (RESEARCH A2–A4, Plan 03 checkpoint), not by this plan:
- GitHub repo secrets `SERVER_HOST`, `SERVER_USER`, `SERVER_SSH_KEY` (ED25519) must be set.
- Server `~/telegram-ai-bot/` must hold `compose.yaml` + `.env`; confirm the path matches the `cd` target.
- Durable server-side GHCR pull credential (public package OR one-time read-only `docker login`).

## Self-Check: PASSED

- FOUND: .github/workflows/deploy.yml
- FOUND: .planning/phases/04-ci-cd-auto-deploy/04-02-SUMMARY.md
- FOUND commit: b2b5f3f (fix — deploy.yml gating)
