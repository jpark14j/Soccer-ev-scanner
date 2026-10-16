# Conversational assistant: local preview and future OpenAI activation

The existing `app.py` → **AI Assistant** page now has conversation history,
suggested follow-up questions, an evidence viewer, loading feedback and sanitized
errors. **Paid requests are disabled by default: `PAID_ANALYST_APPROVED = "0"`.**
No subscription, credits, API key or production deployment was changed for this
implementation. The official `openai` Python SDK is installed as a dependency;
installing/importing it does not make an API request.

## Test the free interface now

1. Keep your preview on `development/verified-sports-intelligence`, entrypoint
   `app.py`. Install `requirements.txt` or let the separate Streamlit preview
   rebuild it. Do not merge PR #1 or change your production app's branch/settings.
2. Keep `PAID_ANALYST_APPROVED = "0"` in the **preview's** Secrets settings. An
   OpenAI key is unnecessary. Never paste a key into chat, GitHub, an issue or logs.
3. Open **AI Assistant**. Ask “What NBA information is available?”, then “What
   about prices?” or use a suggested question. The previous sport carries into
   follow-ups. Answers say **Local · rule-based**, not generative AI.
4. Try model evaluation, expected value, missing props, stale prices and forward
   performance. Missing odds keys yield an honest empty state; current research
   evaluations do not become validated betting opportunities.
5. **Clear conversation** removes session history and consent. It does not reset
   usage limits. A preview pinned to a specific commit must be updated explicitly
   to this development commit; no existing running checkout was replaced here.

## How grounding works

Both modes use server-built facts from current application records: NBA/soccer/MLB
coverage, Ontario-key quotes, exact-selection best observed prices, source and
receipt times, evidence-gated opportunities, research evaluation diagnostics,
forward performance summaries, EV definitions and capability limitations.
No extra odds/statistics requests are triggered by the language model. The dashboard's
existing collection cache/quota still applies when the app loads or refreshes.

In OpenAI mode, a bounded snapshot plus recent user questions/conversation topics
is sent through the official SDK's **Responses API**. A strict structured schema
lets the model select evidence IDs, topic, sport and follow-up questions. All IDs
are checked locally; unknown fields, invented values, incomplete responses and
refusals cause a clearly labeled local fallback. The model cannot write the factual
answer prose. The server renders it from evidence and appends availability and
freshness notices. It rechecks quote expiry after waiting for the response.

This is deliberately an evidence-selection assistant, not unrestricted generative
sports research. It cannot browse for injuries, calculate unsupported probabilities,
promote research models, assert profitability, wager, purchase, send messages, run
code/SQL or alter records. No tools/functions, external retrieval or remote
conversation IDs are configured. Future richer reasoning needs separately tested,
source-backed calculations and data permissions. Current live, prop and executable
parlay limitations remain unchanged.

Historical report hashes are checked before use. Their data dates, research status
and promotion blockers appear in answers. Historical Brier scores in those reports
are multiclass diagnostics; the forward tracker's Brier score is binary. Do not
compare them as if they used identical definitions or datasets. Ontario availability
is limited to the repository's dated registry and exact authorized provider keys,
not an assertion that a sportsbook will accept a wager at an observed price.

## Enable OpenAI later, only after deciding to accept costs

**These are future operator steps; none were performed by this change.**

1. Review OpenAI's current model documentation, pricing, data controls and your
   odds/statistics contracts. Confirm that sending those analytical records to
   OpenAI is permitted. Keep this private preview restricted to intended testers;
   this repository does not implement subscriber identity or per-user billing.
   The user-added Dev Container configuration currently disables Streamlit CORS
   and XSRF protection for its preview launcher. Before enabling paid access,
   review that host configuration, restore those protections and verify the
   authenticated forwarded URL. This change preserves that existing launcher.
2. Configure a dedicated OpenAI project/key and appropriate provider spending,
   rate, model and alert controls. Provider budgets/alerts may themselves be soft
   thresholds; verify their actual enforcement. App limits are not a provider
   billing cap. No purchases or credits are automatically initiated by this app.
