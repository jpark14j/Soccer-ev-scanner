# Free statistics and positive-EV publication increment

The five existing pages and navigation are retained. The latest targeted
completion is documented in [Saved picks and accuracy](SAVED_PICKS_AND_ACCURACY.md).
Home retains three slots and can show genuine recorded experimental predictions,
explicitly unapproved, while qualifying positive-EV choices retain every model,
uncertainty, current-source, Ontario price and independent joint/ticket gate.
Experimental predictions never become approved bets merely by being displayed.
Apparent point-estimate edges above 50% remain withheld for independent review.

## Sources and coverage

Already reviewed sources are reused without requesting new accounts or keys:

* OpenLigaDB, ODbL 1.0: key-free Bundesliga full-season fixtures/results, exact
  reviewed IDs, regulation finals, prior-day score policy, six-hour freshness.
  Previous-season reconciliation repaired 12 genuinely missing results. EPL
  remains blocked by incomplete source coverage; Ligue 1 needs a reconciled
  current source. Other competitions are not silently substituted.
* BoxScoreLab, CC BY 4.0 publisher files: NBA regular seasons 2022–23 through
  2025–26; 4,910 reconciled games after explicit neutral-site exclusions. No
  verified key-free current fixture/availability feed is configured.
* Preserved permitted Retrosheet archive: MLB through 2025. A permitted key-free
  2026 archive and current fixtures are unavailable. Postseason probabilities
  cannot be inferred from a regular-season study.

Previously reviewed exclusions remain: football-data.co.uk currently prohibits
commercial/model-training uses; official MLB website terms do not establish
permission for the requested automated commercial use. A mirror's code licence
does not transfer rights to somebody else's sports feed. BALLDONTLIE is not used
because it needs a new account/key. No new signup is required by this increment.
See CURRENT_STATISTICS_RESEARCH.md for attribution and the earlier source audit.

## Additional offline score-model comparisons

`team_score_study.py` uses the existing permitted archives, without downloads.
NBA ridge score means use earlier rolling scored/conceded game averages and rest
days, with paired empirical score residuals. MLB compares conditional independent
Poisson and negative-binomial run grids with training-period dispersion.
These are game-score features, not possession efficiency, confirmed pitchers,
injuries, rosters or other unavailable statistics.
The explicit Retrosheet ATH/OAK franchise alias prevents the 2025 abbreviation
change from discarding early Athletics games. Original archives stay unchanged;
relocation and park effects are still unmodeled.

Whole dates are isolated. The earlier warm period is split into disjoint ridge
fit and residual periods. A subsequent season selects the predefined candidate
scale/distribution using single-task Brier score. The latest available season
evaluates moneyline, a fixed half-point total, and coherent 2/3-leg score events.
Joint events are intersections in the same score scenarios; marginal
probabilities are never multiplied. Fixed total lines are study targets, not
historically observed sportsbook offers. Non-tie conditioning is a limitation,
not a mechanistic overtime/extra-innings model.

The archive test seasons have been inspected by earlier project studies. This
comparison is retrospective, not new independent confirmation. Aggregate,
code/data-hash-bound reports include day-block intervals, Brier/log loss,
calibration bins and training-only constant baselines. No raw dataset is added
to the public repository, and no model is promoted or enabled for current games.
Existing frozen studies, assets and source manifests remain unchanged.

## Manual odds fallback

Best Picks & Parlays → “Compare a sportsbook price · optional research” accepts
an exact supported selection, a currently reviewed Ontario operator and a price
the user attests seeing now. A parlay requires the actual combined ticket price;
there is no individual-price multiplication. Prices expire after five minutes.

Entered observations are explicitly user-reported, not independently verified.
Conditional experimental model EV is a mathematical comparison only, never an
actionable positive-EV recommendation. Calibration frequency ranges are not
event-specific confidence intervals, so they do not create conservative EV.
Manual entry cannot change model approval, ticket restrictions, predictions,
provider provenance or the Home publication gate. A reviewed independent price
and ticket verification path would be required before such entries could be
published as verified opportunities.

Entries are bounded to 30 in the server session; JSON download retains the
user's copy. They are not written into the read-only shared replica and may
disappear on session loss/restart. They are separate from permanent pregame
forecast records and actual wagers. No wager is placed and no personal prose,
credentials or arbitrary model data are stored in the price export.

## Independent free automation

Activation status: **owner-approved and initial refresh verified**. The owner
explicitly approved the free-data activation on 2026-10-18 after the earlier
automatic approval block. The installed private
`.github/workflows/free_statistics_refresh.yml` is pinned to a reviewed full
development SHA; `proposals/` remains a non-executable reference copy.

