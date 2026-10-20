# Phase 6 — current-price readiness and quantitative research

This increment builds on Phase 5 commit
`565aacfe6983fd4e8101ef367404ec2c59107dce`, on
`development/verified-sports-intelligence` and Draft PR #1. Existing work is
preserved. The four pages, frozen models, approval/calibration gates, provider
adapters, workflows and dependencies remain unchanged. There are no new keys,
paid integrations, purchases or automatic wagers. `PAID_ANALYST_APPROVED = "0"`,
nine daily odds credits and six daily results requests per store remain the
defaults. **Zero actual odds, results or OpenAI requests were made this phase.**

## Why current odds can be zero

Results freshness and price freshness are different. Price eligibility expires
after five minutes using the original source/receipt timestamps. A default
30-minute retrieval cache and seven-day inspection retention do not extend this
window. A cached provider response can therefore be a successful retrieval and
still contain no current usable prices. An automatic minute UI update only
rechecks eligibility; it does not poll providers.

The read-only local audit found eight saved market snapshots. Before repair,
394 observations were restorable, all stale. The legacy-key fix recovers another
516 genuine saved observations: **910 unique observations, all stale, zero
currently eligible**, at 2026-10-17 03:35 UTC. Of these, 880 concern upcoming games
in the inspection window; 30 are started/outside the window. These are individual
book/selection/line observations, not games. Their source times are unchanged.
The actual local ledger still records nine credits used on October 16 UTC;
no allowance was reset, increased or consumed by diagnosis.

Confirmed defects repaired:

- Legacy featured snapshots named `last-success-<league>` were excluded by the
  previous suffixed-key query. Both legacy and multi-market/event scopes restore.
- Results revisions invalidated session inference, but named odds-snapshot
  revisions did not. Sessions now merge newly saved prices and re-evaluate using
  saved results, without calling either provider or resetting the scan timestamp.
- Merging every old snapshot could resurrect an outcome absent from a newer
  complete query. Newer scoped responses, including empty responses, withdraw
  absent offers. Conflicting simultaneous snapshots fail closed.

The preview's earlier 265-price/six-book/23-group display and fresh results counts
are user reports, not independently verified hosted observations here. The local
audit establishes local expiry and the code defects; it cannot prove which cause
applies to the hosted store. A healthy database alone does not prove that its
previous snapshots survived a Community Cloud restart/redeployment. No external
backup or off-host restore has been configured or verified.

The dashboard and picks page explain zero prices and a safe next action. Expand
**Odds availability, distinct rankings and selection exclusions** for:

- Raw saved snapshot observations, unique IDs and rejected/malformed records.
- Session, restorable-store and selected-view counts, with current/stale/window
  categories separate from supported model-evidence counts.
- Store instance identity, original receipt, configured retrieval TTL, last query
  statuses/errors and current local quota/reset information.
- Separate explanations for missing store data, storage failure, expiry, view
  filters, fresh saved prices outside a session/scope, and invalid/window data.

The receipt-plus-TTL field is a diagnostic approximation, not proof that any
particular query or provider account is ready. Different queries have separate
caches. Compare store identity to a previous record before asserting a reset.
When current prices exist but no prediction qualifies, the summary shows the
actual input/evidence blocker separately. Fresh football results do not supply
new sportsbook observations or make every contract model-supported.

## Daily experimental summaries

**AI's Top Research Pick — Experimental** now leads both AI Dashboard and Best
Picks & Parlays. It is computed locally from existing statistical models and
rules, with no generative AI request. It reuses the existing binary favored-side
grouping, consistency checks and strict research-display gates. Both YES and NO
cannot become competing top picks for the same contract. Approved selections
remain in **Today's Best-Supported Bet**, which retains its existing gates.

Among eligible experimental selections, the deterministic default compares:
verified input provenance; narrower supplied calibration range; calibration-bin,
test and calibration support; known risk categories; lower supplied probability
bound; lower model-minus-break-even difference; point estimate; source freshness.
Thus the top research pick need not have the highest probability or best price
comparison. The existing three rankings remain visible separately. A positive
comparison is explicitly unvalidated, and no experimental EV is created.

Cards show the exact selection/market, game, sport, league, UTC kickoff, supplied
model estimate/range, observed Ontario sportsbook price and original timestamps.
The calibration range is not an independently verified confidence guarantee for
that particular game. Break-even `1 / decimal odds` is shown separately from the
model probability. The entire supplied range above/below break-even determines
positive/negative status; an overlapping range is inconclusive. Evidence and
limitations are expandable. None of these labels is approval or profitability.

