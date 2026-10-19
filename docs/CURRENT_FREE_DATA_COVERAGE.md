# Current free-data readiness — 19 October 2026

This increment preserves the five pages, existing models and approval rules.
The Odds API hold, nine-credit ceiling, paid-AI disablement and production are
unchanged. No account or new API key is required by these adapters.

## Sources actually checked

- [SportScore documented date API](https://sportscore.com/developers/api/):
  `/api/v1/fixtures/`, filtered by exact UTC date, sport and competition. The
  earlier standings/widget queries did not establish result coverage. Actual
  date-filtered responses supply completed EPL/Ligue 1 results and exact future
  kickoffs. Its [terms](https://sportscore.com/developers/terms/) allow cached,
  attributed derived analytics, including early commercial applications; they
  prohibit competing raw-feed/bulk redistribution. The exact visible dofollow
  attribution is displayed on every app page. Raw receipts remain private.
- Frozen [OpenFootball CC0 fixtures](https://github.com/openfootball/football.json)
  are the complete season identity/pairing registry. File hashes stay pinned.
  Missing scores (including list-shaped scores the old parser did not accept)
  are supplied only by independently matched SportScore finals; no unknown
  score is converted to a draw. Current completed dates/scores must match every
  frozen completed fixture. Model artifacts and historical evaluation are intact.
- [Sporting Events NBA JSON](https://sporting-events.org/data/nba/): its
  [dataset licence](https://sporting-events.org/data/) permits personal/commercial
  attributed use. The actual export contains 1,193 team fixtures and two context
  headings. Context headings are excluded, not turned into games. Exact UTC
  tipoffs and all 30 reviewed teams are checked. No score comes from this export.
- NBA finals use the documented SportScore basketball day endpoint when games
  have actually finished and reconcile to exact scheduled teams and tipoff.
  No regular-season games have finished at this check, before October 20 tipoff.
  The reviewed competition identifier is `national-basketball-association`, with
  exact response name `National Basketball Association`; `nba` returned an empty
  day and must not be used as evidence of missing games.
  Seven actual April 12, 2026 finals from the corrected endpoint were checked
  against the existing licensed BoxScoreLab history: every score matched. Its
  two October 20 scheduled games also match the Sporting Events teams/tipoffs.
  This verifies source reconciliation, not a future live settlement or model edge.
- MLB: the [Sporting Events MLB export](https://sporting-events.org/data/mlb.json)
  contains four tournament/Opening Day headings without teams, times or scores.
  SportScore documents no baseball endpoint. Retrosheet's available archive in
  this app stops in 2025. Public MLB Stats API accessibility is not permission to
  redistribute/use its data commercially; no such access was activated.

## Actual reconciliation and model scope

EPL: all 353 previously scored 2025–26 matches are retained; 27 missing finals
are recovered by exact fixture/date matching. Current full schedule: 380 fixtures,
69 prior-day finals through October 18, no overdue prior-date gaps. While the
October 19 Tottenham–Coventry match is in progress, the unchanged league-wide
unresolved-game gate blocks inference. After it finishes, a verified refresh
withholds its same-day score; the next UTC-day refresh can use that final. A
postponement, conflict or missing final continues to block inference.

Ligue 1: 282 old finals are retained and all 24 missing 2025–26 results are
recovered. Current schedule: 306 fixtures, 63 prior-day finals through October
18, no overdue gaps. Actual offline inference produces eight experimental
over/under 2.5 estimates; the promoted Le Mans team still fails the unchanged
16-prior-game requirement and is excluded.

NBA: the existing 4,910-game, 2022–26 date-block Elo study is reused without
retraining, replacement or approval. Frozen calibration uses 2024–25; 2025–26
test Brier is 0.208554, log loss 0.604931. Its opening 14-day subgroup has only
102 games (Brier 0.224095; log loss 0.642174). Current scope is explicitly the
first 14 regular-season days, with unmodeled offseason roster/injury changes
disclosed. Actual source-based rehearsal yields 43 upcoming game-winner estimates
in seven days. Every earlier scheduled game must have a verified prior-day final;
otherwise all NBA inference stops. No preseason, props, totals, playoff or
postseason probabilities are transferred from this model.

MLB 2026/postseason remains blocked. Resolving it requires a source with explicit
permitted data use, actual game-level teams/times/finals and suitable postseason
evidence. The regular-season study is not a postseason model. No permission,
new account or purchase is implied by this diagnosis.

## Scheduling, persistence and limits

The existing four-hour private single-writer job refreshes these adapters.
An extra-source import can reuse fresh Bundesliga data without resetting its
original refresh clock. Up to 200 extra public GET attempts per run, plus at most
one existing Bundesliga GET, are allowed; attempts are recorded before transport.
There are no retries or redirects. Failed transports wait three hours; recent
dates/future fixtures cache for three hours, source observations expire after six
hours. Earlier successful historical dates are reused. Initial historical
catch-up is larger than ordinary updates, well below SportScore's published
approximately 10,000 requests/day/IP fair-use allowance. This is separate from
the held Odds API budget; no held-provider call is made.

Independent source errors cannot replace an accepted completed score or suppress
other working sports. Unknown teams, missing finals, conflicting scores, moved
completed fixtures and unsupported statuses fail closed. Snapshot commits retain
the recovered store identity and verify original protected ledgers/budgets and
fresh readback. Prepared private audit receipts can be reused with their actual
checksums/timestamps, never relabeled as newly observed.

Only genuinely recorded pregame rows may appear on Home/Picks. Verified finals
label the same immutable records for the accuracy-only tracker. No forecast is
backfilled. Existing Bundesliga coherent two/three-leg SGPs remain supported;
compatible cross-game/mixed-sport candidates expose logical joint bounds only,
not an invented joint probability, ticket price, EV or model approval.

## Preview

Open the existing development preview and click **Find Best Bets Now**. Home,
Best Picks & Parlays and Upcoming Games read the committed Supabase replica.
Expand the existing evidence/data-blockers section for unsupported fixtures.
The existing page refresh picks up new worker generations; clicking does not
make a sports-provider request. Community Cloud hosting sign-in may still be
required; its private hosting controls were not changed.

## Targeted completion increment (October 19, 2026)

The opening fortnight is no longer an arbitrary NBA season cutoff. The same
frozen Elo updates, calibration and historical frequency ranges can be used
through the reviewed 2026–27 regular-season fixture window, backed by the
existing 1,225-game unseen-season evaluation. Beyond the opening fortnight,
both teams must have a verified current-season result within 21 days of tipoff.
All earlier played games still require reconciled finals; no preseason/playoff
transfer, roster data, new fit, improved-accuracy claim or approval is implied.
Explicit postponed/cancelled source statuses are retained but supply neither
scores nor predictions. Suspensions, unknown missing results and conflicts
remain blockers. Same-date tipoff changes cannot settle an original differently
timed prediction. A disappeared NBA fixture fails closed: repeated pairings
cannot safely be linked across dates without an exact reviewed source binding.

Cross-game research no longer disappears five minutes after a saved prediction.
It retains the six-hour source freshness gate and the original publication time.
Within the existing parlay details, eligible NBA, soccer and mixed-sport scopes
can each contribute a two/three-leg candidate. Duplicate fixtures, opposing
outcomes and shared teams are excluded. Ranking uses narrower marginal
calibration ranges, then the weakest individual probability, never payout.
These combinations have Frechet logical bounds and a corresponding fair-odds
range, **not a calibrated joint probability**. No independence, executable
combined price or EV is claimed. Existing Bundesliga SGP cards and all single
cards remain unchanged. When an existing Home parlay slot has no supported point
forecast for the selected competitions, the same card can show recorded bounds;
it does not replace an available existing point-forecast card.

The existing single writer now records up to six bound-only combinations before
all kickoffs. Every leg retains its fixture, kickoff, model, marginal estimate,
uncertainty and source receipt. Results are reconciled separately per leg; every
leg must have an exact final before accuracy changes. Rescheduled, void/ambiguous
or incomplete combinations stay out of the settled denominator. Repeated clocks
or snapshots do not manufacture extra decisions. Bounds are excluded from
point-probability Brier/log-loss calculation and challenger calibration/training.
An in-cooldown worker may analyze already verified cached inputs without any
source GET or receipt-clock reset; frontend browsing still never records rows.

MLB sources were rechecked, without ingesting restricted data:

- [Retrosheet game logs](https://www.retrosheet.org/gamelogs/index.html) explicitly
  cover 1871–2025; its event/postseason downloads also stop in 2025. Attribution
  permits the existing historical study, but does not supply missing 2026 games.
- [MLB's official terms](https://www.mlb.com/official-information/terms-of-use)
  restrict automated collection and reuse without applicable permission. Public
  Stats API reachability or a third-party wrapper's code licence does not grant
  that permission. Neither was activated.
- The previously tested Sporting Events MLB export has four context headings,
  not team/time/final-score game records. SportScore's documented sport coverage
  does not include baseball.
- The public `925Sports/mlb-2026-game-logs` repository has no visible data-use
  licence; a file named for 2026 does not establish permission, completeness or
  postseason suitability. No raw data from it was imported.

Consequently 2026 MLB singles, pitcher inputs and MLB/mixed-MLB parlays remain
blocked. Required: permitted complete current fixtures/finals, reviewed identities
and season phases, and matching model evidence. No new account or paid service
was enabled. Genuine settlement must be checked after an actually recorded game
finishes; deterministic settlement tests are not a claim of live accuracy.
