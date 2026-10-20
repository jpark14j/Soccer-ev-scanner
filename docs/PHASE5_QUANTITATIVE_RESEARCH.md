# Phase 5: results recovery and quantitative model evaluation

October 16, 2026, America/Toronto. Continues commit
`9e1ab19a734f91d18b4c731b6ec9649dded92073` on the existing development branch and
Draft PR #1. Main, production, paid-service defaults and API allowances are unchanged.

## Interrupted work recovered

The working tree contained one unfinished new file, `results_journal.py`, and no
other uncommitted changes. Its original contents were preserved under ignored
`work/phase5/recovered/` before continuing it. No previous Phase 4 work was reset.

## Results failures: reproduced causes and fixes

1. The only full normalized snapshot occupied the same cache key as the latest
   refresh attempt. A crash-safe failure entry replaced the old success before
   HTTP; a timeout/error then occupied that key for six hours. Normalized event
   observations could survive while the full snapshot and its coverage were no
   longer visible. **Accepted snapshots now have a separate append-only private
   SQLite journal**, including original receipt, source hash, reviewed identities,
   full normalized schedule and provenance. Failures cannot update/delete it.
   A legacy successful cache is migrated before replacement; a fresh surviving
   journal entry can restore missing cache visibility without HTTP.
2. `synchronize` initially checked only whether a *previously used* source hash
   differed. A shared cached analysis whose model preparation had failed had no
   used hash, so a new session could ignore results saved by another session.
   **Fresh cached results plus supported current quotes now trigger cache-only
   re-evaluation when no successful prepared source was used.** Original scan,
   source and quote times are preserved. No odds/results request is made.
3. The cached Streamlit loader accepted `db_path` but reopened the environment's
   default instead. The initial app store could also precede lazy Secrets loading.
   Store setup now resolves environment/Secrets first, and analysis opens exactly
   the supplied store path. Existing explicit environment values retain precedence.
   Blank result-credential environment values no longer shadow Streamlit Secrets.
4. Connection exceptions previously collapsed into one generic string. Fixed,
   non-sensitive codes now distinguish disabled/missing/invalid credentials,
   unreviewed use, timeout, TLS/connection, HTTP auth/permission/rate/server errors,
   schema/identity/coverage, reconciliation, missing/expired/future receipt and
   storage/integrity failures. No raw exception, token, header or body is exposed.
   Diagnostics separate the **last attempt**, **last accepted success** and
   retained normalized observations. The main coverage time is the accepted
   source receipt, not a newer failed-attempt time. A cached schedule that becomes
   past due is rechecked against today's date; a fresh receipt does not hide gaps.

Six requests/day/store, six-hour cache/failure suppression, 24-hour 429 cooldown,
no automatic retries, exact fixture/team reconciliation and all forecast gates
remain. An expired retained success is **inspection only**. Failed newer schema,
binding or score reconciliation cannot fall back into an approved forecast.

This fixes same-disk retention, not Community Cloud disk eviction. A stable store
instance/creation timestamp is shown under Settings' storage status; a changed
identity reveals a different/recreated database. It does not establish why the
host recreated it. A backup restored to the same private disk preserves the
identity and journal. The existing consistent private SQLite backup function
includes journal, quotas, bindings and paper records; an off-host copy still
requires an operator-managed destination. No automatic GitHub upload, public
redistribution, external database or guaranteed Cloud persistence is configured.
Already overwritten legacy full snapshots cannot be reconstructed reliably from
unversioned receipt information alone; retained normalized rows remain inspectable.

The reported hosted provider errors could not be independently reproduced with
the preview's token/store. These are verified code-level root causes, not a claim
that every hosted connection failure was caused by storage. Local football-data.org
credentials and network authorization are absent. No authenticated request was
made here; the preview's next permitted explicit check remains necessary.

## Accuracy: actual candidate-held-out comparison

`quant_research_policy.json` fixes the model family, periods and small parameter
grids. Each league is fitted separately on genuine pinned OpenFootball CC0 results:

- Goal training: July 2020–June 2023. Time-weighted ridge Poisson attack/defence
  with a home effect; training-only Dixon-Coles low-score correction.
- Calibration: July 2023–June 2024. Either monotone binary Platt maps or one
  temperature fitted to the complete score distribution using proper log score.
- Test: July 2024–June 2025. No test outcome enters coefficient/rho/calibration
  fitting or parameter selection. Test results do not choose a new champion.

Poisson, Dixon-Coles, coherent temperature, frozen-model replay and a calibration-
period constant baseline are compared on **identical eligible fixtures**. Existing
models are replayed through their unchanged prior-date functions and original
calibration; no same-day result enters their features. New coefficients are fixed
before calibration, while frozen strengths continue updating from earlier games.
Unseen/promoted or insufficient-training-history teams are excluded from common
comparisons. These selection effects and unequal updating are disclosed limitations.

