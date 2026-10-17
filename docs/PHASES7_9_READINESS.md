# Phases 7–9 — final engineering and operational readiness

Continues the existing repository from Phase 6 commit
`26ec3869f4aeddccce49a42d21176c43c5430fc5`. The initial working tree was clean.
Completed earlier phases and all existing tests were preserved. Development stays
on `development/verified-sports-intelligence`, Draft PR #1 only. Main, production,
production Secrets and deployment configuration were not changed; no merge,
subscription, trial, purchase or real paid-AI request occurred.

## What was implemented

| Milestone | Functioning engineering increment | Practical limit |
| --- | --- | --- |
| 7A | Distinct probability, defined price-sensitivity and best-supported marginal-parlay rankings; explicit probability fallback | Research ranges are historical bucket intervals, not event-specific confidence bounds; no validated EV |
| 7B | Compatible same-game, multi-game and mixed 2/3-leg shortlists; coherent scenario settlements, explicit no-independence logic; historical baseline/sensitivity/stability report | No approved current joint forecast or operator ticket adapter |
| 7C | Frozen-model/coverage audit; prospective policy prepared without retuning the reused test set | Untouched future outcomes and complete permitted new-sport inputs remain necessary |
| 8A | Automatic first-pregame contract/model/protocol records alongside legacy paper logs; exact cached-result labeling, immutable losses, deduplication and conflict holds | Current capture support is the existing frozen soccer binary models; no historical backfill |
| 8B | Scoped five-state reliability scorecards; precision/power planning, block uncertainty, completed-cohort review, league-specific and expiring registry approvals, reviewed suspension | Technical review eligibility is not model activation or betting-opportunity approval |
| 8C | Disabled optional private Supabase snapshots/readback/new-file restore; model assets and budgets preserved; restore request hold | No external service/account configured or tested; no shared primary database or scheduler |
| 9A | Five concise daily results on existing four pages; expandable evidence; source-grounded local assistant knows forward scorecards | Empty outcomes and model-only research remain valid when data is missing |
| 9B | Full synthetic-provider workflow and safeguards tested; startup/security/dependency verification | Software replay is not live coverage, real forecast performance or hosted-browser verification |
| 9C | Readiness report, setup/preview instructions, milestone commits and continuation checkpoint | Production readiness is not claimed |

Details and exact methods: [Phase 7](PHASE7_RESEARCH_ENGINE.md),
[Phase 8](PHASE8_FORWARD_DURABILITY.md),
[verification evidence](evidence/master-phases-verification.json).

## Daily experience and ranking

AI Dashboard and Best Picks & Parlays lead with:

1. **TOP AI SINGLE / AI's Top Research Pick — Experimental**: the default
   price-sensitivity research result, or an explicitly labeled probability
   fallback. Exact game, market, outcome, model estimate/range and current
   observed Ontario price/timestamp stay distinct from break-even probability.
2. **TOP AI PARLAY**: compatible same-book 2/3-leg multi-game research chosen by
   existing weakest-leg evidence. Different games do not establish independence.
3. **Best Risk-Adjusted Research Opportunity**: only when the entire supplied
   nonzero calibration range exceeds observed break-even. The documented score
   is `(lower − break_even) / range_width`; it is research sensitivity, not
   independently validated value, expected profit or a Sharpe ratio.
4. **Today's Best-Supported Bet / APPROVED OPPORTUNITY**: the unchanged strict
   single/joint-model, current-price, settlement, execution and value gates.
5. **Model Reliability**: relevant league/contract/model status and missing
   forward evidence. No selected model means no inferred reliability.

The three rankings and compatible SGP/multi-game/mixed formats are expandable.
Model disagreement remains unavailable when no supported event-level comparison
exists. No invented score fills that gap. Singles are not displaced by an
assumed superior parlay. Theoretical price products are never executable quotes.
Model-only replay requires a genuine retained forecast with matching fresh
source/model/fixture proof; it exposes no stale sportsbook price or value.
Changed adapter/source hashes appropriately block older replay until a genuinely
new supported inference is possible; old evidence is not relabeled as current.

**Page loads are now provider-request free.** Initial opens, page navigation,
competition/book filters, minute UI updates, local chat and saved-research
rechecks use stored observations/results only. Valid forecasts can still be
recorded locally; “no provider request” does not mean local storage is unwritten.
The cache binds to store instance identity as well as its path, so a recreated
store does not silently reuse another generation's cached analysis. Original
source times are never renewed. The previous query audit is retained separately.

