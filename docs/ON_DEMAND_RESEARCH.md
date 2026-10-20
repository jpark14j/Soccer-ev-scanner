# Find Best Bets Now — owner-requested research

Home now has **Find Best Bets Now**. The dashboard still reads a Supabase replica;
it never receives a service-role key, collects sports data directly or writes
authoritative research. An authenticated owner request dispatches the existing
private GitHub workflow. That workflow performs one fenced research cycle and
commits to the existing store. No Supabase migration or new database is needed.
The five pages/design remain unchanged.

The private workflow has **no scheduled trigger**. `RESEARCH_WORKER_ENABLED=0`,
`RESEARCH_SCHEDULE_ENABLED=0`, and `PAID_ANALYST_APPROVED=0` stay zero. The separate
manual permission defaults to zero too. Neither the button nor installation
releases holds, resets usage, approves a model or starts a workflow automatically.

## Remaining setup — only after provider/budget review

Current account-wide Odds API credits and permitted research/storage use must
be verified privately, including other consumers of the shared production key.
Current soccer-results access must also be established. The existing provider
hold is still active; its existing operator review/reconciliation procedure is
required before any live run. [Read-only provider-hold review](PROVIDER_HOLD_REVIEW.md)
locates that procedure and checks actual state without using sports API credits.
Do not assert review flags or release it as a
workaround. No real run or new recommendation is claimed by these offline tests.

The new Home control requires two private credentials the development environment
does not have. Keep both out of chat, source, screenshots and reports:

1. In GitHub account **Settings → Developer settings → Personal access tokens →
   Fine-grained tokens**, create a short-lived token for **only**
   `jpark14j/sports-ai-private-recovery`: **Actions: Read and write** and
   **Contents: Read-only** (plus default metadata access). No administration or
   Secrets permissions. Put it only in development Streamlit **Settings →
   Secrets** as `RESEARCH_MANUAL_GITHUB_TOKEN`. This token may dispatch private
   workflows; protect/revoke it like a password.
2. Generate a random 256-bit owner access code and its SHA-256 fingerprint
   privately. A browser-only option in the existing Supabase SQL Editor is:

   ```sql
   WITH token AS MATERIALIZED (
     SELECT encode(gen_random_bytes(32), 'hex') AS value
   )
   SELECT value AS private_owner_code,
          encode(digest(value, 'sha256'), 'hex') AS owner_hash
   FROM token;
   ```

   This read-only query initializes/writes no research records. Save the code
   in your password manager. Put only `owner_hash` in preview Secrets as
   `RESEARCH_MANUAL_OWNER_HASH`. The original code is entered only in Home →
   **Private research access**, never into the assistant/chat. Owner access lasts
   ten minutes; the input is cleared after submission. Use a generated code,
   not a memorable password.
3. Once the **existing** provider-permission/account-scope/hold reviews and the
   included GitHub Actions minutes review are complete, the owner may explicitly
   authorize `RESEARCH_MANUAL_ENABLED=1` in **both** preview Secrets and private
   repository Actions Variables. Keep automatic flags zero. The workflow also
   requires the existing `RESEARCH_DATA_RIGHTS_VERIFIED=1`,
   `RESEARCH_BUDGET_SCOPE_REVIEWED=1`, private `ODDS_API_KEY`, and the existing
   shared-state credentials; none is set by this implementation. Keep soccer
   results credentials only in their supported private Secrets. Configure the
   optional football-data.org integration only when its permitted use is reviewed.
4. Unlock Home and click **Find Best Bets Now** once. The button submits exactly
   one request, shows pending/running/failed status, and waits for a matching
   verified Supabase commit before saying results are loaded. An immediate reader
   sync after completion avoids waiting out the normal five-minute cache. A job
   success alone does not prove a forecast or qualified pick exists.

The deployed Git commit is checked against the private worker's literal reviewed
pin before dispatch and again in the workflow. If the hosting checkout has no
Git metadata, `RESEARCH_MANUAL_APP_COMMIT` can be set to the exact reviewed full
development SHA in preview Secrets. Update this optional value with every
reviewed deployment; mismatches block requests.

## Bounds, evidence and privacy

The same nine-credit daily odds cap, six results requests, twelve discovery
reservations, remote lease/fence and provider holds apply. Production use remains
outside the development ledger. Manual requests reuse identical observations for
at least 60 seconds rather than the old 30-minute retrieval cache; stale source
prices still fail the five-minute eligibility gates. Current model inputs and
model approval rules are unchanged. NBA/MLB may supply prices only; supported
soccer models need complete fresh reconciled results. No new model is approved.

Home separately shows supported model research and unmodeled observed-price
research, including feasible 2/3-leg combinations when available. Price-only
ordering is freshness/stable research ordering, not a statistical favorite or
positive-EV claim. Rejected/missing model numbers are withheld. Contradictions,
dependence warnings and operator restrictions use the existing selector. No
validated joint probability, actual combined ticket or parlay EV is inferred.
Only genuine pregame forecasts enter forward tracking; price-only candidates
are not retroactively recorded as predictions.

Dispatch tokens stay server-side. GitHub error bodies/redirects are not read or
followed. Unknown delivery is never automatically retried. Request status and
short-lived authorization live only in the browser session's server-side state;
closing the session can lose its progress view, while committed research remains
in Supabase. A five-minute session cooldown/poll throttle is not a global billing
control. Remote provider budgets and GitHub billing controls remain necessary.
Status polling does not collect sports data. No live dispatch was performed here.