**Model-only fallback** replays a genuinely computed, retained frozen soccer
forecast; it never derives a new probability from stale odds. It requires a
future exact reconciled fixture, a forecast less than six hours old, matching
frozen model/code/data/source hashes, fresh complete permitted results, and all
existing research-display gates. Expired, changed or conflicting inputs block
replay. In-memory rechecks preserve the previous evidence; immutable paper
records are also inspected, bounded to 1,000 recent records. No stale odds,
sportsbook offer, break-even, value or betting recommendation is displayed.
There is no price-free forecast for games never actually modeled. If the current
source changes, recheck supported saved current prices; old forecasts cannot be
silently applied to the revised inputs. An empty ephemeral store cannot recover
records which were never externally backed up.

**AI's Top Research Parlay** reuses the existing same-book 2/3-leg generator and
weakest-leg evidence ranking. Shared-game/team/player links stay outside this
default summary. Other games are not declared independent. Individual estimates
and source timestamps remain explicit; the individual-odds product is labeled
**theoretical; combined ticket unverified**. Joint winning probability and parlay
EV remain unavailable. No minimum candidate count is forced. Linked alternatives,
opposing selections and price-only tools remain in the existing research areas.

## Additional model evaluation

The new offline evaluator uses the same pinned, reviewed historical archive and
matched cases as Phase 5. A predeclared separate research policy adds monotone
ridge beta calibration and a prior-season annual refit of Dixon-Coles goal rates.
The constrained beta optimizer checks its convergence rather than silently
accepting a fit. Hyperparameters are not selected on test outcomes.

Static training ends June 2023; calibration is July 2023–June 2024; test is July
2024–June 2025. Annual refit training ends June 2024, using only outcomes available
before test, and transfers the prior out-of-sample binary calibration. Frozen
comparators update only from strictly preceding games. All methods in a task use
identical test matches. Excluded unsupported/new-team cases can still bias the
reported sample. Constant and Phase 5 static Dixon-Coles/Platt baselines, log loss,
ECE, calibration bins and 1,000 UTC-day-block bootstrap intervals are retained in
the complete report.

Lower Brier/log loss is better. Values below are reproduced from real archived
outcomes; they are not current predictions or betting performance.

| League / target | Test n | Frozen Brier | Beta DC Brier | Annual DC Brier | Beta log loss | Beta ECE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| EPL BTTS | 342 | 0.248481 | 0.247907 | 0.247200 | 0.689181 | 0.035335 |
| EPL goals 2.5 | 342 | 0.252121 | 0.252362 | 0.255312 | 0.699300 | 0.086646 |
| Bundesliga BTTS | 210 | 0.237093 | 0.234782 | 0.239687 | 0.661999 | 0.032139 |
| Ligue 1 goals 2.5 | 272 | 0.241122 | 0.242944 | 0.242061 | 0.678829 | 0.027683 |

Every new method's paired Brier difference interval against the frozen model
includes zero. For Bundesliga beta calibration it is −0.009430 to +0.004519.
That nominal improvement is uncertain and has worse ECE than frozen (0.014872).
For EPL BTTS the simple calibration-only constant baseline scores 0.245489 Brier,
better than the beta challenger. Annual refitting worsens some tasks. There is
no credible replacement demonstrated here. These dates were previously inspected
in project research; later seasons remain incomplete. Intervals do not correct
for all model-search/cross-day dependence. **No model is replaced or approved.**
No verified historical market benchmark or profitability evidence is available.

Reproduce offline with the exact pinned source files, without a network fetch:

```bash
OPENBLAS_NUM_THREADS=1 python -m intelligence.phase6_evaluation --source work/phase2/source
```

The distributable [report](../research_assets/quantitative/phase6.json) includes
policy, source and code hashes. Private raw archives are not bundled in CI;
local re-execution reproduced every result except generation time/checksum.
Report integrity and statistical/settlement contracts are tested in CI.

## Joint settlement research

The existing coherent soccer score distribution now has held-out diagnostics for
three fixed hypothetical score-based contract combinations:

1. BTTS Yes + Over 2.25 goals (including half-loss states).
2. Home +0.25 + Under 3.0 goals (including half-win and push states).
3. Home win + BTTS Yes + Under 3.5 goals (three dependent legs).

