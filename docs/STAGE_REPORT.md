# Development stage report

## Automatic slate/dashboard increment — 2026-10-16

1. **Implemented:** card-based landing page and collapsed raw data, automatic
   configured-window event discovery and capped rotating market research,
   evidence-ranked game selections, one qualified/research shortlist per book,
   private immutable pregame forecasts, conditional final-result collection and
   guarded settlement, consistent private backups, candidate registry, expanding
   folds/comparisons, drift review and explicit promotion/rollback controls.
   Existing manual selectors and local/disabled-OpenAI assistant remain functional.
2. **Files:** `app.py`; `slate.py`, `slate_views.py`, `book_optimizer.py`,
   `processing.py`, `persistence.py`, `worker.py`, `lifecycle.py`, `operations_ui.py`;
   existing pipeline/provider-result/parlay/analyst/CLI/settings/performance UI;
   `config/settlement_rules.json`; manual offline `research_audit.yml`; new tests,
   guides and verification evidence. Exact changes are visible in Draft PR #1.
3. **Passed:** 230 offline tests, compilation/dependency/secret/whitespace checks,
   isolated Streamlit HTTP 200, genuine zero-credit discovery, historical captured
   data UI replay and two genuine three-fold archive challenger runs. See
   [VERIFICATION.md](VERIFICATION.md) for scope and external limitations.
4. **Incomplete:** genuine current calibration/joint/prop models, fresh independent
   validation, operator rules and combined prices; external preview browser;
   durable Community Cloud data and an independent scheduler. No approved model,
   executed wager, real automated settlement, scheduled retraining or profit claim.
5. **APIs/costs:** no new subscriptions, paid OpenAI or spending-limit increases.
   Real discovery used zero provider credits; cap remained 9/9. Pending-result
   collection can reserve two existing credits per league, never beyond the cap.
   Private research backups/CLI evaluation add no API charge. Supplier/hosting rights
   and future durable-worker setup remain separate requirements.
6. **Next:** test the development preview, secure/test durable shared storage and
   permitted current data, then obtain actual historical/joint/combined-price
   evidence before recommending bets. Main/production remain untouched and Draft
   PR #1 stays unmerged. [Preview and operations instructions](AUTONOMOUS_RESEARCH.md).

## Advanced-market increment — 2026-10-16

This dated increment supersedes older market/test limitations where stated below.
No commercial model, player forecast or executable parlay has been approved.

1. **Implemented:** audited current market/docs coverage; narrow featured/event
   searches; English selections/unknown scope; mixed-market and same-game 2/3-leg
   research; source-preserving stale inspection; explicit 9/9 UTC/Toronto reset;
   secure cap settings, canonical cache/fetch leases; sport-specific score research
   with genuine NBA/MLB diagnostic evaluations; loss-inclusive ledger breakdowns
   and cautious intervals; opt-in bankroll loss/Kelly gates; grounded props/parlay
   assistant. See [the detailed guide](ADVANCED_MARKETS.md).
2. **Files:** `app.py`; new `intelligence/{markets,market_ui,data_settings,quota,
   advanced_models,market_validation,performance_ui,bankroll,risk_ui}.py`; updated
   provider/storage/pipeline/refresh/parlay/analyst/performance/CLI modules; five new
   test files including a fixture helper; README, architecture/assistant/parlay/stage/
   verification guides; three market/model evidence JSONs and consolidated checks.
3. **Passed:** 203 offline tests, compilation/dependency/secret checks, genuine
   quota-bounded advanced-market retrieval, real archive evaluations, historical
   captured-response UI replay, isolated Streamlit health 200. Actual test details
   and external-preview limitation are in [VERIFICATION.md](VERIFICATION.md).
4. **Incomplete:** Ontario coverage beyond observed markets; current licensed
   player/context history, newly evaluated soccer score markets, integer/quarter
   settlement modeling, current calibrated forecasts, joint validation, genuine
   combined prices/book restrictions, automatic accepted-ticket outcomes and a real
   forward record. Cloud build/browser remains independently unverified.
5. **API/costs:** existing current-odds access used six conservative local credits
   (3/9 to 9/9; five provider-reported credits), no new subscription or paid AI.
   Local assistant/model evaluation/loss illustrations need no model API. Further
   data/redistribution rights are not inferred and require supplier confirmation.
