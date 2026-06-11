# Feature Research

**Domain:** Public Telegram bot fronting an LLM (general-purpose AI assistant, one-shot text replies)
**Researched:** 2026-06-11
**Confidence:** HIGH (table stakes / anti-features), MEDIUM (some differentiator complexity estimates)

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist on any LLM chat bot. Missing these makes the bot feel broken even though the locked v1 scope is intentionally minimal.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `/start` command | First thing every Telegram user sends; bots that ignore it look dead. Telegram auto-sends `/start` when a user opens a bot for the first time. | LOW | Reply with a short "I'm an AI assistant, just send me a message" greeting. No registration needed for v1. |
| `/help` command | Telegram convention; users expect a usage/commands summary. | LOW | Static text: what the bot does, that it has no memory, that it's text-only. |
| Plain-text message → LLM → reply | The core value. A text message must reliably produce an LLM answer. | LOW | One-shot: build a fresh single-message prompt per request, no history. Already the locked core behavior. |
| Typing indicator (`sendChatAction: typing`) | LLM latency is 2–60s; without feedback users assume the bot is broken and re-send. | MEDIUM | The action auto-clears after ~5s, so a **keepalive loop** must re-send every ~4–5s until the reply is ready, then stop. This is the #1 subtle bug in the ecosystem (indicator stuck on forever) — ensure cleanup/cancel on completion or error. |
| Long-reply splitting (4096-char limit) | LLMs routinely exceed Telegram's 4096-UTF8-char message cap; the API rejects oversized `sendMessage` calls. | MEDIUM | Split bot-side into ≤4096-char chunks, send sequentially. Prefer splitting on paragraph/line boundaries, not mid-word. Note: messages can arrive out of order; a small delay between chunks reduces this and avoids flood limits. |
| Graceful error message on LLM/API failure | Timeouts, rate limits, provider 5xx, and network errors are routine for a public bot. Silence = looks broken. | LOW | Catch exceptions around the LLM call and the Telegram send; reply with a short, friendly "Sorry, something went wrong, please try again." Never leak stack traces or API keys. |
| Basic text formatting (or safe plain text) | Users expect code blocks, bold, lists to render — LLMs emit Markdown by default. | MEDIUM | **Pitfall:** Telegram MarkdownV2 requires escaping 18 special chars; raw LLM Markdown frequently triggers `400 Bad Request: can't parse entities` and the whole reply fails to send. Safest v1: send as **plain text** (no `parse_mode`), or use HTML mode (only `<`, `>`, `&` to escape), or a Markdown→entities converter. Always have a plain-text fallback resend on parse failure. |
| Handles non-text input without crashing | Locked scope is text-only, but strangers will send photos, stickers, voice, files. | LOW | Don't crash or hang — reply with a one-line "I only handle text right now." Distinct from *supporting* media (a differentiator). |
| 24/7 reliability / auto-restart | A public bot that silently dies between deploys feels broken. | LOW–MEDIUM | Covered by the Docker + droplet decision (restart policy). Feature-level requirement: the polling loop must survive transient errors and keep running. |

### Differentiators (Competitive Advantage)

