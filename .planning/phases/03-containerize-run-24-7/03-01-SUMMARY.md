---
phase: 03-containerize-run-24-7
plan: 01
subsystem: infra
tags: [docker, docker-compose, dockerignore, litellm, ghcr, non-root, security]

# Dependency graph
requires:
  - phase: 02-reliability-hardening
    provides: A stable polling bot (bot/ package, config.py, timeout-hardened handlers) ready to containerize
provides:
  - Reproducible hardened Docker image (litellm pinned to 1.88.1)
  - .dockerignore that keeps .env and non-build files out of the build context
  - Dockerfile that runs the bot as non-root botuser
  - compose.yaml that both builds locally (build: .) and pulls from GHCR (image:)
  - Corrected .env.example using LLM_* var names matching bot/config.py
affects: [03-02-deploy-runbook, 04-cicd-auto-deploy]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Non-root container user (botuser) via addgroup/adduser --system + USER directive"
    - ".dockerignore as the load-bearing DEP-03 control (excludes .env from build context)"
    - "Dual build:/image: compose service — same file builds locally and pulls from GHCR"
    - "Exact version pin for litellm; let litellm manage openai/httpx transitively (no manual pins)"

key-files:
  created:
    - .dockerignore
  modified:
    - requirements.txt
    - Dockerfile
    - compose.yaml
    - .env.example

key-decisions:
  - "Pin litellm to exact 1.88.1 (version from active .venv) for reproducible local/server builds"
  - "Do NOT pin openai or httpx separately — litellm pulls them transitively; manual pins cause resolver conflicts"
  - "No HEALTHCHECK instruction (D-10) — restart: unless-stopped covers crash recovery for a polling bot"
  - "Let the system assign botuser UID/GID via --system flags rather than hardcoding"

patterns-established:
  - "Pattern: non-root container — create system group+user, add USER directive after final COPY"
  - "Pattern: secret-safe build context — .dockerignore excludes .env before the daemon ever sees it"
  - "Pattern: one compose service serves both local build and GHCR pull paths"

requirements-completed: [DEP-01, DEP-03]

# Metrics
duration: ~15min
completed: 2026-06-15
---

# Phase 3 Plan 01: Buildable Hardened Image Summary

**Reproducible, secret-safe Docker image: litellm pinned to 1.88.1, .dockerignore blocking .env from the build context, Dockerfile running the bot as non-root botuser, and a compose.yaml that builds locally or pulls from GHCR.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-06-15
- **Completed:** 2026-06-15
- **Tasks:** 3 (2 auto + 1 human-verify checkpoint)
- **Files modified:** 5 (1 created, 4 modified)

## Accomplishments

- Pinned `litellm` to exact `1.88.1` so local and later server builds resolve identically (reproducible builds; T-03-03 mitigation).
- Created `.dockerignore` excluding `.env`, `.git/`, `.venv/`, `tests/`, `.planning/`, `*.md`, `__pycache__/`, `.claude/` — the load-bearing DEP-03 control that keeps secrets out of the Docker build context and image layers (T-03-01 mitigation).
- Hardened the `Dockerfile`: creates a system `botuser` group/user and adds `USER botuser` so the process runs non-root (T-03-02 mitigation). No HEALTHCHECK added per D-10.
- Added `build: .` to the `bot` service in `compose.yaml` alongside the GHCR `image:` tag, enabling `docker compose build` locally and `docker compose pull && up -d` on the server from one file.
- Fixed `.env.example` to use `LLM_API_KEY`/`LLM_MODEL` (matching `bot/config.py` REQUIRED_VARS) so copying it to `.env` boots the bot without a ConfigError (T-03-04 mitigation).

## Task Commits

Each task was committed atomically:

1. **Task 1: Pin litellm and add .dockerignore** - `3b48c15` (chore)
2. **Task 2: Harden Dockerfile, add compose build, fix .env.example** - `f6c9de5` (feat)
3. **Task 3: Human-verify checkpoint** - no commit (verification only; approved)

