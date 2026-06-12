# Phase 1: Working AI Bot - Context

**Gathered:** 2026-06-12
**Status:** Ready for planning

<domain>
## Phase Boundary

A running Telegram bot that: receives a user's text message via long polling, sends it to the OpenAI (ChatGPT) API as a one-shot prompt, and returns the reply in the same chat — plus `/start` and `/help` commands. Configuration (Telegram token, OpenAI key, model name) comes from environment variables, and the bot fails fast at boot if a required variable is missing.

**In scope:** MSG-01, MSG-02, MSG-03, CMD-01, CMD-02, LLM-01 (happy-path text → reply).
**Out of scope (later phases):** error/timeout handling and async concurrency (Phase 2), Docker + droplet + 24/7 (Phase 3), tests + CI/CD (Phase 4). Also deferred (v2): typing indicator, long-reply splitting, non-text input guard, memory, persona config, cost/rate controls.
</domain>

<decisions>
## Implementation Decisions

The user reviewed the gray areas and delegated these UX choices to Claude ("the PRD is good… let's start"). Recorded defaults:

### Assistant Persona & Tone
- **D-01:** Minimal system prompt — a single "You are a helpful assistant" style instruction. Friendly, concise, neutral. No elaborate character/persona for v1 (configurable persona is deferred to v2).

### Command Copy (`/start`, `/help`)
- **D-02:** `/start` — short welcome that tells the user they can just send a message and get an AI reply, and points to `/help`. Keep it one or two short lines.
- **D-03:** `/help` — explains the bot answers any text message using AI, one message at a time, with no memory of past messages yet. Plain, brief.

### Reply Behavior
- **D-04:** Soft-nudge the model toward reasonably concise answers via the system prompt (helps cost and reduces the chance of hitting Telegram's 4096-char limit). **No hard `max_tokens` cap** — cost controls are deliberately deferred (PRD §9). The >4096-char failure remains a documented known limitation for v1.
- **D-05:** Reply in the **same language the user writes in** (e.g. Khmer in → Khmer out). Achieved via a system-prompt instruction; rely on the model's native multilingual ability.

### Claude's Discretion
- Exact wording of the system prompt and the `/start` / `/help` text.
- Project/module layout, function names, and how config is read/validated (planner/executor decide).
- Local run mechanism (e.g. `python main.py` / `.env` loading) and dependency pinning.
- OpenAI call parameters beyond the model (e.g. temperature) — pick sensible defaults for a general assistant.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Product & Requirements
- `PRD.md` — full product requirements; §5 architecture, §6 F1–F3 (MSG/CMD/LLM), §7 configuration reference (env vars + defaults)
- `.planning/PROJECT.md` — project context, constraints, key decisions (direct OpenAI, gpt-4o-mini default)
- `.planning/REQUIREMENTS.md` — requirement IDs MSG-01..03, CMD-01..02, LLM-01 (Phase 1 scope)
- `.planning/ROADMAP.md` — Phase 1 goal + success criteria

### Research (stack/architecture/pitfalls)
- `.planning/research/STACK.md` — Python 3.12, python-telegram-bot 22.7, openai 2.41.1; versions verified
- `.planning/research/ARCHITECTURE.md` — component boundaries, data flow, build order
- `.planning/research/PITFALLS.md` — relevant now: fail-fast on missing config, secrets via env only (others like concurrency/409 belong to Phase 2)
- `.planning/research/SUMMARY.md` — consolidated findings
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield project, no source code exists yet. This phase establishes the initial structure.

### Established Patterns
- None yet. Phase 1 sets the conventions (env-based config, module layout) that later phases extend.

### Integration Points
- External services only: Telegram Bot API (polling) and OpenAI ChatGPT API. No internal systems to integrate with.
</code_context>

<specifics>
## Specific Ideas

- The user's own description of the loop matches the plan exactly: "create a bot → get token → choose model + key → python script gets user input → small prompt with the input → run through LLM → send output back to Telegram."
- A second BotFather token should be used for local testing vs. production to avoid 409 conflicts (relevant from Phase 2/3, noted here so it's not forgotten).
</specifics>

<deferred>
## Deferred Ideas

- **Configurable persona / system prompt** — v2 (CONV-02). v1 uses a fixed minimal prompt.
- **Long-reply splitting (>4096 chars)** — v2 (UX-02). v1 accepts the known limitation.
- **Typing indicator, non-text input guard** — v2 (UX-01, UX-03).
- **Cost controls (max_tokens clamp, rate limits, billing cap)** — v2 (COST-*); OpenAI dashboard billing cap recommended operationally before going public.

None of these are in Phase 1 scope — captured so they aren't lost.
</deferred>

---

*Phase: 1-Working AI Bot*
*Context gathered: 2026-06-12*