The worker uses only existing Supabase credentials
and the already reviewed GitHub Actions allowance; no new account/key is needed.
The separate quote-free job is scheduled every four hours (UTC), plus manual
dispatch. It makes at most one fixed OpenLigaDB GET per run, no redirects or
automatic retries, two-MB response bound, 30-second request deadline, at least
three hours between successful refreshes (except across a UTC date boundary).
Six scheduled requests per day; GitHub scheduling is best-effort and can delay.
Runner time counts against the existing private Actions allowance; the included
allowance is finite and not a billing guarantee.

The initial background refresh in private run `39176130851` performed one
OpenLigaDB GET at 2026-10-18T23:21:21Z and saved Supabase generation 4. A fresh
hosted readback verified the original store identity, unchanged provider hold,
unchanged budgets and protected records. Seven experimental singles, three
eligible 2-leg SGPs and seven eligible 3-leg SGPs were generated. Seventeen new
pregame snapshots were saved before kickoff: 34 stored snapshots now represent
17 distinct decisions, with zero verified outcomes. None are approved bets.

The initial workflow's refresh step succeeded but its later browser harness
failed because checking out the public app removed the private helper. Browser
verification was separated into a read-only artifact-based job, without another
source request. Temporary push/browser triggers are removed after verification;
the recurring updater retains only scheduled/manual triggers. Actual scheduled
run `39182615790` on 2026-10-19 succeeded: it retained the fresh cached source,
used zero public/provider requests, and verified Supabase generation 6, the
recovered identity, active provider hold and unchanged budgets. The preceding
new-day refresh `39181163890` verified 54 completed Bundesliga results, zero
unresolved past fixtures, seven experimental singles, three 2-leg SGPs and seven
3-leg SGPs. There were 51 saved snapshots covering 17 distinct decisions and
zero verified outcomes. This proves those runs, not future availability or
profitable picks. GitHub cron remains best-effort.

The existing live-odds automatic worker/schedule and paid AI flags remain zero.
The held provider paths, nine-credit cap and remote reservations are untouched.
The job receives no Odds API, OpenAI or football-data.org token. It acquires the
existing fenced single-writer lease, checks the recovered store identity and
active provider hold, verifies frozen assets, and preserves protected records
and budgets. After validation it saves source snapshots, prospective forecasts,
verified outcomes and monitoring, then checks a fresh hosted readback.
It cannot initialize an empty store, release a hold or promote a model.
Failed collection/validation never replaces the committed successful snapshot.
Old inputs still expire; failed refreshes do not extend their freshness.

Repeated source refreshes do not increase the number of independent decisions:
monitoring uses the first genuinely recorded forecast per fixture/model/task.
Unpriced records never imply financial returns. Current results may label only
matching original kickoff/fixture forecasts recorded before kickoff.

`statistics_learning.py` reuses the existing 300-training/200-calibration,
30-day-block and fixed 180-day future-test policy, in separate immutable tables.
A protocol is locked before new eligible observations. Earlier known forecasts
and backtests are retained but excluded from new prospective evidence. Candidate
calibration is fitted only after sufficient genuinely observed results; future
challenger probabilities must themselves be recorded before kickoff. A single
evaluation waits for the full fixed cohort and verified results; missing records
cannot be backfilled. Models never auto-promote. No challenger can presently be
trained from the very small pending forward sample.

## Verification limits

Automated unit/integration tests use synthetic data and blocked transports.
Real archived evaluations and restored hosted data are separate operational
checks. A private Actions localhost browser test is not an authenticated test of
Streamlit Community Cloud. Previous anonymous preview access was denied; retain
that distinction until a real hosted authenticated session can be observed.
Supabase verification demonstrates the tested generation and readback, not an
unlimited retention guarantee or disaster recovery independent of Supabase.

The activation regression suite passed 756 local tests. A midnight-sensitive
test was made deterministic and an explicit UTC-date-boundary refresh test was
added; the production refresh behavior was unchanged. Compilation, dependency
checks, credential scanning, and local Streamlit health/root startup passed.
CI on the earlier functional commit passed 754 tests with one existing
private-archive skip; current CI is linked from Draft PR #1. Local AppTest exercised
all five pages using the genuine generation-3 hosted readback, including an
explicitly synthetic, session-only manual-price comparison. The original
17 genuine pregame records and frozen model assets remain preserved alongside
the newly verified generation-4 records.

The new NBA score challenger tested 1,225 games: moneyline Brier 0.2114, log loss
0.6114, versus the prior recent Elo study's Brier 0.2086. MLB tested 2,426 games:
moneyline Brier 0.2457, log loss 0.6845, versus prior Elo 0.2437. The new MLB total
task failed its simple baseline (Brier 0.2672 versus 0.2509). These comparisons
do not support replacing the existing models. Joint task metrics and calibration
details remain in the hash-bound research report, separate from current picks.