6. **Next:** test the development preview, then obtain current permitted statistics,
   timestamped historical prices, genuine parlay quotes/rules and fresh held-out
   evidence before recommendations can responsibly qualify. Main/production and
   `PAID_ANALYST_APPROVED = "0"` remain unchanged; PR #1 stays draft/unmerged.

## Earlier staged implementation

2026-10-15 Toronto · repository `jpark14j/Soccer-ev-scanner` · baseline `8e78990` ·
branch `development/verified-sports-intelligence`.

This is a functioning development increment in the existing application. It is
**not the fully validated commercial platform**. All locally implementable stages
were advanced; external-data-dependent stages remain explicitly partial. No
production deploy, paid signup/upgrade, Telegram delivery or model promotion occurred.

## Stage 1 — Technical audit: completed

- Implemented: reviewed every original tracked file, architecture, features, real
  integrations, EV, experimental models, Telegram and Actions; created a separate
  branch before edits. Key weaknesses: unvalidated probabilities, multiplied
  parlays, missing quote timestamps, one-book bias, duplicate logic, potential
  secret-bearing errors, no tests or permanent results. Later licensing research
  also found the free history feed unsuitable for default commercial use.
- Files: `docs/TECHNICAL_AUDIT.md`, `.gitignore`.
- Verification: clean starting tree and local baseline matched `origin/main`;
  no original automated suite existed.
- Incomplete: historical production incident/secrets-access audit, live deployment
  inspection and independent security assessment.
- APIs/costs: none.
- Next: verified Ontario provider mapping.

## Stage 2 — Ontario sportsbook data: implemented for existing provider

- Implemented: dated official-directory snapshot, operator/feed distinction,
  reviewed expiry, seven documented Ontario keys including paid-only BET99 and
  separate OLG basis; no US/global substitutes. Modular provider protocol,
  timestamp preservation, shape/number validation, retries, quota reservations,
  caching, safe error messages and exact-market comparison.
- Files: `config/ontario_books.json`, `intelligence/domain.py`, `registry.py`,
  `providers.py`, `storage.py`, `docs/PROVIDERS.md`.
- Passed: real retrieval across NBA, MLB and seven soccer competitions; six
  Ontario keys observed. Software tests cover malformed/duplicate quotes,
  jurisdiction expiry, safe errors, cache and budget.
- Incomplete: other Ontario operators without a documented configured feed;
  operator execution/geolocation; universal suspension confirmation.
- APIs/costs: existing Odds API quota used, no new paid subscription. Advertised
  free 500 credits/month; 20K paid tier $30 USD/month. Account billing not inferred.
- Next: statistics/history inputs and sport-specific modeling.

## Stage 3 — Multi-sport infrastructure: partial

- Implemented: NBA, MLB and all seven requested soccer competitions, featured
  market retrieval and opt-in event/prop adapter; licensed local-history manifests,
  deduplication, conflict handling and completed-date checks. Free-source automated
  commercial download disabled; personal mode has a four-day persistent cache.
  Added explicit FiveThirtyEight NBA and Retrosheet MLB archive imports with
  publisher permissions/attribution, doubleheader IDs and hashes; daily completed
  NBA/MLB result collection uses the existing Odds API account.
- Files: `intelligence/history.py`, `providers.py`, `pipeline.py`,
  `free_history.py`, `results.py`, `docs/DATA_CONTRACTS.md`, `docs/FREE_DATA.md`.
- Passed: actual feed contract for all nine competitions, empty/error fail-closed
  paths, historical cleaner and prop participant/line contract tests.
- Incomplete: licensed automated NBA/MLB/player/context statistics integrations;
  actual prop coverage for Ontario remains unverified. Two real prop samples
  returned no quotes (`docs/evidence/prop-samples.json`).
- APIs/costs: the implemented archives are free under the reviewed publisher
  permissions, and result collection uses existing account quota. No new
  subscription is required for this increment. Current advanced inputs remain
  unavailable; do not buy or assume rights to them.
- Next: chronological validation with genuine datasets.

## Stage 4 — Prediction models: partial; no model approved for recommendations

- Implemented: retained soccer shrinkage Poisson model, separate NBA margin-normal
  and MLB run-Poisson candidates; date-blocked chronological evaluation, calibration
  temperature fitted outside test, multiclass Brier/log loss, market baseline,
  empirical intervals, source/data/code hashes, model versions and expiry/promotion
  checks. Prior-day-only features and exact team aliases prevent key leakage paths.