**Plan metadata:** committed with this SUMMARY (docs)

## Files Created/Modified

- `.dockerignore` - **New.** Excludes `.env`, `.git/`, `.venv/`, `tests/`, `.pytest_cache/`, `.ruff_cache/`, `.planning/`, `*.md`, `__pycache__/`, `*.pyc`, `*.pyo`, `.claude/`, `*.DS_Store` from the build context; keeps `requirements.txt` and `bot/` reachable.
- `requirements.txt` - Changed bare `litellm` to `litellm==1.88.1`; left `python-telegram-bot==22.7` and `python-dotenv>=1.0,<2` unchanged; no openai/httpx pins.
- `Dockerfile` - Added `RUN addgroup --system botuser && adduser --system --ingroup botuser botuser` and `USER botuser` (after the final `COPY bot/ bot/`). Kept `FROM python:3.12-slim`, `ENV PYTHONUNBUFFERED=1`, COPY/pip steps, and `CMD ["python", "-m", "bot"]` unchanged. No HEALTHCHECK.
- `compose.yaml` - Added `build: .` to the `bot` service; retained `image: ghcr.io/${GITHUB_REPOSITORY:-telegram-bot-ai}/bot:latest`, `env_file: .env`, `restart: unless-stopped`.
- `.env.example` - Renamed `OPENAI_API_KEY` → `LLM_API_KEY` and `OPENAI_MODEL` → `LLM_MODEL`; kept `TELEGRAM_BOT_TOKEN` and `ALLOWED_CHAT_IDS`.

## Checkpoint Verification Results (Task 3 — human-verify, APPROVED)

All three checks passed:

1. **Build succeeds:** `docker compose build` completed with no error; image built as `ghcr.io/telegram-bot-ai/bot:latest` and pip resolved `litellm==1.88.1`.
2. **Non-root process:** `docker run --rm --entrypoint id <image>` showed `uid=100(botuser)` — confirmed not `uid=0(root)`.
3. **No secrets in image:** `docker run --rm --entrypoint sh <image> -c "ls -a /app && test ! -f /app/.env && echo NO_ENV_IN_IMAGE"` printed `NO_ENV_IN_IMAGE`; `/app` contained only `bot/` and `requirements.txt` — no `.env` baked in.

## Decisions Made

None beyond plan — followed the plan as specified. Key planned decisions reaffirmed: exact litellm pin for reproducibility, no separate openai/httpx pins (avoid resolver conflicts), no HEALTHCHECK (D-10, restart policy covers recovery), system-assigned botuser UID/GID.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration introduced by this plan. (Existing pre-deploy reminder still stands: set a hard LLM provider billing cap before the public bot goes live — tracked as a Phase 3-4 blocker in STATE.md.)

## Requirements Satisfied

- **DEP-01 (build half):** The same `compose.yaml` + `Dockerfile` produce one image buildable locally; Plan 02 will run that same image on the server. (Full DEP-01 completes with the Plan 02 deploy runbook.)
- **DEP-03:** `.env` is excluded from the build context via `.dockerignore` and confirmed absent from image layers (checkpoint check 3); `.env.example` ships placeholders only with correct var names.

## Next Phase Readiness

- The hardened, reproducible image is the exact artifact Plan 03-02's VPS deploy runbook will push to GHCR and run on the server.
- Ready for Plan 03-02 (Wave 2): GHCR push, server bootstrap, pull+run, auto-restart/reboot recovery.
- Note: DEP-01 is half-complete (build verified locally); the run-on-server half is delivered by Plan 03-02.

## Self-Check: PASSED

- FOUND: .dockerignore
- FOUND: requirements.txt (litellm==1.88.1)
- FOUND: Dockerfile (USER botuser)
- FOUND: compose.yaml (build: .)
- FOUND: .env.example (LLM_API_KEY)
- FOUND commit: 3b48c15 (Task 1)
- FOUND commit: f6c9de5 (Task 2)

---
*Phase: 03-containerize-run-24-7*
*Completed: 2026-06-15*
