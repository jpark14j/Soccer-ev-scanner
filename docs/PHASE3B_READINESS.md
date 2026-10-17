# Phase 3B: current pregame readiness and research ranking

October 16, 2026, Ontario time. Base commit:
`86f784f931c804381743a34f897e5e4969ee9d9b`. Existing development branch and
Draft PR #1 only. No model was trained, retuned or approved; no API budget was
increased. No new odds, authenticated results or paid AI request was made here.
“Current forecasts” means pregame estimates; live in-game models remain unavailable.

## Root causes found in code

1. `multi_readiness.readiness` used the bundled OpenFootball coverage when a
   model had not been prepared. Preparation is lazy: Bundesliga requires BTTS
   quotes, and Ligue 1 requires totals exactly 2.5. A configured/current results
   cache could therefore coexist with an old diagnostic date and no inference.
2. EPL's “current forecasting” string checked the expanded-model bundle flag.
   EPL uses its own frozen artifact, so the wrong conditional could print “Not
   implemented” even while EPL forecasts were present.
3. `research_views.render_health` literally said the expanded source results
   ended September 20. That sentence ignored the configured provider entirely.
4. The results-only Settings button updated SQLite, but left the browser session's
   analysis unchanged until a separate odds-analysis refresh. Other sessions and
   shared analysis caches could also retain an earlier prepared source snapshot.
5. Unapproved singles were ranked by model presence, supplied width and freshness,
   then an opaque quote ID. Probability and model-minus-break-even disagreement
   were not ordering criteria. Complementary Over/Under selections could tie on
   evidence and be ordered by hash. The low-probability Unders were not validated
   positive-EV picks, but their placement made their purpose unclear.
6. The stale count summed individual quote statuses across the saved analysis.
   Restoration retains featured/event snapshots for up to seven days, including
   outside-window records kept for inspection. `Quote.status` returns `stale`
   before checking whether kickoff has passed. The total neither counted games
   nor explained origin, window, duplicates or current-price gaps.
   The default retrieval cache is 30 minutes while price eligibility is five
   minutes; returning a cached response never extends its original timestamps.

## What is implemented

`diagnostics.py` is now the shared source for competition diagnostics, dashboard
health and a downloadable readiness report. It separates:

| Field | Meaning |
| --- | --- |
| `historical_training_source`, `historical_training_cutoff` | Frozen historical provenance and fitting cutoff; current observations do not overwrite them |
| `current_source`, `current_completed`, `latest_result`, `source_check` | Available current-season results and actual receipt; a download date is not a score date |
| `current_source_verification_fresh`, `source_problem` | Six-hour keyed-provider verification and unresolved/conflict/permission/freshness problems |
| `prepared_current_snapshot` | Source/data hashes and prior-date feature tail used to prepare a model, which may instead be needed for outcome labels |
| `used_current_snapshot` | Prepared snapshot associated with a supported inference attempt; preparation alone does not claim execution |
| `available_current_snapshot_sha256`, `cached_snapshot_differs_from_used` | Newer cached evidence versus the prepared snapshot, without silently replacing historical provenance |
| `model_input_readiness` | Preliminary source/preparation status; per-event sample, team, exact kickoff and market gates still apply |
| `inference_attempts`, `snapshot_estimates`, `last_inference_at` | Supported frozen-model attempts and actual emitted estimates in this saved analysis |
| `current_estimates`, `current_supported_prices` | Estimates/prices still eligible now, within the scan window |
| `unsupported_current_markets` | Current observed markets lacking the relevant frozen model; prices do not create forecasts |
| `validation`, `betting_edge` | Remain “Not approved” for all three soccer models |

The latest completed source result can be today while model features end on an
earlier date: frozen feature construction excludes same-calendar-day results.
This is reported separately rather than incorrectly backdating model inputs.

`cached_research.py` re-evaluates existing quotes after source/permission/cache
freshness changes, without any HTTP request. Results-only refresh immediately
updates the session, records eligible forecasts before kickoff and checks pending
labels. A separate **Recheck saved research · no API calls** button is available
in Data & Model Health. It uses local/cached results only, including for pending
outcomes and the optional legacy personal feed. Expired results cannot trigger
an automatic network request on navigation. Page/filter changes do not rescan
odds. Original odds, scan receipt times and source timestamps are retained.

