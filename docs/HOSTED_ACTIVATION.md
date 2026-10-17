# Development preview: hosted checks and guarded activation

Continues Phase 10 at `4efa22f`. Production and the app's `main` branch are not
changed. No sports data, paid API call, quota release or hosted worker is enabled
by deploying this code. All existing model approval/calibration gates remain.

## What is known and what still needs hosted evidence

The owner reported Supabase generation one, the expected snapshot checksum, no
reader synchronization warning and matching recovered store identity
`478dbf23ce374b0dafc727eca737bc5e` in preview. This is evidence of a successful
initial reader path, not independently observed reboot persistence or worker
operation. The development environment has no Supabase credentials and cannot
operate the owner's hosted UI. No hosted success is inferred from offline tests.

In preview, Settings & Research Tools → Research Operations now displays the
committed snapshot SHA-256, store identity, generation and checkpoint type.
Bootstrap/storage checkpoints are distinguished from actual research runs.
**Verify fresh Supabase reads · no sports requests** performs two independently
restored remote reads, checks integrity/identity and rejects changed content in
the same generation. Results are cached five minutes. It writes no remote state
and makes zero sports-provider/AI requests. Temporary restored files are deleted.

The CLI adds:

* `python -m intelligence.background --verify-shared`: the same fresh read test,
  through the worker-only service-role connection. Requires
  `RESEARCH_EXPECTED_STORE_INSTANCE` and existing shared-state configuration.
* `python -m intelligence.background --storage-check`: one fenced operational
  checkpoint with no research cycle, provider call, forecast, label, budget
  reservation or hold release. It checks expected identity/assets before commit,
  preserves record counts and verifies the committed snapshot with two fresh
  reads. The default remote request hold can remain **true** throughout.

An actual storage check advances the generation (normally one → two). It does
not bootstrap an empty store or reconstruct missed pregame forecasts. After a
successful check, refresh the preview after its five-minute sync TTL and verify
that generation. Then reboot only the preview and verify that generation and
identity again. This establishes recovery across that restart, not infinite
retention, disaster recovery or recurring prediction operation. Keep the private
recovery archive and plan for the existing bounded two-head retention.

## Supported background host

GitHub scheduled workflows run only from a repository's default branch. Adding
cron on the application's development branch would not create an unattended
worker. Changing its production default branch is not authorized. The supported
alternative is the existing **private recovery repository**, using
`deploy/private_worker.yml` as `.github/workflows/development_research.yml` on its
own default branch. That private repository's application is file storage/worker
hosting; the Streamlit application and Draft PR remain in the original repository.

The installed workflow must pin a reviewed immutable application commit and the
expected recovered store identity. It checks out only the public application
source, with no persisted Git credentials. State credentials are supplied only
to the final server-side step; setup/install steps receive no provider Secrets.
Permissions are read-only. No Telegram, deployment, merge, artifact upload,
publication of private data or repository-write step exists. The remote lease,
generation fence and write-ahead budgets remain the provider authority.

### Exact first setup — state checks only

1. Preserve any genuine preview-only records before switching/rebooting it.
2. In the private `jpark14j/sports-ai-private-recovery` repository, open
   **Settings → Secrets and variables → Actions → Secrets → New repository
   secret**. Add `RESEARCH_STATE_SERVICE_KEY` using the existing Supabase legacy
   **service_role JWT** from **Supabase → Project Settings → API Keys → Legacy
   API Keys**. Keep it only in private worker Secrets; never in chat, the preview,
   source or logs. The current adapter does not accept new-format `sb_secret_`
   keys. Do not rotate keys as part of this setup.
3. On the adjacent **Variables** tab, add `RESEARCH_STATE_URL` with the exact
   HTTPS project origin. The installed workflow pins the expected store identity
   and application SHA, so those do not need to be typed by the owner.
4. Before running Actions, inspect your personal GitHub account's
   **Settings → Billing & licensing** (or **Billing and plans**). Confirm included
   Actions minutes are available and paid overages are blocked. If those controls
   cannot establish no paid usage, do not run the job; retain the free preview
   reader check. Then set private repository variable
   `RESEARCH_ACTIONS_FREE_TIER_REVIEWED=1`. This flag records your review; it is
   not a billing control. No other workflow flags are required for state checks.
5. Open the private repository's **Actions → Development research worker → Run
   workflow**, select **verify**, and run. Expect two independent restores with
   `remote_writes=0`, the expected identity and zero sports/AI requests. Do not
   share credential screenshots or full private logs in chat.
6. Run that workflow again with **storage-check**. Expect a new generation,
   `record_counts_preserved=true`, `provider_hold_preserved=true`, and zero
   sports-provider requests. Confirm it in preview, then perform the preview
   restart check above. Leave worker/schedule variables absent or zero.

### Safe configuration diagnostics

Prefer the project origin `https://<project-ref>.supabase.co` in
`RESEARCH_STATE_URL`. The adapter also accepts the same official origin with a
trailing slash or the exact `/rest/v1` / `/rest/v1/` suffix copied from Supabase's
REST API panel. Those forms are normalized before the RPC path is appended.
Arbitrary paths, queries, fragments, credentials, ports and other hosts remain
blocked before any network call. This does not relax key-role or host checks.