- Files: `intelligence/soccer.py`, `models.py`, `evaluation.py`, `cli.py`;
  `docs/evidence/*-research.json`, `intelligence/free_history.py`, `results.py`.
- Passed: probability-mass and future-results invariance across sports, no test-set
  calibration selection; genuine Premier League evaluation ran with 129 test events,
  Brier 0.631861 and log loss 1.049975. These are diagnostics, not successful
  model validation. Genuine NBA archive evaluation: 701 test games, Brier 0.409227,
  log loss 0.595752; MLB: 1,494, Brier 0.496889, log loss 0.690019. Neither has a
  timestamped sportsbook benchmark; both archives fail current-data recency.
  No sport was promoted; simple warmup-only baselines are also recorded.
- Incomplete: independently credible calibrated production models; lineup, injury,
  pace, measured xG, pitcher, park/weather and player-feature models; adequately
  sized untouched datasets and timestamped historical market benchmarks.
- APIs/costs: licensed statistics and historical odds needed; existing provider's
  historical endpoints are paid and were not called.
- Next: evaluate better candidates only with suitable data; EV gates already wired.

## Stage 5 — Expected value: implemented with restrictive eligibility

- Implemented: EV `p × decimal odds − 1`, push-return utility, implied/no-vig
  probabilities, empirical uncertainty envelope, conservative EV cutoff and explicit
  score `conservative EV × (1 − interval width)`; best qualifying equivalent price.
  Only evidenced h2h models can publish. Market consensus alone never qualifies.
- Files: `intelligence/ev.py`, `domain.py`, `pipeline.py`.
- Passed: +14% worked example, boundaries, invalid numbers/push mass, exact selection
  matching, current/expired/suspended/future quotes, model-domain and uncertainty gates.
- Incomplete: spread/total/Asian/prop push/half-settlement prediction and validation.
- APIs/costs: no extra service.
- Next: extend markets only after their models and settlement rules are verified.

## Stage 6 — Daily parlay research MVP implemented; qualification still gated

- Implemented: same-Ontario-book 2/3-leg discovery from current pregame observations,
  sport/book/leg/category filters, bounded/diversified top-three ranking, actual
  single prices/timestamps, explicitly theoretical all-win product, precise model/
  joint-price/restriction blockers, integer-score contradiction checks and dependence
  warnings. Research never enters the published prediction ledger. Existing qualified
  analysis gates and diagnostic builder are preserved. Selected-competition refresh
  respects quota/cooldown and skips score collection. Existing matching historical
  archives can supply clearly dated research estimates and calibration envelopes;
  mismatched datasets cannot borrow evaluation/calibration results.
- Files: `intelligence/parlay_research.py`, `parlay_ui.py`, `research_refresh.py`,
  `team_codes.py`, `pipeline.py`, `analyst_context.py`, `app.py`, research/UI tests,
  README and [the research guide](PARLAY_RESEARCH.md).
- Passed: complete regression suite, selection and filter paths, stale/invalid/unknown
  Ontario quotes, opposing/nested legs and score feasibility versus brute-force
  outcomes, conditional bounds, unavailable combined prices/EV, quota and exact
  calibration-dataset matching. Genuine three-competition provider check: 516 quotes,
  454 current Ontario observations, three research candidates, zero executable
  parlays. Genuine captured-data Streamlit controls and local-mode assistant pass.
- Incomplete: actual authorized combined quotes, book restriction feed and validated
  joint models. No parlay recommendation or positive parlay EV is asserted. Community
  Cloud preview access is blocked from this environment; user browser check remains.
- APIs/costs: existing provider credits only (three competitions for the live smoke);
  no subscription purchase, paid OpenAI activation or new service. Static archived
  history remains old research data and may be absent on Community Cloud.
- Next: validate the user's preview rebuild, then integrate real combined-price and
  current/joint-model evidence before recommendations can qualify.

## Stage 7 — Conversational assistant: SDK integrated, paid usage disabled

- Implemented: official OpenAI Python SDK Responses adapter with strict evidence
  selection, server-rendered facts, current quote rechecks and local fallback.
  Streamlit chat includes bounded history, contextual follow-ups, loading, clear,
  idle expiry, privacy notice, per-session consent and evidence views. Secure
  environment/Streamlit Secrets settings support model selection without code
  changes. Atomic daily/monthly/session request and token/USD admission limits
  reserve conservatively before client construction, without automatic retries.
