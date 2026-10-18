# Current statistical research increment

The existing five-page application and betting approval rules are preserved.
No Odds API request, paid AI call, provider-hold release or recurring activation
is part of this increment. Raw downloaded datasets remain private.

## What is available

- Bundesliga: OpenLigaDB's complete 2025–26 season reconciles all 294 previously
  scored fixtures and supplies exactly 12 missing scores. A fresh full 2026–27
  schedule supplies current results and exact UTC kickoffs. Unknown identities,
  mismatched dates/scores, missing fixtures and ambiguous result periods fail
  closed. Only `After90Minutes` finals enter soccer features.
- NBA: four publisher-licensed BoxScoreLab regular-season CSVs, 2022–23 through
  2025–26, contain 4,920 games before ten games without a unique home designation
  are excluded. All reciprocal scores, season counts and team identities are
  checked. The 4,910 retained games do not replace the old archive.
- MLB: the preserved Retrosheet archive has 7,276 usable 2023–25 games after its
  existing tie/suspended-game exclusions. It has no 2026 coverage. A full-season
  2025 evaluation is now available; it cannot authorize a current 2026 forecast.

Sources and permissions: [OpenLigaDB](https://www.openligadb.de/) publishes API
results under [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
The dashboard attributes it and offers its normalized source subset separately
from private models, ledgers and other history. [BoxScoreLab downloads](https://boxscorelab.com/downloads/)
state CC BY 4.0; attribution accompanies the NBA report. Retrosheet's existing
[notice](https://www.retrosheet.org/notice.txt) is retained. Publisher permission
does not establish league endorsement or blanket third-party clearance.

Football-data.co.uk currently excludes commercial/AI-training use and was not
used for these updates. The tested SportScore public feed returned an overdue
Arsenal fixture and far-future Celtics fixtures, so it was not used to activate
forecasts. EPL OpenLigaDB data was incomplete; its 2025 endpoint was empty.
Ligue 1 current full-season results remain unavailable in the prepared sources.
BALLDONTLIE documents free authenticated NBA/MLB Games endpoints and ML use in
its terms; no new account, trial, subscription or request was activated here.

## Reproducible model evidence

The offline commands are `python -m intelligence.recent_nba --bundle <private
source folder> --output research_assets/recent_nba.json` and `python -m
intelligence.recent_mlb --history-dir <existing licensed archive> --output
research_assets/recent_mlb.json`. Reports contain source hashes, code hashes,
whole-season partitions, calibration samples, Brier/log loss, reliability bins
and day-block bootstrap intervals. They contain no invented pregame records.

NBA warms on 2022–24, calibrates on 2024–25, and tests on 1,225 eligible 2025–26
games. Brier is 0.208554 versus a simple baseline's 0.247109 and the existing
model's 0.209915. The paired Brier difference interval includes zero: no model
replacement or approval is justified. The first 14 days have only 102 games;
current fixture and offseason-readiness requirements remain unresolved.

MLB warms on 2023, calibrates on 2024 and tests on 2,426 2025 games. Brier is
0.243727 versus simple baseline 0.248639. On 2,414 common test games, the paired
Brier difference from the existing model is -0.003237 (day-block 95% interval
-0.005882 to -0.000344). This is a retrospective comparison on archive dates
previously examined in the project, not independent prospective confirmation,
a market comparison or evidence of profitable betting.

Bundesliga coherent score research retains the competition's frozen venue-model
parameters. The only score-temperature selection uses 2023–24 score likelihood
on a fixed .85/1/1.15 grid (selected 1.0). The 2025–26 test has 290 eligible games;
16 games lack sufficient prior team samples. Exact score masks evaluate four
fixed two/three-leg tasks. Home-win + over 2.5 Brier is 0.189260 versus baseline
0.208265; away-win + over 2.5 is 0.169373 versus 0.189725. Three-leg results are
mixed and show little or no improvement. All models remain unapproved.

## Current forecasts and combinations

Home and Best Picks & Parlays read saved verified inputs and look ahead seven
days. No training or sports-provider retrieval runs on page load. Ordinary sport
and leg-count filters apply. Current Bundesliga binary estimates use unchanged
frozen calibration. The SGP section uses one coherent score distribution for
both leg estimates and joint score-cell sums. It never multiplies calibrated
marginals. Fair decimal odds are 1/model probability, not sportsbook quotes.

An SGP inspection candidate needs at least 50 earlier calibration-bin cases,
100 calibration/test cases and an envelope width no greater than .5. These are
research display checks, not betting approval. The UI ranks evidence-qualified
candidates by model probability within each leg count and explains uncertainty
and weak baseline performance. No executable ticket, EV or positive edge is
claimed. Cross-game/mixed-sport combinations retain logical joint bounds only;
no unsupported point probability is filled in.

A current-source snapshot expires after six hours. Today's reported finals are
withheld entirely from model inputs because source update timestamps lack a
verified offset; no timezone or same-day feature is invented. A fresh observation
is required after the UTC date changes. Other unresolved/overdue games remain
blocking. Current NBA/MLB and unsupported competitions remain explicitly blocked.

## Private, hold-preserving import and forward records

`python -m intelligence.statistics_import --bundle <prepared private files>
--publish-prepared` requires an already bootstrapped expected store and an active
provider hold. It performs only Supabase I/O: all statistics files must already
exist and match their fixed source URLs and checksums. It acquires the existing
fenced writer lease, preserves previous ledgers, model backups, local budgets and
recovery holds, records eligible forecasts before kickoff, checkpoints, then
independently restores and verifies the hosted head. It never initializes a new
remote store. No writer key belongs in the preview.

New append-only `statistics_forecasts` and `statistics_outcomes` tables distinguish
unpriced forward research from historical tests and published betting picks.
No missed pregame forecast is reconstructed. Outcome reconciliation requires an
exact fixture, originally recorded kickoff and verified regulation final. These
records have no assumed stake, price, monetary profit or ROI. The Performance
Tracker shows their separate counts. Import failures leave the last committed
snapshot intact. A stale prepared current-source file is rejected.

A one-off private Actions import and a read-only preview browser check can verify
this increment without enabling the existing worker or schedule. This is not a
claim of unattended refresh: recurring flags remain zero, and external free-tier
access still needs configuration before NBA/MLB current inputs can be collected.
