# Development stage report

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

## Stage 6 — Parlay engine: analysis safeguards implemented; discovery partial

- Implemented: arbitrary-dependence joint bounds, duplicate/opposing-leg rejection,
  exact combined-price/restriction/leg/book/source-time checks, joint-estimate
  validation gate and variance categories when evidence qualifies. Missing evidence
  stays theoretical without invented price/EV. Exact no-opportunity message used.
- Files: `intelligence/parlays.py`, `app.py`.
- Passed: correlation-sensitive supplied joint example (different from the
  independence product), bounds, mismatched prices/restrictions, duplicate/opposing legs.
- Incomplete: fitted joint models, actual combined quote feed, sportsbook-specific
  restriction feeds and automatic qualified-combination search.
- APIs/costs: a licensed combined-pricing/restriction source is essential; quote unknown.
- Next: connect exact parlay evidence rather than multiply singles.

## Stage 7 — Conversational analyst: local mode implemented, paid option disabled

- Implemented: grounded responses from current records for qualifying selections,
  risks, availability, performance and unavailable information. Optional strict-schema
  OpenAI intent router, locally checked enums, bounded questions/output, conservative
  monthly request reservations and local fallback. All factual output is rendered
  from analytical templates; the model cannot insert numeric claims.
- Files: `intelligence/assistant.py`, `llm.py`, `app.py`, `tests/test_llm.py`.
- Passed: empty records, stale exclusion, no invented facts, approval and budget
  gates, rejection of extra model fields. No live LLM call made.
- Incomplete: paid API credential/access/approval and live API verification; broad
  open-ended free-form generative reasoning intentionally not trusted as fact.
- APIs/costs: default $0. Optional GPT-4.1 mini advertises $0.40/M input and $1.60/M
  output tokens. Illustrative 2,000 input + 500 output tokens cost $0.0016 per answer
  ($1.60 per 1,000), excluding tax/extras. Routing output is capped at 200 tokens.
  A proposed $5 USD/month **local** cap is disabled with paid mode; approval required.
  Official pricing: https://developers.openai.com/api/docs/models/gpt-4.1-mini
- Next: enable only after approval, secure credentials/network setup and verification.

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