The primary Dixon-Coles + binary-calibration comparison is below. Lower losses
are better. This compares models, not an actual deployed before/after replacement.

| League / market | Calibration / common test n | Frozen Brier → challenger | Frozen log loss → challenger | 95% interval for challenger − frozen Brier |
| --- | ---: | ---: | ---: | --- |
| EPL BTTS | 337 / 342 | 0.24848 → 0.24665 | 0.69068 → 0.68652 | −0.00737 to +0.00345 |
| EPL goals over 2.5 | 337 / 342 | 0.25212 → 0.25142 | 0.69859 → 0.69693 | −0.00545 to +0.00451 |
| Bundesliga BTTS | 240 / 210 | 0.23709 → 0.23503 | 0.66707 → 0.66258 | −0.01066 to +0.00625 |
| Ligue 1 goals over 2.5 | 272 / 272 | 0.24112 → 0.24301 | 0.67493 → 0.67897 | −0.00622 to +0.00983 |

Every primary comparison interval includes zero. The coherent-temperature
challenger also has no convincing Brier improvement over the frozen comparator.
Test ECE for the primary challenger versus frozen is EPL BTTS 0.02895/0.05517,
EPL totals 0.08258/0.08810, Bundesliga 0.01916/0.01487 and Ligue 1
0.04302/0.05286; ECE is a binning-sensitive descriptive diagnostic. The complete
artifact includes all baselines/methods, Brier/log-loss/classification intervals,
reliability bins, sample/exclusion counts, fitted parameters, source/policy/code
hashes and paired 1,000-resample UTC-day-block intervals. These assume exchangeable
day blocks and do not capture model-search or cross-day uncertainty.

**No accuracy improvement has been established strongly enough to replace a
model.** Moreover, 2024–25 was already inspected by earlier project models: it is
unseen by the new candidate fitting, **not a genuinely fresh independent project
confirmation period**. All five 2025–26 files are incomplete. Independent
prospective data and a timestamped tradable market benchmark remain essential.
No profitability, prospective win rate or model approval follows from these scores.

Reproduce offline using the already reviewed raw archive (not bundled in Git):

```bash
OPENBLAS_NUM_THREADS=1 python -m intelligence.quant_evaluation --source work/phase2/source
```

The command makes no network request. Do not change frozen source/policy/model
files to run it. The report is in `research_assets/quantitative/evaluation.json`;
the UI verifies content, policy and candidate-code hashes before displaying it.

## Coverage and source audit

| Competition | Current capability | Remaining blocker |
| --- | --- | --- |
| EPL | Existing experimental BTTS / goals 2.5 inference | Fresh complete permitted results, exact fixture, team history and current Ontario supported price gates still apply |
| Bundesliga | Existing experimental BTTS inference | Same gates; no model transfer |
| Ligue 1 | Existing experimental goals 2.5 inference | Same gates; no other totals line assumed supported |
| La Liga / Serie A | Historical ingestion and explicit model stop | Each 2024–25 archive has 370/380 completed games; no candidate fit or new live model |
| NBA / MLB | Existing observed prices/archive tools | No ready current sport-specific model or permitted current results account; props need additional player/context data |

Three bounded public archive GETs checked the current CC0 license and 2024–25
La Liga/Serie A files. License and both file hashes exactly match the pinned
snapshot; no missing final was recovered. Missing 2025–26 scores are EPL 27,
Bundesliga 12, Ligue 1 24, La Liga 15 and Serie A 36. No result is filled or inferred.

