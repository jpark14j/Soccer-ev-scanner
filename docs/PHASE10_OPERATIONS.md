# Phase 10 — operational research, honest readiness

For the bootstrapped development preview's request-free checks, private worker
setup and future-date multi-sport search, use [HOSTED_ACTIVATION.md](HOSTED_ACTIVATION.md).
Its staged setup keeps all provider requests held while hosted storage is tested.

Continues `f3b69232e85e26b08f141ce2cf6a5a3682a0d200` on
`development/verified-sports-intelligence`, Draft PR #1 only. The interrupted
uncommitted work was recovered, inspected and retained; nothing was reset.
No main/production deployment, production Secrets, account, paid service,
subscription, OpenAI request, sportsbook/results request or remote service was
activated during development. Existing frozen models, data manifests, historical
reports and old tests are preserved.

## Baseline gaps and delivered architecture

The Phase 7–9 snapshot adapter was a backup, not a shared budget authority.
An ephemeral GitHub runner could not safely reuse it while Streamlit wrote its
own state. The new **optional single-writer mode** resolves that software gap:

1. A Postgres control row fences overlapping workers. Every provider reservation
   commits remotely **before** HTTP, independently of SQLite snapshots. A crash
   cannot restore spent allowance. A replica cannot request data or publish.
2. The worker downloads the current committed SQLite head into a private new
   file, verifies hashes/model assets, hydrates newer remote budget reservations,
   runs the existing frozen research/forward pipeline, prepares publications and
   performs results/learning work without Streamlit.
3. A fenced compare-and-swap transaction commits the compressed snapshot,
   immutable publication receipts, successful run identity and heartbeat.
   A missed pregame deadline rejects the commit. The last two successful
   snapshots remain available; failures do not replace the last success.
4. Streamlit downloads a verified **read replica** when explicitly configured.
   State reads are cached five minutes. Sports-provider requests remain absent
   from page loads, filters and local chat. Local diagnostic computations cannot
   upload, spend, publish or become authoritative new predictions.

This is **single-writer snapshot synchronization**, not transactional multi-writer
SQLite or continuous replication. Postgres is the authoritative control/budget
store. A local prepared recommendation is published only once its pregame
commit receipt exists. SQLite backup/restore remains a separate disabled tool;
it cannot overwrite this head or release remote budget holds.

Implementation: `migrations/010_shared_research.sql`, `shared_state.py`,
`background.py`, `publication_journal.py`, `learning.py`, `automation_ui.py` and
`config/continuous_learning_policy.json`, with existing adapters/UI integration.

## What can run

| Capability | Readiness | Evidence / remaining limit |
| --- | --- | --- |
| Historical data/models retained | VERIFIED WORKING locally | Frozen artifacts and existing historical tests preserved; no reset/replacement |
| Supported pregame research | VERIFIED WORKING in deterministic replay | EPL BTTS/totals 2.5, Bundesliga BTTS, Ligue 1 totals 2.5; real current inputs/odds remain essential |
| Overall single/parlay comparison | VERIFIED WORKING locally | Explicitly declines an overall winner when joint probability/pricing are incomparable; separate singles and 2/3-leg research remain |
| Controlled shared budgets/fences | VERIFIED WORKING in local Postgres | Shipping SQL migration, concurrency, lease/CAS and crash tests; hosted access still needs configuration |
| Independent research worker | IMPLEMENTED — NEEDS CONFIGURATION | CLI and branch-only GitHub dispatch job; no external schedule activated |
| Shared off-host persistence | IMPLEMENTED — NEEDS CONFIGURATION | Checksummed fenced commits and replica readback; no real Supabase account/read-write/redeploy verified |
| Immutable published research | VERIFIED WORKING with synthetic records | First contract/model combination across prices/sides; genuine records need pregame remote receipts |
| Automatic result reconciliation | IMPLEMENTED — NEEDS CONFIGURATION | Existing exact football-data.org matching reused; postponements/missing/conflicts block settlement; no account/token configured here |
| Paper performance | VERIFIED WORKING with synthetic records | Fixed one-unit observed-price single score contracts; losses, ROI and drawdown retained; no actual betting profits |
| Automated challenger fitting/testing | VERIFIED WORKING with synthetic evidence | Locked post-protocol training/calibration, actual future pregame challenger records, fixed prospective cohort; real sample absent |
| Team/player/joint model improvements | PARTIALLY IMPLEMENTED / BLOCKED | Existing goal models and coherent joint research retained; this phase adds calibration challengers, not unsupported NBA/MLB/player models |
| Model promotion/rollback | PARTIALLY IMPLEMENTED | Existing reviewed activate/suspend/rollback safeguards retained; no automatic approval; challenger report prepares review only |
| Four pages/local assistant | VERIFIED WORKING locally | Existing navigation/tools retained; published research, learning and automation statuses added |
| Recurring hosted operation / commercial rights | BLOCKED pending external verification | No scheduled run or hosted durability claimed; licensing and shared-provider account scope must be resolved |