**Refresh analysis** is now an explicit provider retrieval, disabled without a
key, remaining allowance or valid settings. Existing narrower market and
results-only controls remain. The provider cache and nine-credit odds/six-request
results defaults are unchanged. A restored-store hold blocks requests even after
the daily clock reset. No extra credits were spent testing these paths.

## Actual predictive and joint evidence

Frozen model parameters and their existing binary evaluation results are
unchanged. **No new independent accuracy improvement is demonstrated.** No model
is replaced or promoted. Repeatedly choosing a new challenger on the same
2024–25 dates would not create an independent test, so this phase does not do it.

The new joint report replays existing score parameters on the same chronological
matched test cases against a training-only coherent league-Poisson baseline.
For the BTTS Yes + Over 2.25 all-full-win target:

| League | Matched test n | Model Brier | Paired Brier difference 95% interval vs baseline | Median scenario range width |
| --- | ---: | ---: | --- | ---: |
| EPL | 342 | 0.249455 | −0.004558 to +0.008084 | 10.70 percentage points |
| Bundesliga | 210 | 0.250938 | −0.008580 to +0.010685 | 12.24 percentage points |
| Ligue 1 | 272 | 0.246277 | −0.010323 to +0.006462 | 11.65 percentage points |

The other tasks are Home +0.25 with Under 3.0 and Home win with BTTS Yes and
Under 3.5. Full joint-state Brier/log loss, paired intervals, calibration bins,
half/push outcomes and quarter stability are in the
[report](../research_assets/quantitative/joint_validation.json). Every new paired
binary Brier difference interval includes zero. Deterministic rate/rho/
temperature scenario ranges are not statistical confidence intervals. These
dates were previously inspected; the report is not independent confirmation.

No marginal probabilities are multiplied into a current SGP forecast. A supplied
coherent scenario preserves same-game dependence; it remains a scenario. Across
games only conditional logical bounds can be shown if every component exists.
No approved joint probability, actual combined ticket price, parlay EV or
operator-settlement claim is made. Mixed formats retain their linked components
and remain research when joint evidence is absent.

## Forward testing and reliability

Supported inference locks a policy before computation. The existing automatic
paper-recording path now also captures first pregame contract/model/protocol
decisions, independent of top-pick status or eventual outcome. Books, opposing
sides and refreshes cannot inflate the sample. Every retained forecast has
chronology, source/hash, baseline and ranking-version evidence. Legacy paper
records and backtests remain separate; their counts must not be added.

Verified exact completed source results append labels, never rewrite predictions.
Missing/postponed/rescheduled fixtures stay pending. Score conflicts quarantine
records and suspend matching research for review. Static settlement fractions
handle pushes and partial outcomes, but no unsupported partial-contract binary
probability is invented. Score-contract hypothetical returns are separate from
actual ticket results and ROI.

Scorecards report probability Brier/log loss, pre-recorded constant-baseline
comparisons, calibration and dated block intervals. Review uses **fully labeled
completed 30-day cohorts**, not whichever settled subset looks favorable.
Insufficient support suppresses intervals. Precision/power plans, missing
outcomes, code/protocol mismatches, deterioration and execution limitations stay
visible. Multiple cohort looks, temporal dependence and external verification
still require scientific review. Winning streaks never automatically activate a
model. Scoped reviewed registry actions and all existing approval requirements
remain mandatory.

The states are Experimental, Under forward evaluation, Eligible for approval
review, Approved and Suspended. Validated probability estimation and approved
betting opportunity are separate decisions. **Actual approved models: zero.**

At the genuine local read-only audit, newly recorded forecasts, labels, accepted
keyed results, reviewed actions and remote backup receipts are all **zero**.
The end-to-end replay's forecasts/results are explicitly synthetic software-test
data. No unplayed game or historical backtest has been presented as live evidence.
Future real observations and calendar time remain essential.

## Coverage and operating readiness

