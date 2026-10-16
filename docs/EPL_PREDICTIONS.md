# Focused prediction models and preview testing

2026-10-16. Existing app, development branch, Draft PR #1 only. No paid AI,
subscriptions, odds budget increases or production deployment changes.

## What now works

`epl-goal-strength-1` produces calibrated **research** probabilities for Premier
League BTTS Yes/No and Over/Under **exactly 2.5** goals, provided its current-input
gates pass. It does not cover match winners, other goal lines, players, NBA or MLB.
The existing sport/market modules and recommendation gates are preserved.

The model uses exponentially weighted team goals scored/conceded, shrunk toward
league averages, and separate league home/away scoring rates. The fixed half-life
is 180 days and prior weight 15 games. Minimum support: 200 league games, 12 team
games and 8 effective weighted games. These choices were fixed in
[`epl_forecast_policy.json`](../config/epl_forecast_policy.json) before this run.
Poisson goal counts and independent home/away scores are **model assumptions**,
not proven relationships or a validated parlay distribution. Injuries, xG,
lineups, player availability and historical prices are not inputs.

The checked-in [`model.json`](../research_assets/epl/model.json) contains fitted
team state, source hashes, sample counts, calibration and genuine evaluation.
It makes inference independent of ignored local `data/` files. Source/code/policy
or artifact mismatches fail closed. This is a research artifact, not an approved
champion; fitting/calibration alone does not establish predictive reliability.

## Genuine chronological results

Training: completed 2020–21 through 2022–23 results. Calibration: 2023–24, 363
eligible of 380 matches. Test: 2024–25, 368 eligible of 380. Exclusions reflect
team-history requirements and are reported; the denominators are not all fixtures.
Features refit using only prior UTC dates, including earlier test outcomes as
they become available. Same/future-date results never enter pregame features.
Monotone Platt calibration is fitted on the calibration season only, frozen for
testing. Archive publication/correction times are unavailable: date ordering
does not prove historical price tradability or real-time source availability.

| Market, positive class | Test n | Binary Brier | Constant baseline | League Poisson baseline | Log loss | Classification accuracy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BTTS Yes | 368 | 0.248816 | 0.247289 | 0.247867 | 0.691345 | 56.79% |
| Over 2.5 | 368 | 0.250114 | 0.250481 | 0.245515 | 0.694373 | 57.07% |

Lower Brier/log loss is better. Binary Brier is `(p − outcome)²`, not the older
two-class sum. The constant baseline uses the calibration-season positive rate;
the league Poisson baseline uses prior-date league rates. Both use exactly the
same eligible test matches as the model.

95% UTC-day block-bootstrap Brier intervals: BTTS **[0.234299, 0.264207]**; totals
**[0.235571, 0.264929]**. Model-minus-constant Brier differences: BTTS +0.001527
**[−0.002760, +0.006530]**; totals −0.000366 **[−0.005267, +0.004997]**. Both include
zero. Classification intervals: BTTS **[51.27%, 61.89%]**; totals **[52.50%, 61.48%]**.
No meaningful advantage over simple baselines is established. Totals also scores
worse than league-only Poisson on this test. These outcomes are reported as found;
hyperparameters were not retuned after seeing them.

The artifact includes full log-loss/baseline intervals, paired differences, ten
reliability bins, ECE and sample sizes. The 1,000 bootstrap resamples use 109 UTC
day blocks and a fixed seed. Exchangeable independent day blocks and stationarity
remain assumptions; between-day dependence is not established. Calibration-bin
Wilson envelopes describe historical outcome frequencies, not event-specific
confidence. Buckets below 50 observations use a full 0–1 envelope.

Later-period monitoring covers 373 eligible matches, August 2025–September 2026,
with **partial coverage**. Brier: BTTS 0.236332; totals 0.243938. ECE changes from
0.056144 to 0.011902 for BTTS and 0.083074 to 0.041937 for totals. Missing scores
and eligibility exclusions can bias these diagnostics. They do not establish
absence of drift or ongoing live reliability. Reused archive periods from earlier
project research also prevent calling this independent fresh confirmation.

**No model meets existing approval standards.** No timestamped historical market
baseline, genuinely independent confirmation, accepted-ticket evidence or reviewed
activation exists. No historical betting ROI, P&L or profitability is calculated.

## Current source and the remaining blocker