Features that set richer bots apart. **All deferred** per locked v1 decisions; listed so the roadmap can sequence them later.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Conversation memory / multi-turn context | The single biggest quality jump; turns a "query box" into a real assistant. | HIGH | Explicitly out of scope for v1 (locked: one-shot). Requires per-user session store, context-window management, and trimming. Drives state + storage architecture. |
| Streaming / progressive replies | Perceived latency drops dramatically; reply appears token-by-token via repeated `editMessageText`. | HIGH | Needs partial-message editing, edit-rate throttling (Telegram limits edit frequency), and re-introduces the MarkdownV2 parse problem on every edit. Defer until after v1 stability. |
| Multimodal input (images, voice, files) | Lets users ask about photos / send voice notes; major engagement driver. | HIGH | Out of scope for v1 (locked: text-only). Requires media download, transcription (voice) or vision model, and provider capability checks. |
| Persona / configurable system prompt | Brand voice or specialized assistant (coding, tutor, etc.). | LOW–MEDIUM | Out of scope for v1 (locked: general assistant, no fixed persona). Cheap to add later via a system-prompt env var once the adapter exists. |
| Inline buttons / commands (`/reset`, `/model`, settings) | Lets users switch model or clear context without typing. | MEDIUM | Most useful *after* memory/multi-model exist; little value in a stateless one-shot bot. |
| Multi-model selection per user | Power users pick GPT-4 vs cheaper models. | MEDIUM | Builds on the swappable adapter, but per-user choice needs state. The adapter design (locked) makes the *backend* swap trivial; per-user UI is the extra work. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that look essential but should be deliberately excluded from v1.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Conversation memory in v1 | "An assistant should remember." | Adds session storage, context-window trimming, and cost growth per turn; the single largest source of v1 scope creep. | Ship one-shot (locked), validate demand, add memory as a planned v1.x feature with its own storage design. |
| Rate limiting / usage caps / abuse guardrails | Cost protection on a public bot. | Genuinely needed eventually, but building it well (per-user quotas, persistence, banning) is its own subsystem. Locked decision is to accept the cost risk for v1. | Defer deliberately. Track spend via the OpenAI dashboard; flag as the **first** thing to add before any real scaling. Document the known unbounded-cost risk. |
| Webhook delivery | "Webhooks are more efficient / production-grade." | Requires a public URL, domain, and TLS — none of which the droplet+polling setup has. Adds ops surface for no v1 benefit. | Polling (locked). Revisit only if scale demands it. |
| MarkdownV2 formatting by default | Pretty rendered replies. | Raw LLM Markdown breaks Telegram's MarkdownV2 parser constantly (`400: can't parse entities`), causing whole replies to fail to send. | Send plain text in v1 (or HTML / entity-converter with a plain-text fallback). Treat rich formatting as a later polish. |
| Heavy multi-provider framework (e.g. LiteLLM) | "Swap any provider easily." | Large dependency for a tiny bot; the locked decision is a hand-rolled adapter. | Thin internal interface + per-provider impl selected by env var (locked architecture decision). |
| Group-chat support / `@mention` handling | "Add it to my group." | Adds mention parsing, privacy-mode config, and multiplies cost/abuse exposure on a guardrail-free public bot. | Keep v1 to 1:1 DMs. Consider groups only after rate limiting exists. |
| Slick onboarding / settings menus | Polish. | No state and no persona in v1 means nothing to configure; pure overhead. | Minimal `/start` + `/help` text only. |

## Feature Dependencies

```
Plain-text message -> LLM -> reply  (core, v1)
    └──requires──> LLM adapter (env-var provider select)
    └──enhanced by──> Typing indicator keepalive (v1)
    └──enhanced by──> Long-reply splitting (v1)
    └──enhanced by──> Graceful error handling (v1)
    └──enhanced by──> Safe formatting / plain-text fallback (v1)

Streaming replies
    └──requires──> editMessageText throttling
    └──conflicts──> Long-reply splitting (both manage message boundaries)
    └──re-triggers──> Markdown parse problem on every edit

Conversation memory (v1.x)
    └──requires──> per-user session store
    └──requires──> context-window trimming
    └──enables──> /reset command, multi-turn quality

Per-user model selection
    └──requires──> per-user state (same store as memory)
    └──builds on──> LLM adapter

Rate limiting / guardrails
    └──requires──> per-user counters + persistence
    └──gates──> safe public scaling, group support