Each score maps to an entire joint settlement state. Masks partition the score
grid, preserving dependence and separate win/push/half-win/half-loss/loss states.
The report evaluates proper multiclass Brier/log loss with block intervals,
all-full-win Brier/log loss, ECE and calibration bins, plus prior calibration
bins, on the same 342/210/272 held-out matches. The coherent temperature is fit
only on calibration dates. Marginal binary calibrators are never multiplied to
obtain a joint probability. Calibration bins are diagnostics, not a joint approval.

These are **offline hypothetical SGP contracts**, not observed operator tickets.
There is no approved current joint probability, settlement/void-rule confirmation,
accepted combination, actual combined price or parlay EV. Multi-game research
remains on the existing marginal-evidence generator with no joint estimate.
Mixed-format research still requires missing independently tested joint/ticket
evidence; it is not automatically surfaced as an executable opportunity.

## Coverage and outstanding blockers

| Competition / sport | Genuine existing current-inference support | What still blocks wider use |
| --- | --- | --- |
| Premier League | Frozen experimental BTTS and exactly 2.5-goal totals | Fresh complete results, mature reconciled teams/fixture, supported current Ontario prices and per-event calibration gates must all pass |
| Bundesliga | Frozen experimental BTTS | Same gates; no transfer to additional contracts |
| Ligue 1 | Frozen experimental exactly 2.5-goal totals | Same gates; other totals lines unsupported |
| La Liga / Serie A | No activated model | Each reviewed 2024–25 file still has 370/380 games; incomplete training/test coverage blocks fit |
| NBA / MLB | Existing odds and archived experimental diagnostics | No ready current sport-specific model/input adapter; permitted current games and player/context data still needed; no invented prop estimates |

Approval failures are distinct: uncertain out-of-sample performance; small or
uncertain calibration buckets; no fresh independent confirmation/market baseline;
missing current team/fixture inputs; unsupported market/settlement; and absent
actual combined ticket prices/joint evidence. Fresh FDA results address only part
of this chain. This phase makes no new source-coverage or current-forecast claim.
Genuine local paper forecasts/outcomes and accepted keyed results snapshots are
still zero. Existing losing and winning record retention is unchanged.

## Test the separate preview

1. Open https://soccer-ev-scanner-preview-jp.streamlit.app/ after the development
   branch rebuild. Confirm only this preview uses
   `development/verified-sports-intelligence`, entrypoint `app.py`. Reboot only
   this preview if Community Cloud has not rebuilt. No merge is needed.
2. Keep existing Secrets and paid approval `"0"` unchanged. No new key is needed.
   Keep existing odds/results caps. Do not refresh odds merely to test the UI.
3. On **AI Dashboard**, inspect the two experimental summaries above the separate
   **Today's Best-Supported Bet**. When evidence is insufficient, explicit empty
   results are expected. A fresh results count alone need not produce a forecast.
4. Expand **Odds availability, distinct rankings and selection exclusions**.
   Compare raw saved, currently eligible and model-eligible counts; review store
   identity, last receipt, query errors, quota and the specific next action.
5. In **Data & Model Health**, click **Recheck saved research · no API calls**.
   It applies newly saved odds/results without a provider request, including
   changes saved by another session. It cannot revive expired prices or deleted
   stores. If another session saves a permitted response, the minute UI update
   applies it without a second scan. A model-only card appears only if a genuine
   retained forecast and its current source proof satisfy the separate gates.
6. Open **Best Picks & Parlays**. Check the same experimental summaries, then
   existing sport/book/leg filters, opposing details and price-only alternatives.
   Expect theoretical combined odds and absent joint probability/EV, not a ticket.
7. Open **Settings & Research Tools → Research tool → Model & Data Diagnostics →
   Phase 6 calibration, annual refit and joint settlement research**. Compare the
   table and expand full evidence for intervals, bins and partial settlement tasks.
   The existing assistant and Performance Tracker remain accessible.

The full 485-test suite, local Streamlit HTTP 200 startup, compilation, dependency
consistency and configured-secret/protected-file checks pass. Synthetic tests
are software verification, not genuine current picks. Hosted browser output,
user-hosted secrets, live provider coverage, actual ticket pricing and external
store durability remain independently unverified. See
[verification evidence](evidence/phase6-verification.json).