### Additional chronological cross-game diagnostics (2026-10-19)

`intelligence.cross_game_study` reuses the verified BoxScoreLab and Retrosheet
archives without any network request. NBA has two later-season test folds
(2024–25 and 2025–26, 1,225 games each); MLB has the 2025 test season (2,426
games). All same-date results are withheld until that date's predictions exist.
The first half of the preceding calibration season fits marginal probabilities;
the second half fits the joint calibrator. Neither uses later test outcomes.

For each leg count, the study chooses disjoint same-date favorite groups by
team identity, excludes repeated-team dates such as doubleheaders, and discards
leftovers. It compares explicitly hypothetical independence products with an
earlier joint calibration map, constrained to logical marginal bounds. Those
bounds are conditional on estimated marginals, not confidence intervals. It
reports Brier score, log loss, reliability bins and day-block uncertainty.
Only aggregate diagnostics and source/code hashes are committed; no historical
forecast is backfilled as though it had been published before a game.

Results do **not** justify promotion. The 2025–26 NBA joint-calibrator-minus-
product Brier differences were -0.001942 (574 two-leg groups; 95% day-block
interval [-0.005322, 0.001363]) and -0.000899 (357 three-leg groups;
[-0.005899, 0.003741]). Earlier NBA differences were positive (worse).
MLB differences were -0.000670 (1,121 two-leg groups;
[-0.002206, 0.000935]) and -0.000076 (749 three-leg groups;
[-0.000663, 0.000572]). Every interval crosses zero. These archives were already
inspected by this project; fitting isolation is not new independent confirmation.
No cross-game or mixed-sport joint model is approved or enabled. Existing
coherent experimental soccer SGPs and prospective monitoring remain unchanged.
The free worker records the hash-verified report's status only; it does not fit
these historical studies every four hours or promote a model.

Reproduce privately, using the preserved provenance-checked NBA bundle:

```sh
python -m intelligence.cross_game_study --nba-bundle PATH_TO_EXISTING_BUNDLE --history-dir data/research/history
```

### Existing Odds API safety (no collection authorized)

The existing The Odds API remains the only odds integration. Its hold remains
active. No new odds provider, account, subscription, key or automatic live-odds
activation is introduced. Legacy settings, reservations and displayed allowance
cannot raise the nine-credit local daily ceiling. At that ceiling, this store
also enforces a 279-credit UTC calendar-month ceiling, retaining any legacy
reservations. A single writer hydrates recent durable remote reservations before
checking it. This is **not** a provider monthly reset, account-wide quota guarantee, or proof that other consumers have
stopped. Existing durable remote reservations and operator reconciliation remain
required. A local midnight does not release the hold or restore provider credits.

Each collection has one transport attempt. A timeout or missing/invalid billing
header holds further local and shared requests without refunding reservations.
A larger-than-reserved observed charge is retained and held for reconciliation.
Responses close on success and failure. Quota observations retain numeric
counters and an account fingerprint, never arbitrary header text or credentials.
A fresh same-account observation below the proposed request cost blocks it;
that cache is an additional safeguard, not proof of account-wide exclusivity.
No sports-provider requests were made to implement or test this increment.

Verification for this increment: 779 full-suite tests passed, followed by the
additional local-PostgreSQL billing-timeout integration test (passed). One
pre-existing date-dependent regression assumed Bundesliga fixtures on every
execution date; its reviewed synthetic Sunday is now fixed explicitly. Local
compilation, dependency checks, loopback Streamlit health/root responses,
credential scanning, the nine frozen-asset hashes and original recovered-store
checksum all passed. No frontend files changed. The earlier five-page browser
proof remains a local browser using a genuine hosted replica; authenticated
Streamlit Community Cloud preview access remains unverified in this environment.

### Final execution: explicit dependence and cached-fixture aging

The cache-only OpenLigaDB adapter now ages a scheduled fixture to unresolved
once its exact kickoff passes, and recalculates full-season coverage at the
inspection time. It never promotes an unknown score, changes the accepted source
receipt or overwrites the successful snapshot. This fixes a case where a receipt
could still be within six hours while its cached coverage incorrectly described
an earlier calendar date. A midnight/kickoff regression verifies both the new
blocking behavior and preservation of the saved source.

`intelligence.dependence_study` diagnoses the earlier joint study's assumptions
with a coherent FGM Bernoulli model. It fits one common pair-dependence parameter,
shrunk toward zero with a fixed penalty, using all observed joint outcomes from
the earlier calibration period. It preserves each marginal and enumerates every
joint state; it does not silently multiply probabilities. The model explicitly
assumes no higher-order interaction and cannot represent every dependence
structure. Later test outcomes never fit its parameter. The report includes
14-day block uncertainty as a sensitivity check alongside day-block intervals.