“Verified locally” is not a claim of real provider coverage, genuine new forward
records, live hosted persistence, accuracy improvement or profitability.
No model was replaced or approved. No current joint probability or combined
bookmaker ticket price was validated. NBA/MLB/props, La Liga and Serie A remain
blocked by their existing data/competition-specific evidence requirements.

## Request and storage policy

* Odds: nine credits per UTC day across this **managed** worker authority;
  results: six requests/day; free discovery is separately bounded to twelve
  requests/day. Each retry reserves again; uncertain reservations are never
  refunded. Unexpected/unknown provider billing holds subsequent requests.
  Reservations pause within one minute of UTC midnight. Server time owns resets.
* The worker queries supported pregame soccer totals/BTTS, not a broad unsupported
  prop scan. Discovery never substitutes invented fixtures. When odds allowance
  is unavailable, it skips discovery and odds but still performs separately
  permitted results and local evaluation.
* Results retain the existing six-hour cache, exact aliases, full-season checks,
  successful snapshot journal and conflict gates. Six daily requests cannot
  guarantee fresh coverage of every league all day. Odds freshness remains five
  minutes; stored publication prices are **historical**, not current offers.
* The current production app and production Telegram workflow are outside the
  new development ledger. **Using the same key in an uncontrolled production
  consumer cannot guarantee an account-wide nine-credit limit.** Activation
  requires reviewing that scope (`RESEARCH_BUDGET_SCOPE_REVIEWED`); this phase
  does not change production to resolve it or create another free account.
  Do not assert the review flag if external concurrent spending is unresolved.
* Shared snapshots are bounded to 64 MiB uncompressed / 4 MiB compressed. Two
  successful compressed heads are retained; journal records remain inside every
  subsequent head. Capacity checks stop new work before the bound is approached.
  This is not unlimited free storage: source-history growth eventually needs a
  reviewed migration/archival design. No immutable records are silently deleted.
* A 15-minute database lease plus generation fencing prevents stale writers
  committing. GitHub jobs time out after 12 minutes. An interrupted job can leave
  an expired-running heartbeat; the next invocation reconciles saved pending
  events. Missed pregame publications are never reconstructed in hindsight.

## Published results and scientific learning

The independent forecast index records every eligible first contract; the new
publication journal separately records selected single/2-leg/3-leg research.
Equivalent book observations/opposing sides cannot multiply independent samples.
Original leg probabilities, ranges, versions, source fixtures, prices/times,
ranking and limitations are immutable. Actual remote publication receipts supply
commit chronology. Prepared local entries alone cannot produce published ROI.

Reconciliation uses verified exact source finals, not scores guessed from odds.
BTTS/totals use the same score-contract settlement functions. Logical parlay
win/loss/push/partial states are recorded, without multiplying probabilities or
inventing operator payouts. Missing/postponed outcomes stay pending; conflicting
evidence quarantines records and preserves earlier evidence. Voids require
operator adjudication and are not inferred from a score.

Paper money uses a disclosed one-unit **single score-contract** stake at the
observed publication price. It is not a placed bet or operator settlement.
Parlays have **no paper money return or EV** without genuine applicable combined
pricing/rules. Predictive forward Brier/log loss/calibration remain separate.
No historical backtest is imported as new live evidence. A short win-rate
interval is descriptive and does not resolve shared-game dependence.

The worker locks the learning policy before eligible future observations. Once
300 fully labeled training and 200 subsequent calibration forecasts exist in a
matching model/contract/protocol scope, each with at least 30 UTC date blocks,
it can fit a monotone Platt calibration challenger. Identity/mapped blends are
chosen only on calibration dates. Missing earlier labels prevent settled-only
selection. Frozen historical champions remain intact.

The candidate is immutable before its next-UTC-day test starts. Challenger
probabilities must actually be recorded before kickoff; no retrospective test
predictions are inserted. One fixed **180-day** future cohort requires 200
forecasts and 30 date blocks, complete labels, paired Brier/log-loss comparisons
and calibration reporting. Missing source forecasts or evidence blocks a claim.
No repeated test tuning, automatic activation or gate changes occur. This is one
candidate per frozen scope: another protocol/candidate requires reviewed design,
not unattended repeated significance fishing. Team-strength/Poisson/DC refits and
joint improvements beyond existing research still require their own legitimate
data/protocol. No real learning improvement has yet been established.

