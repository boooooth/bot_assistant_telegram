# Phase 1: Working AI Bot - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-12
**Phase:** 1-Working AI Bot
**Areas discussed:** Persona & tone, /start & /help wording, Reply length, Reply language (all delegated to Claude)

---

## Gray areas presented

The user was offered four gray areas to decide. They reviewed them and chose to delegate all to Claude — *"since the prd is good, if you dont need anymore answer from me, let's start then"* — accepting sensible defaults rather than discussing each.

| Area | Options offered | Outcome |
|------|-----------------|---------|
| Assistant persona & tone | Defined persona/system prompt vs. blank "helpful assistant" | Delegated → minimal "helpful assistant", concise/friendly (D-01) |
| `/start` & `/help` wording | What the commands say | Delegated → short welcome + brief usage (D-02, D-03) |
| Reply length / conciseness | Free-running vs. nudge concise | Delegated → soft-nudge concise, no hard cap (D-04) |
| Reply language behavior | Always English vs. match user's language | Delegated → match user's language (D-05) |

**User's choice:** Proceed with Claude's sensible defaults for all four; no further discussion.
**Notes:** The user confirmed the PRD captures requirements correctly and wanted to start building. Their own description of the message loop matched the planned Phase 1 flow exactly.

---

## Claude's Discretion

- Exact system prompt and `/start` / `/help` copy
- Module layout, naming, config-reading approach
- Local run mechanism and dependency pinning
- OpenAI call parameters beyond model (e.g. temperature)

## Deferred Ideas

- Configurable persona / system prompt — v2 (CONV-02)
- Long-reply splitting (>4096 chars) — v2 (UX-02)
- Typing indicator, non-text input guard — v2 (UX-01, UX-03)
- Cost controls (max_tokens clamp, rate limits, billing cap) — v2 (COST-*)
- Separate BotFather token for local vs. production (relevant Phase 2/3)
