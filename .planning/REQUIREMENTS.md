# Requirements: Telegram AI Bot

**Defined:** 2026-06-11
**Core Value:** Send a message in Telegram, get a useful LLM reply back — reliably, 24/7.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Core Messaging

- [ ] **MSG-01**: Bot receives text messages from any Telegram user via long polling
- [ ] **MSG-02**: Each text message is sent to the configured LLM as a one-shot prompt (no conversation history)
- [ ] **MSG-03**: The LLM's reply is sent back to the user in the same chat

### Commands

- [ ] **CMD-01**: `/start` returns a short welcome explaining what the bot does
- [ ] **CMD-02**: `/help` returns brief usage guidance

### LLM Integration

- [ ] **LLM-01**: Bot calls the OpenAI (ChatGPT) API directly to generate the reply for each message; the model name is configurable via an environment variable

### Reliability

- [ ] **REL-01**: On LLM/network error or timeout, the bot replies with a friendly error message instead of going silent or crashing
- [ ] **REL-02**: A slow LLM call for one user does not block replies to other users (async / concurrent handling)
- [ ] **REL-03**: Exactly one polling instance runs per bot token (no 409 "terminated by other getUpdates" conflicts)

### Deployment & Ops

- [ ] **DEP-01**: The bot runs in a Docker container; the same image runs locally and on the droplet
- [ ] **DEP-02**: The bot runs 24/7 on a DigitalOcean droplet and auto-restarts on crash or reboot
- [ ] **DEP-03**: Secrets (Telegram token, LLM API keys) are provided via environment only — never committed to git or baked into the image
- [ ] **DEP-04**: Pushing to `main` triggers a GitHub Actions pipeline that builds the image and deploys it to the droplet

## v2 Requirements

Deferred to a future release. Tracked but not in the current roadmap.

### Bot UX

- **UX-01**: Typing indicator with keepalive while the LLM generates a reply
- **UX-02**: Split replies longer than Telegram's 4096-character limit across multiple messages
- **UX-03**: Non-text input guard — reply "text only" to photos/voice/stickers instead of ignoring them

### Cost & Abuse Controls

- **COST-01**: Cheap default model + max-output-token clamp + OpenAI dashboard billing cap
- **COST-02**: Per-user rate limiting
- **COST-03**: Global daily usage cap

### Conversation

- **CONV-01**: Multi-turn conversation memory (bot remembers prior messages in a chat)
- **CONV-02**: Configurable persona / system prompt

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Multi-provider / swappable LLM abstraction | Wired directly to OpenAI for v1 simplicity; switching providers later is a deliberate code change |
| Webhook delivery | Polling is simpler, needs no domain/HTTPS, and matches prior experience |
| Multimodal input (images, voice, files) | Text-only for v1; large surface area, needs vision/transcription |
| Streaming replies | High complexity; conflicts with reply splitting; deferred indefinitely |
| Group-chat support | Cost/abuse multiplier; wait until rate limiting exists |
| Per-user model selection / inline settings | Depends on state/memory; not useful until those exist |

## Known v1 Limitations

Accepted trade-offs from the minimal v1 scope (not bugs):

- **Long replies may fail to send.** Without UX-02 (reply splitting), any single LLM answer over 4096 characters will be rejected by Telegram. Acceptable for v1; first candidate to fix.
- **Unbounded cost.** The bot is public with no rate limits or spend caps (COST-*). Strangers' messages incur LLM token cost with no ceiling. Accepted per project decision; setting an OpenAI dashboard billing cap is recommended as a near-free backstop.

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| MSG-01 | TBD | Pending |
| MSG-02 | TBD | Pending |
| MSG-03 | TBD | Pending |
| CMD-01 | TBD | Pending |
| CMD-02 | TBD | Pending |
| LLM-01 | TBD | Pending |
| REL-01 | TBD | Pending |
| REL-02 | TBD | Pending |
| REL-03 | TBD | Pending |
| DEP-01 | TBD | Pending |
| DEP-02 | TBD | Pending |
| DEP-03 | TBD | Pending |
| DEP-04 | TBD | Pending |

**Coverage:**
- v1 requirements: 13 total
- Mapped to phases: 0 (set during roadmap creation)
- Unmapped: 13 ⚠️ (resolved by roadmapper)

---
*Requirements defined: 2026-06-11*
*Last updated: 2026-06-11 after initial definition*
