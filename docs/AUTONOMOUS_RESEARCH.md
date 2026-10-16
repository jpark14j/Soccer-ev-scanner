# Automatic slate research and operational boundaries

2026-10-16 · extends `6bad6ab` on `development/verified-sports-intelligence`.
This is the existing Streamlit application and Draft PR #1, not a new application.
Main, production hosting, subscriptions and paid OpenAI remain unchanged.

## What to click in the preview

1. Open **https://soccer-ev-scanner-preview-jp.streamlit.app/** after Community
   Cloud rebuilds the development branch, entrypoint `app.py`.
2. **AI Dashboard** is the default. Read games discovered/observed, games with
   current markets, games with research estimates, evaluated game-market groups,
   books observed, qualified singles, model status, odds receipt time and quota.
   Discovery is not a claim that every market was retrieved or every game modeled.
3. Read **Best Selections by Game** cards. The dashboard previews three games; the
   sidebar page offers more. Each game shows at most two selections and explains
   missing evidence. Equal-evidence price-only samples have no demonstrated
   statistical superiority. No selections are invented for an unscanned game.
4. Read **Sportsbook Parlay Shortlist**. Choose **2 legs**, **3 legs** or **2 or 3
   legs**. At most one qualified ticket per observed book is shown. With present
   evidence, **No Qualifying Parlay** is expected. Optionally expand **Strongest
   available research candidate — unvalidated** for its real individual prices,
   starts, English selections, theoretical product and blockers.
5. **Daily Parlay Research / AI Parlay Builder** also provide these cards. The
   previous functional filters/selector remain in the collapsed **Advanced research
   filters and legacy selector**. Optional bankroll loss analysis remains available;
   Kelly is disabled for unvalidated research combinations.
6. Raw odds are in **Advanced Details / Raw Market Data**, collapsed by default,
   on the dashboard, sport pages, advanced market explorer and legacy candidates.
   The ordinary experience does not require scrolling through an odds table.
7. **Research Operations** explains automatic processing, private research records,
   database health, model artifacts, drift diagnostics and disabled infrastructure.
   **Performance Tracker** separates published forward/backtest outcomes from
   private forecast-label diagnostics and historical archive evaluations.
8. Ask **AI Assistant** “Which games did you analyze?” or “What is the best-supported
   parlay research candidate for BetMGM?” Local rule-based answers use the same
   records and acknowledge incomplete coverage. No question is sent to OpenAI.

If the menu is missing, inspect/reboot only the preview in Community Cloud and
confirm its development branch and `app.py`. Do not replace production. This
execution environment cannot verify the public preview browser/build; local
AppTest and HTTP health checks are separate evidence.

## Automatic, partial full-slate analysis

On opening/reloading, the existing cached pipeline discovers provider events for
configured competitions, default NBA/Premier League/MLB, within the next 48 hours.
`SLATE_WINDOW_HOURS` accepts 1–168 through environment/Streamlit Secrets.
The provider documents event listing as zero credits; identical requests still
use the shared cache. A failed listing is explicitly incomplete, with saved
observations as fallback. A zero-event list does not prove no games exist elsewhere.

The engine considers featured moneyline/spread/total queries and documented
per-event NBA points/rebounds/assists/threes, soccer BTTS and supported MLB props.
Asian-style returned lines remain inspectable, not verified settlement forecasts.
Undocumented corners are not automatically requested; exact discovery remains
available in Advanced Markets. Documented keys do not establish Ontario access.
No US/global substitution or unauthorized scraping is used.

Within the existing local cap, the queue first preserves breadth with one
oldest-needed featured task per competition, then alternates event/featured work.
Event priorities interleave competitions/market families. Unqueried and older
tasks rotate first; current observations and recent empty queries are reused.
No-event windows skip unnecessary featured calls. A provider failure halts later
chargeable tasks and imposes a shared five-minute backoff. Existing canonical
cache, minimum 60-second reuse, fetch leases, retries and atomic reservations remain.

The cap is still **9 by default in the UI**, honoring explicit environment/Secrets
settings. It is not raised or cleared by this engine. At 9/9, discovery/cached
inspection can work, but no chargeable query is made. The normal next local reset
is UTC midnight: October 17, 2026 00:00 UTC equals October 16 **20:00 EDT**. Provider
account/monthly reset is distinct. Different databases do not share local counters.

Coverage records show each discovered event, query status, empty/failing/reused/
unrequested task and original receipt times. “Markets evaluated” means actual
current game-market observations checked, not every provider market in the catalog.
The 30-minute default response cache can outlive the five-minute quote freshness
limit. The render timer rechecks expiry without polling the provider. Reopening
or explicit refresh can do more research only when cache/quota permit.

The real 14:05 EDT verification discovered nine Premier League games and one MLB
game in 48 hours; NBA returned zero. Twenty-three market tasks were assessed but
chargeable endpoints were prohibited, and the existing budget stayed 9/9. No new
current odds or qualifying opportunity resulted. See the dated evidence record;
this is not a promise of tomorrow's coverage.

## Ranking and parlay search

Every eligible current Ontario single in the observed scan window is scored.
Equivalent selections compare real prices across books. Game ranking prioritizes
qualification, conservative EV only when validated, model evidence, supplied
uncertainty and freshness. Deterministic ties are research samples, not proof that
one side is better. Missing/old player context is never fabricated.

Per-book pools of at most 24 eligible legs enumerate all requested 2/3-leg
combinations. Larger pools use a disclosed deterministic beam of width 24: all
eligible singles are scored and can extend the beam, but not every combination
is evaluated. Search counts and method are visible. No global optimality claim.
Opposing, duplicate, shared-player and score contradictions use the existing
compatibility engine. Same-game, shared-team and cross-game dependence remain
explicit; cross-game independence is never inferred.