- Files: `intelligence/assistant.py`, `llm.py`, `analyst_config.py`,
  `analyst_context.py`, `analyst_usage.py`, `chat_privacy.py`, `chat_ui.py`,
  `app.py`, requirements, `pytest.ini`, assistant/UI tests and
  [OpenAI setup guide](OPENAI_ASSISTANT.md).
- Passed: official SDK against an in-memory HTTP transport; approval/key/consent
  gates, unavailable/stale/unvalidated records, rejected schema injection, secret
  rejection/redaction, sanitized auth/quota/timeout failures, concurrency and
  usage limits; Streamlit chat/follow-up/clear/expiry and all existing tests.
  See [verification matrix](VERIFICATION.md) for final counts/startup evidence.
- Incomplete: live OpenAI access, account billing, provider-side retention,
  Codespaces/remote preview browser verification and unrestricted generated prose.
  No real OpenAI request was made; `PAID_ANALYST_APPROVED = "0"` remains the default.
  Existing live/prop/parlay/model-validation limitations are unchanged.
- APIs/costs: local mode $0 model API cost. Optional GPT-4.1 mini documented text
  rates are $0.40/M input and $1.60/M output tokens, subject to provider change.
  An illustrative 2,000 input + 500 output tokens is $0.0016 USD before tax.
  The $5/month local reservation safeguard is not a provider billing cap; paid
  use still requires future explicit approval, a secure key and session consent.
- Next: review the development preview locally; enable and live-verify only after
  the operator's future paid decision and network/privacy/data-rights checks.

## Stage 8 — Streamlit dashboard: implemented in existing entrypoint

- Implemented: ten requested sections, automatic cached load, current quote/estimate
  distinction, transparent empty states, source/receipt/status fields, sport views,
  theoretical parlay UI, analyst, performance breakdowns and connection/settings
  information. Existing deployment entrypoint and secret names retained.
- Files: `app.py`, shared services; `requirements.txt`.
- Passed: all ten sections and missing-key startup through Streamlit AppTest;
  local HTTP health returned 200 `ok`.
- Incomplete: production Streamlit deployment, mobile browser/manual accessibility
  review and multi-user subscriptions/accounts. Raw odds CSV export removed for
  licensing; a future derived-analysis export can be added under permitted rights.
- APIs/costs: no new service; persistent production storage needed.
- Next: verify preview/deployment after review, without changing production prematurely.

## Stage 9 — Live markets: boundary implemented; forecasting incomplete

- Implemented: observed in-play listings, clear lack-of-state warning and strict
  exclusion of started games from pregame recommendations. Timer rechecks expiry
  without automatic high-frequency provider calls.
- Files: `domain.py`, `pipeline.py`, `app.py`.
- Passed: started/stale/suspended quote and publication gates. No live prediction
  or latency success is claimed.
- Incomplete: synchronized score/clock/player/state/suspension feed, separate live
  models, latency validation and cost-aware live scheduler.
- APIs/costs: reliable live state rights/feed needed; no subscription enabled.
- Next: implement sport-specific state models after data access is secured.

## Stage 10 — Telegram automation: code implemented; delivery unverified

- Implemented: existing script/bot/workflow preserved, NBA/soccer/MLB singles and
  three parlay-category summaries, complete evidence fields, one morning report,
  persisted pending reservation, durable prediction archive before sending, safe
  uncertain-send handling, configurable competitions/hour and default-branch guard.
- Files: `telegram_alerts.py`, `intelligence/notifications.py`, `ledger.py`, existing
  `.github/workflows/telegram_alerts.yml`.
- Passed: formatting, safe transport failure, Toronto window, deduplication and
  archive-before-send contract tests. No real Telegram message sent.
- Incomplete: actual Telegram acceptance and production workflow permissions/run.
- APIs/costs: existing Telegram token/chat secrets must be available in deployment;
  they were not supplied in this environment. No additional paid API.
- Next: perform controlled authorized delivery verification with actual bot access.

## Stage 11 — Performance verification: ledger implemented; outcomes not available

- Implemented: immutable content-identified publications, evidence-backed append-only
  settlement import/CLI, verified-time closing-price inputs, loss-inclusive one-unit
  P&L/ROI, win rate, drawdown, binary Brier/log loss, calibration and dimensions.
  Forward/backtest records separated; fresh runners restore derived Git archives.
