# Phase 5: UX Polish - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-16
**Phase:** 5-UX Polish
**Areas discussed:** Typing indicator duration, Reply split strategy, Non-text guard message

---

## Typing Indicator Duration

| Option | Description | Selected |
|--------|-------------|----------|
| Fire once, let it expire | Call send_chat_action once before/on receipt. Shows for ~5s then disappears. Zero extra complexity. | ✓ |
| Loop until reply arrives | Renew every 4s in background asyncio task. Keeps indicator alive for full call duration. | |
| You decide | Claude picks based on existing async pattern. | |

**User's choice:** Fire once, let it expire.
**Notes:** None.

---

## Typing Indicator Placement

| Option | Description | Selected |
|--------|-------------|----------|
| Right before the LLM call | Fire send_chat_action just before await complete(). Unauthorized users never see "typing...". | |
| Right after receiving the message | Fire before any processing — before allowed_chat_ids check. Every user sees instant feedback. | ✓ |

**User's choice:** Right after receiving the message (Option 2).
**Notes:** User initially asked for clarification on the two options. After explanation, chose to fire immediately on receipt so all users — authorized or not — see instant "typing..." feedback.

---

## Reply Split Strategy — Split Boundary

| Option | Description | Selected |
|--------|-------------|----------|
| At paragraph/newline boundaries | Find last \n before 4096-char limit and split there. Preserves paragraphs, avoids mid-sentence cuts. | ✓ |
| At the hard 4096-char limit | Slice string every 4096 chars. Simple but can cut mid-word. | |

**User's choice:** At paragraph/newline boundaries.
**Notes:** None.

---

## Reply Split Strategy — Message Cap

| Option | Description | Selected |
|--------|-------------|----------|
| Cap at 3 messages | Send first 3 chunks, truncate remainder with a note. Prevents chat flooding. | |
| No cap — send all parts | Send every chunk until reply is fully delivered. Could be 5–10 messages. | |
| You decide | Claude picks a sensible default. | ✓ |

**User's choice:** You decide (Claude's discretion).
**Notes:** Claude chose cap at 3 — 3×4096 chars ≈ 2,400 words, already very long for a chat context.

---

## Reply Split Strategy — Message Threading

| Option | Description | Selected |
|--------|-------------|----------|
| Reply to original for first, sequential after | Part 1 quotes user's message; parts 2–3 are plain send_message. | |
| All parts as replies to original | Every part quotes/threads back to original message. | ✓ |
| All parts sequential (no reply threading) | All parts as plain send_message. Loses thread anchor. | |

**User's choice:** All parts as replies to original.
**Notes:** User asked for explanation of reply threading vs. plain send. After seeing visual examples, said "quoted is kinda good" and then confirmed they want all parts quoted.

---

## Non-text Guard Message — Response Type

| Option | Description | Selected |
|--------|-------------|----------|
| Generic message for all types | One response for all non-text types. Simple, one handler. | ✓ |
| Type-aware messages | Different responses per type (photo, voice, sticker, etc.). Friendlier but more branching. | |

**User's choice:** Generic message for all types.
**Notes:** None.

---

## Non-text Guard Message — Tone

| Option | Description | Selected |
|--------|-------------|----------|
| Helpful nudge | "I only understand text messages — send me a question and I'll reply!" | ✓ |
| Minimal/factual | "Text messages only." Short and direct. | |
| You write it | User provides exact wording. | |

**User's choice:** Helpful nudge.
**Notes:** None.

---

## Non-text Guard Message — Authorization Check

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — all users get guard message | Unauthorized users who send non-text get the guard message too. No silent drops. | ✓ |
| No — only authorized users get guard message | Unauthorized non-text senders are silently dropped. More obscure. | |

**User's choice:** Yes — all users get the guard message.
**Notes:** None.

---

## Claude's Discretion

- **Message cap for reply splitting:** Cap at 3 messages. Rationale: 3×4096 ≈ 2,400 words is already very long for a Telegram chat. Prevents flooding for edge-case very long LLM responses.
- **Exact wording of truncation note:** Open (e.g. `...(truncated)`).
- **Exact wording of guard message:** "I only understand text messages — send me a question and I'll reply!" (tone is locked; exact phrasing open to minor polish).

## Deferred Ideas

None — discussion stayed within phase scope.