[BALLDONTLIE NBA](https://nba.balldontlie.io/) and
[MLB](https://mlb.balldontlie.io/) documentation lists account-keyed free games,
teams and players at five requests/minute. Player game stats, injuries and lineups
require paid access; free game access does not establish commercial redistribution
rights or enough data for props. No account, trial, subscription or integration
was activated. [Retrosheet game logs](https://www.retrosheet.org/gamelogs/index.html)
remain useful permitted-with-attribution archives through 2025 on the reviewed
page; no current 2026 feed was verified there. The next NBA/MLB step is a reviewed
free-account games adapter with current completeness/identity checks, followed by
independent sport-specific validation. No API key is requested in chat.

## Same-game research: completed foundation, not approved tickets

`score_distribution.py` constructs one nonnegative normalized soccer score matrix
with an explicit analytic bound on omitted tail mass (required below 1e−8).
Poisson goal rates, optional Dixon-Coles correction and a coherent score
temperature generate match-winner/draw, BTTS and total probabilities from the
**same distribution**. Individually calibrated binary probabilities cannot be
substituted into that joint model. Dependence between selections is preserved by
enumerating score cells, not multiplying individual outcome probabilities.

The settlement foundation handles winner/BTTS, integer/half totals and handicaps,
and quarter Asian lines split across the two neighboring lines. Win, push, loss,
half-win and half-loss joint states remain separate. These are mathematical
score-target settlements, not verified sportsbook period/void/combination rules.
No parlay payout or EV is inferred from fractional states. NBA/MLB and cross-game
joint modeling are explicitly rejected by this soccer-only function.

The offline report evaluates the full score distribution with proper multiclass
Brier/log loss and uncertainty, plus two defined same-game events (BTTS + over
2.5; home win + over 2.5). Common test samples are 342/210/272 by league. For
example, Bundesliga home-win/over-2.5 has Brier 0.18224 and log loss 0.54934; its
paired Brier difference against a training-only league-Poisson joint baseline is
−0.03557 to −0.00305. This is one of several retrospective comparisons on reused,
selected data, not independent joint calibration, a bookmaker comparison or an
approved SGP edge. All joint-event validation flags remain false.

**Automatic current SGP candidates from these challengers are not enabled.**
Current research remains on the frozen marginal models. Further work must freeze
an independently supported score model, validate joint events prospectively,
establish operator settlement/restrictions and obtain real combined prices.

## Simple final result and preview steps

**Today's Best-Supported Bet** now appears on AI Dashboard and Best Picks &
Parlays. It uses the existing publication/value gates first and the same explicit
uncertainty-adjusted score for every supported format. Its ticket-evidence API
accepts genuine combined/joint evidence in the future; no such adapter is
configured now. Existing leg gates still block unsupported markets. High
probability alone, experimental model scores or theoretical products cannot
trigger this result. It normally says **NO QUALIFYING BET**. This is a research
decision rule, not a demonstrated optimal staking/portfolio strategy.

1. Open https://soccer-ev-scanner-preview-jp.streamlit.app/ after the development
   branch rebuild. If needed reboot **only this preview** through Manage app.
   It should remain on `development/verified-sports-intelligence`, `app.py`.
2. Leave existing Secrets and paid approval `"0"` unchanged. No new key is needed.
   The existing optional results connection uses `FOOTBALL_DATA_TOKEN`,
   `FOOTBALL_DATA_ENABLED` and `FOOTBALL_DATA_USE_REVIEWED`; never expose tokens.
3. In **Settings & Research Tools → Research tool → Settings**, inspect **Current
   soccer results**. Compare each last attempt, last success, freshness, retained
   observations and failure code. Under storage status note store identity/time.
   A failed attempt should retain a previous accepted snapshot; an expired success
   should not enable inference. An empty recreated store cannot recover lost data.
4. If credentials/use are already configured and the six-request allowance permits,
   **Refresh soccer results only** checks selected competitions once per cache
   miss. Do not repeat it to solve a lost store or use an odds refresh as a repair.
   Successful results immediately re-evaluate saved supported quotes without odds
   calls, including in another session. Old prices still expire after five minutes.
5. In **AI Dashboard → Data & Model Health**, use **Recheck saved research · no API
   calls**. Confirm input/fixture/calibration blockers remain explicit. Existing
   EPL/Bundesliga/Ligue 1 estimates can appear only if every gate passes.
6. Open **Settings & Research Tools → Research tool → Model & Data Diagnostics →
   Quantitative model challengers · offline held-out research**. Inspect the common
   test table; full evidence/joint diagnostics are in a nested expander.
7. On **Best Picks & Parlays**, inspect the new final-result summary and preserved
   Phase 4 experimental cards. Single/SGP/multi-game/mixed qualification counts
   and missing evidence are expandable. No qualifying bet is a valid outcome.
   Existing four pages, assistant, price-only tools and performance tabs remain.

The local server/UI tests are verified separately from hosted preview access.
The hosted token/store/current forecast output, rebuilt browser UI and off-host
restore have not been independently verified here. Genuine newly observed
current forecasts and paper outcomes in this environment: zero. Paid AI, live
predictions, actual wagering and new player-prop probabilities remain disabled.

## Verification and remaining work

All existing tests are retained. Added regressions cover failure/success retention,
legacy migration, missing cache, fresh/stale/future receipts, source expiry,
store-path/Secrets ordering, same-disk reopen/consistent backup, append-only journal,
private errors, new-session inference, probability/settlement identities, correlated
score enumeration, training leakage, model report integrity, format-neutral value
gates and Streamlit navigation. Local reproduction of actual archive metrics also
passes; that one test explicitly skips in CI, which does not contain the private
raw archive. Synthetic numerical/provider fixtures are not genuine forecasts.

The [verification matrix](VERIFICATION.md) and
[evidence JSON](evidence/phase5-verification.json) record final tests/startup/CI.
No frozen model, approval/calibration policy, navigation, dependencies or existing
workflow is changed. Extra paid AI/odds/authenticated result requests: zero.
The nine-credit odds cap and six-request results cap are unchanged.

Remaining priorities are a verified durable private store; one successful permitted
hosted current-source check; repair of incomplete seasons; genuinely fresh independent
and prospective validation; historical Ontario tradable prices and market baselines;
joint calibration/operator settlement and real ticket prices; then sport-specific
NBA/MLB expansion. No replacement, validated joint probability or betting edge has
been established by this increment.
