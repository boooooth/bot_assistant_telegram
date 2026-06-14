# Pitfalls Research

**Domain:** Public Telegram bot fronting an LLM (general-purpose AI assistant, polling-based, OpenAI default, Dockerized on a Linux VPS, deployed via GitHub Actions)
**Researched:** 2026-06-11
**Confidence:** HIGH

These pitfalls are specific to a Telegram-bot-to-LLM bridge. Generic web/security advice is omitted. Every critical pitfall is something that has bitten this exact class of project. Locked decisions (public, no guardrails v1, one-shot, polling, OpenAI default, Docker, Linux VPS, GitHub Actions) are respected — the risks each creates are flagged rather than argued against.

## Critical Pitfalls

### Pitfall 1: Unbounded cost from a public, uncapped bot (ACCEPTED RISK — flagged)

**What goes wrong:**
The bot is public with no rate limiting, no per-user caps, and no spend ceiling. Every stranger's message — including spam, abuse, automated floods, and "jailbreak my homework" essays — bills the owner's OpenAI account. A single bad actor scripting `sendMessage` in a loop, or the bot link getting shared in a large group, can run the bill from a few dollars to hundreds in hours. The owner has explicitly accepted this for v1, but the failure mode is real and fast.

**Why it happens:**
v1 deliberately omits guardrails for leanness. Cost is invisible until the OpenAI invoice or the prepaid balance drains. There is no natural backpressure — Telegram delivers every message, the bot forwards every message, OpenAI bills every message.

**How to avoid (cheap mitigations, even if deferred):**
The user accepted unbounded spend, but the following cost almost nothing and should be on the table:
- **Set a hard OpenAI billing limit / monthly budget cap** in the OpenAI dashboard (Settings → Limits). This is the single most important mitigation — zero code, and it converts "unbounded" into "bounded by a number you chose." When the cap is hit, the API returns 429 `insufficient_quota` and the bot simply stops spending. **Strongly recommend doing this in v1 even though caps are out of scope** — it is account configuration, not bot code.
- **Use a cheap default model** (e.g. a `gpt-4o-mini`-class / small model) rather than a flagship model. 10–30x cost difference per token for a general-assistant use case.
- **Clamp `max_tokens` on completions** so a single reply can't generate a 4000-token essay. One line in the adapter.
- **(Deferred, design for it now):** a trivial in-memory per-user-id throttle (e.g. N messages / minute) is a few lines and is the natural place the "revisit before scaling" decision lands. Leave a clean seam for it.

**Warning signs:**
OpenAI usage dashboard climbing faster than your own testing explains; replies to messages you didn't send; the same `user_id` or `chat_id` appearing dozens of times per minute in logs; sudden spike after the bot username is posted anywhere public.

**Phase to address:**
The OpenAI billing cap + cheap model + `max_tokens` clamp belong in the **LLM adapter / OpenAI integration phase** (configuration, not feature). Per-user throttling is a deliberate post-v1 item but the adapter/dispatch phase should leave a seam for it.

---

### Pitfall 2: Two instances polling the same bot token (409 Conflict)

**What goes wrong:**
Only one consumer may call `getUpdates` per bot token. The moment a second consumer starts — your laptop dev instance is still running while the droplet deploys, a GitHub Actions deploy starts the new container before stopping the old one, or someone runs the bot locally to debug prod — Telegram returns **HTTP 409 `Conflict: terminated by other getUpdates request`**. Updates start getting split between instances or dropped, replies look random or duplicated, and the bot appears "flaky" with no obvious cause.

**Why it happens:**
The constraint is invisible: nothing stops you from starting a second process, and Telegram's only signal is a 409 buried in logs. Polling makes this especially easy to trip because there's no webhook URL collision to make the duplication obvious. The deploy pipeline is the most common trigger — naive "build then `docker run`" without stopping the old container leaves two pollers up.

**How to avoid:**
- **Exactly one polling process per token, always.** Treat this as an invariant.
- Deploy must **stop the old container before starting the new one** (`docker stop`/`docker rm` or `docker compose up -d` which recreates, with a brief overlap is unavoidable but should be minimized — accept the few-second gap rather than running both).
- Use a **separate bot token for local dev** (a second bot via BotFather). Never poll prod's token from a laptop.
- Treat a 409 in logs as a **page-worthy error**, not noise — it means a phantom second poller exists.