| Scope | Available | Remaining blocker |
| --- | --- | --- |
| Premier League | Experimental BTTS and exactly 2.5-goal totals | Fresh complete reconciled permitted results, mature team inputs, current Ontario price and calibration gates per selection |
| Bundesliga | Experimental BTTS | Same gates; other markets need their own validation |
| Ligue 1 | Experimental exactly 2.5-goal totals | Same gates; no transfer to other lines |
| La Liga / Serie A | History and explicit diagnostics | Each required reviewed 2024–25 file remains 370/380; no ready frozen model |
| NBA / MLB | Existing observed-price, archive and diagnostic tools | Permitted current histories, sport-specific current inputs and independent validation; player props additionally need player logs/availability/context |
| SGP / mixed | Compatible model-backed research, coherent offline/scenario settlement | Approved current joint forecast, operator acceptance/rules and genuine combined price absent |
| Multi-game parlay | Same-book model-backed research and logical dependency information | Cross-game dependence/joint validation and actual combined price absent |
| Storage | Same-disk SQLite backup plus disabled private off-host adapter | Real remote setup/readback/restore unverified; snapshot protection is not shared transactional persistence |
| Background automation | Offline manual audit and existing protected notification workflow | Online research worker disabled; shared budgets, verified durability and supported scheduler missing |

The optional remote-storage setup requires **your own free account/private
bucket, provider-use/privacy review and server-only Secrets** as documented in
Phase 8. It is not essential to test the UI. It has not been activated here.
Actual source rights for commercial redistribution are not assumed. No new API
key is required for the implemented saved-data research workflow. Independent
future model evidence cannot be obtained merely by buying or enabling storage.

## Exact preview checks without unnecessary requests

1. Open https://soccer-ev-scanner-preview-jp.streamlit.app/ after the development
   branch rebuild. Confirm only this preview uses
   `development/verified-sports-intelligence`, entrypoint `app.py`. Reboot only
   this preview if necessary. No merge or production change is needed.
2. Leave all existing paid-AI and budget settings unchanged. Keep
   `PAID_ANALYST_APPROVED = "0"` and remote backup flags `"0"`. Do not paste keys
   into chat or create an external account just to test the interface.
3. On AI Dashboard, select Premier League, Bundesliga and Ligue 1 if desired.
   Merely opening/filtering the app now reads saved data without provider calls.
   Inspect the five daily summaries. Exact empty reasons or model-only research
   can be correct; a fresh results count alone does not make prices current.
4. Expand **Odds availability, distinct rankings and selection exclusions**.
   Compare raw stored, current-eligible and model-eligible observations; original
   receipt times, prior query audit, store identity, quota and next action.
   The genuine local store still contains 910 stale observations and zero current
   eligible prices. Hosted counts and the hosted zero-price cause are unverified.
5. Use **Data & Model Health → Recheck saved research · no API calls**. It
   recomputes with saved inputs, cannot revive expired prices or recover an
   erased store, and does not change the odds allowance. Do not press Refresh
   analysis merely to verify layout. If you later deliberately need new prices,
   prefer an existing narrow market request and inspect remaining quota first.
6. Open **Best Picks & Parlays**. Inspect the three distinct rankings and
   **Three research rankings and compatible parlay formats**. SGP/mixed entries
   remain clearly unpriced joint research; no candidate is forced. Existing
   filters, opposing details and price-only tools remain available.
7. Open **Performance Tracker → Prospective paper research**. Inspect first
   contract counts, scoped states, missing evidence and downloadable scorecards.
   Do not add these counts to legacy paper/backtest logs. No real new record is
   claimed by this development session.
8. Open **Settings & Research Tools → Model & Data Diagnostics → Joint research ·
   simpler baseline, sensitivity and stability**. Existing Phase 5/6 reports are
   preserved. In **Research Operations**, optional backup should remain disabled.
9. Open **AI Assistant** in local mode. Ask “How is forward performance measured?”
   or “What is the model reliability?” It retrieves application scorecards and
   labels answers **Local · rule-based**. Chat cannot upload, promote, place bets,
   purchase services or run arbitrary code/database commands.

All **534 local tests pass** (49 added since Phase 6); old tests are unchanged.
Compilation, dependency consistency, secret checks and 34 protected-file
comparisons pass. The full joint report reproduces except generation timestamp/
checksum. An isolated Streamlit process returned HTTP 200 `ok` on port 8515 with
credentials removed, odds cap zero and paid AI/results refresh/remote backup off.
Milestone 7 CI passed 497 tests plus one documented raw-archive skip; milestone 8
passed 527 plus that skip. Final CI is checked after publishing this increment.

The public preview URL is inaccessible from this environment's web reader.
Hosted browser state, credentials, actual provider output and remote durability
remain independently unverified; this does not mean the preview is down. Main,
production, workflows and paid settings are unchanged. Actual odds/results/
OpenAI/remote-storage requests this development workflow: **zero**.
