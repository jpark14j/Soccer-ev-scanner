# Verification matrix

Local automated tests use clearly synthetic fixtures and block outbound requests.
They verify software behavior, not betting profitability or feed-wide correctness.
The live smoke evidence is separately recorded with actual response/source times.

| Requested check | Result / evidence |
| --- | --- |
| Real odds retrieval | Actual The Odds API responses for NBA, MLB and all seven soccer competitions; 2,331 normalized quotes including non-Ontario records, six Ontario keys observed; `evidence/odds-retrieval.json`. |
| Ontario availability | Official iGO snapshot + documented Ontario provider keys, expiry tested. No US/global substitution. Actual operator execution/geolocation not tested. |
| NBA analysis | Distinct research candidate, probability mass, missing-history and future-data tests pass. Real free archive evaluation completed on 701 test games, but data ends in 2015 and has no sportsbook baseline; model remains research. |
| Soccer analysis | Original Poisson candidate retained/refactored, date-leakage tests pass. Genuine Premier League chronological evaluation remains research, not market-beating evidence. |
| MLB analysis | Distinct run-count candidate and future-data tests pass. Real Retrosheet archive evaluation completed on 1,494 test games; data ends in 2025 and lacks a sportsbook baseline. Pitcher/lineup/weather inputs absent. |
| Player props | Contract/participant/line normalization and count formula tests pass. Earlier samples returned no quotes; the latest MLB strikeout sample returned six current Ontario observations, while NBA points returned none. No validated prop recommendations. |
| Free history / scores | Published-licence NBA/MLB imports, doubleheaders, resumed-game exclusion and chronology tests pass. Real existing-provider scores request returned 0 completed NBA / 3 MLB records; no results inferred. |
| Expected value | Numerical example 0.60 × 1.90 − 1 = 0.14, boundary/invalid-value and push-return tests pass. |
| Parlay correlation | Frechet bounds, non-independent supplied joint estimate, mutually exclusive/duplicate-leg rejection tested. New same-game score-model scenarios are explicitly unvalidated; no approved joint model connected. |
| Genuine combined prices | Exact book/leg/restriction/time gate tested; missing combined quote yields theoretical status with no odds/EV. No live combined quote provider verified. |
| Live updates | Observed in-play prices can be listed. No score/clock/state/latency feed or validated live model; live forecasts deliberately disabled, never described as verified. |
| Stale quotes | Source/receipt/future/suspension and publication-time expiration checks pass; cache never resets source time. |
| Telegram | Message formatting, token-redaction, schedule, pending-state/delivery claims, no-duplicate mechanics tested. Actual send not tested: Telegram secrets unavailable in this environment. |
| Conversational model | Official SDK Responses API exercised with in-memory HTTP transport; approval/key/consent gates, shared atomic limits, secret rejection, bounded history, stale evidence and sanitized API failures pass. No real OpenAI request made; default remains `"0"`. See [assistant guide](OPENAI_ASSISTANT.md). |
| GitHub Actions | YAML, branch guard, archive-before-send and pinned actions inspected/tested. Remote CI succeeded on implementation commit `86197da`, run [38843575101](https://github.com/jpark14j/Soccer-ev-scanner/actions/runs/38843575101), including dependency install, pytest and compilation. Daily production job not invoked. |
| Streamlit | All ten sections plus missing-key startup pass AppTest; local server `/_stcore/health` returned HTTP 200 `ok`. Existing production deployment not changed/tested. |
| Credential security | Secrets excluded from Git, no literal credentials added, sanitized provider/Telegram errors tested. Existing production secrets not read/changed. |
| History accuracy | Append-only publication/settlement triggers, deduplication, real-source requirement, losing record metrics, archive restore/tamper checks pass. No actual settled forward predictions exist. |
| Existing features | Same repo/app entrypoint, soccer aliases/results candidate, league selection, market comparison and daily Telegram path retained. Raw odds CSV export removed for licensing; unvalidated picks and multiplied parlays intentionally replaced by evidence gates. |

The evaluation artifact records real scores (multiclass Brier and log loss), source,
data/code hash, calibration/test sizes and promotion blockers. These are predictive
research diagnostics, not ROI, a calibrated true event probability, or a profit claim.
Do not tune candidates on this test period and reuse it as an untouched test again.
A new model version needs a new genuinely held-out evaluation.

Further checks requiring credentials/contracts/deployment: actual Telegram acceptance,
remote daily job and its commit permissions, persistent Streamlit ledger and backups,
operator-level price execution/market rules, historical market timing, licensed NBA/
MLB/prop datasets, score/state synchronization, live latency/suspension handling,
combined parlay pricing, subscriber privacy/consent, and commercial rights.

## Conversational assistant update — 2026-10-16

The complete development suite now passes **119 tests**, with real Requests and
HTTPX transports blocked. The official OpenAI SDK 2.54.0 is exercised through an
in-memory transport. Local Python compilation and dependency consistency checks
pass. An isolated Streamlit server on port 8503 returned HTTP 200 `ok`; AppTest
covers all sections and the conversational controls. The existing production and
preview processes were not replaced. See
[evidence/assistant-sdk-verification.json](evidence/assistant-sdk-verification.json).

Paid OpenAI calls remain disabled by default and **zero real OpenAI requests were
made**. Authentication, live model access, real billing/tokenization, provider
retention and remote preview browser behavior remain unverified. No production
secrets, main-branch changes, purchases or PR merge were made for this update.

## Daily parlay research update — 2026-10-16

**162 tests pass** with real transports blocked, including the selector, all filters,
source expiry, single-book provenance, duplicate/contradictory/nested legs, integer
score feasibility against enumerated outcomes, dependence warnings, no invented
joint probability/combined quote/EV, exact calibration-dataset matching and explicit
quota-controlled refresh. Existing assistant and all dashboard sections still pass.
Compilation and configured-secret scanning pass; isolated Streamlit health is 200.

A genuine NBA/MLB/Premier League check returned 516 normalized observations,
454 current Ontario quotes and three research candidates. Captured current data
renders three NBA-only and Soccer-only candidates; MLB-only correctly yields none
because just one eligible MLB event was present. The three-leg filter and local
assistant work on the same data. No executable parlay, published research prediction,
validated model promotion or positive parlay EV is asserted.

The separate Community Cloud preview URL is unreachable from this environment
(proxy connection failure and inaccessible web-reader result), so its actual build/
login/browser state is **unverified**. This does not establish that the app is down.
See [preview test steps](PARLAY_RESEARCH.md) and
[evidence/parlay-research-verification.json](evidence/parlay-research-verification.json).

## Advanced markets and risk update — 2026-10-16

**203 automated tests pass**, including the previous suite. Real Requests/HTTPX
transports remain blocked in tests. Additional checks cover canonical market
caching, concurrent fetch leases, narrow refresh and exact-identity merges,
Streamlit Secrets/zero-cap handling, UTC/Toronto DST reset, seven-day stale
inspection, source timestamps, English selections/scope, prop contradictions,
score-model chronology/joints, unvalidated EV suppression, bankroll gates, actual
loss-inclusive metrics/interval assumptions, advanced pages and grounded local chat.
Compilation, dependency consistency and configured-secret scanning pass.

The [dated genuine provider audit](evidence/advanced-market-access.json) observed
372 NBA spread/total, 10 MLB run-line, six MLB pitcher-strikeout and four Premier
League BTTS current Ontario quotes. NBA points returned none. Local reservations
moved 3/9 to 9/9; no cap was raised/reset. Other props/corners/Asian markets were
not live-verified. No historical endpoint, OpenAI request or Telegram send occurred.

Real NBA/MLB archives were evaluated with chronological features/calibration and
separate scoring periods: 701 / 1,494 test games per fixed-threshold task. Source,
code/data hashes, baseline scores, calibration bins and conditional intervals are
recorded in `evidence/*-advanced-research.json`. These are exploratory forecast
diagnostics using previously researched archive periods, not historical sportsbook
bets or independent confirmation. No model is promoted, and ROI/P&L remain absent.
New soccer advanced-market code has unit tests only; no player model was trained.

A **historical replay** of the genuine captured responses restored 394 observations
(392 current at capture), 332 raw unvalidated score forecasts and three candidates.
Advanced Markets, Daily Parlay Research, the same-game scenario, Performance Tracker
and MLB-prop local chat rendered without exceptions, with no new provider requests.
The replay does not make those old prices current now. An isolated port-8505 server
with odds cap zero and paid AI off returned HTTP 200 `ok`.

The public Community Cloud URL again failed with `ProxyError` from this environment.
Its rebuild/browser is unverified; this is not evidence it is down. Open the preview
and follow [ADVANCED_MARKETS.md](ADVANCED_MARKETS.md). See the consolidated
[verification evidence](evidence/advanced-phase-verification.json). Production,
main, production secrets and deployment configuration were not modified.