**Warning signs:**
`Conflict: terminated by other getUpdates request` / 409 in logs; users report intermittent no-reply or double-reply; messages handled "sometimes"; behavior changes depending on whether your laptop is on.

**Phase to address:**
Two phases. The **single-instance invariant + dev-vs-prod token separation** is a bot-runtime/config concern (polling setup phase). The **stop-old-before-start-new** ordering is a CI/CD deploy phase concern and must be an explicit step in the GitHub Actions workflow.

---

### Pitfall 3: Slow LLM call blocks the whole bot (no concurrency)

**What goes wrong:**
`python-telegram-bot` v20+ (and equivalent async frameworks) process updates **sequentially by default** (`concurrent_updates=0`). An LLM completion can take 5–30+ seconds. While the bot awaits OpenAI for user A, users B, C, D get no response — their messages queue behind A. With a public bot and several simultaneous users, the bot feels dead. If the handler is written with a blocking (synchronous) HTTP call instead of `await`, it's even worse: it stalls the entire event loop including the poller itself.

**Why it happens:**
The default sequential behavior is safe and invisible at single-user testing scale — you never notice because you're the only user. It only manifests under concurrent public load. Mixing a synchronous OpenAI SDK call into an async handler is an easy mistake that silently serializes everything.

**How to avoid:**
- Enable concurrent update processing: `ApplicationBuilder().concurrent_updates(True)` (or an integer cap). One-shot replies with no shared state make this safe — there's no `ConversationHandler` ordering to break.
- Use the **async** OpenAI client (`AsyncOpenAI`) and `await` it; never call a blocking SDK method inside an async handler. If using a sync framework, offload to a thread/worker.
- Size `connection_pool_size` / `pool_timeout` to match the concurrency level so parallel handlers don't exhaust the HTTP pool (a documented gotcha when using `concurrent_updates`).
- Send a quick "typing…" chat action so users know it's working during the wait.

**Warning signs:**
Replies arrive in strict first-come-first-served order with long gaps; a single slow request makes all users wait; bot stops polling entirely while a request is in flight; "pool timeout" / connection pool warnings in logs once concurrency is on but pool size isn't raised.

**Phase to address:**
**Polling/dispatch phase** — concurrency must be a designed-in property from the first working bot, not retrofitted. The async LLM call belongs to the **LLM adapter phase**; the two must be consistent (async all the way down).

---

### Pitfall 4: 4096-character message limit silently truncates or 400s LLM replies

**What goes wrong:**
Telegram's `sendMessage` text field is capped at **4096 UTF-8 characters**. LLMs happily produce longer replies (code dumps, long explanations). Send one as-is and the API rejects it with a 400 (`message is too long`) — the user gets *nothing*, not a truncated reply. The bot looks broken specifically on the most useful (longest) answers.

**Why it happens:**
Testing uses short prompts that yield short replies, so the limit is never hit in dev. It's a content-length edge case that only the real world exercises. UTF-8 counting (emoji, non-Latin scripts cost more) makes naive `len()` checks wrong.

**How to avoid:**
- **Split long replies into ≤4096-char chunks** and send sequentially, or clamp `max_tokens` so replies stay short (also helps cost — see Pitfall 1).
- Split on a safe boundary (newline/paragraph), not mid-word; be careful not to split inside a Markdown/HTML entity if using formatted parse modes (an unclosed entity also 400s).
- Count by encoded length, not Python `len()`, if near the boundary.

**Warning signs:**
Long answers produce silence while short ones work; `Bad Request: message is too long` or `400` in logs; users say "it ignores my hard questions."

**Phase to address:**
**LLM adapter / reply-delivery phase** — chunking is part of "send the reply back," and the `max_tokens` clamp ties into the OpenAI integration.

---

### Pitfall 5: No OpenAI error/timeout handling — bot hangs or dies on the first hiccup

**What goes wrong:**
OpenAI calls fail in normal operation: 429 rate limits, 429 `insufficient_quota` (out of money), 500/503 transient errors, and — most insidious — calls that just hang with no response. Without an explicit request timeout, a single stuck call can tie up a handler (and, combined with Pitfall 3, the whole bot) indefinitely. Without retry, transient 500s surface to users as failures. Without distinguishing error types, the bot either spams retries against an out-of-quota account or gives up on recoverable errors.