Source: [openfootball/football.json](https://github.com/openfootball/football.json),
pinned revision `e6744429ee395bc86f247348c6184bb08d4eb361`. The publisher README
dedicates its data, schema and scripts to the public domain; LICENSE.md is CC0
1.0. This is the publisher's grant, not league endorsement or clearance of every
possible third-party right. See the pinned URLs and SHA-256 values in
[`epl_source_snapshot.json`](../config/epl_source_snapshot.json). No commercial
redistribution permission is assumed for The Odds API or other existing feeds.

2,298 completed results were imported: five complete 380-game seasons, 353 results
in 2025–26, and 45 in 2026–27. The live public refresh checked October 16 still
ends **September 20**, with **15 past fixtures missing scores**: five in September
and ten October 10–12 fixtures. Upstream
Football.TXT has the same gap. Fresh file generation is not fresh result coverage.
No results, postponed status or missing statistics are inferred.

The app checks the public license and current-season JSON at most once per rolling
24 hours per shared local database (at most two public GETs; no API key). It caches
failures too and uses a fetch lease. `EPL_PUBLIC_REFRESH = "0"` disables this.
An upstream license/schema change or revision/removal of an existing result blocks
forecasts pending review. Added completed prior-date results update feature state;
the historical calibrator and report remain frozen. Freshness is based on result
dates, never download times. Network failure cannot make old data current.

A forecast requires current Ontario odds, a supported exact market, explicitly
matched teams and source fixture/date, sufficient history, no unresolved earlier
current-season team fixtures, and source results no older than 21 days. Current
public data fails these gates. **The preview is not expected to produce actual
current EPL probabilities yet.** An updated complete permitted result source is
needed; no current-results account was created. NBA 2015/MLB 2025 archives also
lack adequate current inputs; their portable current models remain unimplemented.

## What the dashboard will show

Research forecasts, when inputs pass, show model version, actual prediction time,
feature history date and sample, calibrated estimate, frequency envelope,
calibration/test sample and sportsbook break-even probability separately. Every
unsupported or rejected forecast has a reason. Research probability is not approved
true probability and does not enable betting EV or recommendation publication.

The high-probability shortlist requires probability ≥65%, envelope lower bound
≥60%, width ≤25%, calibration support ≥50, current prices **and independent
reliability evidence**. That evidence is currently absent; the shortlist is empty.
The current model does not automatically earn it through a calibration flag.
Future evidence requires explicit model-review/inference integration; manually
editing a JSON flag is not approval. High probability is not positive EV.

Parlay research still detects contradictions/dependencies. These exploratory
single models do **not** validate joint parlay probabilities. No multiplication
of leg probabilities, executable odds product or parlay EV is enabled.

## Paper records and durability

Only genuine current pregame forecasts from an actual scan are appended to the
immutable private shadow ledger, with actual recording time and source/code/data
hashes. Refreshing a page does not backdate or rewrite them. A later exact team/date
match to public full-time results can append a **source-target hit/miss**, never
operator settlement or betting returns. Immutable paper results show per sport,
market and model sample counts, hits, misses, hit rates, Brier, log loss and
reliability bins. Overlapping observations are dependent, not independent trials.

Backtests stay in the versioned artifact. Paper forecasts stay in shadow tables.
Published hypothetical forward decisions remain in the existing separate ledger.
**No actual wagers are imported or placed, and no actual-wager record is claimed.**
Community Cloud disk persistence across redeploy/reboot is unverified. Existing
private backup/restore guidance still applies; no permanent commercial performance
record can be promised without verified durable off-host storage.

## Reproduce without paying

Use the existing virtual environment / installed requirements and run:

```bash
python -m intelligence.cli evaluate-epl --cache-directory work/prediction --download
python -m pytest -q
```

The first command downloads eight public pinned files (license plus seven seasons),
verifies reviewed hashes, rebuilds the artifact and prints real diagnostics. It
does not call an odds, OpenAI or subscription API. Removing `--download` reuses
local verified files. Do not use the current fitted state for past events: historical
evaluation refits prior-date state separately. Hyperparameter changes need a new
version, new evaluation and fresh independent evidence before approval.

## Test your separate Streamlit preview

1. Open [the existing preview](https://soccer-ev-scanner-preview-jp.streamlit.app/).
   Its source must remain repository `jpark14j/Soccer-ev-scanner`, branch
   `development/verified-sports-intelligence`, entrypoint `app.py`. Do not change
   the production app or main branch. Community Cloud normally rebuilds this preview
   when its branch changes; if it is sleeping, wake it. If it has not rebuilt, use
   **Manage app → Reboot app** on this preview only.
2. Leave `PAID_ANALYST_APPROVED = "0"`, the existing odds credit cap, provider key
   and all production secrets unchanged. No new key or account is required for the
   public-source model. Never paste keys into chat or GitHub.
3. On **AI Dashboard**, read **Data & Model Health** for source dates and missing
   inputs. Open **Performance Tracker → Held-out model evaluations → Premier League
   calibrated BTTS / goals 2.5** for the model version and 363/368 calibration/test
   counts. Use the sport filters on Best Picks & Parlays to inspect existing data.
4. Press **Refresh analysis** once. It honors the existing odds cache/credit cap;
   it cannot force paid requests or renew old quote timestamps. If the cap is spent
   or prices are older than five minutes, no current quote is fabricated.
5. Open **Best Picks & Parlays → Singles**, or **Settings & Research Tools → Research
   tool → Soccer Analytics** for the detailed model view. BTTS or exactly 2.5-goal
   totals can be modeled once the permitted source catches up and fresh market
   quotes exist. Until then, inspect the explicit stale-result / unresolved-fixture
   reasons. Match-winner cards are outside this focused model, not missing silently.
6. Open **Performance Tracker → Held-out model evaluations → Premier League
   calibrated BTTS / goals 2.5** for full historical metrics, intervals and calibration
   bins. **Prospective paper research** shows actual paper records, not backfilled successes.
7. Open **Best Picks & Parlays → Parlays** and **Settings & Research Tools → Research
   tool → AI Assistant** to check existing behavior.
   Parlays remain theoretical and local assistant mode remains free. Raw odds remain
   collapsed. No current predictions or profitable selections should be forced.

Local server startup and Streamlit AppTest interactions are verified separately
from the hosted service. Access to this Community Cloud URL is blocked by this
execution environment's proxy; its rebuilt UI has not been remotely verified here.
