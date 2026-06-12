# Phase 1: Working AI Bot - Pattern Map

**Mapped:** 2026-06-12
**Files analyzed:** 9 (8 to create + 1 config file)
**Analogs found:** 0 in-repo / 9 — **all analogs are EXTERNAL** (RESEARCH.md verified code examples)

> **GREENFIELD — READ FIRST.** This is Phase 1 of a brand-new project. A `**/*.py` glob across the
> repo returns **zero** source files; the repo contains only `.planning/`, `CLAUDE.md`, and `PRD.md`.
> There are **no in-repo analogs to copy from and none were fabricated.** Phase 1 *establishes* the
> conventions that later phases will copy. The canonical, source-of-truth patterns for every file
> below are the **verified code examples in `01-RESEARCH.md` (§ "Code Examples", §"Architecture
> Patterns")**, which were checked against official PTB 22.7 and openai 2.41.1 docs/repos. The planner
> and executor should treat those excerpts as the analog and reproduce them with the small
> discretionary fills (copy wording, temperature) noted in CONTEXT.md.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `bot/config.py` | config | transform (env → Settings) | RESEARCH.md Pattern 1 (external) | external-canonical |
| `bot/openai_client.py` | service | request-response (one-shot LLM) | RESEARCH.md Code Example §2 (external) | external-canonical |
| `bot/handlers.py` | controller/handler | request-response / event-driven | RESEARCH.md Code Example §3 + Pattern 3 (external) | external-canonical |
| `bot/prompts.py` | config/constants | static data | RESEARCH.md Code Example §4 (external) | external-canonical |
| `bot/main.py` | composition root | wiring / startup | RESEARCH.md Code Example §1 + Pattern 2 (external) | external-canonical |
| `bot/__main__.py` | entrypoint | startup | RESEARCH.md Code Example §5 (external) | external-canonical |
| `bot/__init__.py` | package marker | — | n/a (empty) | n/a |
| `.env.example` / `.gitignore` / `requirements.txt` / `README.md` | config/docs | — | RESEARCH.md Standard Stack + Structure (external) | external-canonical |
| *(optional)* `tests/test_config.py`, `tests/test_openai_client.py`, `tests/conftest.py` | test | unit | RESEARCH.md Validation Architecture / Wave 0 (external) | external-canonical |

## Pattern Assignments

Because there is no in-repo code, each assignment points to the exact RESEARCH.md excerpt to copy. All
line references below are into `01-RESEARCH.md`.

### `bot/config.py` (config, transform) — fail-fast env loader
- **Analog:** RESEARCH.md **Pattern 1** (lines ~200-223). Copy the `ConfigError`, frozen `Settings`
  dataclass, and `load_settings()` exactly.
- **Core pattern:** single reader of `os.environ`; collect missing required keys
  (`TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`) and raise `ConfigError` naming them; `OPENAI_MODEL` defaults
  to `gpt-4o-mini`. Optionally add `openai_timeout` default 60 (RESEARCH Open Q2 / Pitfall 5).
- **Constraint:** the ONLY module that reads `os.environ` (anti-pattern: scattered reads, lines ~263).

### `bot/openai_client.py` (service, request-response) — direct one-shot call
- **Analog:** RESEARCH.md **Code Example §2** (lines ~344-358).
- **Core pattern:** `async def complete(client, model, user_text)` → `await
  client.chat.completions.create(model=..., messages=[{system}, {user}])` → return
  `resp.choices[0].message.content or ""`. Messages rebuilt every call ⇒ no memory (MSG-02).
- **Constraints:** the ONLY module importing `openai`; use `AsyncOpenAI` + `await` (never sync client —
  Pitfall 3, lines ~293-297); NO adapter/factory/Protocol (anti-pattern, lines ~261).

### `bot/handlers.py` (controller/handler, request-response) — PTB async handlers
- **Analog:** RESEARCH.md **Code Example §3** (lines ~363-379) + Pattern 3 (lines ~247-256).
- **Core pattern:** three `async def h(update, context: ContextTypes.DEFAULT_TYPE)` coroutines.
  `start`/`help_cmd` reply static copy from `prompts.py` (no LLM). `handle_text` reads
  `update.message.text` (MSG-01), calls the injected completion via `context.bot_data["complete"]`
  (MSG-02/LLM-01), then `await update.message.reply_text(reply)` (MSG-03).
- **Constraint:** no SDK imports, no module globals, no hardcoded copy/model here.

### `bot/prompts.py` (config/constants, static) — copy in one place
- **Analog:** RESEARCH.md **Code Example §4** (lines ~383-394).
- **Core pattern:** `SYSTEM_PROMPT` (D-01 minimal persona + D-04 concise nudge + D-05 mirror language),
  `START_TEXT` (D-02), `HELP_TEXT` (D-03). Exact wording is Claude's discretion (CONTEXT D-section).

### `bot/main.py` (composition root, wiring) — framework-owned polling
- **Analog:** RESEARCH.md **Code Example §1** (lines ~313-341) + Pattern 2 (lines ~230-240).
- **Core pattern (strict order):** `logging.basicConfig(INFO)` → `load_settings()` FIRST (fail-fast
  before building anything) → `AsyncOpenAI(api_key=...)` (optional `timeout=`) → `ApplicationBuilder()
  .token(...).build()` → inject `app.bot_data["complete"]` closure → register `CommandHandler("start")`,
  `CommandHandler("help")`, `MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)` →
  `app.run_polling(allowed_updates=Update.ALL_TYPES)`.
- **Constraint:** never hand-roll `getUpdates` (anti-pattern, lines ~260).

### `bot/__main__.py` (entrypoint) — enables `python -m bot`
- **Analog:** RESEARCH.md **Code Example §5** (lines ~398-402): `from .main import main; main()`.

### Supporting files
- `requirements.txt` — copy verbatim from RESEARCH.md lines ~110-114 (`python-telegram-bot==22.7`,
  `openai==2.41.1`, `python-dotenv>=1.0,<2`).
- `.gitignore` — MUST include `.env` from commit #1 (Pitfall 2 / Security V14).
- `.env.example` — blank values for `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`, `OPENAI_MODEL`.
- `README.md` — run via `python -m bot` (RESEARCH Open Q3).

## Shared Patterns

Cross-cutting conventions Phase 1 *establishes* (no existing source — these become the project baseline):

### Async correctness (applies to: handlers.py, openai_client.py, main.py)
**Source:** RESEARCH.md Pattern 3 + Pitfall 3 (lines ~243-256, ~293-297).
Everything is `async` end-to-end: PTB handlers are coroutines; the OpenAI call uses `AsyncOpenAI` +
`await`. Never call a blocking/sync SDK method inside an `async def`.

### Fail-fast config / single env reader (applies to: config.py, consumed by main.py)
**Source:** RESEARCH.md Pattern 1 + Pitfall 1 (lines ~196-224, ~281-285).
`load_settings()` is the first call in `main()`; raises `ConfigError` naming any missing required var
before the `Application` is built. Explicit Phase 1 success criterion.

### Secrets hygiene (applies to: .env.example, .gitignore, all logging)
**Source:** RESEARCH.md Pitfall 2 + Security Domain V14 (lines ~287-291, ~513, ~526).
Secrets via environment only; `.env` gitignored from commit #1; `.env.example` with blank values; never
hardcode or log tokens/keys.

### Logging discipline (applies to: main.py setup, any future logging)
**Source:** RESEARCH.md anti-patterns + Security V7 (lines ~265, ~511, ~521).
stdlib `logging` at INFO; log chat id + status/latency only — never message bodies or replies.

### Error handling — DEFERRED, document only
**Source:** RESEARCH.md Pitfall 4 & 5 (lines ~299-306).
No retry/backoff/typed-error handling this phase (Phase 2). 4096-char reply limit is an accepted,
documented v1 limitation (D-04). A modest `AsyncOpenAI(timeout=60)` is acceptable hygiene (optional).

## No Analog Found

**All files.** No in-repo source exists (greenfield). This is expected and not a gap — the substitute
source-of-truth is `01-RESEARCH.md`'s verified Code Examples (§1-5) and Architecture Patterns (1-3),
mapped per-file in "Pattern Assignments" above. The planner/executor should reproduce those excerpts
directly rather than searching the (empty) codebase for analogs.

| File | Role | Data Flow | Reason no in-repo analog |
|------|------|-----------|--------------------------|
| all `bot/*.py` + support files | various | various | Greenfield Phase 1 — no prior source code; this phase sets the conventions |

## Metadata

**Analog search scope:** entire repository root (`**/*.py` glob)
**Files scanned:** 0 source files found (only `.planning/`, `CLAUDE.md`, `PRD.md` present)
**Source-of-truth substitute:** `01-RESEARCH.md` (Code Examples §1-5, Architecture Patterns 1-3) — verified against PTB 22.7 / openai 2.41.1 official docs
**Pattern extraction date:** 2026-06-12