**Why it happens:**
The happy path works in testing, so error handling gets deferred and never added. Defaults often have generous or no timeout. Devs treat all 429s the same when `rate_limit_exceeded` (wait + retry) and `insufficient_quota` (stop) require opposite responses — and retrying a failed request still counts against the per-minute limit, deepening the hole.

**How to avoid:**
- **Always set an explicit request timeout** on the OpenAI client (e.g. 30–60s) so a hung call can't wedge a handler.
- **Retry transient errors (429 rate_limit, 5xx) with exponential backoff + jitter** (e.g. `tenacity.wait_random_exponential`); honor the `retry-after-ms` header when present.
- **Do not retry `insufficient_quota` or 4xx auth/validation errors** — reply to the user with a graceful message and stop. (This is also the cap-hit path from Pitfall 1.)
- Cap total retries (e.g. 3) so a degraded API doesn't make users wait forever.
- On final failure, send the user a friendly "I couldn't get an answer right now, try again" rather than silence or a stack trace.

**Warning signs:**
Bot occasionally goes silent under load; handlers that never complete; retry storms in logs against a quota-exhausted key; users see no reply when OpenAI has a transient blip; unhandled-exception tracebacks in container logs.

**Phase to address:**
**LLM adapter / OpenAI integration phase.** Build timeout + typed-error handling + retry policy as part of the adapter so swapping providers later inherits the same robustness contract.

---

### Pitfall 6: Leaked API tokens / secrets (Telegram token + OpenAI key)

**What goes wrong:**
The Telegram bot token and OpenAI API key get committed to git, baked into the Docker image, printed in logs, or hardcoded in source. A leaked Telegram token lets anyone hijack the bot (and, via getUpdates, race you — Pitfall 2). A leaked OpenAI key lets anyone spend your money (Pitfall 1, but uncapped and external). Public-repo key leaks get scraped by bots within minutes.

**Why it happens:**
Quick local testing with a hardcoded key that "I'll move to env later"; `.env` accidentally committed because it isn't gitignored; secrets baked into the image at build time via `ARG`/`COPY .`; logging the full request including headers; CI logs echoing secrets.

**How to avoid:**
- Secrets via **environment variables only**, never in source. `.env` in `.gitignore` from commit #1; ship a `.env.example` with blank values.
- **Never `COPY .env` or bake keys into the image.** Inject at `docker run`/compose runtime (`--env-file` / `environment:`). The image must be safe to push to a registry.
- On the droplet, store secrets in a root-only `.env` file (or systemd `EnvironmentFile`), not in shell history or the compose file in a repo.
- In GitHub Actions, use **encrypted repository/environment secrets**; never `echo` them. Be aware GitHub masks known secret values in logs only if registered as secrets — don't print derived values.
- **If a key ever touches git history, rotate it** (revoke via BotFather / OpenAI dashboard). Removing the commit is not enough; it's already scraped.

**Warning signs:**
`git log -p` shows a token; `.env` tracked by git; image scan / `docker history` reveals keys; GitHub secret-scanning alert; unexpected bot activity or OpenAI spend from regions you've never used.

**Phase to address:**
**Foundational config phase** (env-var loading, `.gitignore`, `.env.example`) and the **CI/CD deploy phase** (GitHub secrets, runtime injection on droplet). This must be right before any secret is created.

---

### Pitfall 7: Bot dies and stays dead — no auto-restart / uptime guarantee

**What goes wrong:**
The core value is "reliably, 24/7." But containers crash (unhandled exception, OOM, OpenAI client bug), droplets reboot (maintenance, kernel updates, power), and Docker daemon restarts. Without a restart policy, the bot stays down until the owner notices — which, with no monitoring, could be days. A public bot that's silently dead is worse than no bot.

**Why it happens:**
`docker run` without `--restart`; no `restart: unless-stopped` in compose; container not started on boot; relying on "it was running when I left." Crashes that should be transient become permanent outages.