3. In **the separate preview app only** → **Manage app → Settings → Secrets**, add
   your own `OPENAI_API_KEY` directly in the secure secrets editor. Do not put it
   in source, a command argument, screenshots, chat, generated reports or GitHub.
   For a local run only, `.streamlit/secrets.toml` is gitignored; secure its file
   permissions. GitHub Actions does not need an OpenAI key for these tests.
4. Start with the disabled settings below. Choose a supported Responses API model
   that supports strict JSON schema. `gpt-4.1-mini` is the configured default;
   access/model availability has **not** been live-tested. For another supported
   model set `OPENAI_MODEL` and positive standard input/output prices, without
   changing source. Models requiring incompatible options will fail safely into
   local mode; no automatic upgrade or alternative-model retry occurs.
5. Use a durable `INTELLIGENCE_DB` for usage counters. Ephemeral Streamlit disks,
   resets or separate previews can restart local counters. Hosting/network policy
   must allow `https://api.openai.com/v1`; this managed environment currently does
   not permit that host and has no OpenAI credential binding. Nothing in this
   change relaxes network policy.
6. After your explicit decision, change **only the intended preview** setting to
   `PAID_ANALYST_APPROVED = "1"`, save and restart/reload. Environment variables
   take precedence over Secrets, including an explicit `"0"`. A remaining `"0"`
   environment value must be changed by the operator before Secrets can enable it.
7. Open **AI Assistant** and read the privacy notice. Check the per-session consent
   checkbox. That checkbox alone cannot override disabled/missing/invalid server
   configuration. Only submitting a question/suggested question can initiate a call.
8. Send one question, inspect **OpenAI-assisted · verified evidence**, evidence IDs,
   usage counters and the provider usage console. This first live verification
   will incur charges if accepted. Check that authentication/quota errors show a
   sanitized warning plus a local answer; no automatic retries are made.
9. Disable again by restoring `PAID_ANALYST_APPROVED = "0"` and restarting. Revoke
   or rotate the provider key through its secure console if required. This does
   not delete already processed provider data; use the provider's controls/policy.

Disabled configuration example (contains **no API key**):

```toml
PAID_ANALYST_APPROVED = "0"
OPENAI_MODEL = "gpt-4.1-mini"
ANALYST_MAX_DAILY_REQUESTS = "20"
ANALYST_MAX_MONTHLY_REQUESTS = "100"
ANALYST_MAX_SESSION_REQUESTS = "20"
ANALYST_MAX_INPUT_CHARS = "2000"
ANALYST_MAX_INPUT_TOKENS = "16000"
ANALYST_MAX_OUTPUT_TOKENS = "800"
ANALYST_MAX_CONTEXT_CHARS = "6000"
ANALYST_MAX_HISTORY_MESSAGES = "8"
ANALYST_MAX_SESSION_MESSAGES = "24"
ANALYST_IDLE_MINUTES = "30"
ANALYST_MONTHLY_USD_CAP = "5"
ANALYST_DAILY_USD_CAP = "0.50"
ANALYST_MAX_REQUEST_USD = "0.02"
ANALYST_TIMEOUT_SECONDS = "25"
# For a different model, configure its current standard USD / million token rates:
# ANALYST_INPUT_USD_PER_MILLION = "..."
# ANALYST_OUTPUT_USD_PER_MILLION = "..."
```

A zero request or dollar limit blocks requests. Invalid settings block paid mode
with an error that never echoes the supplied value. Request limits allow 0–1,000
per day/session and 0–10,000 per month. Character limits allow 50–8,000; input bounds
1,000–64,000; output caps 128–4,096; context 1,500–16,000 characters; history 0–20
messages; session retention 4–60 messages; idle expiry 5–120 minutes; timeout 5–60
seconds. Dollar caps permit $0–100 daily/monthly, $0–1 per request. Token rates
permit $0–1,000 per million, but must be positive to enable requests. Known model
rates cannot be overridden below the checked baseline; recheck rates before use.

## Costs and usage safeguards

GPT-4.1 mini's documented standard text pricing checked on 2026-10-16 is
$0.40/million input and $1.60/million output tokens. An illustrative 2,000 input +
500 output tokens costs **$0.0016 USD** before tax, without asserting the actual
size of this app's requests. The API decides actual token usage. No web-search,
code-interpreter or other paid tools are enabled. Pricing can change.

