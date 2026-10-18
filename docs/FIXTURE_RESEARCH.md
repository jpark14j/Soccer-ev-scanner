# Fixture research without an odds request

Home and Best Picks & Parlays retain the existing five-page application. Both
now include **Model research without live odds**. This uses saved, permitted,
full-season football-data.org results and exact upcoming kickoffs. It makes no
provider call. The unchanged EPL BTTS/2.5-goal models, Bundesliga BTTS model and
Ligue 1 2.5-goal model supply experimental estimates when all input checks pass.
Missing, expired, conflicting or postponed results withhold estimates. No fake
price or sportsbook object is constructed to satisfy a prediction function.

The displayed fair decimal is `1 / model probability`, not an available price.
No EV or betting approval is supplied. Display-time calculations are not claimed
as permanent pregame records; existing committed, price-backed forward records
and paper performance remain separate and unchanged.

Unpriced combinations use two or three distinct fixtures and reject shared
teams. They show individual estimates and logical joint bounds, never a silently
multiplied probability. For marginals `p1 ... pn`, the all-win range is
`max(0, sum(p)-n+1) ... min(p)`. Reciprocal endpoints imply a fair-odds range;
a zero probability lower bound has no finite upper fair-odds bound. These are
conditional mathematical bounds, not calibrated probability intervals or an
accepted combined ticket. Cross-game and cross-sport dependence remains unknown.
Priced research keeps every existing Ontario, expiry, evidence and approval gate.

## Reproducible NBA and MLB historical challengers

`python -m intelligence.team_rating --history-dir data/research/history --output work/team-sport-evaluation.json`

This uses the existing licence-manifest/hash-checked archives, without downloads.
NBA has a bounded score-margin Elo update; MLB has a win/loss Elo update. Whole
dates are forecast before any same-day updates. Initial 60% of dates warm up the
model; next 20% select temperature; final 20% test. Each incumbent is calibrated
on the same earlier calibration dates and compared on a common supported cohort.
The training-prevalence baseline never uses test outcomes. Test-period earlier
dates can update later features; the calibrator is frozen. Reports include binary
Brier, log loss, calibration bins, ECE and date-block bootstrap intervals.

Observed archive tests:

| Sport | Test games | Existing model Brier | Challenger Brier | Challenger log loss | Paired Brier difference 95% interval |
| --- | ---: | ---: | ---: | ---: | --- |
| NBA | 701 | 0.20461 | 0.20602 | 0.59853 | -0.00357 to +0.00689 |
| MLB | 1,494 | 0.24844 | 0.24662 | 0.68621 | -0.00534 to +0.00201 |

Both intervals include zero: neither establishes a credible improvement. No
incumbent is replaced or model approved. These dates were previously inspected
in the project, so they are not a new independent prospective confirmation.
Archive availability/correction timing and cross-day dependence are unresolved.

NBA data still ends June 2015; MLB ends September 2025. Their genuine historical
models do **not** authorize current forecasts. Current permitted results, exact
fixtures, matching calibrated inputs and model review remain required. No player,
injury, pitcher, lineup or live data is fabricated. The UI explains these gaps.

## Hosted diagnostics

The owner-authorized private diagnostics can read Supabase and query the
documented non-billable `/v4/sports` account metadata without collecting odds or
results. They do not change holds, budgets or activation. The active hold is a
persistent operator gate, separate from daily usage; midnight/key rotation does
not clear it. Worker manual authorization is a separate configuration gate.
Actual hosted reports stay in private Actions, not this public repository.
