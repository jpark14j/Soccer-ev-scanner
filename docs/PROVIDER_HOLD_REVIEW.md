# Provider hold: read-only readiness review

The existing operator procedure is in **PHASE10_OPERATIONS.md → step 4**.
Only an operator in the private Supabase SQL editor can release the hold; the
app, manual worker and read RPC cannot do it. Rotating the odds key resets
neither account usage nor the development ledger.

The owner has confirmed data-use, shared-budget and included Actions reviews.
The remaining check is the actual hosted ledger/control state and worker
configuration. No sports request is needed for that check.

**One next action:** in the private repository, **Actions → Development research
worker → Run workflow → operation `hold-review`**. Request ID and expected app
commit inputs can remain blank for this read-only operation. It uses the existing
state connection and receives only booleans about sports-secret presence, not the
odds/results keys. No new credentials or storage verification run are required.

The report reads the hosted state once and restores the verified snapshot into
a temporary query-only file. It checks the expected store, local recovery hold,
writer lease, saved/remote current-UTC-day reservations, actual private review
flags, manual enable flag and whether source Secrets are present. Saved results
receipt status is separate from a model-readiness or provider-access test.
No records, budgets, holds, snapshots or configuration are changed. It makes
zero sports-provider and paid-AI calls. The report never prints credential values,
raw service URLs, reader fingerprints or raw historical data.

If the observed state permits preparation, the report includes a **proposal**
for the existing SQL-editor reconciliation. The proposal deliberately contains
`release_approved := false` and is not executed by any code path. It requires
explicit operator approval before use and refuses stale reviews, changed UTC
day, changed generation/checksum/store, an active writer, or unreconciled charges.
It only preserves/increases reservations with `GREATEST`, appends the operator
audit entry and changes the remote hold. It never edits a forecast or snapshot.

The default proposal conservatively reserves all **9 odds / 6 results / 12
discovery** slots for the current UTC day. It therefore cannot permit a same-day
research request. A first run must wait until the next UTC day while external
account credits remain sufficient. An immediate same-day reconciliation needs
verified exact usage, not an assumption of zero. Unknown account usage or unknown
provider charges must not be guessed away. This review supplies no new release
RPC or automatic approval mechanism.

Home previously refreshed an open view only on snapshot-generation changes.
Hold, reservation and worker-status changes do not always advance that generation.
The view now notices those control changes at its existing five-minute read
interval, without treating server/read timestamps as new data or spending sports
credits. Thus a separately approved release will not leave an open page stuck on
the old hold indefinitely. Any optional fixed preview app-revision override must
still match the reviewed deployment pin.
