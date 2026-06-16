---
phase: 4
slug: ci-cd-auto-deploy
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-15
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 (async via `asyncio.run()`; no pytest-asyncio needed) |
| **Config file** | none — default discovery of `tests/test_*.py` |
| **Quick run command** | `pytest -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest -q` (plus `ruff check .` for code tasks)
- **After every plan wave:** Run `pytest -q && ruff check . && ruff format --check . && mypy bot/ --ignore-missing-imports`
- **Before `/gsd-verify-work`:** Full suite green + successful end-to-end pipeline run on `main` with human-verified server state
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | QA-01 | — | handler tests cover authorized, unauthorized, error paths | unit | `pytest tests/test_handlers.py -q` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | QA-02 | — | ruff/mypy pinned in requirements-dev.txt | smoke | `grep "ruff==" requirements-dev.txt && grep "mypy==" requirements-dev.txt` | ✅ (exists, but incomplete) | ⬜ pending |
| 04-02-01 | 02 | 2 | DEP-04, QA-02 | T-04-04 (CI bypass) | deploy.yml uses workflow_run gated on CI conclusion == success | smoke | `python -c "import yaml; d=yaml.safe_load(open('.github/workflows/deploy.yml')); wr=d['on']['workflow_run']; assert wr['workflows']==['CI']; assert 'completed' in wr['types']; print('ok')"` | ✅ (exists, needs update) | ⬜ pending |
| 04-03-01 | 03 | 3 | DEP-04, QA-02 | T-04-04 | GHCR cred decision made; pipeline runs CI then deploy | manual | human-verify: confirm GitHub Actions run shows ci-checks → deploy sequence | ❌ checkpoint | ⬜ pending |
| 04-03-02 | 03 | 3 | DEP-04 | — | server runs new version; no 409 during release | manual | human-verify: `docker compose ps` on server + inspect logs around release | ❌ checkpoint | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_handlers.py` — covers QA-01: `handle_text` (happy/error/allowlist/no-op), `start`, `help_cmd` — delivered by Plan 04-01 Task 1
- [ ] `requirements-dev.txt` — add pinned `ruff==0.12.0` and `mypy==1.17.1` — delivered by Plan 04-01 Task 2
- [ ] `.github/workflows/deploy.yml` updated — `workflow_run` trigger referencing `[CI]` + job condition `conclusion == 'success'` + `--pull always --force-recreate` — delivered by Plan 04-02 Task 1

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Push to `main` triggers ci-checks then deploy (only when CI green) | DEP-04, QA-02 | Requires a live GitHub Actions run on the real repo | Push a commit to `main`; observe GitHub Actions run; confirm ci-checks completes before deploy starts; confirm deploy does NOT run if ci-checks fails |
| Server runs the newly built version after a successful pipeline | DEP-04 (SC-4) | Requires SSH access to VPS | After pipeline completes, SSH to server; run `docker compose ps`; verify image digest matches the GHCR push from the same commit |
| No 409 "terminated by other getUpdates" in logs during release | DEP-04 (SC-5) | Requires live deploy observation | Run `docker compose logs --since=<deploy-time>` on server; verify no `409` errors appear around the restart |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (checkpoints are exempt)
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
