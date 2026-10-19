# Saved predictions and accuracy

The same five pages and sidebar are retained. Home's existing three slots show
supported saved single, two-leg and three-leg predictions. Qualifying positive-EV
choices retain their original gates; otherwise a genuine, eligible experimental
forecast can fill the corresponding prediction slot, with an explicit unapproved
label and no invented sportsbook odds or EV. The original no-qualifying-positive-
EV message remains accurate when only experimental predictions are available.

**Find Best Bets Now** reloads saved research and opens Best Picks & Parlays. It
has no passcode, owner-code input, workflow dispatch, provider request or paid AI
request. In shared mode it invalidates the existing reader cache so the next app
run obtains the saved replica. A short session cooldown coalesces repeated clicks.
Old private dispatch controls remain protected in backend code but are not
exposed by the frontend. No credential, hold or quota setting is removed.

Source-based prediction cards display original values from an immutable pregame
record. The source receipt, exact fixture/kickoff/contract, model evidence,
probability and uncertainty must still match a currently eligible forecast.
Only floating-point roundoff up to 1e-12 is tolerated when matching; the original
stored probability is displayed. A changed forecast is withheld until a worker
has actually recorded it. Browsing never writes predictions or backfills them.

Performance Tracker has only these three primary metrics:

- Singles Accuracy (%).
- 2-Leg Parlay Accuracy (%).
- 3-Leg Parlay Accuracy (%).

Each metric shows correct / eligible settled predictions and pending counts.
There is no percentage when the denominator is empty: it shows **Not enough
results yet**. All-leg wins are required for a parlay win. Pending, void, partial,
unresolved, postgame, unverified and backtest records are excluded. Accuracy is
not a profitability or model-approval claim.

The first immutable pregame record per fixture/scheduled kickoff/model/exact selection is counted
once; repeat refresh snapshots do not increase the denominator. A rescheduled kickoff
is a separate prospective record; the unresolved original cannot suppress its
subsequently verified outcome. The report reads
the statistics ledger and eligible committed research publications. Legacy
publication preparations without a pregame shared commit receipt, quarantined
labels and ambiguous partial outcomes are excluded. Experimental and validated
counts remain distinguishable in one collapsed section. Historical records and
older backend financial logs are preserved; no financial metric is rendered on
Performance Tracker.

The approved background worker already retrieves verified results and settles
these pregame source contracts. Accuracy is calculated from its saved labels.
Performance Tracker now participates in the existing periodic saved-state check,
so a newly committed label appears without a provider request from the browser.
The schedule remains best-effort; there are currently no genuinely settled
forward outcomes, so live settlement success is not claimed. Deterministic
integration tests cover win/loss/pending results and duplicate refreshes.

Current coverage is unchanged: genuine Bundesliga source forecasts and coherent
experimental same-game combinations are available when their inputs pass.
EPL/Ligue 1 current reconciliation, NBA fixture/offseason readiness and permitted
2026 MLB results/fixtures remain blocked under the no-new-account constraints.
Historical models and all approval gates are preserved. Different-game or mixed-
sport probabilities are not manufactured; logical bounds remain separate from
validated joint forecasts. No new provider, service, key or subscription is used.
