# Phase 2 source audit and model selection

October 16, 2026 (Ontario). Baseline `6607ded`; development branch only.

The first audit found missing current inputs rather than a missing generic AI
algorithm. NBA's licensed research snapshot ends in 2015; MLB's Retrosheet archive
ends in 2025. Locally observed provider finals cover only a short window and cannot
reconstruct a season. Player availability, expected minutes, pitchers, bullpen,
weather, parks and historical market prices are unverified. Personal-only sources
remain disabled; no account, subscription or additional odds budget is authorized.

OpenFootball's publisher dedicates data to CC0. The reviewed pinned revision is
`e6744429ee395bc86f247348c6184bb08d4eb361`, unchanged from the EPL audit. This grant
is not league endorsement or blanket third-party rights clearance. We explicitly
downloaded 28 additional pinned public JSON files (four leagues × seven seasons),
reusing the seven EPL files and license already cached; no odds request was made.
Raw sources stay private/ignored. Source hashes make this archive reproducible.

| Competition | Complete historical seasons verified | 2024–25 scores / expected | 2025–26 scores | Current 2026–27 scores / past unresolved |
| --- | --- | --- | ---: | --- |
| Premier League | 2020–21 to 2024–25 | 380 / 380 | 353 | 45 / 15 |
| Bundesliga | 2020–21 to 2024–25 | 306 / 306 | 294 | 33 / 12 |
| La Liga | 2020–21 to 2023–24 | 370 / 380 | 365 | 64 / 15 |
| Serie A | 2020–21 to 2023–24 | 370 / 380 | 344 | 50 / 10 |
| Ligue 1 | 2020–21 to 2024–25 | 306 / 306 | 282 | 41 / 13 |

All five current result files end September 20. Fresh generated JSON timestamps
do not repair source scores; the publisher warns that upstream Football.TXT is not
automatically updated. Ligue 1 changed from 20 to 18 clubs starting 2023–24, so
expected totals must be season-specific. Unscored fixtures remain unresolved;
postponements and missing outcomes are never inferred. Unscored fixtures on the
current date (one in each non-EPL file) are not counted as past missing results.

Chosen new targets: **Bundesliga BTTS** and **Ligue 1 total goals 2.5**, because
both have complete calibration/validation/final-test seasons. A venue-specific,
shrunk, decayed Poisson method fits each competition's own scoring environment and
team home/away strengths. It does not transfer EPL fitted parameters. Policy,
periods and minimum samples in `config/expanded_model_policy.json` were set before
scoring. Train through June 2022, calibrate 2022–23, diagnose validation 2023–24,
and reserve 2024–25 as final test. No retuning after scores or model promotion.
These archives are exploratory research, not fresh independent betting evidence.

Other soccer competitions are discovery targets, not implemented model coverage.
Domestic/cup/national teams need distinct competition IDs, explicit team aliases,
score targets and coverage policies. Cross-league comparisons need genuine linking
matches and opponent/league effects; national teams additionally need roster and
infrequent-fixture handling. No pooled cross-league strengths or parlay independence
assumption will be introduced. Existing EPL model and historical report stay frozen.

The [free-results review](FREE_RESULTS_READINESS.md) still applies: OpenLigaDB
requires exact payload/coverage and ODbL obligations reviewed, football-data.org
requires a free account, TheSportsDB has separate development/production terms,
and Football-data.co.uk is not silently enabled for commercial training. Public
official league endpoints do not automatically supply commercial redistribution
rights. No new source is represented as a complete current-results service.
