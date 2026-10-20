# Daily Parlay Research — working MVP

Open the existing development preview:
**https://soccer-ev-scanner-preview-jp.streamlit.app/**

This preview uses `development/verified-sports-intelligence`, entrypoint `app.py`.
Production/main remain untouched; Draft PR #1 remains unmerged. Keep
`PAID_ANALYST_APPROVED = "0"`; the selector never calls a language model.

## Open and test it

1. After Community Cloud rebuilds the pushed development commit, refresh your
   preview URL and select **Daily Parlay Research** in the sidebar. The existing
   **AI Parlay Builder** page opens the same selector and preserves its separate
   qualified-leg diagnostic. If the new menu is absent, use **Manage app** on this
   **preview only**, check its development branch/`app.py`, inspect rebuild logs or
   reboot the preview. Do not change your production app.
2. Keep the initial research filters at NBA + Soccer + MLB, available sportsbooks,
   2 + 3 legs and all categories. The sidebar's competition/sportsbook selections
   constrain this page too. Up to three distinct event sets appear if enough
   compatible current quotes exist at one sportsbook.
3. Test **Number of legs → 3**, then individual sports, sportsbooks and risk
   categories. Different games/sports can be combined; different sportsbooks
   cannot be combined into one actual ticket. Filters do not fetch extra data.
4. If there are no current candidates, expand **Get current prices and inspect
   search coverage**. Narrow sidebar competitions and/or **Research sports** first
   (for example NBA only, or Premier League only). Click **Refresh selected odds**.
   The button states the minimum local credits needed; retries also count.
   It uses your existing `ODDS_API_KEY` from preview Secrets, not an OpenAI key.
5. Inspect each leg's event/start, sport, selection/line, sportsbook, individual
   price, source/receipt timestamps, implied probability and model evidence.
   **What must be verified before this can qualify** lists missing requirements
   and dependence warnings. Model history dates are visible, including old archives.
6. Inspect **Coverage and exclusion details** if the page is empty. Stale/suspended/
   in-play/unverified quotes and contradictory or duplicated outcomes are rejected.
   One upcoming MLB game with two opposing winner selections cannot make an
   MLB-only 2-leg parlay; another eligible game/market is needed. Do not expect a
   candidate for every sport or every day.

The verified local run found three research candidates overall, three with NBA-only
and Soccer-only filters, and none with MLB-only because the captured feed contained
only one eligible MLB event. These are observations from 2026-10-16, not a promise
about what the preview will show later.

## What the numbers mean

- Individual prices are real provider observations from exact Ontario sportsbook
  keys in the dated registry. Source and receipt age must both be at most five
  minutes. The timer rechecks age every 60 seconds without polling the API.
- **Theoretical all-win odds product** multiplies the individual decimal prices
  solely as a hypothetical all-win payout reference. It is not an actual combined
  quote, accepted parlay, independence assumption or sportsbook offer. Pushes/voids
  can change settlement. This provider integration has no combined-price endpoint.
- **Market implied probability** is `1 / individual decimal odds`, including margin.
  It is not the model forecast, and implied or model probabilities are never
  multiplied to supply a joint parlay probability.
- Research model estimates come only from genuine available history. They remain
  explicitly unvalidated unless the existing publication evidence gates pass.
  Calibration is used only when report code/version/scope/expiry and the exact
  historical dataset hash match. Otherwise the forecast is uncalibrated and its
  uncertainty envelope is 0–1. Calibration counts, held-out scores and blockers are
  inspectable. Bin Wilson envelopes are not event-specific confidence guarantees.
- If every leg has a model estimate, dependence-free Frechet bounds are shown
  conditionally on those inputs, with another range allowing their supplied
  envelopes. These are mathematical bounds, not a fitted or calibrated joint
  estimate; research inputs remain research-only.
- Individual EV appears only with suitable validated, current market evidence.
  **Parlay EV and joint probability stay unavailable** until a validated dependence
  model and actual authorized combined quote cover the exact selections, with
  sportsbook acceptance/rules established. No candidate from this selector is
  executable, published as a recommendation or inserted into the performance ledger.

## Selection and ranking

The selector now admits current, pregame NBA/Soccer/MLB reviewed featured markets,
BTTS and actually returned supported player/corners observations at one Ontario
sportsbook. **Advanced Markets** provides explicit narrow featured/event retrieval;
the selector's original refresh remains h2h. Undocumented corners need exact event
discovery. Catalog support does not establish Ontario availability. Use market-type
filters and **Research event scope → One selected event** for same-game analysis.
Period markets remain excluded. Quarter/integer lines have no settlement forecast.

