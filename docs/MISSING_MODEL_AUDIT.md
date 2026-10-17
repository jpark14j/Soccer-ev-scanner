# Missing forecasts: audit and focused model selection

2026-10-16 · development baseline `06b3f57` · no production changes.

| Cause | Finding | Resolution / remaining constraint |
| --- | --- | --- |
| Missing soccer features | Default `load_soccer` has no licensed local history; personal-only football-data downloads are intentionally disabled | Add a publisher-CC0 outcome source, not enable the restricted personal feed |
| Missing deployment files | NBA/MLB history and evaluation artifacts live under ignored `data/` | Package a portable focused fitted-state/evaluation artifact; never require a developer's private disk |
| Old history | NBA ends 2015 and MLB 2025; current results accumulated locally are far below training needs | Keep old research separate; do not call it current team/player context |
| Unsupported markets | Player logs, availability, lines/period settlement and market-specific evaluation are absent | Start with Premier League BTTS and exactly 2.5-goal totals |
| Inference requirements | Prior models need league/team sample sizes and exact aliases; missing inputs legitimately return no forecast | Add explicit contracts, exact aliases and per-quote reason codes |
| Calibration | Old advanced score forecasts have full 0–1 envelopes; no new soccer calibration artifact was deployed | Fit calibration on its own earlier season and evaluate on a later season |
| Validation / approval | No reviewed champion; no timely historical market comparison, independent confirmation or joint validation | Preserve every publication gate; display only accurately labeled research forecasts |

The chosen public source is `openfootball/football.json`, pinned revision
`e6744429ee395bc86f247348c6184bb08d4eb361`. Its README explicitly dedicates the
schema, **data** and scripts to the public domain; `LICENSE.md` contains CC0 1.0.
This is the publisher's grant, not blanket third-party rights clearance or league
endorsement. Source URLs, retrieval time and content hashes accompany artifacts.

Audited EPL seasons 2020–21 through 2024–25 each have 380 completed records.
2025–26 has only 353; 2026–27 has 45 through September 20, with fifteen past fixtures
missing scores: five in September and ten on October 10–12. Upstream `openfootball/england` has the same gap;
the checked current CSV mirror path is unavailable. A generated-file update date
does not establish current source scores. Postponements and missing scores are
unknown, never inferred results. Recent unresolved fixtures must block affected
teams' current forecasts, not silently become zeros or disappear from coverage.

Initial method: exponentially weighted, shrunk team scoring/conceding strengths
and league home/away scoring rates, with Poisson goal-count assumptions. Use only
prior dates, explicit minimum team support and observed final scores; no odds,
injuries, xG or lineup guesses. BTTS and a fixed 2.5-goal threshold are the two
evaluated outcomes; their distributions are not a validated parlay joint model.

The policy in `config/epl_forecast_policy.json` fixes training through June 2023,
calibration in 2023–24 and untouched-for-this-fit scoring in 2024–25, before
computing diagnostics. Older project research may overlap these archive periods;
these are exploratory out-of-sample diagnostics, not fresh independent approval
evidence. Walk-forward refits may use earlier settled dates, never same/future
dates. Calibration parameters/bins stay frozen during test scoring. Report simple
baselines, binary Brier/log loss, accuracy and sample sizes, calibration and UTC-day
block-bootstrap intervals. No historical prices means no betting ROI/P&L.

Current free-account results APIs may provide an alternative, but require a
credential and review of access/data terms. None was signed up for or enabled.
The existing Ontario odds cap and `PAID_ANALYST_APPROVED = "0"` remain unchanged.
