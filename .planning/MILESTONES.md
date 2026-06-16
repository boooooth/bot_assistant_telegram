# Milestones

## v1.0 MVP — Shipped 2026-06-16

**Phases:** 1–4 | **Plans:** 8 (7 executed, 1 deferred) | **Timeline:** 2026-06-11 → 2026-06-16 (5 days)

**Delivered:** A public Telegram bot that accepts text from any user, calls OpenAI via LiteLLM, and replies — packaged in Docker with CI-gated GitHub Actions auto-deploy.

**Key Accomplishments:**
1. Walking skeleton + fail-fast config — bot scaffolded with env validation and pinned deps
2. End-to-end slice — LLM client, PTB handlers, composition root wired; live smoke test approved
3. LiteLLM timeout (30s) — bot stays responsive under slow/failing LLM calls
4. Hardened Docker image — non-root `botuser`, `.dockerignore` blocks secrets, `litellm==1.88.1` pinned
5. VPS deploy runbook — GHCR push, server bootstrap, `restart: unless-stopped` auto-recovery verified
6. Handler tests + dev tooling parity — 6 pytest tests, `ruff`/`mypy` pinned in `requirements-dev.txt`
7. CI-gated deploy — `deploy.yml` fires only after `CI` passes on `main`, with `--force-recreate` safety

**Known deferred at close:** 04-03 live pipeline validation (no VPS provisioned). DEP-04 code-complete; live verification pending.

**Archive:** `.planning/milestones/v1.0-ROADMAP.md` | `.planning/milestones/v1.0-REQUIREMENTS.md`
