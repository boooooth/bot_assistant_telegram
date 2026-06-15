# Phase 3: Containerize & Run 24/7 - Context

**Gathered:** 2026-06-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Package the bot as a production-ready Docker image, push it to GHCR manually (first deploy before CI/CD exists), and run it 24/7 on a Linux VPS with auto-restart on crash or reboot — with secrets injected at runtime only, never in git or the image.

**In scope:** DEP-01 (same image locally and on server), DEP-02 (24/7 + auto-restart), DEP-03 (secrets via env only).
**Out of scope:** CI/CD automation (Phase 4), tests (Phase 4), rate limiting, conversation memory.
</domain>

<decisions>
## Implementation Decisions

### LiteLLM & Env Var Rename (ALREADY DONE — pre-Phase 3)
- **D-01:** LiteLLM is kept as the deliberate LLM call mechanism — it was incorrectly listed in "What NOT to Use". No code change needed; this was the real implementation all along.
- **D-02:** `OPENAI_API_KEY` → `LLM_API_KEY` and `OPENAI_MODEL` → `LLM_MODEL` across all code, tests, and docs. **This rename was completed in the PR merged before Phase 3 began.** Do NOT redo it.
- **D-03:** Pin LiteLLM to a specific version in `requirements.txt` (e.g. `litellm==X.Y.Z`). Check the currently installed version via `pip show litellm` and pin to that.
- **D-04:** Docs updated: CLAUDE.md and PROJECT.md now reflect LiteLLM as the real choice, language generalized to "LLM provider".

### First VPS Deploy Approach
- **D-05:** Push to GHCR manually for this phase. Build image on laptop → push to GitHub Container Registry → SSH to server → `docker compose pull && docker compose up -d`. Server never builds, only runs.
- **D-06:** Requires a GitHub Personal Access Token (PAT) with `write:packages` scope to push to GHCR. One-time setup. The PAT is used locally on the developer's machine — not stored in the repo.
- **D-07:** `compose.yaml` references `ghcr.io/${GITHUB_REPOSITORY}/bot:latest` — this is the image name to push to and pull from.

### Dockerfile Hardening
- **D-08:** Add a non-root user (e.g. `botuser`) — run the bot process as non-root inside the container. Security best practice; limits blast radius if the process is compromised.
- **D-09:** Add a `.dockerignore` file — exclude `.git/`, `.venv/`, `tests/`, `.planning/`, `.env`, `*.md` from the build context. Faster builds, smaller context, no accidental file leaks.
- **D-10:** Do NOT add a `HEALTHCHECK` instruction — `restart: unless-stopped` already handles crashed processes. Keep it minimal.

### compose.yaml Fix
- **D-11:** Add `build: .` to the existing `compose.yaml` service alongside the existing `image:` tag. With both present: `docker compose up --build` builds locally; `docker compose pull && up` pulls from GHCR (what Phase 4 will automate). One file covers both phases.

### Claude's Discretion
- Exact non-root username and UID/GID in Dockerfile.
- `.dockerignore` exact file list (use common sense for Python projects).
- Whether to use `docker compose up -d` or `docker compose up --build -d` for the initial local build step.
- Server bootstrap steps (install Docker, create `.env`, etc.) — document as runbook comments or README section.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Product & Requirements
- `.planning/ROADMAP.md` — Phase 3 goal + success criteria (DEP-01, DEP-02, DEP-03)
- `.planning/REQUIREMENTS.md` — requirement IDs DEP-01, DEP-02, DEP-03
- `.planning/PROJECT.md` — updated key decisions (LiteLLM, Linux VPS, GHCR)

### Existing Code & Config
- `Dockerfile` — current minimal scaffold; Phase 3 hardens it (non-root user, .dockerignore)
- `compose.yaml` — current file; Phase 3 adds `build: .`
- `requirements.txt` — LiteLLM is unpinned; Phase 3 pins it
- `bot/config.py` — reads `LLM_API_KEY` and `LLM_MODEL` (already renamed; do not use old OPENAI_* names)
- `.env.example` — template for server `.env` file; verify it lists `LLM_API_KEY` and `LLM_MODEL`

### Stack & Architecture
- `.planning/research/STACK.md` — Python 3.12-slim base image rationale
- `CLAUDE.md` — updated LiteLLM section, `LLM_MODEL`/`LLM_API_KEY` env var names

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Dockerfile` — already uses `python:3.12-slim`, `PYTHONUNBUFFERED=1`, copies `bot/`, runs `python -m bot`. Only needs non-root user added.
- `compose.yaml` — already has `env_file: .env` and `restart: unless-stopped`. Only needs `build: .` added.
- `requirements.txt` — has `litellm` unpinned; needs version pin.

### Established Patterns
- Secrets via `env_file: .env` in compose — already established; never baked into image.
- `python:3.12-slim` base — already in use; keep it.
- `PYTHONUNBUFFERED=1` — already set; keep it.

### Integration Points
- GHCR image name: `ghcr.io/${GITHUB_REPOSITORY}/bot:latest` — already in compose.yaml; push target for manual deploy.
- Server `.env` must contain: `TELEGRAM_BOT_TOKEN`, `LLM_API_KEY`, `LLM_MODEL` (optional), `ALLOWED_CHAT_IDS` (optional).

</code_context>

<specifics>
## Specific Ideas

- Use a second BotFather token for local dev to avoid 409 conflicts with the production bot (noted in Phase 1 context, relevant now that the server will run the real token).
- Phase 4 will automate the GHCR push + SSH pull via GitHub Actions. Phase 3 does it manually once — priming the registry so Phase 4 has less to configure.
- Server bootstrap is manual (one-time): install Docker, `docker compose` plugin, create `.env`, run `docker compose pull && up -d`. Phase 3 should document this as a runbook (README section or inline comments).

</specifics>

<deferred>
## Deferred Ideas

- **Health check (`HEALTHCHECK` in Dockerfile)** — skipped for Phase 3; `restart: unless-stopped` is sufficient. Add in a future hardening pass if needed.
- **Automated server bootstrap script** — manual steps are fine for Phase 3 (one server, one time). A script would be overkill until there are multiple servers.
- **CI/CD automation** — Phase 4. Phase 3 does the manual equivalent once.

</deferred>

---

*Phase: 3-Containerize & Run 24/7*
*Context gathered: 2026-06-14*