```

### Dependency Notes

- **Everything requires the LLM adapter:** the hand-rolled, env-var-selected adapter (locked) is the spine; build it first.
- **Typing keepalive is independent and cheap** but needs a cancel/cleanup path or it sticks on indefinitely (the ecosystem's most common bug).
- **Streaming conflicts with simple long-reply splitting:** both decide message boundaries, and streaming reintroduces formatting fragility. Don't attempt both in the same phase; ship splitting first.
- **Memory and per-user model selection share a state store:** if/when memory is built, model selection becomes cheap to add on top.
- **Guardrails gate scaling and group chat:** anything that increases exposure should wait until rate limiting exists.

## MVP Definition

### Launch With (v1)

Minimum viable, fully consistent with the locked decisions.

- [ ] Polling loop that receives text messages and stays up — core delivery (locked).
- [ ] `/start` and `/help` commands — Telegram convention; bot feels alive.
- [ ] Text message → LLM (one-shot, no history) → reply via hand-rolled adapter — the core value (locked).
- [ ] Typing indicator with keepalive + cleanup — essential UX given LLM latency.
- [ ] Long-reply splitting at the 4096-char limit — prevents the API rejecting big answers.
- [ ] Graceful error reply on LLM/Telegram/network failure — public bot hits these constantly.
- [ ] Safe output formatting: plain text (or HTML/entity converter) with plain-text fallback on parse error — avoids whole-reply failures.
- [ ] Non-text input gets a polite "text only" reply instead of crashing.

### Add After Validation (v1.x)

- [ ] Rate limiting / usage caps — **trigger: any real traffic or cost concern; this is the first thing to add.**
- [ ] Conversation memory (multi-turn) — trigger: users repeatedly want follow-up context.
- [ ] Configurable persona / system prompt — trigger: a clear use-case niche emerges (cheap once adapter exists).

### Future Consideration (v2+)

- [ ] Streaming replies — defer: high complexity, conflicts with splitting, reintroduces formatting fragility.
- [ ] Multimodal (images / voice / files) — defer: large surface, needs vision/transcription + media handling.
- [ ] Per-user model selection + inline settings — defer: needs state and only matters with memory/multi-model.
- [ ] Group-chat support — defer until guardrails exist (cost/abuse multiplier).

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Text → LLM → reply (one-shot) | HIGH | LOW | P1 |
| `/start` + `/help` | MEDIUM | LOW | P1 |
| Typing indicator + keepalive | HIGH | MEDIUM | P1 |
| Long-reply splitting (4096) | HIGH | MEDIUM | P1 |
| Graceful error handling | HIGH | LOW | P1 |
| Safe formatting / plain-text fallback | MEDIUM | MEDIUM | P1 |
| Non-text input "text only" guard | MEDIUM | LOW | P1 |
| Rate limiting / usage caps | HIGH (post-launch) | MEDIUM | P2 |
| Conversation memory | HIGH | HIGH | P2 |
| Persona / system prompt | MEDIUM | LOW | P2 |
| Streaming replies | MEDIUM | HIGH | P3 |
| Multimodal input | HIGH | HIGH | P3 |
| Per-user model selection | MEDIUM | MEDIUM | P3 |
| Group-chat support | MEDIUM | MEDIUM | P3 |

**Priority key:** P1 = must have for launch · P2 = add after validation · P3 = future consideration.

## Competitor Feature Analysis

| Feature | `father-bot/chatgpt_telegram_bot` (popular OSS) | Lightweight LLM bots (e.g. `DoctorLai/llm-telegram-bot`) | Our v1 Approach |
|---------|--------------------------------------------------|----------------------------------------------------------|-----------------|
| Memory | Yes (multi-turn, per-chat) | Minimal / optional | None — one-shot (locked) |
| Streaming | Yes (part-by-part edits) | No | No — full reply, split if long |
| Formatting | Markdown with escaping logic | Often plain text | Plain text / HTML with fallback |
| Multimodal | Yes (voice, images) | No | No — text only (locked) |
| Provider abstraction | OpenAI-centric | Often single provider | Hand-rolled adapter, env-var swap (locked) |
| Rate limiting | Per-user allowed-list / quotas | Usually none | None in v1 (locked, accepted cost risk) |
| Delivery | Polling | Polling | Polling (locked) |

Takeaway: our v1 deliberately matches the *lightweight* tier, not the feature-rich tier. The richer bots' headline features (memory, streaming, multimodal, guardrails) are exactly our deferred/anti-feature list — the deferral is intentional and consistent.

## Sources

- Telegram Bot API — features, formatting, message limits: https://core.telegram.org/bots/api , https://core.telegram.org/bots/features (HIGH — official)
- `sendChatAction` reference (typing, 5s expiry): https://telegram-bot-sdk.readme.io/reference/sendchataction (HIGH — official-derived)
- Typing-indicator keepalive / stuck-indicator bugs: openclaw issues #26621, #26761, #27177, #27219 (MEDIUM — corroborated community/issue reports)
- 4096-char limit & splitting practice: node-telegram-bot-api #165, father-bot #268, java-telegram-bot-api #226 (MEDIUM–HIGH — corroborated across libraries)
- MarkdownV2 escaping pitfalls & plain-text/HTML fallback: botnamefinder MarkdownV2 escape guide, symfony #42697, sudoskys/telegramify-markdown (MEDIUM — multiple corroborating sources)
- Competitor feature sets: github.com/father-bot/chatgpt_telegram_bot , github.com/kirill-markin/chatgpt-telegram-bot-telegraf , github.com/DoctorLai/llm-telegram-bot (HIGH — primary repos)

---
*Feature research for: public Telegram LLM assistant bot (one-shot, text-only, polling)*
*Researched: 2026-06-11*