The qualified path accepts exact `CombinedPrice` and `JointEstimate` contracts,
evaluates every supplied genuine quoted ticket, applies the existing freshness,
restriction, uncertainty and EV gates, then selects one per book by conservative
EV. **No adapter currently supplies these combined/joint contracts.** Research
products remain theoretical. There is no executable parlay EV or actual accepted
ticket record. Historical model diagnostics do not become candidate win rates.

## Predictions, results and durability

Qualified singles retain the existing immutable publication-before-start ledger.
Raw unvalidated pregame estimates now also create **private shadow forecasts**,
with original price/time/model/target and a unique first-forecast identity.
They cannot enter published betting ROI or Telegram recommendations. Historical
UI replays are test fixtures, not backdated genuine forward predictions.

Ended pending publications/shadow events cause automatic completed-results
collection when the same database has two remaining credits. Cached daily result
collection is reused. No pending events means no automatic score query unless
the operator explicitly enables the existing `COLLECT_RESULTS` option.
All provider score snapshots append; conflicting corrections block automatic
settlement. Missing games outside the provider's short results window remain
pending; postponed/abandoned events are never guessed voids or losses.

Provider-declared completed NBA/MLB finals can label explicit full-final research
targets as hit/miss/push. These are forecast-label diagnostics, not operator
wins/losses, accepted tickets or profit. Soccer period scope, player results and
quarter lines require additional verified adapters. Published bet settlement
requires exact event/participants/start plus reviewed book/sport/market rules and
provider scope. `config/settlement_rules.json` is deliberately empty: no operator
rules were verified. No real publication was automatically settled in this session.

SQLite and immutable records survive a process restart on the **same disk**.
The existing derived prediction/settlement JSONL archives can rebuild the ledger.
Private raw feeds, results and shadow records are not committed to Git. The
backup CLI uses SQLite's consistent backup API, preserves quota and all tables,
uses private file permissions and refuses overwriting existing backups.

```bash
python -m intelligence.cli research-cycle --offline
python -m intelligence.cli backup --output work/private-backups/research-NEW.sqlite3
```

A backup on Community Cloud's ephemeral disk is not off-host protection. **Data
survival across Community Cloud redeployments is unverified and not provided by
this increment.** A writable/healthy disk or a self-set environment flag cannot
prove it. Configure and test a durable shared store/off-host backup before relying
on long-running learning or account-wide quota; do not enable a separate worker
with an independent fresh counter as a spending workaround.

## Model lifecycle and scheduling

There is no newly approved model. Existing NBA/MLB archives still end in 2015/2025;
player/injury/lineup/current context and historical executable odds are missing.
The new registry preserves content-addressed candidate artifacts, data/code hashes,
evaluation periods, sample sizes, expanding folds and append-only reviewed actions.

```bash
python -m intelligence.cli train-challenger --league NBA
python -m intelligence.cli train-challenger --league MLB
```

These commands require already imported provenance-checked history; they do not
download data or purchase anything. Both ran against genuine local archives in a
private test database, producing three folds each and **zero activations**.
Folds can overlap and reuse earlier research periods; they are exploratory,
not independent confirmation. Comparison refuses different source/test periods.
With no active reviewed champion, no performance improvement is asserted.

Training never activates a model. Publication now additionally requires a reviewed
registry activation matching the exact current report. Existing gates remain:
sample sizes, timely market benchmark, calibration/uncertainty and recency. New
activation also requires independent fresh unseen-period and permitted-data/scope
evidence, at least 100 unique forward decisions, a positive dependence-aware
improvement lower bound and explicit review/verification references. Rollback must
target a previously approved, still-eligible artifact. The `review-model` CLI is
an operator action, not available through chat. Attestations need real evidence.

Forward drift monitoring groups actual settled publications by sport/market/model,
deduplicates events and compares successive 100-event Brier windows. An increase
above the predeclared 0.03 threshold requests review. It is a diagnostic threshold,
not a formal change-point proof; no automatic promotion/rollback follows. With no
settled forward history, monitoring correctly reports insufficient data.

Streamlit runs on-open analysis, **not an always-running background service**.
The scheduler-neutral worker defaults to disabled online operation. Online use
requires `RESEARCH_WORKER_ENABLED`, `RESEARCH_DURABLE_STORAGE_VERIFIED` and
`RESEARCH_DATA_RIGHTS_VERIFIED` all explicitly `1`, an existing configured odds key,
and the same capped persistent database as the UI. These flags are deployment
attestations, not independent verification. No such worker was enabled here.

The new development-only Actions workflow is **manual, offline and read-only**,
with no data/AI secrets or notification/deployment step. No cron was installed:
GitHub scheduled workflows require default-branch installation, and main must
remain untouched. Scheduled collection and scheduled retraining are **not
operational**. Use a separately verified persistent worker/scheduler later;
no hosting subscription or default-branch change was made.

## Verification and remaining work

Tests cover spend/coverage/caching/backoff, whole-slate single scoring, large-pool
disclosure, exact combined/joint gates, collapsed UI, game/book assistant facts,
immutable forecasts, automatic result collection, conflicting scores, scope,
pushes, backup restore with quota, manual activation/rollback and disabled workers.
See [VERIFICATION.md](VERIFICATION.md) and the consolidated evidence JSON.

Still required for evidence-backed parlays: current legally usable statistics and
player context, timestamped historical prices, verified market/settlement rules,
fresh independently held-out joint calibration, genuine combined-price access,
durable storage and a loss-inclusive forward record. Commercial redistribution
rights remain unverified. No winnings, high win rate or profitable strategy is
claimed, and no wager can be placed by this application.
