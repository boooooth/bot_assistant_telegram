# Phase 5: UX Polish - Context

**Gathered:** 2026-06-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Add three targeted UX behaviors to the existing handler layer: (1) a typing indicator shown to the user while the LLM call is in flight, (2) automatic splitting of long LLM replies across multiple messages when the response exceeds Telegram's 4096-char limit, and (3) a friendly response to non-text messages (photo, voice, sticker, video, file) instead of the current silent drop.

**In scope:** Typing indicator, reply splitting, non-text message guard.
**Out of scope:** Conversation memory, rate limiting, streaming responses, persona changes, webhook mode.

</domain>

<decisions>
## Implementation Decisions

### Typing Indicator
- **D-01:** Fire `send_chat_action(ChatAction.TYPING)` once — fire-and-forget, let the ~5s TTL expire naturally. No background renewal loop.
- **D-02:** Fire the typing action immediately after receiving the message (before the `allowed_chat_ids` check), so every user — authorized or not — sees "typing..." as instant feedback.

### Reply Splitting
- **D-03:** Split at paragraph/newline boundaries. Find the last `\n` before the 4096-char limit and split there. Preserves paragraph structure; avoids cutting mid-sentence.
- **D-04:** Cap at 3 messages. If the reply requires more than 3 chunks, send the first 3 and append a truncation note (e.g. `...(truncated)`).
- **D-05:** All split parts sent as `reply_text()` with `reply_to_message_id` pointing to the original user message. Every chunk shows the quoted reply — consistent visual threading.

### Non-text Guard
- **D-06:** One generic `MessageHandler` with `~filters.TEXT & ~filters.COMMAND` catches all non-text types (photo, voice, sticker, video, document, etc.) — no per-type branching.
- **D-07:** Guard message tone: helpful nudge — "I only understand text messages — send me a question and I'll reply!"
- **D-08:** The guard applies to all users including those not in `allowed_chat_ids`. No silent drops for anyone — unauthorized users who send non-text messages get the guard message too.

### Claude's Discretion
- Cap for reply splitting is 3 messages (chosen by Claude: 3×4096 chars ≈ 2,400 words, already very long for a chat context).
- Exact wording of the truncation note after the 3-message cap.
- Exact wording of the non-text guard message (tone is "helpful nudge" per D-07).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Product & Requirements
- `.planning/ROADMAP.md` — Phase 5 goal and scope (typing indicator, reply splitting, non-text guard)
- `.planning/PROJECT.md` — key decisions, constraints, established stack

### Existing Code (integration points for all three features)
- `bot/handlers.py` — `handle_text` is the integration point for typing indicator (D-01, D-02), reply splitting (D-03–D-05), and the pattern to follow for the new guard handler
- `bot/main.py` — handler registration; non-text guard requires adding a new `MessageHandler` here with `~filters.TEXT & ~filters.COMMAND`
- `bot/prompts.py` — where new user-facing strings (guard message, truncation note) should live alongside `START_TEXT`, `HELP_TEXT`

### Tests
- `tests/test_handlers.py` — existing test file and `asyncio.run()` idiom; new tests for all three behaviors go here

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `update.message.reply_text()` — established reply pattern; used for typing indicator placement, split parts (D-05), and guard response (D-06)
- `context.bot.send_chat_action()` — PTB async method for `ChatAction.TYPING`; available on the bot object already in scope inside handlers
- `filters.TEXT & ~filters.COMMAND` in `main.py` — existing filter pattern; non-text guard inverts this with `~filters.TEXT & ~filters.COMMAND`
- `bot/prompts.py` — already holds `START_TEXT`, `HELP_TEXT`, `SYSTEM_PROMPT`; natural home for new strings

### Established Patterns
- All handlers are `async def (update, context)` — new guard handler follows the same signature
- Error handling in `handle_text` uses a bare `except Exception` with `logger.exception()`; same pattern applies if splitting raises
- `asyncio.run()` idiom in tests (not pytest-asyncio) — new handler tests follow this

### Integration Points
- `bot/main.py` line 29: `app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))` — add the non-text guard handler after this line with an inverted filter
- `handle_text` lines 35–43: LLM call + reply block — typing indicator fires before line 35 (before auth check per D-02); reply split replaces the single `reply_text(reply)` call at line 42

</code_context>

<specifics>
## Specific Ideas

- The reply split helper should be a standalone function (e.g. `split_text(text, max_len=4096)`) that returns a list of chunks — keeps `handle_text` readable and makes the splitter independently testable.
- All user-facing strings (guard message, truncation note) go in `bot/prompts.py` as constants — consistent with `START_TEXT` / `HELP_TEXT` pattern already there.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 5-UX Polish*
*Context gathered: 2026-06-16*