- Files: `intelligence/storage.py`, `ledger.py`, `performance.py`, `cli.py`, `app.py`.
- Passed: immutable triggers, duplicate suppression, archive restore/tamper detection,
  losing outcomes, metric calculations and absent-data nulls.
- Incomplete: automatic licensed result/closing-line adapters and actual forward
  track record; shared durable Streamlit storage/backup. No profits are claimed.
- APIs/costs: licensed results may require supplier access; existing Git is used
  for scheduled derived archives, not subscriber PII or raw feed resale.
- Next: connect outcome sources, maintain full loss-inclusive history and backups.

## Stage 12 — Production preparation: development verification completed, launch blocked

- Implemented: offline unit/integration/UI suite, read-only secret-free CI, pinned
  workflow actions, bounded dependencies, architecture/data/provider/legal/release
  documentation and real retrieval/research evidence. Original production secrets,
  `.daily_digest_state.json`, deployment and `main` remain untouched.
- Files: `tests/`, `.github/workflows/ci.yml`, `requirements-dev.txt`, `README.md`,
  `docs/ARCHITECTURE.md`, `DATA_CONTRACTS.md`, `FREE_DATA.md`,
  `COMMERCIAL_READINESS.md`, `VERIFICATION.md`.
- Passed locally: **68 automated tests**, compile checks, diff whitespace check,
  actual odds contract checks, genuine chronological evaluation, Streamlit health.
- Incomplete: production deployment, real Telegram/LLM sends, independently credible
  prediction/prop/live/parlay validation and supplier/commercial approvals. Remote
  CI also passed on the implementation commit `86197dafdb62ed8ae775354c2cf19b8a3bb4ceb9`:
  https://github.com/jpark14j/Soccer-ev-scanner/actions/runs/38843575101 .
- APIs/costs: no new paid services. The user confirmed no paid data subscriptions
  and requested free-first work. Free archives and current result collection were
  added; free feed credentials/access are needed for additional current history.
  Player/live/historical market evidence remains unavailable.
- Next: review this branch, verify free refresh credentials/rights, train/test
  candidates on new
  untouched data, then verify deployment and notifications before merging.
# Focused prediction stage — 2026-10-16

1. **Implemented:** audited missing inference; selected EPL BTTS / goals 2.5;
   imported hash-verified publisher-CC0 outcomes; fitted decayed/shrunk Poisson
   strengths and frozen monotone calibration; genuine chronological/baseline/
   bootstrap diagnostics; deployed portable fitted state; explicit current-input
   gates and daily free-source refresh; research card/assistant integration;
   conservative high-probability gate; immutable paper recording and public target
   labels separated from betting results. Existing parlay and assistant remain.
2. **Files:** `intelligence/epl_{source,goal_model,validation,forecasts}.py`,
   `config/epl_{forecast_policy,source_snapshot}.json`,
   `research_assets/epl/model.json`; pipeline/processing/slate/CLI, concise cards,
   assistant facts and performance integration; `tests/test_epl_predictions.py`,
   `tests/test_epl_ui.py`, slate/conftest updates; model audit, reproducibility/
   preview guide and verification evidence/documentation. No production configs.
3. **Passed:** 259 tests (29 added); compileall; pip consistency; whitespace;
   actual account-free public results refresh; existing-app local HTTP 200 health;
   Streamlit AppTest valid research, stale-data cards, soccer/performance/assistant.
4. **Incomplete:** current source results end September 20 and 15 prior fixtures
   lack scores. Current forecasts are blocked, not fabricated. Historical results
   do not beat baselines convincingly; no independent evidence/approval, actual
   joint parlay prices/models, current NBA/MLB/player feature feeds, actual wagers,
   or verified durable Community Cloud ledger. Hosted preview cannot be reached
   from this environment's proxy. No genuine current forecast is claimed.
5. **API/cost:** no new account/key/subscription, paid AI or odds requests; unchanged
   existing 9-credit cap (currently 9/9). Public refresh uses at most two GETs per
   rolling day per shared store. Publisher CC0 grant does not clear other feeds'
   commercial redistribution rights. No current-results account was activated.
6. **Next:** obtain complete permitted recent results and fresh supported markets
   within the existing cap, collect prospective paper evidence, review independent
   validation versus timestamped markets, then consider reviewed model promotion
   and joint-model research. Do not tune on the reported test or relax gates.

See [actual metrics and exact preview click steps](EPL_PREDICTIONS.md).
