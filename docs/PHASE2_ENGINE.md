# Phase 2: multi-competition data and research models

October 16, 2026, Ontario. Existing app/branch/PR only. No paid API, account,
subscription, odds budget increase, production change or model approval.

## Implemented coverage

| Dataset | Genuine completed results imported | Latest result | Current readiness |
| --- | ---: | --- | --- |
| Premier League | 2,298 | 2026-09-20 | 15 earlier unscored fixtures; frozen EPL model unchanged |
| Bundesliga | 1,857 | 2026-09-20 | 12 earlier unscored fixtures; current inference blocked |
| La Liga | 2,319 | 2026-09-20 | 15 earlier unscored fixtures; no new model |
| Serie A | 2,284 | 2026-09-20 | 10 earlier unscored fixtures; no new model |
| Ligue 1 | 2,075 | 2026-09-20 | 13 earlier unscored fixtures; current inference blocked |
| NBA archive | 3,940 | 2015-06-16 | Historical research only; not current-season features |
| MLB archive | 7,276 | 2025-09-28 | Historical research only; current pitching/availability inputs missing |

Soccer covers seven pinned seasons, 2020–21 to 2026–27, including explicitly
incomplete recent seasons. Bundesliga has five complete historical seasons;
Ligue 1 has five, with its 20-to-18-club change accounted for. La Liga/Serie A
have complete 2020–21 through 2023–24, but ten scores missing in 2024–25. The
[audit and model selection](PHASE2_DATA_AUDIT.md) preceded model evaluation.

The new public adapters actually retrieved current Bundesliga and Ligue 1 files,
verified the publisher license hash, and recorded source timestamps/hashes. They
still contain only the September results above. This verifies **source receipt**,
not adequate current coverage or independently checked score accuracy. Same-day
unscored fixtures are not classified as missing completed results. No old gap was
interpolated or filled from an unlicensed site.

Portuguese Primeira Liga, Eredivisie, MLS, UEFA Champions/Europa/Conference leagues,
World Cup/qualifiers, Euro, Nations League, Copa América and AFCON have registry
identities for future discovery. **Registry targets are not imported datasets,
confirmed provider keys, complete market coverage or working models.** Existing
documented Odds API competitions remain available; no speculative key is requested.

## Data architecture and provenance

`competitions.py` defines stable competition IDs, kinds and expected season sizes.
`config/team_aliases.json` contains explicit source/feed spellings; no fuzzy
matching, generic suffix stripping or generative entity mapping occurs. Stable
country/club IDs link reviewed spellings within a competition. Cross-country,
club/national-team or ambiguous identities are never guessed. Archive NBA/MLB
codes without a reviewed current-franchise mapping remain archive-only IDs.

`event_data.py` stores immutable event observations and data snapshots in the
existing SQLite architecture. Records retain source/event/competition/team IDs,
scores/status, calendar date versus verified kickoff precision, source receipt,
available source-update time, target scope and license reference. Dates are not
silently converted to invented kickoff times. Domestic soccer pairs reconcile
within a season; NBA/MLB/cup cross-provider IDs need explicit bindings, particularly
for doubleheaders. An uncertain binding never becomes a merged game.

Duplicate fixtures, unknown aliases, malformed/future scores and invalid provenance
fail contract checks. Completeness needs expected teams and distinct home/away
pair coverage, not just a matching row count. Conflicting completed scores, scope,
date changes or withdrawn results remain visible; no latest-score overwrite is
used to make inference eligible. Incremental updates append observations. Existing
NBA/MLB result histories now exclude conflicting event versions rather than silently
selecting a corrected score. Historical software/evaluation functions are retained.

`data_adapters.py` normalizes verified pinned OpenFootball files, existing licensed
NBA/MLB archives and **already collected** provider finals. The provider bridge
makes no requests and does not add credit costs. The workspace had no collected
current provider finals at verification time; the bridge is software-tested with
synthetic source contracts, not claimed as a complete live feed.

