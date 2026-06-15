# Phase 4: CI/CD Auto-Deploy - Research

**Researched:** 2026-06-15
**Domain:** GitHub Actions CI/CD, pytest async testing, Docker Compose release semantics, GHCR auth
**Confidence:** HIGH

## Summary

Phase 4 closes the loop on automated delivery. Most of the building blocks already exist in the repo: a working `ci.yml` (ruff lint + format, mypy, pytest, docker build check) and a `deploy.yml` that builds, pushes to GHCR, and SSH-deploys via `docker compose pull && up -d`. The phase is therefore **mostly a fix-and-fill exercise, not greenfield construction**. Four concrete gaps must be closed: (1) no `tests/test_handlers.py` covering `handle_text`/`start`/`help_cmd` (QA-01); (2) `deploy.yml` has `needs: []` and triggers independently of CI, so deploy does **not** wait for CI to pass (DEP-04/QA-02 — the central success criterion); (3) the SSH deploy block interpolates `${{ secrets.GITHUB_TOKEN }}` into the remote shell command, which is both a credential-handling smell and functionally fragile (the job token is revoked at job end, so it cannot serve future server-side pulls of a private GHCR image); (4) `requirements-dev.txt` lists only `pytest`, while CI installs `ruff`/`mypy` ad-hoc — local/CI tooling parity is incomplete.

The cleanest gating mechanism for this single-repo, single-environment project is **the single-workflow `needs:` pattern**: fold the build+deploy jobs into one workflow whose `deploy` job declares `needs: [ci-checks]` and `if: github.ref == 'refs/heads/main'`. This is GitHub's recommended dependency-gating primitive [VERIFIED: GitHub Docs], avoids the well-documented `workflow_run` pitfalls (it does not run for fork PRs, runs in the default-branch context, and adds a confusing second run), and keeps "CI proves the code is good; CD ships it" as two jobs in one DAG rather than two loosely-coupled files. The PRD already sanctions this as the "one file" option (§13.4).

