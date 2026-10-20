# Phase 4: model-first parlay intelligence

Implemented on `development/verified-sports-intelligence`, continuing from
`e38ecf94e55891a6b095efad0994b38f1a73a9d0`. Draft PR #1 only. No production,
main, Secrets, subscription, approval policy or API budget was changed.

## What works

**Best Picks & Parlays → AI Parlay Intelligence** now builds model-backed 2-leg
and 3-leg research candidates automatically from the saved analysis. Explanations
are local, deterministic descriptions of statistical evidence, not paid language
model output. NBA/soccer/MLB selection contracts are supported by the engine;
actual estimates require a functioning sport/competition/market model.

Equivalent sportsbook observations are grouped by sport, competition, reviewed
team identities, exact UTC kickoff, market, line and participant. Opaque event IDs
alone cannot create another game. Opposing binary outcomes share one group. Only
the side with model probability greater than 50% can enter the default shortlist.
A tie, missing favored-side price or inconsistent model snapshots/probabilities
withholds that group. A price never supplies a model probability. Integer/quarter
lines with push/partial-settlement exposure and three-way markets remain outside
this binary shortlist until an explicit outcome-distribution contract exists.

Each card shows the sport, game, league, kickoff, exact selection, individual model
estimate and supplied calibration envelope, experimental status, observed Ontario
book/individual decimal price, original source update and receipt. **Why this leg?**
contains the method, sample sizes, opposing observed outcomes, model/price
comparison, provenance and blockers. Missing opposing prices are not manufactured.

The central view separates:

1. **Highest estimated win probability**: one 2-leg and one 3-leg candidate when
   supported, plus an expandable list of favored individual outcomes. The heading
   refers to marginal model estimates, not a validated parlay winning chance.
2. **Strongest potential value**: favored individual estimates above the observed
   margin-inclusive break-even percentage, with uncertainty. This is unvalidated
   model disagreement, not established value, positive EV or profitability.
3. **Alternative experimental research candidates**: additional combinations
   ordered by evidence quality, at most two cards (three parlay cards total). Known linked-game/team/player
   combinations require an explicit research-control checkbox and stay here only.

No output minimum is forced. Unsupported price-only combinations remain in
**Parlays → Unsupported and price-only research · full existing generator**.
The existing single tools, sportsbook optimizer, same-game scenarios, qualified-leg
diagnostics, assistant, performance tracker and all four navigation pages remain.

## Ranking and dependence

All existing research-display requirements remain: calibration demonstrated,
bucket n≥50, calibration and held-out test n≥100 each, supplied envelope width≤50
percentage points, current input history (21 days for soccer, 90 for other sports),
fresh optional-results verification and current eligible Ontario pregame prices.
These checks permit research display; they do not approve a model.

Within each sportsbook, every eligible favored group is scored. A bounded pool of
at most 24 favored markets is searched, prioritizing different games before more
markets from one game. Equivalent offers at that book consume one pool position.
The pool uses existing evidence ordering: envelope width, calibration/test support,
lower estimate and freshness. Two-leg and three-leg shortlists are separate:

- Default ordering: strongest weakest-leg lower envelope, then weakest-leg point
  estimate, then narrower maximum envelope, larger minimum calibration bucket and
  fresher worst source timestamp. Stable selection IDs resolve remaining ties.
- Alternative ordering: fewer known links, narrower maximum envelope, larger
  minimum bucket, stronger marginal lower/point estimates and freshness.

This is a disclosed research heuristic, not a proven optimal winning portfolio.
Payout is not a ranking objective. The best individual price is compared only for
the same outcome; all legs in any displayed parlay come from one book. Books with
the same physical selections are deduplicated by evidence/freshness and stable
IDs, without a favored operator. Cross-book maximum prices never form a ticket.

Known shared-game/team/player links stay out of the default shortlist. Existing
pairwise and integer-score feasibility checks reject contradictory or repeated
constraints even when linked research is enabled. Reviewed team aliases and
physical-game normalization also protect against alternate feed IDs. Same-league
and shared-model/calibration errors are explicitly disclosed. **Different games
or sports do not prove independence.**

No marginal probabilities are multiplied. **No validated joint probability,
combined sportsbook ticket, executable combined price or parlay EV is available.**
The individual-odds product is clearly theoretical. Logical Fréchet bounds appear
only in technical details, conditional on unvalidated marginal estimates; they
are not a confidence interval or calibrated parlay forecast. Operator acceptance,
period/settlement rules, player availability and cross-game dependence remain
missing evidence. Separate 2/3-leg ranks cannot prove the 3-leg candidate is more
likely to win than the 2-leg candidate.

## Genuine models and current-data limitations

| Competition | Actual existing frozen research model | Current blockers |
| --- | --- | --- |
| Premier League | `epl-goal-strength-1`: BTTS and total goals exactly 2.5 | Complete reconciled fresh results, mature/current team history, exact fixture and supported current Ontario price must all pass |
| Bundesliga | Competition-specific venue-goals BTTS | Same current-input/fixture/price gates; no other competition's model is reused |
| Ligue 1 | Competition-specific venue-goals total goals exactly 2.5 | Same gates; unsupported lines/markets produce no estimate |
| La Liga / Serie A | No frozen validated/current research model | Incomplete historical seasons need repair, own chronological evaluation/calibration and model artifacts |
| NBA | No currently ready model | Bundled results end June 16, 2015; current reconciled history and sport/market validation needed; props also require permitted player logs/minutes/availability |
| MLB | No currently ready model | Bundled results end September 28, 2025; current results plus permitted pitcher/lineup/park context and sport/market validation needed |

