# Soccer-ev-scanner — Ontario sports intelligence development

This upgrades the **existing** Python/Streamlit app on
`development/verified-sports-intelligence`. The production entrypoint remains
`app.py`; the existing Telegram script, workflow path and secret names are retained.
Nothing on `main` has been deployed or had its secrets changed by this work.

Latest: [Everyday research screens and current readiness](docs/EVERYDAY_RESEARCH.md)
documents the five-page interface, corrected read-only budget explanation, and
successful hosted generation-2 storage/read checks. Live research and scheduling
remain disabled; provider usage and permissions still require review. Earlier
phase reports below describe their implementation-time evidence.

[Phase 10 operational readiness and one-time setup](docs/PHASE10_OPERATIONS.md)
adds the optional fenced background worker, shared budget authority, published
research/paper ledger and prospective calibration challengers. All activation
flags remain disabled; real hosted operation still needs configuration.

The [Phases 7–9 readiness report](docs/PHASES7_9_READINESS.md) covers the defined
risk/probability rankings, dependent-format research, immutable prospective
evaluation, scoped reliability and disabled optional private recovery. Page
loads now inspect saved data without provider calls; retrieval remains explicit
and capped. No independent accuracy gain, approved model, executable parlay EV
or hosted durable storage is claimed. Start with its exact preview instructions.

The [Phase 6 research guide](docs/PHASE6_TOP_RESEARCH.md) documents the new
experimental top single/parlay summaries, read-only zero-odds audit and saved-price
session repairs. It also reports the additional beta-calibration/annual-refit and
joint-settlement backtests. No credible independent model improvement, approved
joint probability or executable SGP is claimed; no frozen model is replaced.
The existing tools, approval gates, paid-AI default and data budgets are preserved. See the [everyday research guide](docs/EVERYDAY_RESEARCH.md) for the five-page navigation and current activation blockers.

The [Phase 5 quantitative research guide](docs/PHASE5_QUANTITATIVE_RESEARCH.md)
documents repaired results retention/session visibility, the new **Today's
Best-Supported Bet** gate, chronological Poisson/Dixon-Coles challenger scores,
coherent soccer joint-score/settlement foundations and exact preview checks.
No challenger convincingly improves the frozen models; none is replaced or
approved. The retrospective archive is not fresh independent confirmation.
Current SGP tickets, NBA/MLB model readiness and Cloud off-host durability remain
blocked. Failed refreshes now preserve accepted results without refreshing their
timestamps or bypassing eligibility gates.

The [Phase 4 parlay intelligence guide](docs/PHASE4_PARLAY_INTELLIGENCE.md) explains
the existing generator. Open **Best Picks & Parlays** for model-favored
binary selections and automatic evidence-ranked 2/3-leg research. Opposing outcomes
stay in details; price-only combinations remain separate. Individual estimates,
uncertainty and observed Ontario prices are distinct. No validated joint win
probability, executable combined ticket, parlay EV or approved model is claimed.
Explanations are local and rule-based. The cards reuse saved analysis; paid AI
remains disabled and existing data-request budgets are unchanged.

The [Phase 3B readiness guide](docs/PHASE3B_READINESS.md) documents consistent
current-source/inference diagnostics, results-only session updates, three separate
research rankings and a stale-price inventory. Your configured preview can use
its genuine results cache; diagnostics distinguish available data from actual
per-market inference. All three soccer models remain experimental and unapproved.
Readiness and paper-record exports make no paid request and expose no token.

The [Phase 3A results guide](docs/PHASE3A_CURRENT_RESULTS.md) describes the optional,
disabled-by-default football-data.org integration, its six-request daily cap,
full-season reconciliation, frozen-model bridge and paper-record export. A free
account token and permitted-use review are still needed to verify actual current
coverage. No September/October gap or genuine new forecast is claimed resolved.

The [Phase 2 engine guide](docs/PHASE2_ENGINE.md) documents the normalized data
foundation for five soccer leagues plus NBA/MLB archives, new Bundesliga BTTS and
Ligue 1 goals-2.5 research models, real held-out scores, bounded public-results
updates and current data blockers. These are research models, not approved betting
edges. The bundled OpenFootball scores remain stale/incomplete; no current opportunity or
profit is invented. The [source audit](docs/PHASE2_DATA_AUDIT.md) explains selection.