Supported full-event legs may display an **unvalidated same-game score-model
scenario** from intersecting score outcomes. It is not an approved joint probability,
independence assumption or EV calculation. Props lack connected player-history models.
See [actual access, model results and limitations](ADVANCED_MARKETS.md).

Search is bounded to 24 legs per sportsbook, balanced across sports/events before
alternate sides. It enumerates 2/3-leg combinations, rejects duplicate/shared
outcomes and contradictory score constraints, and flags same-game/shared-team
(including doubleheader) dependence. No pair of different games is deemed independent.
The three results use distinct physical event sets, including across sportsbooks.
The search is deterministic and not exhaustive; no optimal-profit claim is made.

All candidates pass the same actual-single-price availability gate. Ranking then
uses validated-model fraction, available-model fraction, explicit dependence/
settlement flags, average supplied interval width (missing counts as 1), oldest
source age, fewer legs and deterministic IDs. The displayed explanation gives the
actual components. It never rewards a larger odds product or asserts a profitable edge.

Risk labels are **price/leg-count proxies**, not validated risk measurements:

| Label | Research rule |
| --- | --- |
| Lower-variance | 2 legs and each individual decimal price ≤ 1.80 |
| Balanced | Remaining combinations with theoretical product ≤ 6.00 |
| Higher-variance | Remaining combinations with product > 6.00 |

Every category can lose. Fitted joint probabilities are required before empirical
variance, reliability or a probability-based risk category can be claimed.

## Existing historical data and costs

The pipeline first uses configured licensed history and locally collected results.
When fewer than 100 NBA/MLB rows are available, it can read already imported,
licence-manifest/hash-checked snapshots in `RESEARCH_HISTORY_DIR` (default
`data/research/history`), with reports in `RESEARCH_MODEL_DIR` (default
`data/research/models`). Explicit archive team-code mappings replace guesses.
Ambiguous names remain unsupported. No historical file is downloaded automatically.

The available NBA snapshot ends in **2015** and MLB in **2025**: these are old
research inputs, not current player/team context or a validated advantage. Source
rights/attribution and import commands are in [FREE_DATA.md](FREE_DATA.md). Data
files are gitignored and do not automatically exist on Community Cloud; the page
works with missing estimates. Free source availability does not establish commercial
redistribution rights. No new historical feed, subscription or paid API was enabled.

Normal loading still uses the existing provider cache and daily cap. The explicit
research refresh shortens the time cache only after a click, fetches selected
competitions, skips completed-score collection, has a 60-second session cooldown
and at least 60 seconds of shared cache even for empty responses. Canonical market
sets, current-observation reuse and database fetch leases reduce duplicate calls.
It retains daily credit reservations/retry accounting. It never increases or
resets a cap. A partial provider failure can retain an honestly stale fallback;
that fallback still cannot enter the selector. Refresh cannot make an old provider
source timestamp current. Separate deployments/databases share provider-account
quota but not local counters; check the account's actual quota/terms.

The interactive default is now 9 credits and three competitions with automatic
score collection off; explicit environment/Streamlit Secrets values are honored.
At 9/9, the exact next UTC reset and Toronto equivalent explain disabled searches.
**Advanced Markets → Include stale / historical** preserves seven-day cached
inspection; these observations cannot enter current candidates. No limit is raised.

## Verification and limits

Automated tests block real Requests/HTTPX transports. They cover actual selection,
filters, source ageing, Ontario eligibility, duplicate/opposing/nested legs, integer
score feasibility against brute-force score outcomes, dependence warnings, missing
prices/models, probability bounds, suppressed EV, calibration dataset matching,
quota handling, shared refresh state and the Streamlit/assistant integration.

A separate genuine provider check requested NBA, MLB and Premier League once each:
516 normalized quotes, 454 current Ontario quotes, three displayed research
candidates and no executable parlay. The UI was exercised using that captured
provider data while fresh, with no additional API requests. Test and source times
are in [the verification evidence](evidence/parlay-research-verification.json).

The external Community Cloud preview URL could not be reached from this execution
environment (proxy connection failure; the web reader also could not access it).
This does not establish that the preview is down. The same branch/entrypoint is
verified with Streamlit AppTest and a local server; Community Cloud's actual build,
login and browser state still need your check using the steps above.

Next work requiring genuine external evidence: authorized combined-parlay pricing,
book-specific acceptance/rules, current licensed statistics and fitted/calibrated
joint models. Until then this is useful **research discovery**, not qualified picks.