`pregame_features` exposes only unconflicted results actually observed by the
requested cutoff, with prior-date form/rest proxies and sample counts. It cannot
backdate a newly downloaded archive into earlier live availability. Archival model
testing is separately labeled: prior dates are used, but original publication and
revision timing cannot be proven. Verified xG, injuries, lineups, player minutes,
pitchers, bullpen, weather and park features remain unavailable.

Source files and normalized private ledgers stay under ignored `work/`/`data/`.
Portable derived fitted states, coverage reports, reviewed aliases, source hashes
and evaluation evidence are versioned. Publisher license permission is not blanket
league endorsement or clearance of third-party rights. Commercial sportsbook
redistribution remains subject to the user's actual provider license.

## Expanded models and actual evaluation

`venue-goals-1` fits each league's own home/away team scoring and conceding strengths,
shrunk to that league's home/away rates. A 365-day half-life and 12-game venue prior
were fixed before evaluation, with 300 league / 16 team / 10 effective team-game
minimums. These are new competition-local fits, not transferred EPL parameters.
Independent Poisson score counts remain an explicit assumption, not a validated
joint parlay distribution. Only the following targets were evaluated:

| New target | Calibration n | Validation n | Final-test n | Binary Brier | Constant baseline | League Poisson baseline | Log loss | Classification accuracy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Bundesliga BTTS Yes/No | 306 | 275 | 275 | 0.241399 | 0.243400 | 0.245258 | 0.675782 | 58.18% |
| Ligue 1 Over/Under 2.5 | 333 | 290 | 306 | 0.242145 | 0.246914 | 0.247484 | 0.677027 | 54.25% |

Train through June 2022; monotone Platt calibration on 2022–23 only; validation
diagnostics in 2023–24; locked final scoring in 2024–25. Goal-strength features
refit using only earlier dates, including earlier test outcomes after their date.
No same/future-day score enters features. Calibration and hyperparameters remain
frozen. No model was selected/retuned based on validation/final-test performance.
Team/promoted-club exclusions and genuine denominators are recorded separately
from complete raw fixture totals; 306 raw test matches is not always 306 forecasts.

Binary Brier is `(p − outcome)²`; smaller Brier/log loss is better. The constant
baseline uses calibration-period prevalence; league Poisson uses preceding-date
league rates. All comparisons use identical eligible events. Genuine 95% UTC-day
block-bootstrap intervals (1,000 resamples, fixed seed) are:

- Bundesliga Brier **[0.231373, 0.251992]**; model-minus-constant **−0.002001
  [−0.004468, +0.000407]**; accuracy **[52.72%, 63.47%]** (94 test day blocks).
- Ligue 1 Brier **[0.233265, 0.250918]**; model-minus-constant **−0.004768
  [−0.010050, +0.000195]**; accuracy **[48.30%, 60.31%]** (100 test day blocks).

Both improvement intervals include zero. There is **no established independently
confirmed forecasting advantage or betting edge**. Historical classification
accuracy is not betting win rate, accepted-ticket performance or profitability.
There are no timestamped historical sportsbook lines/prices, market-implied
baseline, betting ROI or P&L. Day-block bootstrap assumes exchangeable independent
days; cross-day dependence and stationarity are unverified.

Final-test calibration ECE: Bundesliga 0.011752; Ligue 1 0.048831. Ten bins, bin
sample counts, calibration-frequency envelopes, all baseline/log-loss intervals
and later partial-season drift diagnostics are in the artifacts. Later monitoring
has 305 Bundesliga / 302 Ligue 1 eligible events, with incomplete outcome coverage;
it cannot prove an absence of drift. Frozen ≥65% forecast subsets have only **1**
and **13** test events respectively; their reported uncertainty is a full 0–1
envelope. They do not validate a high-probability shortlist.