The [everyday research guide](docs/EVERYDAY_RESEARCH.md) is the current navigation
and preview guide: Home, Best Picks & Parlays, Upcoming Games, Performance Tracker,
and Settings. The advanced sport, market, operations and assistant
modules remain accessible through Settings → Admin / Developer Tools. Pages/filters reuse the session
scan; explicit refreshes still obey the existing cache and credit cap. See the
[free-results readiness review](docs/FREE_RESULTS_READINESS.md) for current gaps.

The earlier [automatic research guide](docs/AUTONOMOUS_RESEARCH.md) explains the
new card-based landing page, automatic budget-aware slate discovery, best selections
by game, one shortlist per sportsbook and guarded operational/model lifecycle.
Raw odds are collapsed under **Advanced Details / Raw Market Data**. Background
scheduling and Community Cloud redeployment persistence remain unconfigured.

The [focused prediction guide](docs/EPL_PREDICTIONS.md) documents the new portable
Premier League BTTS / 2.5-goal models, real chronological test results, exact input
gates and preview steps. Neither beats the simple baselines convincingly or meets
approval standards. The default OpenFootball path is incomplete/stale; the
configured optional feed can support experimental pregame estimates only when
all existing input and current-price gates pass. See the
[missing-model audit](docs/MISSING_MODEL_AUDIT.md) for NBA/MLB and other-market gaps.

The application retrieves genuine NBA, soccer and MLB sportsbook observations,
checks Ontario feed provenance and freshness, and publishes only selections that
pass model evidence and uncertainty-adjusted EV requirements. **No model has been
promoted on the evidence available in this session. No profitable strategy is
claimed.** The honest current result is no qualifying recommendations.

Read [the audit](docs/TECHNICAL_AUDIT.md), [provider review](docs/PROVIDERS.md),
[stage results](docs/STAGE_REPORT.md), [free data choices](docs/FREE_DATA.md), [architecture](docs/ARCHITECTURE.md) and
[verification matrix](docs/VERIFICATION.md) before rollout. The latest
[advanced-market guide](docs/ADVANCED_MARKETS.md) documents actual Ontario coverage,
same-game research, model diagnostics and precise quota-reset behavior.

## Run the existing app

Python 3.11+:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
streamlit run app.py
python -m pytest -q
```

Use the existing `ODDS_API_KEY` through environment variables or Streamlit Secrets.
Telegram additionally uses `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in Actions
Secrets. Never commit credentials or put them in command-line arguments.

All ten requested sections plus Advanced Markets, Daily Parlay Research, Best
Selections by Game and Research Operations are present. The analyst answers from current
application records; default local mode **does not call a language model API**.
The official OpenAI SDK integration is implemented but disabled by default with
`PAID_ANALYST_APPROVED = "0"`. The conversational page supports bounded history,
follow-ups, evidence views, consent and usage limits in both local and optional
OpenAI modes. OpenAI selects verified evidence; the server renders factual text.
See [the assistant setup and privacy guide](docs/OPENAI_ASSISTANT.md) for free
preview testing and future paid activation. No paid request was made. Live and prop recommendations remain disabled
until their necessary inputs and validation exist; observed prices are distinct
from predictions and from executable sportsbook offers.

## Daily Parlay Research