## One consolidated setup checklist — optional, not performed here

1. **Resolve permissions and budget scope first.** Review data-provider terms
   and off-host storage/privacy for your actual use. Free access does not imply
   commercial redistribution rights. Confirm that other consumers of the same
   odds/results accounts will not spend outside the managed allowance. Leave
   everything disabled if this cannot be established without a separately
   authorized production change. Review current free-tier limits and set provider
   billing controls; do not purchase or enable paid overages.
2. **Create your own free Supabase project**, if you choose, and run
   `migrations/010_shared_research.sql` in its SQL editor. It creates a held
   single-writer authority with RLS and no public table access. Generate a private
   high-entropy reader token locally (for example `secrets.token_urlsafe(32)`).
   Put only its SHA-256 hex digest into `research_control_state.reader_hash`;
   keep the original only in Secrets. Use legacy **anon JWT for the preview** and
   **service-role JWT for the independent worker only**. Never put the writer key
   in the public/client UI or commit it. This adapter intentionally does not
   accept arbitrary hosts or new-format keys without a reviewed migration.
   Set the digest with `UPDATE public.research_control_state SET
   reader_hash='REPLACE_WITH_64_HEX_SHA256_DIGEST' WHERE id;` in your private SQL
   editor. The digest is not the raw token.
3. **Bootstrap the inspected existing preview store** from a trusted private
   backup, preserving its identity/history. On your trusted machine set
   `RESEARCH_SHARED_STATE_ENABLED=1`, `RESEARCH_STATE_USE_REVIEWED=1`,
   `RESEARCH_STATE_URL` (official HTTPS project origin), and server-only
   `RESEARCH_STATE_SERVICE_KEY`. Run
   `python -m intelligence.background --bootstrap PATH_TO_EXISTING.sqlite3`.
   It performs no sports requests; verify `shared_readback_verified=true`.
   It refuses an existing remote head and never releases the request hold.
   Do not replace a lost store with a fabricated historical record.
4. **Reconcile usage before releasing the hold.** In the private SQL editor,
   inspect `research_provider_budget` and provider dashboards for the current
   **UTC** day. In one transaction lock `research_control_state FOR UPDATE`,
   upsert each day's `odds` and `results` usage using
   `GREATEST(existing_used, reviewed_used)`, append an operator-review entry to
   `research_control_audit`, and set `held=false`. Reviewed counts must include
   other known consumers and never reduce known reservations. If usage is
   uncertain, reserve the full nine/six and wait for the next UTC day; if the
   account scope itself is unresolved, **keep the hold**. This step cannot be
   performed through chat or by restoring a local SQLite backup.
   A conservative ready-to-review SQL transaction (after account-scope review)
   is below. It reserves the **entire current-day allowance**, so no new sports
   calls are possible until the next UTC day. Do not reduce these values without
   verified account usage, and do not run it while other spending is uncontrolled.

   ```sql
   BEGIN;
   SELECT id FROM public.research_control_state WHERE id FOR UPDATE;
   INSERT INTO public.research_provider_budget(day,provider,used) VALUES
     ((now() AT TIME ZONE 'UTC')::date,'odds',9),
     ((now() AT TIME ZONE 'UTC')::date,'results',6)
   ON CONFLICT(day,provider) DO UPDATE
     SET used=GREATEST(research_provider_budget.used,excluded.used);
   INSERT INTO public.research_control_audit(action,details) VALUES
     ('operator_budget_review',
      '{"scope_reviewed":true,"policy":"full current-day allowance reserved"}'::jsonb);
   UPDATE public.research_control_state SET held=false WHERE id;
   COMMIT;
   ```
   If the chosen bootstrap file itself has the existing restored-backup recovery
   hold, reconcile that local hold with the documented
   `python -m intelligence.cli review-recovery-budget` procedure **before**
   bootstrap; a remote release does not bypass a local recovery hold.