## Three distinct research rankings

The dashboard and Singles page provide a **Research ranking** selector:

- **Most reliable model evidence**: narrower supplied envelopes, larger historical
  calibration/test samples, then stronger individual lower bounds/probabilities
  and freshness. Stable IDs are a final tie-breaker.
- **Highest estimated win probability**: descending marginal model probability,
  with the evidence requirements below. Probability is not expected return.
- **Strongest model-versus-market difference**: descending positive difference
  between the model estimate and `1 / decimal odds`. Negative differences are
  excluded from this view. The associated uncertainty may still cross zero.

Research-display requirements are explicit: calibrated estimates, calibration-bin
sample at least 50, calibration and held-out samples at least 100 each, supplied
envelope width at most 50 percentage points, current model inputs and current
eligible Ontario prices. The width and sample rules are display filters, not new
statistical approval standards or evidence that a strategy wins. Historical
calibration-bin envelopes are not event-specific confidence intervals.

For the user-reported examples, `36.9% - 1/2.18` is about **−9.0 percentage points**,
and `32.3% - 1/2.30` is about **−11.2 points**. These arithmetic checks do not
independently verify the reported quotes or model outputs. Such selections cannot
lead the positive-difference view. Cards show the difference and translated
envelope, with warnings when the point estimate is below break-even or the
envelope crosses zero. No unvalidated single EV or established edge is invented.

When no rows meet a ranking's requirements the app says so. Other estimates and
prices remain in a collapsed inspection section. Existing publication gates and
qualified-single calculations are unchanged.

Parlay research still rejects contradictions and reports dependence. Search now
uses calibration support and individual envelopes/probabilities transparently,
instead of resolving equal-evidence alternatives by hash. Per-leg price differences
are descriptive comparisons only. High individual probabilities do not validate
independence or a joint distribution. Actual combined price, executable status,
joint point estimate and parlay EV remain unavailable without their existing
required evidence; no new parlay is approved.

## Stale-price findings and limits

The actual development-store audit restored **394 unique quote IDs across 25
upcoming games**, all stale, with no duplicate IDs and no current eligible price.
All were marked as restored private-cache observations. They represent an actual
current-price gap in that store, not 394 games or actionable prices. Odds usage
remained **9/9**; no refresh or budget reset was attempted.

The user reported **422 stale observations** in a different store on Community
Cloud. That store cannot be inspected from this environment, so the exact 422
breakdown is **not independently verified**. The new price inventory exposes
total/unique/duplicate rows, origin counts, status counts, current eligible prices,
stale upcoming prices, outside-window/started inspection rows, and other invalid
rows. Those partition counts sum to the observed total. Dashboard research metrics
apply sidebar filters; diagnostic inventory explicitly covers the full saved scan.
Stale prices are never re-timestamped or used to fill a research shortlist.

## Genuine forecasts and forward tracking

The user reports a configured preview with 60 EPL, 46 Bundesliga and 55 Ligue 1
finals, zero unresolved past fixtures, and experimental EPL outputs. These are
**user-reported observations**, not authenticated data newly retrieved here.
This environment has no football-data.org token or access to the preview's store;
its network policy also excludes that API host. No credentials were requested.

The existing model functions are exercised through the full adapter/cache/
reconciliation/inference pipeline in tests for all three leagues, using explicitly
synthetic results and prices. That proves the conditional software path, **not
real current Bundesliga/Ligue 1 execution**. The running preview's diagnostics
and readiness export now demonstrate execution only when actual supported quotes
produced estimates. A current results cache without the required market is not
called a working forecast.

| Competition | Existing supported research markets | Approval |
| --- | --- | --- |
| Premier League | BTTS, totals exactly 2.5 | Research only |
| Bundesliga | BTTS | Research only |
| Ligue 1 | Totals exactly 2.5 | Research only |

Pregame records retain original timestamps, versions, adapter/data hashes and
quotes. Duplicate first-seen records are ignored; later verified exact-fixture
outcomes append hit **and miss** labels. Cache-only and explicit market refreshes
now also invoke this recording path. Historical backtests, paper labels and
published hypothetical wager outcomes stay separate. No prospective accuracy is
inferred from held-out history, and no new model meets approval requirements.