All three soccer models remain **experimental and unapproved**. Historical
calibration envelopes are not event-specific confidence intervals. Evidence may
include 50% or the sportsbook break-even point and reverse the apparent preference.
Current-source availability alone does not prove an inference ran successfully.

The local store has no current keyed-results observations or genuine paper
forecasts/outcome labels. A read-only run of the new selector over 394 saved
prices across 25 upcoming games rejects all 394 as stale and displays no candidate.
Its October 16 odds budget remains 9/9. No real current parlay is claimed from
software fixtures. The previously user-reported current EPL preview estimates are
not an independent verification of the hosted store or Bundesliga/Ligue 1 output.

Brief source recheck on October 16, 2026 (documentation reads, no new feed requests):

- [Football-data.org coverage](https://www.football-data.org/coverage) documents
  the three supported leagues plus La Liga and Serie A. The optional adapter is
  already implemented; its free account token/use review, cache, completeness and
  exact reconciliation gates still apply. This is not proof of actual current
  access, commercial resale rights or a ready additional model.
- [BALLDONTLIE NBA documentation](https://nba.balldontlie.io/) lists free account-
  keyed games/teams/players access at five requests/minute. Player game stats and
  injuries require paid tiers. A future reviewed free-games adapter could address
  NBA result history, but not automatically props, current model validation or
  commercial redistribution rights. No trial, account or paid plan was activated.
- [Retrosheet game logs](https://www.retrosheet.org/gamelogs/index.html) provide
  archives through 2025 on the reviewed page and permit use with required credit.
  No 2026 archive was verified there; old logs alone do not solve current MLB
  input readiness. A current permitted results/context source remains necessary.

## Exact preview test steps

1. Open https://soccer-ev-scanner-preview-jp.streamlit.app/ after Community Cloud
   rebuilds this development branch (`app.py`). If the new heading is absent,
   reboot **this preview only** from its Manage app menu and reload. Do not change
   production, merge PR #1 or add a new deployment.
2. Choose **Best Picks & Parlays** in the sidebar. **AI Parlay Intelligence**
   appears above the existing Singles/Parlays tabs. Leave paid approval `"0"`,
   odds cap 9 and all existing Secrets unchanged; no new key is required.
3. Leave **Model-research sports** at all three sports. In **Parlay research
   controls**, select 2 and/or 3 legs. Sidebar **Sportsbooks in view** filters
   already loaded observations. These filters do not retrieve another odds scan.
4. Inspect the three sections. Open **Why this leg?** for opposing outcomes and
   evidence; open **Why this combination?** for risks/dependencies. Confirm that
   combined tickets say unverified, odds products theoretical, and joint probability
   and parlay EV unavailable. YES/NO should not both be top recommendations.
5. No candidates is a valid result. Open **Selection exclusions, opposing outcomes
   and search method**, then **Sport and model coverage**. A usable model alone
   is insufficient if there are not at least two compatible favored prices at one
   book, or calibration/source/freshness/dependency gates fail.
6. For result/input diagnostics use **AI Dashboard → Data & Model Health**, or
   **Settings & Research Tools → Model & Data Diagnostics**. The existing
   **Recheck saved research · no API calls** reuses saved results/quotes. Fresh
   results cannot revive expired odds. Do not refresh odds when the daily cap is
   exhausted. Five-minute price eligibility is unchanged; the 30-minute provider
   retrieval cache can still contain expired observations. Minute-by-minute card
   checks remove stale candidates without HTTP calls.
7. Adding sidebar **Competitions** changes scan scope and may consume available
   credits. Do so only deliberately within the existing allowance. Bundesliga
   needs actual BTTS observations; Ligue 1 needs actual totals exactly 2.5.
   Catalog or source coverage does not guarantee those markets at a given book.
8. Test the preserved local assistant via **Settings & Research Tools → Research
   tool → AI Assistant**, and the separate forward/backtest performance tabs.

Automated Streamlit interactions and an isolated local HTTP startup are verified.
The hosted rebuild, interactive preview and actual current output could not be
independently inspected here. Community Cloud local-file retention across
redeployments is still not guaranteed. No durable combined-ticket prediction
ledger or prospective parlay win rate is claimed.

## Files and verification

New: `intelligence/parlay_intelligence.py`, `intelligence/parlay_intelligence_ui.py`,
`tests/test_parlay_intelligence.py`, this guide and its evidence JSON. Updated:
`research_ranking.py`, `research_views.py`, `workspace_ui.py`,
`tests/test_current_results.py`, README, navigation guide and verification matrix.
The synthetic results fixture now keeps scheduled
test games in the future after 23:50 UTC; no existing assertion or gate was weakened.

**417 offline tests pass, 34 added**. Coverage includes favorite/price separation,
equivalent/opposing consistency, weak/missing evidence, source price expiry and
provenance, bounded search, alias-based physical deduplication, contradictions,
dependency alternatives, same-book prices, no joint/EV/ticket invention, actual
frozen model functions with synthetic current inputs, all four UI pages, filter
request guards and credential redaction. Provider payloads and NBA/MLB probabilities
in software tests are explicitly synthetic and are not coverage/performance claims.
Compilation, dependency consistency, whitespace, configured-secret and frozen-model
checks pass. Streamlit health returns HTTP 200 `ok` on isolated port 8512 with
credentials absent, cap zero, data refresh and paid AI disabled. Existing CI is
unchanged and runs on the development commit; inspect its linked GitHub result.

There are no new dependencies, keys, subscriptions or API costs. Real odds/results
and paid AI requests added by this phase: zero. Paid approval defaults to `"0"`;
the existing nine-credit per-store daily odds cap and model approval/calibration
policies are unchanged. A future phase can improve permitted current NBA/MLB data,
build competition-specific models, and independently validate joint/combined-price
adapters; none is silently approximated by this selector.
