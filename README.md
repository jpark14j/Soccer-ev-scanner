# Soccer-ev-scanner — Ontario sports intelligence development

This upgrades the **existing** Python/Streamlit app on
`development/verified-sports-intelligence`. The production entrypoint remains
`app.py`; the existing Telegram script, workflow path and secret names are retained.
Nothing on `main` has been deployed or had its secrets changed by this work.

The application retrieves genuine NBA, soccer and MLB sportsbook observations,
checks Ontario feed provenance and freshness, and publishes only selections that
pass model evidence and uncertainty-adjusted EV requirements. **No model has been
promoted on the evidence available in this session. No profitable strategy is
claimed.** The honest current result is no qualifying recommendations.

Read [the audit](docs/TECHNICAL_AUDIT.md), [provider review](docs/PROVIDERS.md),
[stage results](docs/STAGE_REPORT.md), [free data choices](docs/FREE_DATA.md), [architecture](docs/ARCHITECTURE.md) and
[verification matrix](docs/VERIFICATION.md) before rollout.

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

All ten requested sections are present. The analyst answers from current
application records; default local mode **does not call a language model API**.
A strict-schema optional OpenAI intent router is implemented but disabled. Paid routing requires explicit approval, a token budget and provider connection.
The model cannot introduce unverified numeric claims; factual answers use templates. Live and prop recommendations remain disabled
until their necessary inputs and validation exist; observed prices are distinct
from predictions and from executable sportsbook offers.

## Configuration and cost control

| Variable | Default | Purpose |
| --- | --- | --- |
| `ODDS_API_KEY` | existing secret | Authorized existing provider account |
| `ODDS_DAILY_CREDITS` | `16` | Local UTC-day reservation cap, including retries |
| `COLLECT_RESULTS` | `1` | Cache and accumulate completed NBA/MLB results once per 24h; `0` disables |
| `ODDS_CACHE_SECONDS` | `1800` | Shared provider response cache |
| `INTELLIGENCE_DB` | `data/intelligence.sqlite3` | SQLite query index/cache; persistent disk recommended |
| `PREDICTION_LEDGER_DIR` | `ledger` | Derived immutable prediction/settlement JSONL archive |
| `HISTORY_DIR` | `data/history` | Licensed historical CSVs plus source manifests |
| `MODEL_DIR` | `data/models` | Chronological evaluation artifacts |
| `PAID_ANALYST_APPROVED` | disabled | Set to `1` only after explicit paid API approval |
| `OPENAI_API_KEY` | absent | Optional paid routing credential in secrets only |
| `ANALYST_MONTHLY_USD_CAP` | `5` | Conservative local monthly reservations; not account-wide billing protection |
| `FOOTBALL_DATA_PERSONAL_RESEARCH` | disabled | Explicit personal-only free-source research mode |
| `DIGEST_LEAGUES` | all nine competitions | Comma-separated configured competition names |
| `DIGEST_HOUR_LOCAL` | `9` | Toronto delivery window; change Actions crons too if hour changes |
| `STREAMLIT_APP_URL` | existing deployment | Link in daily report |

Nine competitions, h2h once daily (270 credits/30 days), plus daily NBA/MLB
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
