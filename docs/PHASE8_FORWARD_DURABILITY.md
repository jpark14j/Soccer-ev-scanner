# Phase 8 — prospective evidence, reliability and optional private recovery

This increment extends the existing paper/registry/storage infrastructure. Legacy
forecasts are not rewritten or backfilled into a new independent sample. No
model is approved, no current data is fabricated and no paid service is enabled.

## Prospective records and exact outcomes

`forward_testing.py` adds an immutable evaluation index beside the existing paper
ledger. The pipeline locks a versioned policy **before** inference. Forecasts
retain exact sport/league/event/teams/kickoff/contract, model version/evidence,
actual forecast and recording times, estimate/range, source and input hashes,
freshness, observed price if current, baseline and ranking version. Code and
policy hashes are part of the protocol lock. Post-lock changes create another
cohort rather than retroactively changing the first prediction.

One first pregame event/contract/model/protocol decision counts across books,
opposing sides and input refreshes. The canonical side is preferred when it was
observed; the retained price is selected before the result. Complementary
probabilities must reconcile. All supported eligible forecasts are eligible for
recording, not only top-ranked or eventually winning selections. Current support
is the unchanged frozen soccer binary models with exact fresh accepted source
proof. Unsupported partial-contract binary probabilities and NBA/MLB guesses do
not enter this forward sample.

The actual prediction/input times must precede recording and kickoff. A
previously computed genuine forecast may be recorded without a currently valid
price, but has no price-based return attached. Records made without a prior
protocol lock remain inspectable and do not count as independent confirmation.
No historical shadow/backtest record is imported as a prospective observation.

Reconciliation uses accepted football-data.org full-season snapshots, exact
provider fixture/team identities, original kickoff, completed regulation-score
scope and completion/receipt chronology. It makes no request. Missing,
postponed or rescheduled fixtures remain pending. Conflicting results quarantine
the affected record without rewriting its forecast or previous label. A scoped
research hold prevents that model/contract being surfaced while the conflict
needs review. Registry/quality changes invalidate cached inference across
sessions without odds calls.

Losses remain in the record. Binary target Brier/log loss are separate from
ticket outcomes. Source-score settlement uses the existing full/half/push
fraction arithmetic; hypothetical one-unit return is
`win_fraction × (decimal_odds − 1) − loss_fraction`. Current frozen forward
models support binary contracts; the generic arithmetic is tested for pushes,
half-wins and half-losses without inventing models for those contracts. Any
reported return is a **score-contract scenario**, not an accepted ticket,
confirmed operator void treatment, executable ROI or actual profit.

## Reliability scorecards

Each sport/league/market/line/model/evidence/protocol scope has separate evidence.
The five display states are Experimental, Under forward evaluation, Eligible for
approval review, Approved and Suspended. The new index normally starts empty or
under evaluation. It never activates a model. Reviewed registry actions remain
explicit and retain all existing validation/licensing/market requirements.
An eligible prediction-model review is distinct from a current approved betting
opportunity, which still needs valid executable prices, value and risk gates.

The predeclared `forward-evaluation-1` policy includes:

- 95% confidence planning and five-percentage-point calibration precision.
- One-percentage-point Brier improvement as a planning effect, 80% power and
  assumed paired-difference SD 0.25.
- Actual paired UTC-day-cluster intervals against the **pre-recorded frozen
  calibration-period constant baseline**, not a silently substituted price.
- Calibration gap intervals across ten predefined bins; multiplicity adjustment
  across those bins; no gap interval when dated support or outcome variation is
  inadequate. Nominal bootstrap coverage still has limitations.
- Fixed 30-day prospective cohorts and at least two completed calendar cohorts
  for stability review. Eligibility uses only fully labeled completed cohorts;
  pending outcomes block settled-only review. Cohort outcomes are never invented
  before time elapses. Multiple cohort looks still need independent review of
  sequential-testing effects; this diagnostic never automatically approves.

The IID worst-case proportion plan is 385 observations for ±5 points. The paired
Brier plan is approximately 4,906 observations with the stated variance/effect.
These are **planning approximations, not automatic approval thresholds**. They
can underestimate information needed under dependence. Existing minimum
requirements are retained; actual interval precision, improvement, calibration,
source integrity and time stability must pass before technical review eligibility.
No test selects an easier threshold to produce approval.

Reports show Brier/log loss, paired differences, calibration, dated block/sample
counts, grouping and descriptive stability. Intervals are withheld below 30
dated blocks. A worse-than-baseline completed recent cohort raises a review
warning. Result-proof failures create a hold; an explicit reviewed registry
suspension disables matching research and does not fall back to an older model.
Champion lookup now scopes the league; an ambiguous sport/market lookup cannot
silently use another league's approval.

Blocks need not be independent across days; shared models, rare outcomes,
bootstrap precision and optional stopping remain concerns. The database is
self-recorded, not externally timestamp-certified. External verification and
human review remain necessary. No short winning streak produces approval. No
model in this project has acquired genuine independent approval this phase.