The result is a rejection, not a promotion: on the latest NBA test fold (574
2-leg groups), Brier difference versus the hypothetical product baseline was
+0.000109, with a 14-day-block interval [0.000005, 0.000235]. MLB 2025 (1,121
2-leg groups) was +0.000202 [0.000003, 0.000379]. Positive differences are worse.
The NBA 3-leg estimate improved by -0.000264 on 357 groups but its interval
[-0.000647, 0.000088] crossed zero; MLB 3-leg results also did not establish
improvement. These are reused archives, not independent prospective evidence.
Existing frozen models, approval gates and current inference are unchanged.

Reproduce with the existing verified private NBA bundle (zero network calls):

```sh
python -m intelligence.dependence_study --nba-bundle PATH_TO_EXISTING_BUNDLE --history-dir data/research/history
```

`intelligence.verify_snapshot` accepts only an existing private SQLite snapshot,
creates a consistent temporary inspection copy, checks identity/frozen assets,
computes current seven-day research and monitoring, and verifies empty positive-EV
slots without prices. It cannot initialize an absent store or save forecasts to
the source. It reports blocked/expired inputs honestly rather than requiring a
candidate. State-only hosted verification and browser checks must remain
separate evidence from offline tests.

Synthetic end-to-end qualification tests exercise NBA, MLB and soccer quote
normalization, single/2-leg/3-leg slots, actual-ticket contract matching, joint
approval requirements, the conservative 2% EV threshold and stale/unapproved
rejection. Their prices and approvals are explicitly test fixtures and are never
stored as real recommendations or proof of live functionality.

Additional free sources checked on 2026-10-19, without new accounts:

- Hoops Menu's documented API licenses its travel dataset under CC BY 4.0.
  The travel export contains team summaries, not fixture pairings; documented
  status endpoints require already-known game IDs and do not supply the complete
  game/team discovery needed here. General site terms allow personal use;
  commercial fixture redistribution is not inferred from the travel license.
  See https://hoopsmenu.com/developers, /openapi.json and /terms.
- MLBDB has current public statistics and documented CSV exports, but its terms
  require written permission for automated access and commercial use. No MLBDB
  game data was downloaded or integrated. See https://www.mlbdb.com/terms.
- Previously reviewed no-key sources and their licensing/coverage limitations
  remain as documented above. No new sportsbook-odds provider was investigated.

Current honest capability classification:

| Capability | Status | Evidence or limitation |
| --- | --- | --- |
| Free Bundesliga refresh, seven-day discovery and durable pregame records | WORKING | Hosted generations/readback and actual scheduled run verified; inputs still expire |
| Bundesliga singles and coherent 2-/3-leg SGP probabilities | EXPERIMENTAL | Genuine source/model estimates, not approved picks or executable tickets |
| EPL/Ligue 1 current predictions | BLOCKED | Current/prior-season reconciliation requirements remain incomplete |
| NBA historical ingestion, chronology and calibration | WORKING | Four reconciled regular seasons; current forecasts are separate |
| NBA current predictions | BLOCKED | No reviewed fixture source/current offseason readiness |
| MLB historical ingestion and calibration | WORKING | Permitted 2023–25 archive; current 2026 data is separate |
| MLB current predictions | BLOCKED | Current results/fixtures missing; regular-season model cannot be transferred to postseason |
| Cross-game 2-/3-leg and mixed-sport joint approval | BLOCKED | Independent validation absent; tested challengers do not justify approval |
| Player props, verified live modeling | UNSUPPORTED | Required player/current-event data and validation absent |
| EV arithmetic, conservative ranking, empty-state filtering | WORKING | Offline contracts and regression tests; no real positive-EV bet is claimed |
| Current Odds API collection | BLOCKED | Owner hold remains active; no credit-consuming verification |
| Actual combined parlay prices | UNSUPPORTED | Existing provider adapter does not supply verified combined tickets; manual inputs remain unverified |
| Free recurring research and outcome monitoring | WORKING | Reviewed private schedule; future availability and financial performance not guaranteed |
| Paid AI, automatic wagering | UNSUPPORTED | Paid integration remains disabled; wagering is not implemented |

There is no new user setup requirement. Releasing the Odds hold is not the only
remaining limitation; source permission/current coverage and independent model
approval cannot be replaced by an engineering flag.

Final execution local verification: 792 tests passed, including the new
kickoff/midnight cache-aging regression, coherent joint-state/marginal checks and
multi-sport end-to-end qualification contracts. Compilation and dependency
integrity checks passed. Hosted readback/browser evidence is reported separately
in Draft PR #1 so offline tests cannot be mistaken for live verification.