The EPL `epl-goal-strength-1` source files, code, policy and original 363/368
calibration/test artifact are unchanged. No new 1X2, NBA, MLB or player-prop model
is claimed. NBA/MLB histories older than 90 days are now blocked in the current
pipeline; their older historical diagnostics remain accessible.

## Model stages, current inference and parlays

Software verification is the technical test/compile/CI record. A **research model**
has reproducible evaluated forecasts but lacks independent approval. **Validated
forecasting model** additionally needs reviewed reliability/calibration evidence.
**Betting-edge approved** additionally needs independent relevant market evidence,
reviewed activation and operational safeguards. These stages are separate; a
calibration fit or passing software tests never promotes a model. Current expanded
reports have `forecast_validated=false`, `edge_approved=false`; every returned
Estimate remains unvalidated and the existing recommendation gates remain intact.

Fresh Ontario supported-market quotes route to the correct competition artifact
before the legacy missing-history path. Inference checks exact aliases and fixture
date, source/individual-team freshness (21 days), unresolved earlier team fixtures,
sample support, source conflicts and artifact/code/market scope. Earlier fitted
state cannot be used for backdated events. Current public updates change feature
state only after reviewed-score preservation checks; historical calibration and
test results remain frozen. Unknown aliases, license/schema changes, source score
revisions/withdrawals or conflicts block forecasts pending explicit review.

**No current genuine pregame forecast is claimed from this phase's available
inputs.** Bundesliga/Ligue 1 public files remain stale/incomplete and Ontario odds
were not refreshed past the spent cap. Complete synthetic inputs test the actual
inference integration; these are software fixtures, not published opportunities.

Research estimates show model/version, probability, calibration envelope/sample,
history end, source check, comparison break-even price and blockers. They never
enable betting EV. Dependency descriptors preserve event, team and competition
groups, with `joint_validated=false`. Existing contradiction/correlation checks
remain; different competitions do not establish independence. No multiplication
of leg probabilities, actual combined price, parlay EV or approved parlay is added.

Only genuine current pregame scan outputs append immutable private forecasts.
Exact later source-reported full-time results can append paper hits/misses; no
backdating, outcome rewriting, operator settlement or accepted-wager claim occurs.
Source-target paper, historical tests and published hypothetical records remain
separate. Public result updates do not silently retrain or promote models.

## Free sources, credentials and request budgets