Performance Tracker's **Prospective paper research** tab leads with the new
forward scorecards. The legacy paper log remains below and can overlap; counts
must not be added. Backtests and published hypothetical records stay separate.

## Durable storage: implemented option, not verified hosted persistence

SQLite backup/reopen on the same disk is already supported. This phase adds an
optional manual Supabase **private Storage** adapter using documented REST
operations. It remains disabled and unconfigured. No external account, trial,
subscription or upload has been created or activated.

Reviewed October 17, 2026:

- [Official pricing](https://supabase.com/pricing) lists a $0 plan, 1 GB file
  storage and 5 GB egress, with inactivity pausing after one week. Automatic
  database backups are not included. Check the actual plan/terms before setup;
  these are not unlimited storage or production availability guarantees.
- [Standard uploads](https://supabase.com/docs/guides/storage/uploads/standard-uploads)
  and [access control](https://supabase.com/docs/guides/storage/security/access-control)
  document uploads/private access. This adapter verifies that the bucket is
  private, never produces a public/signed download link and refuses redirects.

One explicit upload attempt per UTC day per store, maximum 20 MiB, performs three
bounded requests: bucket-privacy verification, upload without overwrite, and
authenticated checksum readback. Failures do not infer success and do not cause
automatic retries. HTTPS origins are restricted to a normal official project
hostname. Raw provider exceptions, keys and response bodies never enter reports.
Backup credentials are also covered by chat redaction and input rejection.

Snapshots preserve SQLite forecasts, labels, results, registry/audit/budget data
and a versioned copy of the frozen model/evaluation/policy assets. Asset writes
are checkpointed into the portable file; live backup handles are closed. Tests
found and prevented missing asset writes left in a WAL sidecar. Snapshots have
private permissions and content-addressed names. Successful receipts prove a
specific byte roundtrip only, not continuous availability, provider retention or
redeploy recovery. Real hosted upload/readback/restore remains **untested** here.

Restore verifies a bounded download, checksum, SQLite integrity/foreign keys and
required tables, then creates a **new file only**. It never replaces the active
database or source models. It appends a provider-request recovery hold, which
persists across UTC resets: a stale snapshot must not reset request allowances.
An explicit operator usage review must preserve/maximize known used budgets
before a deliberate migration. Concurrent old/new deployments still do not
share an atomic quota ledger. Therefore online/background workers remain hard
disabled even if the old readiness environment flags are set. Manual capped
refreshes remain available in a normal non-restored preview store.

## Optional setup later — no credentials in chat

1. If desired, create your own **Free** Supabase project and review its privacy,
   data location, retention, licensing and limits. Do not enable a trial, paid
   tier or billing upgrade. No account setup was performed in this work.
2. Create a private bucket named `research-private`. Do not make it public or
   add anonymous access policies. The adapter verifies the privacy setting.
3. Configure only the separate preview's Streamlit Secrets. The supported key
   format is the server-only legacy `service_role` JWT from your project; it has
   broad project access, must stay server-side and must never be pasted in chat,
   GitHub, reports or browser fields. Do not substitute an unrelated key.

```toml
RESEARCH_REMOTE_BACKUP_ENABLED = "0"
RESEARCH_BACKUP_USE_REVIEWED = "0"
RESEARCH_BACKUP_URL = "https://<project-ref>.supabase.co"
RESEARCH_BACKUP_BUCKET = "research-private"
RESEARCH_BACKUP_SERVICE_KEY = "<server-only legacy service_role JWT>"
PAID_ANALYST_APPROVED = "0"
```

4. Leave both backup flags `"0"` until you deliberately authorize the private
   transfer and confirm the free plan/permissions. Later, setting both to `"1"`
   enables the explicit button in **Research Operations**. Merely opening a page
   or reading configuration never uploads anything. Keep older snapshots outside
   the ephemeral host, inspect your provider storage usage and stay within its
   free limits; this application does not buy more space or delete your history.
5. Use **Create private off-host snapshot · explicit upload** once, or run
   `python -m intelligence.cli backup-remote` in a securely configured environment.
   Keep the nonsecret object reference/receipt privately off-host. Successful
   readback does not yet demonstrate a post-redeployment restore.
6. Test a restore separately with
   `python -m intelligence.cli restore-remote --object <object-reference> --output data/private-restored.sqlite3`.
   Inspect records, model assets and request budgets before considering any
   migration. No active app/store switch is automatic.
7. Only after personally reconciling actual provider usage, an operator can use
   `review-recovery-budget --odds-used <0-to-9> --results-used <0-to-6> --reference <https-review-reference>`
   with `INTELLIGENCE_DB` pointing to the restored file. This is an attested
   operator review, not an API verification. It never decreases stored usage.
   The action is unavailable to chat. Without a review the hold remains active.

Shared durable primary storage, atomic cross-host budgets, scheduler support,
independent timestamp certification and off-host restore verification are still
operational blockers. The adapter is a practical optional recovery path, not a
claim that Community Cloud records now survive redeployments.