5. **Configure only the separate preview's Streamlit Secrets**:
   `RESEARCH_SHARED_STATE_ENABLED="1"`, `RESEARCH_STATE_USE_REVIEWED="1"`,
   `RESEARCH_STATE_URL`, `RESEARCH_STATE_READER_KEY` (anon JWT),
   `RESEARCH_STATE_READ_TOKEN`, plus existing source-use flags as appropriate.
   Keep `PAID_ANALYST_APPROVED="0"` and `RESEARCH_WORKER_ENABLED="0"` there.
   A configured preview reads the shared committed head, not a new provider scan.
   It needs **no service-role key**. Reboot only the preview. Verify the saved
   generation in Settings & Research Tools → Research Operations.
   `config/shared_state.example.toml` provides safe disabled defaults to merge
   into the preview's existing Secrets; do not replace production or discard
   unrelated existing preview settings.
6. **Configure worker-only GitHub repository settings**, after the previous
   checks: Secrets `RESEARCH_STATE_SERVICE_KEY`, existing `ODDS_API_KEY`, and
   optional `FOOTBALL_DATA_TOKEN`; Variables `RESEARCH_STATE_URL`,
   `RESEARCH_SHARED_STATE_ENABLED=1`, `RESEARCH_STATE_USE_REVIEWED=1`,
   `RESEARCH_DATA_RIGHTS_VERIFIED=1`, `RESEARCH_BUDGET_SCOPE_REVIEWED=1`.
   For current soccer results, obtain your own free **football-data.org** account,
   confirm its competitions/terms, and set `FOOTBALL_DATA_ENABLED=1` and
   `FOOTBALL_DATA_USE_REVIEWED=1`. Configure tokens privately, never in chat.
   The three target leagues can consume three results requests per cache-miss
   cycle, bounded by six/day. No key/account is configured by this development.
   Set `RESEARCH_WORKER_ENABLED=1` only when ready for the first deliberate run.
7. **Verify one explicit development run**. The already-existing default-branch
   workflow `telegram_alerts.yml` supports a dispatch with the explicit ref
   `development/verified-sports-intelligence`; its new development-only job has
   read-only repository permissions and no Telegram/deployment/repository-write
   steps. Run `gh workflow run telegram_alerts.yml --repo
   jpark14j/Soccer-ev-scanner --ref development/verified-sports-intelligence` from
   your securely authenticated CLI. Verify the development ref/job in Actions,
   a new remote generation/heartbeat and readback, then the same generation in
   preview. A real pregame forecast/publication and later exact result are needed
   to verify the full live cycle. Re-run the same hourly slot to confirm no
   duplicate work. No automatic recurring schedule is inferred from this run.
   GitHub documents [manual dispatch and selecting a non-default ref](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).
8. **Schedule only after that verification**. GitHub cron uses the default
   branch; changing main is not authorized. The included
   `deploy/research.crontab.example` instead dispatches the development ref from
   an existing always-on machine with `gh` securely authenticated, twice daily
   at 10:17/16:17 UTC (06:17/12:17 Toronto EDT; 05:17/11:17 EST). Verify your
   scheduler's UTC handling, executable path, repository Actions allowance and
   spending controls first. If no independent scheduler exists, operation is
   **manual dispatch, not unattended**. No external account/scheduler was created.
   Inspect heartbeat/missed-run status after leaving Streamlit closed. Verify a
   preview reboot can read the same publications and budgets. Free service
   pausing, network failure and delayed GitHub jobs remain possible.

## Preview verification without activation or spending

Open https://soccer-ev-scanner-preview-jp.streamlit.app/ after its development
rebuild (`app.py`). Leave paid AI and all new flags at zero. Four pages and the
local assistant remain available without Supabase. Dashboard explains when an
overall winner cannot be established; existing best singles/parlays remain.
Performance Tracker begins with Published Research & Paper Performance and AI
Learning Status; real zero-data states are expected. Settings & Research Tools →
Research Operations shows Automation Health and missing setup. Page/filter/local
chat checks make no sports requests. Do not press a provider refresh just to test
layout. Original published-price history must not be read as a current offer.

Tests include real **local Postgres** execution of the shipping control migration,
independent-process SQLite readback, provider/HTTP mocks, synthetic publication
losses and prospective challenger data. These are software integration tests,
not proof of hosted Supabase, a recurring schedule, real new forward results or
profitable models. Exact final local/CI counts are recorded after verification in
the PR/checkpoint. The final local run passed **559 tests**, including **25 new
tests**. The 38 pre-existing test files and seven frozen research asset files
are byte-for-byte unchanged. Compilation, dependency consistency, whitespace
and configured-secret scans pass. Isolated Streamlit startup returned HTTP 200
`ok` on port 8516 with credentials removed, paid AI/new integrations disabled
and the local odds cap zero. Public hosted-preview access remains subject to the available
environment; inability to inspect it is not a claim that the preview is down.