**How to avoid:**
- **`restart: unless-stopped`** (compose) or `--restart unless-stopped` (run) so Docker relaunches on crash and on droplet reboot (Docker service is enabled at boot by default on the droplet).
- Make the container **crash cleanly and let Docker restart it** rather than catching everything and limping — but ensure transient OpenAI/Telegram errors are handled (Pitfalls 5) so the process doesn't crash-loop on every message.
- Add a **lightweight liveness signal** (log heartbeat, or later a healthcheck / uptime ping) so "silently dead" becomes visible. Even a free external uptime check pinging a tiny health endpoint or a periodic self-log catches the days-of-downtime case.
- Avoid crash-loops with no backoff: if it crashes immediately on start (bad config), `unless-stopped` will hammer-restart. Validate config (tokens present) at startup and fail fast with a clear log.

**Warning signs:**
Bot silent after a server reboot; `docker ps` empty after a crash you didn't notice; container in a restart loop (`docker ps` showing repeated restarts); no logs for hours.

**Phase to address:**
**Docker/deployment phase** (restart policy, boot enablement). Monitoring/heartbeat is a small add that can live in the same phase or be flagged as a fast-follow.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| No usage caps / rate limiting (locked decision) | Lean v1, ships faster | Unbounded spend, abuse exposure; one bad actor = big bill | v1 only, AND only with an OpenAI billing cap as a backstop; revisit before any public sharing |
| Sequential update processing (default) | Zero config | Bot feels dead under concurrent load | Never for a public bot — enable concurrency from day one |
| Hardcoded model name / params in handler | Fast | Cost + behavior locked into business logic; provider swap harder | Never — put in adapter/config |
| Catch-all `except` that swallows OpenAI errors | "Bot doesn't crash" | Hides quota/auth failures; users get silence; masks crash-loops | Never — handle by error type |
| Single token shared dev + prod | One less BotFather step | Constant 409 conflicts, dropped updates | Never — separate tokens are free |
| Secrets in compose file committed to repo | Convenient | Leak on first push; rotation pain | Never |

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Telegram getUpdates | Running >1 poller per token (dev + prod, or deploy overlap) | Exactly one poller per token; stop old before new; separate dev token |
| Telegram sendMessage | Sending >4096 chars or unbalanced Markdown/HTML | Chunk to ≤4096 on safe boundaries; clamp max_tokens; validate parse-mode entities |
| OpenAI completions | No timeout; treat all 429s alike; retry on insufficient_quota | Explicit timeout; backoff+jitter on rate_limit/5xx; stop on quota/auth; honor retry-after-ms |
| OpenAI client in async handler | Blocking sync call inside `await` handler | Use AsyncOpenAI and await; size connection pool to concurrency |
| Docker secrets | Baking keys into image via COPY/ARG | Inject env at runtime; image is secret-free and registry-safe |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Sequential update handling | Users wait behind each other; bot "dead" during a reply | `concurrent_updates(True)` + async LLM call | As soon as 2+ users are active simultaneously |
| Connection pool too small for concurrency | "pool timeout" warnings; stalls under load | Raise connection_pool_size/pool_timeout to match concurrency | When concurrency is enabled but pool left at default |
| Uncapped reply length | Slow sends, 4096 errors, high token cost | Clamp max_tokens; chunk output | On long-answer prompts / under cost pressure |
| Retry storm against rate limit | Bill/limit worsens; cascading 429s | Backoff + jitter; cap retries; respect retry-after | Under any sustained 429 condition |
| Public floods with no throttle | OpenAI spend spike; possible Telegram flood limits | Billing cap now; per-user throttle later | When bot link is shared publicly / scripted abuse |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Telegram token in git / image / logs | Bot hijack; 409 races; impersonation | Env-only, gitignore, runtime injection, rotate if leaked |
| OpenAI key in git / public repo | Direct financial theft (scraped in minutes) | Same as above + OpenAI billing cap limits blast radius |
| No spend cap on public uncapped bot | Drained balance / large bill from one abuser | OpenAI dashboard hard limit (cheap, do in v1) |
| Logging full user messages/prompts | Privacy exposure of strangers' inputs | Log metadata (user_id, latency, status), not raw prompt bodies |
| CI echoing secrets | Leak via build logs | Use GH encrypted secrets; never print them |

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Silent failure on errors/timeouts | User thinks bot is broken, leaves | Friendly fallback message on final failure |
| No feedback during slow LLM call | User repeats message (extra cost + dupes) | Send "typing…" chat action while awaiting |
| Long answers vanish (4096 limit) | Most useful replies never arrive | Chunk replies; or clamp length and offer "continue" |
| No /start or help text | New users don't know what to do | Minimal /start reply (cheap, no LLM call) |
| Bot processes non-text it can't handle | Confusing errors on stickers/photos | Ignore or politely decline non-text (text-only is in scope) |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Polling works locally:** Often missing — verify it's the *only* poller (no second instance/token), and that deploy stops the old container before starting new.
- [ ] **LLM reply returns:** Often missing 4096-char chunking and a max_tokens clamp — verify with a prompt that forces a >4096-char answer.
- [ ] **OpenAI call succeeds:** Often missing timeout + typed error handling — verify behavior on a forced 429/timeout and on an out-of-quota key.
- [ ] **Concurrency:** Often left at sequential default — verify two users get parallel, not serialized, replies.
- [ ] **Secrets handling:** Often `.env` not gitignored or baked into image — verify `git status`, `docker history`, and that the image runs with secrets injected only at runtime.
- [ ] **24/7 uptime:** Often missing restart policy — verify container restarts after `docker kill` and after a droplet reboot.
- [ ] **Cost backstop:** Often missing — verify an OpenAI billing hard limit is set before the bot goes public.

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Leaked token/key | LOW (if caught fast) | Revoke/rotate via BotFather/OpenAI dashboard immediately; redeploy with new secret; audit usage |
| Runaway cost spike | LOW–MEDIUM | Set/lower OpenAI hard limit; revoke key to halt; identify abusing user_id; add throttle |
| 409 polling conflict | LOW | Kill the phantom poller; ensure single instance; fix deploy ordering / dev token |
| Bot down after crash/reboot | LOW | Add restart policy; `docker compose up -d`; add heartbeat so next time is detected |
| Long-reply 400s | LOW | Add chunking + max_tokens clamp; redeploy |
| Blocking/serialized replies | LOW–MEDIUM | Enable concurrent_updates; switch to async client; raise connection pool |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Secrets leakage (#6) | Foundational config (first) | `.env` gitignored; image secret-free; runtime-injected |
| Single-instance polling / 409 (#2) | Polling/dispatch setup + CI deploy | One poller per token; separate dev token; deploy stops old first |
| Blocking on slow LLM (#3) | Polling/dispatch setup | Two users get parallel replies |
| OpenAI error/timeout handling (#5) | LLM adapter / OpenAI integration | Graceful behavior on forced 429/timeout/quota |
| 4096-char truncation (#4) | LLM adapter / reply delivery | >4096-char reply delivered as chunks |
| Unbounded cost (#1) | LLM adapter (cap+model+max_tokens) + post-v1 throttle seam | OpenAI hard limit set; cheap model; max_tokens clamped |
| Uptime / auto-restart (#7) | Docker/deployment | Survives `docker kill` and droplet reboot |

## Sources

- Telegram Bot API — message length & getUpdates single-consumer / 409 conflict: https://core.telegram.org/bots/api ; https://github.com/yagop/node-telegram-bot-api/issues/165 ; https://medium.com/@ratulkhan.jhenidah/telegram-polling-errors-and-resolution-4726d5eae895 (HIGH — cross-checked against official API docs)
- OpenAI rate-limit / 429 / backoff handling: https://cookbook.openai.com/examples/how_to_handle_rate_limits ; https://platform.openai.com/docs/guides/rate-limits ; https://help.openai.com/en/articles/5955604-how-can-i-solve-429-too-many-requests-errors (HIGH — official cookbook + docs)
- python-telegram-bot concurrent_updates / connection pool / sequential default: https://docs.python-telegram-bot.org/telegram.ext.application.html ; https://docs.python-telegram-bot.org/en/v22.0/telegram.ext.application.html (HIGH — official library docs)
- Docker restart policies (`unless-stopped`) for 24/7 containers: Docker official docs (HIGH — standard, widely documented)
- Public-bot cost/abuse risk, secret-leak scraping, deploy-overlap 409: known operational experience for this bot class (MEDIUM–HIGH — well-established community knowledge, consistent across sources)

---
*Pitfalls research for: public Telegram → LLM bot (polling, OpenAI, Docker, DO droplet, GitHub Actions)*
*Researched: 2026-06-11*
