# Retrospective

## Milestone: v1.0 MVP

**Shipped:** 2026-06-16
**Phases:** 4 | **Plans:** 8 (7 executed, 1 deferred)
**Timeline:** 2026-06-11 → 2026-06-16 (5 days)

### What Was Built

- Walking skeleton + fail-fast config loader (Phase 1)
- End-to-end LLM reply in Telegram — live smoke test approved (Phase 1)
- 30s LiteLLM timeout so slow calls don't hang indefinitely (Phase 2)
- Hardened Docker image: non-root `botuser`, `.dockerignore` blocking secrets, `litellm==1.88.1` pinned (Phase 3)
- VPS deploy runbook: GHCR push, server bootstrap, `restart: unless-stopped` auto-recovery verified (Phase 3)
- 6 handler unit tests + `ruff`/`mypy` pinned in `requirements-dev.txt` (Phase 4)
- CI-gated `deploy.yml` via `workflow_run` — deploy fires only after green CI on `main` (Phase 4)

### What Worked

- **Vertical MVP order** — having a real working bot in Phase 1 kept motivation high and gave Phase 2-4 a concrete target to harden around.
- **LiteLLM from the start** — choosing provider-agnostic LiteLLM in Phase 1 meant no code refactor was needed when config evolved.
- **Pinning everything early** — pinning `litellm==1.88.1`, `ruff==0.12.0`, `mypy==1.17.1` avoided the classic "green locally, red in CI" version drift.
- **RESEARCH.md doing the legwork** — having researched pitfalls (Compose #9259, `GITHUB_TOKEN` revocation, `workflow_run` vs `needs:`) meant the planner could avoid anti-patterns rather than discover them in production.

### What Was Inefficient

- **Requirements checkboxes never updated** — all 15 requirements were implemented but remained `[ ]` in REQUIREMENTS.md until the milestone close. Updating them at phase boundaries would have been lower-effort than a bulk audit at the end.
- **04-03 deferred** — the final plan required a VPS that wasn't provisioned. Planning could have surfaced this dependency earlier so the user could provision in parallel.
- **ROADMAP.md had stale `[ ]` checkboxes** — phases 1-3 still showed as unchecked at Phase 4 start, requiring a manual cleanup at close.

### Patterns Established

- `asyncio.run()` for async tests — zero pytest-asyncio config, consistent with the existing test idiom
- `workflow_run` two-file CI/CD structure — `ci.yml` untouched; `deploy.yml` gated on it
- `.dockerignore` as the load-bearing secrets control — keeps `.env` out of the build context entirely
- Command-first runbook style in README — numbered steps with copy-paste commands and expected output

### Key Lessons

- **Defer live-infra validation explicitly** — when a plan requires external infrastructure (VPS, secrets, DNS), flag it as a human-checkpoint plan from the start and don't block phase completion on it.
- **Check requirements traceability table at each phase close** — a 2-minute checkbox sweep at the end of each phase prevents a 15-requirement bulk update at milestone close.
- **Compose `--force-recreate` is non-negotiable for `:latest` tags** — Compose bug #9259 is real and silent; always include it.
- **`workflow_run` fires on branches only, not PRs** — this is exactly what you want for deploy gating but is a footgun if you expect it to run on PRs too.

### Cost Observations

- Sessions: ~5 focused sessions over 5 days
- No notable context overflows or reasoning failures
- Phase 4 RESEARCH was the highest-value artifact — prevented 3-4 re-dos (Compose bug, token revocation, workflow_run scoping)

---

## Cross-Milestone Trends

| Trend | v1.0 |
|-------|------|
| Phases per milestone | 4 |
| Plans per milestone | 8 |
| Deferred plans | 1 (04-03) |
| Days to ship | 5 |
| Requirements coverage | 15/15 addressed |
