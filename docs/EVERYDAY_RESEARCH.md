# Everyday research screens and live-research readiness

Open the existing development preview:
https://soccer-ev-scanner-preview-jp.streamlit.app/

The sidebar now has **Home**, **Best Picks & Parlays**, **Upcoming Games**,
**Performance Tracker**, and **Settings**. This replaces the earlier four-page
navigation; the application, deployed branch and production entry point remain
the same. All previous detailed tools are retained under **Settings → Admin /
Developer Tools**. This section is an organization aid, not an authentication
boundary: never treat a collapsed expander as access control for private data.

Home shows the strongest supported single and parlay, or honest empty states.
The preferred binary outcome comes from the existing model/evidence gates,
never from implied sportsbook probability. Best Picks separates estimated win
chance from approved value. Other observed outcomes appear under **Why this
pick?**. Unsupported price-only combinations remain in the detailed research
tool. No candidate is forced. Individual odds products remain theoretical;
there is no validated joint probability, verified combined ticket or parlay EV.

Upcoming Games includes saved discoveries and observed fixtures across NBA,
soccer and MLB, including future dates within the configured rolling window
(default 48 hours, existing maximum 168). Ontario local time is used. A saved
fixture with no eligible current prices is explicitly waiting for prices. Saved
games are partial coverage, not a complete verified league schedule. Opening
pages or changing filters never requests sports data. Visible research is
rechecked every minute; stale prices fail the unchanged gates.

Performance Tracker shows genuine committed pregame publications separately
from the distinct forward-forecast log. One-unit paper single results are
hypothetical, not real winnings. Historical observations, older paper logs and
backtests stay separate in **Detailed Performance**. Calibration and approval
standards are unchanged; no accuracy improvement is claimed by this UI change.

## Fixed misleading budget display

Previously `remaining=0` meant either an exhausted local allowance, a recovery
hold, or a read-only dashboard. The banner incorrectly described all three as
exhaustion. `remaining` still returns zero to **enforce** read-only/held operation.
Additional diagnostic fields now separately report local headroom, actual local
exhaustion, the read-only restriction, and the observed remote hold.

Zero saved local reservations out of nine means nine below that local cap. It
does not authorize this read-only dashboard to retrieve odds. Supabase's remote
write-ahead budget/hold remains authoritative for a worker. Neither counter
establishes the external Odds API account balance. Production uses the same
account (owner-confirmed), so production use is outside this development ledger.
A midnight reset or closing a browser tab cannot verify/replenish provider
credits, release a hold, or bound other consumers' requests.

## Hosted evidence already observed on October 17, 2026

Private GitHub Actions logs were inspected without printing credentials or
private service URLs:

* Run #2: fresh state reads verified at generation 1, two independent restores,
  zero remote writes and zero sports-provider requests; provider hold true.
* Run #3: storage-only preservation checkpoint verified at generation 2, record
  counts and provider hold preserved, two independent restores and zero
  sports-provider requests.
* Run #4: fresh reads verified at generation 2, two independent restores, zero
  remote writes and zero sports-provider requests; provider hold true.

These checks need not be repeated. They verify the hosted read/checkpoint path,
not a live research run, recurring scheduler, future retention or preview reboot
persistence. This implementation does not run any of those operations.

## Prepared first research run — not executed or enabled

The existing private worker already discovers five supported competitions
(NBA, Premier League, MLB, Bundesliga, Ligue 1), examines the configured future
window, reuses saved responses, reserves remote budgets before requests, and
stops at the existing nine-credit daily odds cap. It retains the six-request
results cap and twelve bounded discovery reservations. No broad player-prop
scan or unbounded polling is added. Discovery and failed calls can still use
request allowance; no single invocation is promised to spend exactly nine.

The worker's existing cycle applies supported frozen models, prepares genuine
pregame single/parlay research, commits to the recovered store, reconciles
verified later results, and evaluates challengers only when the locked evidence
requirements pass. An empty result is legitimate. Premier League BTTS/goals 2.5,
Bundesliga BTTS and Ligue 1 goals 2.5 remain experimental and require complete,
fresh, permitted current results. Current NBA/MLB model inputs, other soccer
competitions and player props remain blocked where their evidence is missing.
Older archives cannot supply current statistics. No model or parlay is approved.

Before an operator may authorize even one `research` run:

1. Verify the actual remaining Odds API allowance and account-wide consumers
   privately in the provider dashboard. Production being reported as open-only
   and Telegram being reported disabled are not proof of total account usage.
   Review permitted research, storage and future commercial use; free access
   does not imply redistribution rights. No provider request was made here to
   discover the balance or infer rights.
2. Establish permitted current soccer-results access and configure the existing
   optional football-data.org adapter privately if available. A free token alone
   does not establish complete current coverage or commercial permission.
3. Only after those reviews, actual usage reconciliation, and explicit owner
   authorization may the existing operator hold-release procedure be used.
   Never reset unknown usage or assert review flags as a workaround. The account
   scope cannot be guaranteed while production consumption is uncontrolled.
4. Review the tested immutable app commit used by the private worker. A later
   one-off research run must be explicitly enabled and its committed readback
   inspected before considering a schedule. Keep the schedule disabled for the
   initial run. No new paid resource, trial or account is needed by this change.

`RESEARCH_WORKER_ENABLED=0`, `RESEARCH_SCHEDULE_ENABLED=0`, and
`PAID_ANALYST_APPROVED=0` remain the required current settings. Provider holds,
remote budgets, model assets and approval policies are untouched. The private
workflow's reviewed source pin can be updated without enabling any of them.
No claim of operational unattended predictions is made before an authorized
hosted research run and genuine later outcomes establish it.