The CLI prints allowlisted codes such as `supabase_origin_invalid`,
`state_key_missing`, `state_key_format_invalid` or `state_key_role_mismatch`
without credential values, raw URLs, exception text or tracebacks. Unknown
transport/storage failures retain `configuration_storage_or_provider`.
The workflow prints a constant selected-operation message before verification.

After an application/workflow fix, use **Actions → Development research worker
→ Run workflow**, select the private repository's **main** and **verify**.
Do not use **Re-run failed jobs** on the older run: GitHub reuses that run's old
workflow/commit and its old immutable application pin. No research activation,
budget release or odds/results credentials are required for verify.

The job is completely skipped until the free-minutes review flag is set. Manual
dispatch defaults to **verify**. State-check modes receive no odds/results token.
The service-role key necessarily permits writes, but **verify** invokes only
read RPCs; use the preview's anon-key verification when read-only privilege is
desired. All CLI failures use sanitized error codes and a nonzero exit status.

### Research activation remains blocked until account review

The owner is currently unsure whether production/Telegram share the same Odds
API account and whether a football-data.org account exists. These are unresolved
gates, not permission to assume independent accounts or current results.

* Inspect the existing production and development credential/account assignments
  privately and check The Odds API dashboard. Do not create another free account
  to evade limits. A development-only nine-credit ledger cannot bound spending
  by an uncontrolled production consumer. If shared/unresolved, keep the hold
  and leave `RESEARCH_BUDGET_SCOPE_REVIEWED` unset. Production is not changed here.
* Current supported soccer inference requires the existing optional
  football-data.org adapter with verified competition coverage and permitted
  use. If no account exists, obtain the provider's free account yourself and put
  its token only in private worker Secret `FOOTBALL_DATA_TOKEN`. Then review/set
  `FOOTBALL_DATA_ENABLED=1` and `FOOTBALL_DATA_USE_REVIEWED=1` in worker Variables.
  A free token does not by itself guarantee complete results or commercial rights.
* Review data permissions, off-host snapshot use and account-wide quota scope
  before setting `RESEARCH_DATA_RIGHTS_VERIFIED=1` and
  `RESEARCH_BUDGET_SCOPE_REVIEWED=1`. Configure the existing `ODDS_API_KEY` only
  in the private worker Secrets. Existing quotas remain nine odds credits,
  six results requests and twelve bounded discovery reservations per UTC day.
* Only after the hosted preservation/restart checks and the reviews succeed,
  reconcile current usage through the existing operator procedure before
  releasing the remote hold. This change does **not** release it. Never reduce
  reservations, infer unknown usage or assert the account-scope review falsely.
* Enable `RESEARCH_WORKER_ENABLED=1`, dispatch **research** once, and inspect the
  committed heartbeat/readback/preview generation. Incomplete inputs should
  produce honest empty research. Only a genuine pregame record and later exact
  result can verify predictions/results, not a storage rehearsal.
* After that deliberate run succeeds, set `RESEARCH_SCHEDULE_ENABLED=1` to
  permit one scheduled run/day. Cron is **14:15 UTC**: **10:15 a.m. Toronto during
  daylight time, 9:15 a.m. Toronto during standard time**. GitHub schedules are
  best effort and may be delayed. At the 12-minute job maximum this schedule
  could use 372 runner minutes in a 31-day month, plus manual runs and other
  repositories' usage. Review total included minutes and billing controls first.

No research or schedule flag is enabled automatically. Stop by setting
`RESEARCH_WORKER_ENABLED=0` and `RESEARCH_SCHEDULE_ENABLED=0`; outstanding remote
reservations must not be reset or refunded after an interrupted job.

## Upcoming-game search across dates and sports

The dashboard uses a rolling **48-hour** window by default, not a today-only
calendar filter. `SLATE_WINDOW_HOURS` supports **1–168 hours** in preview Secrets
and private worker Variables. Match those values to inspect the same horizon.
Best Picks & Parlays displays the range in America/Toronto time. Existing model
input/future-horizon gates can still reject a fixture within this browsing window.

The worker now discovers **NBA, Premier League, MLB, Bundesliga and Ligue 1**
within that same window. It retrieves the existing soccer research targets
(EPL/Ligue 1 totals; EPL/Bundesliga BTTS) and NBA/MLB match-winner observations.
It rotates older-needed market scopes, stops at the existing nine-credit cap,
and skips discovery once allowance is gone. It does not spend on a broad prop
scan. Not every discovered fixture/market will receive odds within this budget.

Saved discovered fixtures stay visible even when no market was purchased, marked
as saved observations with original receipts. They are not current lineup/game
verification and cannot supply probabilities or betting recommendations.
Fresh Ontario prices, valid result inputs and existing model gates are still
required. NBA/MLB prices do not activate unsupported prediction models. No joint
probability, executable combined ticket, positive EV or profitability is invented.