Before constructing the SDK client, the app checks approval, key, valid settings,
consent, input length/content, request counts, input bound, output cap and dollar
limits. SQLite atomically reserves an estimated maximum cost using configured
standard rates, a conservative UTF-8-byte input bound plus framing allowance, and
the entire output cap. Old conversation turns are dropped to fit the input bound.
An oversized remaining context blocks the request rather than silently discarding
the new question. This estimate is designed for the documented text model; other
models' tokenization/billing must be verified before activation.

Reservations remain after failures/timeouts and are never refunded automatically.
Request IDs prevent repeat submission of the same attempt. Current-month legacy
adapter reservations count toward the new monthly safeguard. The daily/monthly
limits are shared by all users of **one database**, use UTC boundaries, and are not
account-wide. Session limits are browser-session controls, not authentication.
Actual returned token counts are diagnostic only. Token price changes, host resets,
other apps and separate databases can invalidate any local spending assumption.
**Use provider controls and monitor actual billing.**

## Privacy and security boundaries

- Session memory holds at most the configured number of messages. Clear chat
  removes it and revokes consent; idle expiry occurs on the **next interaction**,
  not via a guaranteed background deletion timer. Disconnected-session cleanup is
  controlled by Streamlit. Administrators can access server memory.
- Prompts/answers are not written to SQLite, reports, Telegram or repository files.
  The usage table holds random request IDs, UTC periods, reservations and token
  counts; records older than 90 days are purged on the next admitted request, not
  by a background timer. Clear chat does not delete budget evidence.
- Paid requests use `store=False`, no `previous_response_id`, no remote conversation
  state and no tools. This avoids response storage for later API retrieval; it
  **does not guarantee zero provider retention**. Standard abuse-monitoring logs
  may be retained for up to 30 days, with policy exceptions. Eligibility for
  modified/zero-retention controls is a separate provider decision. API data is
  not used for training by default under the provider's current policy; review it.
- Only bounded recent **user questions and topic metadata**, not old assistant
  prices, accompany the current evidence. No raw settlement-source URLs, account
  details, secrets or database commands are included. Personal data typed into a
  paid question can still be transmitted; avoid entering it. Pattern-based
  credential detection is a safeguard, not comprehensive sensitive-data detection.
- Credential-like input is rejected before chat history/transmission; known
  configured secrets and common key/token patterns are redacted from evidence.
  User/source text is displayed as plain text, preventing embedded Markdown images.
  Raw SDK errors, bodies and exception text are never displayed/logged. SDK/HTTP
  debug loggers are suppressed. Do not enable host-level payload/body capture.
- The SDK endpoint is fixed to OpenAI; an `OPENAI_BASE_URL` environment variable
  cannot redirect keys/context. API clients are server-side and created only after
  every approval/limit check. There is no key-entry widget or key in client state.
- A public commercial assistant still needs authentication, abuse controls,
  documented consent/privacy processes, persistent shared limits, licensed data
  rights and an incident/retention policy. This change does not establish those.

## Verification

Run `python -m pytest -q` and `python -m compileall -q app.py intelligence`.
Tests block real Requests and HTTPX transports. In-memory SDK transport tests
exercise the actual Responses request/response format, not a paid connection.
Streamlit AppTest covers chat, follow-ups, consent defaults, clearing, idle expiry,
credential rejection and missing data. Negative tests cover disabled/key/consent
gates, prompt/schema injection, stale/unvalidated records, API failures, request
limits and atomic concurrent budget reservations. Live OpenAI access, real billed
tokens and provider-side retention are **unverified** because paid usage remains
disabled. Existing sports-data/model limitations are in [VERIFICATION.md](VERIFICATION.md).

Official references:

- [OpenAI Python SDK](https://github.com/openai/openai-python)
- [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [GPT-4.1 mini and pricing](https://developers.openai.com/api/docs/models/gpt-4.1-mini)
- [API data controls](https://developers.openai.com/api/docs/guides/your-data)