The [publisher's OpenFootball documentation](https://github.com/openfootball/football.json)
provides account-free JSON and CC0 dedication, while warning that upstream results
are not automatically current. The [existing source-readiness review](FREE_RESULTS_READINESS.md)
documents unavailable or unverified alternatives; no unauthorized website scraping,
paywall bypass, unregistered account or paid endpoint is used.

NBA archive attribution: FiveThirtyEight, CC BY 4.0, game information credited by
publisher to Basketball-Reference; modified home-game score-only subset. MLB
Retrosheet permission requires attribution, retained prominently in the application
footer and metadata; [publisher notice](https://www.retrosheet.org/notice.txt).
Neither archive supplies current team/player/starting-pitcher information.

Two potential free accounts could materially help later, but neither was created:

- [Football-data.org](https://www.football-data.org/pricing): free delayed fixtures/
  scores for major soccer competitions; needs an account/token and rights review.
  Exact current/historical gap coverage still needs a contract test.
- [BALLDONTLIE NBA](https://nba.balldontlie.io/): documented free teams, player
  identities and games, with an API key and 5 requests/minute. Player game stats,
  injuries/lineups and advanced metrics are not in that free tier. Check commercial
  terms; do not enroll in a paid plan or payment-method trial. No key is requested
  in chat and no adapter was activated without credentials/rights verification.

Official MLB endpoints' commercial reuse permission remains unverified; no new
integration is enabled. Retrosheet remains the vetted historical option.

The existing **nine-credit odds cap** and paid-AI settings are unchanged. Legacy direct-provider/non-autonomous default values now also use nine (previously
16), closing an inconsistent unconfigured CLI path; no configured cap was raised.
New current-result retrieval has its own hard **six HTTP attempts per UTC day per
shared store**, including failures, no retries, fixed source allowlist, license
hash verification, bounded payloads, fetch leases and 24-hour success/failure
caching. License checks share the same cache across leagues. Existing frozen EPL
refresh retains its separate at-most-two GETs/day behavior: at most **eight**
automatic public requests combined, never eight odds credits. Navigation/filter
changes still reuse session snapshots and make no provider request.

An **explicit one-off archive import** may download at most 36 reviewed pinned
files (license + seven seasons × five leagues), sequentially at a minimum 250 ms
between new downloads, no retries, with hashes and cache reuse. It is never called
by UI rendering or scheduled automatic analysis. This phase needed 28 extra archive
GETs (EPL/license reused), three live public GETs, zero odds requests and zero paid
AI requests. Existing odds usage stayed 9/9; local public HTTP counts are separate.

Community Cloud is not continuous processing. Existing disabled-by-default worker,
CLI backup and durability attestations remain the optional scheduling path: use a
private persistent shared store and an explicitly configured free local scheduler
only after rights/durability review. A new ephemeral runner cannot recreate old
provider results or permanently preserve research. No scheduling, production
workflow or automatic training deployment was enabled.

## Reproduce and test your preview

```bash
python -m intelligence.cli import-multi-history --directory work/phase2/source --download
python -m intelligence.cli evaluate-expanded --league Bundesliga --directory work/phase2/source
python -m intelligence.cli evaluate-expanded --league "Ligue 1" --directory work/phase2/source
python -m pytest -q
```

The explicit import downloads only reviewed public pinned files; omit `--download`
to reuse them. Raw files/normalized ledger are private and ignored. Do not tune the
published policy against this final test; a challenger needs a new version, locked
period and independently reviewed evidence before any promotion.

1. Open [your existing preview](https://soccer-ev-scanner-preview-jp.streamlit.app/)
   after its development-branch rebuild. If necessary reboot **this preview only**,
   using its Manage app menu. Keep `app.py`, production, Secrets and the cap unchanged.
2. **AI Dashboard → Data & Model Health → Model, source and coverage diagnostics**
   shows ingested competitions, current gaps and targets without data. The extra
   models are research-only and stale scores must not produce picks.
3. **Best Picks & Parlays → Singles → Competition** selects Bundesliga or Ligue 1.
   Sport/book/market/evidence filters only inspect the current scan. An empty
   result or explicit blocker is correct; no quote is invented to fill a model.
4. **Performance Tracker → Held-out model evaluations** opens **Bundesliga · btts**
   and **Ligue 1 · totals_2.5**. Verify sample counts and final-test numbers above,
   separate from paper results. Frozen EPL evidence remains in its own expander.
5. For a detailed scan, change sidebar **Competitions** to the desired supported
   leagues and use **Refresh analysis** once when quota permits. This is an
   explicit capped request, unlike inspection filters. **Settings & Research Tools
   → Research tool → Advanced Markets** can explicitly request the relevant markets;
   do not increase the cap. Spent quota or stale cached prices legitimately block
   current research. No actual refreshed Ontario prices were verified this phase.
6. **Parlays** retains theoretical combinations, source prices, dependence warnings
   and missing joint/pricing requirements. **Settings & Research Tools** retains
   all advanced modules and the free local assistant. Exactly four top-level pages
   remain. No paid AI or new top-level competition pages were added.

Automated Streamlit interactions verify these paths locally. Hosted Community Cloud
rebuild/browser and real mobile rendering remain unverified from this environment.

The single next priority is a complete, permitted current-results feed reconciled
against fixtures for the three evaluated soccer leagues, followed by prospective
paper recording. Adding more models before resolving that bottleneck is lower value.