The local development store still has zero genuine paper forecasts/outcome labels;
the preview's counts are not known here. Streamlit Community Cloud local storage
is not guaranteed to survive redeployment. The existing private paper export and
consistent SQLite backup remain useful, but no durable hosted storage or restore
has been verified. See the [Phase 3A storage review](PHASE3A_CURRENT_RESULTS.md).

## Beginner preview verification

1. Open [the existing preview](https://soccer-ev-scanner-preview-jp.streamlit.app/)
   after its development-branch rebuild. Keep the same `app.py` entrypoint and all
   existing Secrets. Do not re-enter or share the already-configured token.
2. In **Settings & Research Tools → Settings → Current soccer results**, inspect
   the existing connection. If needed, click **Refresh soccer results only** once.
   It reuses the six-hour cache and original six-request daily results limit;
   the default three leagues consume at most three requests on cache misses.
   It immediately re-evaluates saved prices without fetching odds.
3. Return to **AI Dashboard → Data & Model Health**. All three source lines should
   reflect the available football-data.org snapshot. Open **Model, source and
   coverage diagnostics**: historical source should remain OpenFootball, with
   current source and feature dates recorded separately. Counts can naturally
   differ from the earlier 60/46/55 as fixtures finish.
4. Check each league's `current_supported_prices`, `inference_attempts`,
   `snapshot_estimates`, `current_estimates` and `current_forecast`. Bundesliga
   needs BTTS; Ligue 1 needs totals 2.5. If only moneylines or other totals exist,
   expect an explicit “Not executed”/unsupported-market result. Do not infer
   successful forecasting merely from a configured feed or a prepared model.
5. Click **Recheck saved research · no API calls** to run model checks against
   existing evidence. If prices or source verification have expired, expect no
   current estimate. Do not retrieve more odds when the nine-credit allowance is
   exhausted. Current supported markets can be requested through the existing
   Advanced Markets tool only when its original quota permits.
6. Switch **Research ranking** among all three views on the dashboard or
   **Best Picks & Parlays → Singles**. Check probability, break-even, difference,
   uncertainty and evidence separately. The positive-difference view must exclude
   negative comparisons. Empty rankings are valid; no pick is forced.
7. Inspect **Parlays**: per-leg evidence may improve, but prices remain theoretical
   and there is no executable parlay EV or newly approved joint model.
8. Inspect the **Saved-scan price inventory** to reconcile the actual stale count,
   then **Prepare readiness evidence export → Download readiness evidence JSON**.
   This makes no API call and contains source hashes/execution counts, not tokens.
9. Check **Performance Tracker → Prospective paper research** after eligible
   current estimates have been recorded before kickoff. Later results can append
   labels; no backfill is counted as prospective success. Download a private
   paper export from Settings before any reboot/redeploy; automatic permanence
   is not claimed.

## Verification and files

383 offline tests pass, including 30 new source-switch/cache/diagnostic/ranking/
stale-inventory/conditional-inference/parlay/tracking/UI regressions. Compilation,
dependency consistency, whitespace and configured-secret checks pass. Local
Streamlit health is HTTP 200 on isolated port 8511 with API credentials removed,
all refreshes disabled, cap zero and paid AI disabled. Frozen model, policy,
alias, evaluation artifact, four-page navigation and workflow files are unchanged.
Hosted rebuild/interactive checks and actual preview exports remain unverified.

New modules: `diagnostics.py`, `cached_research.py`, `research_ranking.py`.
Updated routing/source helpers: `app.py`, `current_results.py`,
`current_results_ui.py`, `current_soccer.py`, `history.py`, `pipeline.py`,
`multi_readiness.py`, `slate.py`. Updated views/ranking: `research_state.py`,
`research_views.py`, `slate_views.py`, `book_optimizer.py`, `parlay_research.py`,
`parlay_ui.py`. Tests: `test_readiness_ranking.py`. Documentation: this guide,
README, the verification matrix and the earlier results-readiness guides.
Machine-readable results: [evidence](evidence/phase3b-verification.json).