Open [your development preview](https://soccer-ev-scanner-preview-jp.streamlit.app/)
and choose **Best Picks & Parlays**. The central **AI Parlay Intelligence** section
shows model-backed research first, with favored binary sides, 2/3-leg controls,
opposing outcomes in details and clear dependency/uncertainty warnings. It does
not force a candidate when evidence or current prices are missing. For the earlier
price-only/same-game selector, choose **Parlays → Unsupported and price-only
research · full existing generator**.
Filter NBA/soccer/MLB, market types, sportsbook, 2/3 legs and price-based risk category.
Choose **One selected event** for same-game research. Up to three
compatible current-price research candidates can appear without validated models.
Individual odds/timestamps are real observations; their combined product is always
labeled theoretical. Optional same-game score-model scenarios are explicitly
unvalidated; no approved joint probability, executable price or parlay EV is invented.
An explicit selected-competition refresh respects existing quota; filters make no
requests. See [preview test steps, methodology and limitations](docs/PARLAY_RESEARCH.md).

Open **Advanced Markets** to request one competition/market or one event's props,
inspect current/stale observations in English and see unknown settlement rules.
NBA spreads/totals, MLB run lines/pitcher strikeouts and soccer BTTS returned actual
Ontario observations in the dated audit. Other catalog support is not verified
coverage. No new model qualifies for betting recommendations.

## Configuration and cost control

| Variable | Default | Purpose |
| --- | --- | --- |
| `ODDS_API_KEY` | existing secret | Authorized existing provider account |
| `ODDS_DAILY_CREDITS` | UI `9`; scheduled CLI `16` | Local UTC-day reservation cap, including retries; environment/Streamlit Secrets honored |
| `COLLECT_RESULTS` | UI `0`; scheduled CLI `1` | Explicit `1` enables cached NBA/MLB completed-result collection; `0` disables |
| `ODDS_CACHE_SECONDS` | `1800` | Shared provider response cache |
| `SLATE_WINDOW_HOURS` | `48` | Automatic configured-competition discovery window, 1–168 hours |
| `INTELLIGENCE_DB` | `data/intelligence.sqlite3` | SQLite query index/cache; persistent disk recommended |
| `PREDICTION_LEDGER_DIR` | `ledger` | Derived immutable prediction/settlement JSONL archive |
| `HISTORY_DIR` | `data/history` | Licensed historical CSVs plus source manifests |
| `MODEL_DIR` | `data/models` | Chronological evaluation artifacts |
| `PAID_ANALYST_APPROVED` | `"0"` | Set to `1` only after explicit paid API approval |
| `OPENAI_API_KEY` | absent | Optional server-side OpenAI credential in secrets only |
| `OPENAI_MODEL` | `gpt-4.1-mini` | Supported Responses/structured-output model; other models need configured prices |
| `ANALYST_MAX_DAILY_REQUESTS` | `20` | Atomic per-database admission cap; monthly/session limits also apply |
| `ANALYST_MAX_OUTPUT_TOKENS` | `800` | Per-response output cap; input bounds also apply |
| `ANALYST_MONTHLY_USD_CAP` | `5` | Conservative local monthly reservations; not account-wide billing protection |
| `FOOTBALL_DATA_PERSONAL_RESEARCH` | disabled | Explicit personal-only free-source research mode |
| `DIGEST_LEAGUES` | all nine competitions | Comma-separated configured competition names |
| `DIGEST_HOUR_LOCAL` | `9` | Toronto delivery window; change Actions crons too if hour changes |
| `STREAMLIT_APP_URL` | existing deployment | Link in daily report |

The UI initially selects NBA, Premier League and MLB, skips unconditional score queries and
shows the exact next local UTC reset in Toronto time too. At 9/9 it keeps stale
inspection available while disabling chargeable searches. It never raises the cap.
Ended pending predictions/research forecasts can trigger capped result collection;
without pending events no score query is needed. Discovery is zero credits;
featured/event tasks rotate within the existing cap and explicitly report skips.
The separate scheduled CLI retains its existing settings. For that CLI,
nine competitions, h2h once daily (270 credits/30 days), plus daily NBA/MLB
completed results (120 credits/30 days) total about 390 before retries/props. The provider currently advertises a free 500-credit tier;
this is **not a statement of your account's billing plan**. No subscription was
created or upgraded. More markets, refreshes, clients or deployments need explicit
quota planning. Prices/rights and Ontario coverage are in the provider review.

The default cache trades freshness for cost. Recommendations expire five minutes
after source/receipt time and are rechecked on render/publication/send. Cached older
prices remain visibly stale and cannot qualify. A timer updates dashboard freshness
without polling the provider. Refresh does not bypass cache or quota. Local caps
are per database; separate deployments share account quota but not local counters.

## Historical data and model evaluation

Use the explicit free historical importers in [free data choices](docs/FREE_DATA.md)
or supply licensed results using [the data contract](docs/DATA_CONTRACTS.md).
The pipeline also accumulates current completed NBA/MLB results locally through
the existing provider, subject to its three-day window and persistent storage. The free
football-data source is not enabled for commercial use. Its policy limits free
files to personal/academic interests and at most twice-weekly light automated
downloads; personal research mode requires a persistent four-day cache. Do not
use that mode for the subscriber product or parallel deployments.

```bash
python -m intelligence.cli evaluate --league 'Premier League'
python -m intelligence.cli evaluate --league NBA --source 'your licensed source reference'
python -m intelligence.cli scan
python -m intelligence.cli evaluate-markets --league NBA
python -m intelligence.cli evaluate-markets --league MLB
python -m intelligence.cli research-cycle --offline
python -m intelligence.cli train-challenger --league NBA
```

Soccer uses the existing shrinkage Poisson candidate, NBA a distinct normal margin
candidate, and MLB a distinct run-count Poisson candidate. They are limited research
baselines, not injury/lineup/pace/pitcher-aware commercial models. Evaluation uses
date-blocked chronological calibration and untouched test periods, baseline scores,
empirical reliability intervals, version/code/data hashes and expiring evidence.
No artifact is promoted just because a forecast exists. Unknown-time baseline odds
cannot prove a tradable edge. Genuine evaluations for all three sports stayed in research status. NBA archive
data ends in 2015 and MLB archive data in 2025; neither supplies a current model
or timestamped market baseline. See `docs/evidence/*-research.json`.

Additional props and period market keys are supported by the provider event adapter:
`OddsAPI.event_odds(league, event_id, markets)`. Requests are explicit and budgeted;
missing Ontario prices are not replaced with US prices. No props are forecast from
game winner models. Integer/Asian lines need push/half-settlement handling and
separate validation before publication.

New NBA paired-score and MLB run-grid research diagnostics use genuine archive
results for fixed spread/total thresholds, chronological calibration and held-out
forecast scoring. They are not historical sportsbook bets and have no betting ROI.
New soccer score-grid code lacks a genuine advanced-market evaluation. See
[model limitations and actual results](docs/ADVANCED_MARKETS.md).

## Telegram and permanent results

The existing workflow still schedules at 13:00 and 14:00 UTC for Toronto daylight
saving, with the script's local morning window and one-day deduplication. GitHub
schedule times can be delayed/skipped. The workflow is restricted to the default
branch and will not send from this development branch.

The workflow commits a delivery reservation, prepares analysis and archives any
qualifying predictions, commits the archive **before sending**, then records
Telegram acceptance. An ambiguous failure stays pending rather than automatically
sending duplicates. After verifying delivery and the failure cause, reconcile
`.daily_digest_state.json` and the local `deliveries` table before retrying. Never
clear pending state on a timer. Exactly-once delivery is not guaranteed by Telegram.

```bash
python telegram_alerts.py --dry-run
```

Dry run makes budgeted data calls and can archive qualifying derived publications;
it sends no message. Do not run it with production data just to test formatting;
unit tests use explicit synthetic fixtures and block all network access.

SQLite stores immutable publications/settlements. The scheduled workflow persists
derived records as `ledger/predictions.jsonl` and `ledger/settlements.jsonl` in Git,
and rebuilds its query index from them on a fresh runner. Files appear only when
real records exist. Streamlit does not automatically push its local records: give
it a persistent volume/backup or shared database before subscribers rely on it.
Git history provides an audit trail, not independent verification of source results.

Until a licensed results adapter is connected, append reviewed outcomes manually:

```bash
python -m intelligence.cli settle --prediction-id ACTUAL_ID --outcome loss \
  --result 'verified final score' --source 'actual result source reference'
```

Optional closing prices also require `--closing-source` and
`--closing-observed-at`; they must have been observed after publication and before
start. Commit settlement archive changes for the scheduled runner to restore them.
All losses are retained. Win rate, one-unit ROI/P&L, drawdown, binary Brier/log loss,
calibration and recorded closing-price value are separated by origin/sport/market/
model. No empty ledger produces fabricated metrics.

## Rollout

Review the development diff, run CI, acquire appropriate statistics and historical
odds rights, validate each market model, establish durable Streamlit storage, and
test Telegram with its actual credentials before merging. Remote workflow success
and production deployment must be observed independently. Do not enable commercial
notifications or claim readiness based on synthetic software tests. The platform
provides analysis, never places bets, and displays Ontario 19+ / uncertainty /
responsible-gambling messaging.