On the 409-conflict concern: the default `docker compose up -d` recreate behavior is **stop-old-then-start-new** (serial, with a brief downtime gap) — which is exactly what prevents two pollers holding the same token simultaneously [CITED: docs.docker.com]. The real risk is the opposite: a documented Compose bug (#9259) where `up -d` after `pull` may *not* recreate the container if it fails to detect the `:latest` image changed, leaving the **old** version running. The fix is to deploy with `docker compose up -d --pull always` (or `pull` then `up -d --force-recreate`).

**Primary recommendation:** Merge CI and CD into one workflow (`needs:`-gated deploy job on `main`); add `tests/test_handlers.py` using the repo's existing `asyncio.run` + `AsyncMock` style; pin `ruff`/`mypy`/`pytest`/`pytest-asyncio` into `requirements-dev.txt`; replace the in-script `GITHUB_TOKEN` login with a dedicated read-only GHCR pull credential persisted once on the server; deploy with `--pull always --force-recreate` to guarantee the new image actually runs.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Lint / format / type-check / unit tests | CI runner (GitHub-hosted) | — | Pure code-quality gate; runs on every push + PR before anything ships |
| Image build + push to registry | CI runner | GHCR (storage) | Build artifacts produced in CI, stored in GHCR; server never builds (DEP-01) |
| Deploy orchestration (SSH, pull, restart) | CI runner → Server (over SSH) | — | GitHub Actions drives the deploy; the actual `docker compose` runs on the VPS |
| Image pull + container lifecycle | Server (Docker daemon) | GHCR | Server pulls the published image and runs it with `restart: unless-stopped` |
| Single-poller safety during release | Server (Compose recreate semantics) | — | Stop-old-before-start-new is enforced by Compose on the box, not by CI |
| Secret storage (SSH key, registry pull cred) | GitHub Encrypted Secrets + server filesystem | — | SSH/registry creds in GH Secrets; app secrets only in server `.env` |

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEP-04 | Push to `main` triggers a GitHub Actions pipeline that builds the image and deploys it to the server | Single-workflow `needs:`-gated deploy job (see Architecture Pattern 1); existing `deploy.yml` build/push + appleboy SSH steps are reusable once gated |
| QA-01 | Automated `pytest` suite covers core message handling and the OpenAI call path | OpenAI path already covered by `tests/test_openai_client.py`; gap is `tests/test_handlers.py` — patterns in Code Examples below |
| QA-02 | CI runs ruff, mypy, pytest, Docker build on every push & PR; deploy proceeds only when CI passes | `ci.yml` already runs all four checks; "deploy only when CI passes" is the gating fix (Pattern 1). Pin dev tooling in `requirements-dev.txt` for parity |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 9.0.x (9.0.3 installed) | Test runner | Already the project test framework; `test_config.py`/`test_openai_client.py` use it [VERIFIED: pip] |
| ruff | 0.12.x (0.12.0 installed; 0.15.17 latest) | Lint + format | CLAUDE.md-mandated single lint/format tool; already wired in `ci.yml` [VERIFIED: pip] |
| mypy | 1.17.x (1.17.1 installed) | Static type check | QA-02-mandated type checker; already wired in `ci.yml` [VERIFIED: pip] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-asyncio | 1.4.0 (installed) | Async test support | Optional — only if handler tests use `@pytest.mark.asyncio` instead of the repo's existing `asyncio.run()` style. See Pattern 2 for the decision [VERIFIED: pip] |

### GitHub Actions (pinned in workflows — already in use)
| Action | Version | Purpose | Notes |
|--------|---------|---------|-------|
| actions/checkout | v4 | Clone repo | Already used in both workflows [CITED: existing ci.yml/deploy.yml] |
| actions/setup-python | v5 | Python 3.12 toolchain | Already in `ci.yml` |
| docker/login-action | v3 | GHCR login (build side) | Already in `deploy.yml`; v3 is the conservative documented pairing with build-push v6 (CLAUDE.md) |
| docker/build-push-action | v6 | Build + push image | Already in both workflows |
| appleboy/ssh-action | v1 | Run deploy commands over SSH | Already in `deploy.yml`; CLAUDE.md-mandated. Pin to a release tag; consider SHA-pinning for supply-chain hardening |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Single workflow + `needs:` gate | Two files + `workflow_run` trigger | `workflow_run` does not fire for fork PRs, runs in default-branch context, and produces a confusing second run with separate logs. Overkill for one repo/one environment [VERIFIED: GitHub Docs / community] |
| Single workflow + `needs:` gate | Branch protection "require CI to pass before merge" | Protects the merge, not the deploy-on-push. PRs merged green can still race a broken `main` push; and direct pushes to `main` bypass it. Use as a complement, not the gate |
| `asyncio.run()` in tests | `pytest-asyncio` `@pytest.mark.asyncio` | `asyncio.run` needs zero config and matches existing `test_openai_client.py`. pytest-asyncio is cleaner for many async tests but adds a config knob (`asyncio_mode`). For ~5 handler tests, match the existing style |
| In-script `GITHUB_TOKEN` GHCR login | One-time server-side `docker login` with a read-only PAT / fine-grained token | The job `GITHUB_TOKEN` is revoked at job end and cannot authenticate future server restarts of a private image; interpolating it into the SSH script also leaks it into the remote process list / shell history [VERIFIED: GitHub Docs] |

**Installation (dev tooling parity fix):**
```bash
# requirements-dev.txt should become:
-r requirements.txt
pytest
pytest-asyncio   # only if @pytest.mark.asyncio style is chosen
ruff
mypy
```
Pin to the versions CI will use (e.g. the installed `ruff==0.12.0`, `mypy==1.17.1`) so a future ruff/mypy release does not turn a green local run red in CI, or vice-versa.

**Version verification:** All four packages confirmed on PyPI 2026-06-15 via `pip index versions` (pytest-asyncio 1.4.0, ruff up to 0.15.17, mypy up to 2.1.0). Installed versions: pytest 9.0.3, ruff 0.12.0, mypy 1.17.1, pytest-asyncio 1.4.0.

## Package Legitimacy Audit

> No *new third-party runtime* packages are introduced by this phase. Dev-tooling additions to `requirements-dev.txt` (`ruff`, `mypy`, `pytest-asyncio`) are already installed in the active environment and are industry-standard.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| pytest | PyPI | 10+ yrs | ~100M/wk | github.com/pytest-dev/pytest | OK | Approved (already used) |
| ruff | PyPI | 3+ yrs | ~40M/wk | github.com/astral-sh/ruff | OK | Approved (CLAUDE.md-mandated) |
| mypy | PyPI | 10+ yrs | ~40M/wk | github.com/python/mypy | OK | Approved (QA-02-mandated) |
| pytest-asyncio | PyPI | 8+ yrs | ~30M/wk | github.com/pytest-dev/pytest-asyncio | OK | Approved (optional) |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*Download/age figures are approximate `[ASSUMED]` from training knowledge; all four are confirmed-present on PyPI as of 2026-06-15 and are first-party tooling of well-known orgs (pytest-dev, astral-sh, python). `gsd-tools` was not on PATH in this session, so the seam verdict column reflects manual registry verification, not the seam.*

## Architecture Patterns

### System Architecture Diagram

```
   Developer
      │  git push (any branch / PR)
      ▼
┌──────────────────────────────────────────────────────────┐
│  GitHub Actions — single workflow (ci-cd.yml)            │
│                                                          │
│  ┌────────────────────────────┐                          │
│  │ job: ci-checks             │  on: push + pull_request │
│  │  - ruff check / format     │                          │
│  │  - mypy bot/               │                          │
│  │  - pytest                  │                          │
│  │  - docker build (no push)  │                          │
│  └──────────────┬─────────────┘                          │
│                 │ success                                 │
│                 ▼  needs: [ci-checks]                     │
│  ┌────────────────────────────┐  if: ref == main         │
│  │ job: deploy                │  (skipped on PR/branch)  │
│  │  - docker build + push ──────────► GHCR (image:latest)│
│  │  - appleboy SSH ──────────┐│                          │
│  └───────────────────────────┘│                          │
└───────────────────────────────┼──────────────────────────┘
                                 │ ssh
                                 ▼
┌──────────────────────────────────────────────────────────┐
│  Linux VPS                                               │
│   docker compose pull                                    │
│   docker compose up -d --pull always --force-recreate    │
│     → STOP old container → START new container           │
│       (serial recreate = only one poller at a time)      │
│   restart: unless-stopped  (24/7)                        │
│   secrets via .env (env_file, runtime only)              │
└──────────────────────────────────────────────────────────┘
```

### Component Responsibilities
| File | Responsibility | Phase 4 change |
|------|----------------|----------------|
| `.github/workflows/ci.yml` | Quality gate (lint/type/test/build) | Becomes the `ci-checks` job; either kept as a reusable workflow or folded into one file |
| `.github/workflows/deploy.yml` | Build/push + SSH deploy | Gain `needs: [ci-checks]` + `if: ref==main`; fix GHCR server login; add `--pull always --force-recreate`; add `workflow_dispatch` |
| `tests/test_handlers.py` | **New** — covers `handle_text`, `start`, `help_cmd`, allowlist branch, error branch | Created (QA-01) |
| `tests/conftest.py` | Shared fixtures | Add Update/Message/context fixtures for handler tests |
| `requirements-dev.txt` | Dev tooling | Add `ruff`, `mypy`, (optional `pytest-asyncio`), pinned |
| `compose.yaml` | Server runtime | No change required; image tag already `ghcr.io/${GITHUB_REPOSITORY}/bot:latest` |

### Pattern 1: Single-workflow CI-gated deploy (RECOMMENDED)
**What:** One workflow file with a `ci-checks` job and a `deploy` job. `deploy` declares `needs: [ci-checks]` (so it only runs if checks pass) and `if: github.ref == 'refs/heads/main'` (so it is skipped on PRs and non-main branches).
**When to use:** Single repo, single environment, deploy-on-push-to-main — exactly this project.
**Example:**
```yaml
# Source: GitHub Docs "Deploying with GitHub Actions" + PRD §13.4 "one file" option
name: ci-cd
on:
  push:
  pull_request:
  workflow_dispatch:        # manual redeploy (gap #3)

jobs:
  ci-checks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements-dev.txt
      - run: ruff check .
      - run: ruff format --check .
      - run: mypy bot/ --ignore-missing-imports
      - run: pytest -q
      - uses: docker/build-push-action@v6
        with: { context: ., push: false }

  deploy:
    needs: [ci-checks]                                  # GATE: only if CI green
    if: github.ref == 'refs/heads/main'                 # GATE: only on main
    runs-on: ubuntu-latest
    permissions: { contents: read, packages: write }
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: ghcr.io/${{ github.repository }}/bot:latest
      - uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SERVER_SSH_KEY }}
          script: |
            cd ~/telegram-ai-bot
            docker compose pull
            docker compose up -d --pull always --force-recreate
            docker image prune -f
```
**Note:** `workflow_dispatch` + `if: github.ref == 'refs/heads/main'` means a manual run from a non-main branch will run CI but skip deploy — acceptable, since manual redeploy is intended from `main`.

### Pattern 2: Testing async PTB handlers without the network
**What:** `handle_text` depends only on `update.message`, `update.effective_chat.id`, `context.bot_data["complete"]`, and `context.bot_data["allowed_chat_ids"]`. None of these require a real Telegram connection — mock `update` and `context` with `MagicMock`, make `reply_text` and `complete` `AsyncMock`s, and drive the coroutine with `asyncio.run()` (matching `test_openai_client.py`).
**When to use:** All handler tests in this phase.
**Example:** see Code Examples below.

### Anti-Patterns to Avoid
- **`workflow_run` two-file gating for a single environment:** does not run on fork PRs, runs in default-branch context, surfaces a second confusing run. Use `needs:` in one workflow [VERIFIED: GitHub Docs / community].
- **Relying on `docker compose up -d` alone after `pull` with a `:latest` tag:** Compose bug #9259 — `up` may not recreate if it does not detect the image changed, leaving the OLD version live. Always `--pull always --force-recreate` (or `--force-recreate` after an explicit `pull`) [CITED: github.com/docker/compose#9259].
- **Interpolating `${{ secrets.GITHUB_TOKEN }}` into the SSH `script:` block:** leaks the token into the remote process list/history, and the token is revoked at job end so it cannot serve future server-side restarts of a private image [VERIFIED: GitHub Docs].
- **Starting the new container before stopping the old (`--no-stop` / blue-green):** would put two pollers on one token simultaneously → 409. For a polling bot, a brief stop-then-start gap is correct, not a defect.
- **Installing `ruff`/`mypy` ad-hoc in CI but not pinning them in `requirements-dev.txt`:** version drift makes "green locally, red in CI" (or vice-versa) possible.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Gate deploy on CI | Custom status-check polling / scripts | `needs: [ci-checks]` job dependency | Native, atomic, GitHub-recommended [VERIFIED: GitHub Docs] |
| Stop old before new container | Manual `docker stop && docker rm && docker run` script | `docker compose up -d --force-recreate` | Compose already does serial stop-then-start; manual scripting reintroduces race windows |
| Fake Telegram for tests | Live bot / integration harness against Telegram API | `MagicMock`/`AsyncMock` of `Update`+`context` | Handlers depend only on a few attributes; no network needed (Pattern 2) |
| Mock async LLM call | Real LiteLLM call in tests | `AsyncMock` patched onto `context.bot_data["complete"]` | Deterministic, offline, no API key or cost |
| Server-side registry auth | Embedding token in deploy script each run | One-time `docker login` with a long-lived read-only pull cred on the server | Survives across deploys; not leaked per-run |

**Key insight:** Almost everything this phase needs is a *native GitHub Actions / Docker Compose feature* or a *standard mock*. The work is wiring and fixing, not inventing.

## Runtime State Inventory

> This phase changes CI/CD wiring and adds tests — it is not a rename/refactor. The only "runtime state" that matters is GitHub-side and server-side credentials/config. Included for completeness because the deploy path touches live infrastructure.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — bot is stateless, no DB/migrations | None |
| Live service config | GitHub repo **Secrets** must exist: `SERVER_HOST`, `SERVER_USER`, `SERVER_SSH_KEY` (ED25519). Server-side: a working `~/telegram-ai-bot/` dir with `compose.yaml` + `.env`. Server-side GHCR login persisted in `~/.docker/config.json` | Verify all three GH secrets are set; verify server dir/compose/.env exist; establish a durable server-side GHCR pull credential (not the job `GITHUB_TOKEN`) |
| OS-registered state | None — Docker `restart: unless-stopped` is the only registration; no systemd unit, no cron | None |
| Secrets/env vars | App secrets (`TELEGRAM_BOT_TOKEN`, `LLM_API_KEY`) live ONLY in server `.env`; CI/CD must never see them. GHCR pull credential for a private package must persist on the server | Confirm package visibility (public vs private) — drives whether a persistent pull cred is needed |
| Build artifacts | GHCR image `ghcr.io/<owner>/telegram_bot_ai/bot:latest` already primed by Phase 3 manual push | `--force-recreate` ensures the freshly pushed `:latest` actually replaces the running container |

**Nothing found in category — confirmed:** No databases, no OS scheduler entries, no compiled/installed packages carrying old state. The bot is stateless by design (PTB tracks the update offset in-memory only).

## Common Pitfalls

### Pitfall 1: Deploy races CI instead of waiting for it (the headline gap)
**What goes wrong:** Current `deploy.yml` has `needs: []` and `on: push: branches:[main]`. On a push to `main`, CI and deploy fire **simultaneously**; deploy ships even if tests/lint fail.
**Why it happens:** `needs: []` declares zero dependencies; the two files are independent triggers.
**How to avoid:** Put deploy in the same workflow as the checks with `needs: [ci-checks]` (Pattern 1). Deploy is then a downstream node that only runs on green.
**Warning signs:** A red CI run and a green deploy run for the same commit SHA appearing at the same timestamp.

### Pitfall 2: New image pushed but old container keeps running
**What goes wrong:** After `docker compose pull`, `docker compose up -d` reports "up to date" and does not restart — the server keeps running the previous build.
**Why it happens:** Compose bug #9259 — the `:latest` tag did not change name, and Compose's service-hash did not include the image digest, so it saw no change.
**How to avoid:** `docker compose up -d --pull always --force-recreate`. Optionally also tag images with the commit SHA so each deploy is a genuinely new tag.
**Warning signs:** Bot behaviour does not change after a deploy; `docker compose ps` shows a container `Created` long before the deploy timestamp.

### Pitfall 3: Server cannot pull a private GHCR image after the job ends
**What goes wrong:** Deploy script logs in with `${{ secrets.GITHUB_TOKEN }}`; later, `restart: unless-stopped` or a manual `docker compose pull` fails with `denied` / `unauthorized`.
**Why it happens:** The job `GITHUB_TOKEN` is auto-revoked at job end. If the GHCR package is **private**, the server has no valid credential afterward.
**How to avoid:** Either make the GHCR package **public** (pull needs no auth), or persist a long-lived read-only credential on the server via a one-time `docker login` (fine-grained token / read-only PAT). Decide package visibility explicitly.
**Warning signs:** First deploy works; a server reboot or second deploy fails to pull.

### Pitfall 4: 409 "terminated by other getUpdates" during deploy
**What goes wrong:** Two poller instances briefly run against the same token during a release.
**Why it happens:** Would only occur if the deploy started the new container *before* stopping the old (it does not by default), or if a local dev instance shares the production token.
**How to avoid:** Default Compose recreate is stop-then-start — keep it (do NOT add start-first/blue-green). Keep a distinct dev token (already established in Phase 3). `--force-recreate` preserves the serial order.
**Warning signs:** `Conflict: terminated by other getUpdates request` in server logs around deploy time.

### Pitfall 5: CI passes on the runner but `mypy` finds nothing / wrong scope
**What goes wrong:** `mypy bot/ --ignore-missing-imports` type-checks only `bot/`, not `tests/`. New test files with type errors won't be caught; and `--ignore-missing-imports` hides missing stubs for `telegram`/`litellm`.
**Why it happens:** Scoping `mypy` to `bot/` is intentional (third-party stubs are incomplete) but means test code is unchecked.
**How to avoid:** Keep `mypy bot/ --ignore-missing-imports` as-is for v1 (it is the right pragmatic scope given PTB/LiteLLM stub gaps). If you want test coverage too, add `tests/` to the path but expect to add `# type: ignore` or stubs. Document the deliberate scope. (This answers research focus #5: the current invocation is correct for this structure.)
**Warning signs:** A type error in a handler slips through because it only manifests in a test helper.

## Code Examples

Verified patterns, grounded in the actual repo signatures.

### Handler test: `handle_text` happy path (matches existing `asyncio.run` style)
```python
# Source: existing tests/test_openai_client.py style + bot/handlers.py signature
import asyncio
from unittest.mock import AsyncMock, MagicMock

from bot.handlers import handle_text


def _make_update(text="hello", chat_id=123):
    update = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.effective_chat.id = chat_id
    return update


def _make_context(reply="hi back", allowed=frozenset()):
    context = MagicMock()
    context.bot_data = {
        "complete": AsyncMock(return_value=reply),
        "allowed_chat_ids": allowed,
    }
    return context


def test_handle_text_replies_with_llm_output():
    update = _make_update("hello")
    context = _make_context(reply="the answer")
    asyncio.run(handle_text(update, context))
    context.bot_data["complete"].assert_awaited_once_with("hello")
    update.message.reply_text.assert_awaited_once_with("the answer")
```

### Handler test: error path returns the friendly message
```python
def test_handle_text_friendly_error_on_llm_failure():
    update = _make_update("boom")
    context = _make_context()
    context.bot_data["complete"] = AsyncMock(side_effect=RuntimeError("api down"))
    asyncio.run(handle_text(update, context))
    update.message.reply_text.assert_awaited_once()
    assert "went wrong" in update.message.reply_text.call_args.args[0]
```

### Handler test: allowlist rejection
```python
def test_handle_text_rejects_unauthorized_chat():
    update = _make_update(chat_id=999)
    context = _make_context(allowed=frozenset({123}))   # 999 not allowed
    asyncio.run(handle_text(update, context))
    update.message.reply_text.assert_awaited_once()
    assert "not authorized" in update.message.reply_text.call_args.args[0]
    context.bot_data["complete"].assert_not_awaited()
```

### Command test: `/start` and `/help`
```python
import asyncio
from unittest.mock import AsyncMock, MagicMock

from bot.handlers import start, help_cmd
from bot.prompts import START_TEXT, HELP_TEXT


def test_start_sends_welcome():
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    asyncio.run(start(update, MagicMock()))
    update.message.reply_text.assert_awaited_once_with(START_TEXT)


def test_help_sends_usage():
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    asyncio.run(help_cmd(update, MagicMock()))
    update.message.reply_text.assert_awaited_once_with(HELP_TEXT)
```

### Edge case: `update.message is None` early-return (no crash)
```python
def test_handle_text_no_message_is_noop():
    update = MagicMock()
    update.message = None
    asyncio.run(handle_text(update, MagicMock()))   # must not raise
```

**Note on style:** The repo's `test_openai_client.py` deliberately uses `asyncio.run()` with no `@pytest.mark.asyncio` and needs no pytest config. Matching that keeps zero new configuration. If the planner prefers `@pytest.mark.asyncio`, add `pytest-asyncio` to `requirements-dev.txt` and set `asyncio_mode = "auto"` in a `pyproject.toml`/`pytest.ini` — but that is added config for no functional gain here.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `workflow_run` to chain CI→CD across files | Single workflow, `needs:` + `if:` gate | Long-standing GH recommendation | Simpler, runs on PRs correctly, one run/log |
| `docker compose up -d` after `pull` | `docker compose up -d --pull always --force-recreate` | Post Compose v2.3 (#9259) | Guarantees the new image actually runs |
| Classic PAT for registry auth | Fine-grained / read-only token, or public package | 2024→2026 GitHub direction | Least-privilege; classic PATs being deprecated [VERIFIED: GitHub Docs] |
| Floating action tags only | Pin actions (tag, optionally SHA) | Supply-chain hardening norm | Reproducible, tamper-resistant CI |

**Deprecated/outdated:**
- `needs: []` in `deploy.yml`: not deprecated syntactically, but semantically wrong here — it declares "no gate," which is the bug.
- Passing `${{ secrets.GITHUB_TOKEN }}` into a remote SSH script: discouraged; revoked at job end and leaked into the remote shell.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Download/age figures for pytest/ruff/mypy/pytest-asyncio | Package Legitimacy Audit | None — all four are confirmed on PyPI and are first-party tooling; figures are illustrative |
| A2 | The GHCR package may be **private** (requiring a persistent server pull credential) | Pitfalls #3, Runtime State | If it is public, the persistent-credential work is unnecessary — but this must be confirmed, not assumed. Drives whether deploy needs server-side login |
| A3 | The three GitHub secrets (`SERVER_HOST`/`SERVER_USER`/`SERVER_SSH_KEY`) are already configured | Runtime State | If not set, deploy fails at the SSH step. Needs a verify step / checkpoint |
| A4 | Server working dir is `~/telegram-ai-bot/` (deploy `cd` target) | Pattern 1 example | Wrong path → deploy `cd` fails. Phase 3 runbook used `~/telegram-ai-bot`; confirm the actual server path |
| A5 | Existing `ci.yml` checks all currently pass on the current tree | Summary | If `ruff format --check` or `mypy` currently fails, gating deploy on CI will (correctly) block deploys until fixed — surface this early |

## Open Questions

1. **Is the GHCR package public or private?**
   - What we know: Phase 3 pushed `ghcr.io/<owner>/telegram_bot_ai/bot:latest`; GHCR packages default to private/inheriting repo visibility.
   - What's unclear: whether the server can pull without a persistent credential.
   - Recommendation: Make the package public (simplest — pull needs no auth), OR provision a one-time server-side `docker login` with a read-only fine-grained token. Add a checkpoint to confirm.

2. **One workflow file or keep two (CI as a reusable workflow)?**
   - What we know: Single-file `needs:` is the recommended gate; PRD §13.4 lists both "one file" and "two files."
   - What's unclear: team preference for keeping `ci.yml` separate for reuse.
   - Recommendation: Single file (Pattern 1). If separation is desired, convert `ci.yml` into a reusable workflow called via `uses:` from the deploy workflow with `needs:` — same gate, more files.

3. **Test style: `asyncio.run()` vs `pytest-asyncio`?**
   - What we know: existing async test uses `asyncio.run()` with no config.
   - Recommendation: match existing style (`asyncio.run()`); skip `pytest-asyncio` unless the planner wants `@pytest.mark.asyncio` ergonomics.

4. **Should images be SHA-tagged in addition to `:latest`?**
   - Recommendation: optional but cheap — add `ghcr.io/<repo>/bot:${{ github.sha }}` alongside `:latest` for rollback/traceability. Not required by any success criterion.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| pytest | QA-01 test suite | ✓ | 9.0.3 | — |
| ruff | QA-02 lint/format | ✓ | 0.12.0 | — |
| mypy | QA-02 type-check | ✓ | 1.17.1 | — |
| pytest-asyncio | optional async tests | ✓ | 1.4.0 | `asyncio.run()` (no dep) |
| Docker (local build check) | QA-02 build step | ✓ (Phase 3 verified) | — | — |
| GitHub Actions runners | DEP-04 pipeline | ✓ (hosted) | ubuntu-latest | — |
| Linux VPS + SSH + GHCR creds | DEP-04 deploy target | ⚠ assumed configured | — | None — deploy blocks without it (A3/A4) |

**Missing dependencies with no fallback:**
- Live VPS reachability + the three GH secrets + server-side GHCR pull credential. These are *operational prerequisites*, not code — the planner should gate the live-deploy success criteria (SC-3/SC-4/SC-5) behind a human-verify checkpoint, since CI cannot self-test "the server is now running the new version."

**Missing dependencies with fallback:**
- `pytest-asyncio` — fall back to `asyncio.run()` (already the repo idiom).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 (async via `asyncio.run()`; pytest-asyncio 1.4.0 available) |
| Config file | none — no `pytest.ini`/`pyproject.toml`; default discovery of `tests/test_*.py` |
| Quick run command | `pytest -q` |
| Full suite command | `pytest -q` (suite is small; quick == full) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| QA-01 | OpenAI call path (messages, model passthrough, content) | unit | `pytest tests/test_openai_client.py -q` | ✅ |
| QA-01 | `handle_text` replies with LLM output | unit | `pytest tests/test_handlers.py -q` | ❌ Wave 0 |
| QA-01 | `handle_text` friendly error on LLM failure | unit | `pytest tests/test_handlers.py -q` | ❌ Wave 0 |
| QA-01 | `handle_text` allowlist rejection / no-message no-op | unit | `pytest tests/test_handlers.py -q` | ❌ Wave 0 |
| QA-01 | `/start` and `/help` return their texts | unit | `pytest tests/test_handlers.py -q` | ❌ Wave 0 |
| QA-02 | Lint passes | smoke | `ruff check . && ruff format --check .` | ✅ (ci.yml) |
| QA-02 | Type-check passes | smoke | `mypy bot/ --ignore-missing-imports` | ✅ (ci.yml) |
| QA-02 | Image builds | smoke | `docker build -t bot:ci .` | ✅ (ci.yml) |
| DEP-04 | Deploy runs only after CI green, only on main | manual/CI-config | inspect workflow run graph for SHA | ❌ Wave 0 (gating fix) |
| SC-4 | Server runs the new version post-deploy | manual | human-verify on VPS (`docker compose ps` + behaviour) | ❌ checkpoint |
| SC-5 | No 409 during release | manual | inspect server logs around deploy | ❌ checkpoint |

### Sampling Rate
- **Per task commit:** `pytest -q` (plus `ruff check .` for code tasks)
- **Per wave merge:** full `pytest -q` + `ruff check . && ruff format --check . && mypy bot/ --ignore-missing-imports`
- **Phase gate:** full suite + a successful end-to-end pipeline run on `main` with human-verified server state before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_handlers.py` — covers QA-01 (handle_text happy/error/allowlist/no-op, start, help)
- [ ] `tests/conftest.py` — add Update/Message/context mock fixtures (optional; helpers can live in the test file to mirror `test_openai_client.py`)
- [ ] `requirements-dev.txt` — add pinned `ruff`, `mypy` (and optional `pytest-asyncio`) so CI installs from one source of truth
- [ ] Workflow gating fix — `deploy` job `needs: [ci-checks]` + `if: ref==main` (DEP-04/QA-02)

## Security Domain

> `security_enforcement: true`, ASVS level 1 in config — section required.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | SSH ED25519 deploy key; GHCR token auth. No app-user auth in scope |
| V3 Session Management | no | Stateless bot; no sessions |
| V4 Access Control | partial | Optional `ALLOWED_CHAT_IDS` allowlist (already in handler — test it); GHCR pull cred should be least-privilege (read-only) |
| V5 Input Validation | partial | User text passed verbatim to LLM (accepted v1 scope); no injection sink server-side |
| V6 Cryptography | no | No custom crypto; rely on TLS for GHCR/SSH transport |
| V14 Config / Secrets | **yes** | Secrets via env/`.env` only (DEP-03); GH Secrets for SSH/registry; never echo a secret into a remote script |

### Known Threat Patterns for GitHub Actions + SSH deploy

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Token leaked into remote process list/history via `script:` interpolation | Information Disclosure | Persist a one-time server-side `docker login`; do NOT pass `GITHUB_TOKEN` into the SSH script [VERIFIED: GitHub Docs] |
| Over-privileged registry credential on server | Elevation of Privilege | Use a **read-only** fine-grained token (pull only); or make the package public |
| Unpinned third-party action runs untrusted code | Tampering | Pin `appleboy/ssh-action`, `docker/*`, `actions/*` to tags (optionally SHAs) |
| Deploy of unverified code (CI bypass) | Tampering | `needs: [ci-checks]` gate — deploy only on green (the core fix) |
| Fork PR exfiltrates secrets | Information Disclosure | `deploy` job guarded by `if: github.ref == 'refs/heads/main'`; deploy steps never run for PRs; `ci-checks` needs no secrets |
| App secrets exposed in image/CI | Information Disclosure | Already mitigated (Phase 3): `.dockerignore` excludes `.env`; secrets only in server `.env` at runtime; CI/CD never sees `TELEGRAM_BOT_TOKEN`/`LLM_API_KEY` |

## Sources

### Primary (HIGH confidence)
- GitHub Docs — Deploying with GitHub Actions; `needs:` job dependencies; events that trigger workflows (`workflow_run` fork/context limits); GITHUB_TOKEN automatic auth & revocation — https://docs.github.com/en/actions
- Docker Docs — `docker compose up` recreate semantics (stop-then-start on image/config change) — https://docs.docker.com/reference/cli/docker/compose/up/
- github.com/docker/compose#9259 — `up -d` may not recreate after `pull` with a fixed tag; `--pull always` / `--force-recreate` remedy
- Existing repo files (ground truth): `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`, `bot/handlers.py`, `bot/openai_client.py`, `bot/main.py`, `compose.yaml`, `tests/test_openai_client.py`, `tests/conftest.py`
- PyPI version verification via `pip index versions` (2026-06-15): pytest, ruff, mypy, pytest-asyncio

### Secondary (MEDIUM confidence)
- GitHub Blog / community discussions — fork PR + `workflow_run` limitations and `pull_request_target` context
- appleboy/ssh-action README + StepSecurity advisory — SSH deploy best practices, host fingerprint verification, action pinning

### Tertiary (LOW confidence)
- Various tutorial posts (Medium, oneuptime, dev.to) on GHCR+SSH deploy and zero-downtime compose updates — cross-checked against the primary Docker/GitHub docs above

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all tooling installed and PyPI-verified; no new runtime deps
- Architecture / gating: HIGH — `needs:` gate is GitHub-recommended and PRD-sanctioned; reuses existing workflows
- Pitfalls: HIGH — each grounded in official docs (compose #9259, GITHUB_TOKEN revocation) and the actual repo state (`needs: []`, in-script token)
- Test patterns: HIGH — grounded in real handler signatures and the existing test idiom

**Research date:** 2026-06-15
**Valid until:** 2026-07-15 (stable domain; re-verify action major versions and ruff/mypy pins if the phase slips a month)
