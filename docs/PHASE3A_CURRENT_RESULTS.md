# Phase 3A: optional current soccer results

Reviewed October 16, 2026, Ontario time. Starting commit:
`bbda4e3d0f8a5aca1d115cadb4a4758da8f26c48`. Development branch only;
Draft PR #1 remains draft and unmerged. No account, paid subscription, new odds
request, AI request or production configuration change was made.

## What is actually ready

An optional football-data.org completed-results integration is implemented and
disabled by default. Its software contract is tested with explicitly synthetic
responses. **No authenticated current-season response was available. No historical
gap was recovered and no new genuine current forecast or paper label was created.**
An account is necessary for this chosen integration; a free account alone is not
proof of complete results, suitable latency or commercial redistribution rights.

Three actual OpenFootball current-season files were re-read through the GitHub
connector at 18:43 Ontario time (22:43 UTC). No model input or ledger was replaced
with the audit responses. Only explicit `score.ft` arrays count as completed;
ambiguous top-level score arrays do not count as verified finals.

| League | Fixtures | Explicit finals | Latest final | Past fixtures without verified finals | Current forecast |
| --- | ---: | ---: | --- | ---: | --- |
| Premier League | 380 | 45 | 2026-09-20 | 15 | Blocked: stale/incomplete results |
| Bundesliga | 306 | 33 | 2026-09-20 | 12 | Blocked: stale/incomplete results |
| Ligue 1 | 306 | 41 | 2026-09-20 | 13 | Blocked: stale/incomplete results |

Same-day unplayed fixtures are not counted as past. La Liga and Serie A retain
their Phase 2 historical infrastructure; no additional models or current readiness
claim was added for them. They are supported by the new results adapter, after
the priority three have been verified, but have no new frozen forecasting model.

## Stage 1: sources and access evidence

| Source tested/reviewed | Coverage and delay evidence | Authentication, limits and gap recovery | Rights and decision |
| --- | --- | --- | --- |
| [OpenFootball](https://github.com/openfootball/football.json), actual en.1/de.1/fr.1 2026–27 JSON | Counts above; source still ends September 20. No update SLA | No account. Three manual connector reads this phase, zero app refresh calls. Existing bounded adapter remains unchanged. Did not recover gaps | Publisher CC0 dedication is not blanket clearance of third-party rights. Retained default; inadequate current results |
| [Football-data.org coverage](https://www.football-data.org/coverage), [pricing](https://www.football-data.org/pricing), [v4 match resource](https://docs.football-data.org/general/v4/match.html), [competition resource](https://docs.football-data.org/general/v4/competition.html) | Free listing includes EPL, Bundesliga, Ligue 1, La Liga and Serie A. Scores/schedules are delayed; the published free-plan description does not specify the delay duration. Exact current completeness is unverified | Registration/token required for matches. Free plan: 10 calls/minute. Explicit whole-season request is designed to include September/October, rather than a rolling three-day window. Direct unauthenticated match-page read did not yield a usable response; no authenticated call made. Actual recovery must be checked after configuration | [Terms](https://www.football-data.org/about) require attribution, confidential credentials, an application/domain-specific subscription and restrict referencing data after cancellation. No logos/photos imported. Preview use must be reviewed; resale, buyer transfer and commercial redistribution need separate confirmation. Optional implementation only |
| [OpenLigaDB directory](https://api.openligadb.de/getavailableleagues), [official project](https://github.com/OpenLigaDB/OpenLigaDB-Samples), [license page](https://www.openligadb.de/lizenz) | Public directory actually returned a 2026 Bundesliga entry with shortcut `bl1`. Listing is not completed-score coverage. Current `getmatchdata/bl1/2026` and numeric-ID match reads did not yield usable payloads in the web tool | No account for public API; no numerical service limit/SLA verified. Shell host not in this environment's allowlist; no bypass attempted. September/October recovery unverified | Homepage's ODbL claim needs attribution/share-alike and source-specific review; license page text was not readable here. Sample-code license does not license the database. Not integrated |
| Existing The Odds API scores | Existing provider documentation limits completed retrieval to three days, which cannot repair the older gaps on October 16 | Existing key; completed retrieval costs credits. **Zero new requests**; existing actual local odds budget remains 9/9 | Existing scope/settlement gates retained. No use as a historical gap filler |

The prior [source review](FREE_RESULTS_READINESS.md) also covers TheSportsDB's
development/production distinction and football-data.co.uk's limited intended
free use. Neither was newly queried or enabled here. No undocumented endpoint or
unauthorized scraping was introduced.

## Stage 2: adapter and reconciliation

`intelligence/current_results.py` implements:

- Fixed HTTPS host and allowlisted `PL`, `BL1`, `FL1`, `PD`, `SA` codes; one GET to
  `/v4/competitions/{code}/matches?season=2026`, without a status/date filter.
- Header-only `X-Auth-Token`; no query-string token, redirects, retries, raw body
  storage, exception text, credentials in repr or request logging.
- Six requests per UTC day per shared SQLite store, an atomic rolling 10/minute
  ceiling, six-hour success/failure cache and a 24-hour shared cooldown on 429.
  Provider/account limits outside this store still apply. Local caps are not
  durable across disk loss or a second deployment; inspect the provider account.
- One request per selected league on a cache miss. First three leagues: at most
  three requests for one pass, six for two passes/day. La Liga/Serie A share the
  same six-request budget. Missing enable flag, token or use review: zero requests.
- Strict full schedule size (380 or 306), balanced distinct home/away pairings,
  season/competition/stage/count checks and exact existing reviewed club aliases.
  No guessed numeric IDs or fuzzy team matching. Valid provider IDs bind to
  canonical identities and cannot silently change across snapshots. An unknown
  official club spelling blocks the snapshot pending reviewed mapping work.
- Only `FINISHED` regular-time integer scores with plausible completion/update
  timestamps enter completed data. Postponed, suspended, cancelled, awarded and
  in-play statuses remain explicitly unresolved; no fabricated score of zero.
- Append-only event observations and snapshot provenance: source IDs, exact UTC
  kickoff, original status mapping, receipt/update times, URL, terms and body hash.
  Score/date/identity conflicts, withdrawn finals and missing fixtures block use.

`intelligence/current_soccer.py` bridges valid observations to copies of the
existing frozen EPL/Bundesliga/Ligue 1 states. Every already-frozen current-season
final must match exactly. New prior-calendar-day finals update features, with
frozen calibration, model files, policies, evaluation reports and approval gates
unchanged. Adapter code and response hashes are recorded separately. A fresh
whole-season response containing unresolved fixtures cannot activate the bridge.
The keyed feed also requires the odds fixture's **exact kickoff**, not just date.

## Stage 3: current forecasts remain conditional

No genuine current forecasts are newly available. The optional bridge must first
pass real full-season access, alias, provenance, completeness and conflict checks;
source verification expires after six hours. Then all existing model sample,
21-day freshness, exact fixture, current CA-ON price and market gates still apply.
EPL supports BTTS and goals 2.5; Bundesliga supports BTTS; Ligue 1 supports goals
2.5. No in-game method or live feed is activated. Model outputs remain experimental,
unvalidated research, with no qualified betting picks, positive-EV or profit claim.
Failure while the optional feed is enabled blocks that feed's model path rather
than silently substituting old observations. With it disabled the original path
and its existing gates remain functional.

## Stage 4: forward tracking and durable storage

Forecasts are recorded only while the source odds are current and kickoff is in
the future; they are never backfilled from a historical test. Original forecast
and outcome rows are immutable. Keyed-provider outcome labels require exact
canonical home/away identity, date and the recorded kickoff, plus reconciled
completed results. Hit **and miss** labels stay visible and are not ticket
settlements, betting ROI or hypothetical wagers. This workspace genuinely has
**zero paper forecasts, zero paper outcome labels and no new published picks**.

Settings now offers a bounded JSON export of actual paper records and labels,
without caches, chat, backtests or credentials. It is an inspection/export format,
not a database restore endpoint. Download and retain it on your own device. For a
full consistent private SQLite backup, use the existing command from the repo:

```bash
python -m intelligence.cli backup --output work/private-backups/new-ledger.sqlite3
```

Copy the resulting backup off the host privately; never add it to Git. Reusing an
existing backup filename is refused. A backup on the same Cloud filesystem is not
off-host protection. Exports retain only what was present when prepared, are not
automatically refreshed, and do not prove that a user saved the download.

[Streamlit explicitly does not guarantee local file persistence](https://docs.streamlit.io/develop/concepts/connections/connecting-to-data).
Restart/redeployment survival is therefore **not verified**, and SQLite alone is
not a permanent commercial ledger. A user-owned free Supabase Postgres project
is a possible future off-host store; its [free project pausing](https://supabase.com/docs/guides/platform/free-project-pausing)
and [backup/export limitations](https://supabase.com/docs/guides/platform/backups)
require care and independent private exports. A migration requires an account,
append-only schema, access controls and a tested restore; none was created or
claimed verified. GitHub Actions artifacts expire and are not a permanent ledger.
No unsolicited account, storage subscription, background worker or public data
upload was enabled.

## Stage 5: preview and configuration

1. Open [your existing preview](https://soccer-ev-scanner-preview-jp.streamlit.app/).
   It must still use `development/verified-sports-intelligence` and `app.py`.
   Allow Community Cloud to rebuild after the branch commit. Production is separate.
2. Choose **Settings & Research Tools → Research tool: Settings → Current soccer
   results**. All four pages and existing tools remain. Without a token/flags the
   connection is disabled, its reason is visible, and the results refresh button
   is disabled. Preparing the paper export makes no API call.
3. If you choose to proceed, register yourself for the **Free** plan at
   [football-data.org](https://www.football-data.org/client/register). Do not select
   livescores, a trial or a paid add-on. Check the account's actual entitlement and
   terms for this preview's domain and intended analysis. Commercial resale and
   transfer to a buyer are not granted merely by adding a token.
4. In **this preview's** Manage app → Settings → Secrets, add the provider token as
   top-level `FOOTBALL_DATA_TOKEN`, privately. Never paste it into chat, GitHub,
   screenshots, logs or the assistant. Keep all existing Secrets. For a default
   disabled configuration, use these non-secret settings:

   ```toml
   FOOTBALL_DATA_ENABLED = "0"
   FOOTBALL_DATA_USE_REVIEWED = "0"
   PAID_ANALYST_APPROVED = "0"
   ```

5. Only after the account/use review, set `FOOTBALL_DATA_USE_REVIEWED = "1"` and
   `FOOTBALL_DATA_ENABLED = "1"` in preview Secrets. This is your declaration of
   a review, not a license certificate. No OpenAI key is needed. Save/restart the
   preview; do not edit production. Environment variables take precedence over
   Secrets. Keep the preview private until publication rights are established.
6. Select the first three results leagues and click **Refresh soccer results
   only** once. This does not retrieve sportsbook prices or increase odds limits.
   Inspect per-league `ok`, coverage, latest result, unresolved past count and
   checked time. An incomplete response or unknown alias must remain blocked.
   Do not repeatedly retry errors: they cache six hours; 429 pauses 24 hours.
7. After real coverage passes, the ordinary **Refresh analysis** uses those
   cached results with existing current Ontario odds, if available. Select the
   three leagues in the sidebar. Supported BTTS/goals-2.5 quotes may require the
   existing Advanced Markets tool. Any odds retrieval still obeys its original
   quota; **do not make extra odds requests when the allowance is exhausted**.
   Best Picks & Parlays separates research estimates from qualified picks.
8. Check **Performance Tracker → Prospective paper research**. Counts change only
   for genuinely recorded eligible pregame forecasts; later reconciled results
   may append labels. Zero is a valid result. Download private paper records
   before any reboot/redeploy.

Local verification and CI results are in [the verification matrix](VERIFICATION.md)
and [machine-readable evidence](evidence/phase3a-verification.json). The hosted
preview's rebuild, real token entitlement, actual provider delay, full-season
score recovery and off-host restoration remain unverified. This execution
environment also does not allow the new API hostname; it was not bypassed. No
change to Community Cloud network policy is implied by these local tests.

## Stage handoff and changed files

Stages 1–2: source review and optional adapter/bridge completed; current-data
verification awaits a user-created free account and permitted-use review.
Stage 3: synthetic contract tests prove the conditional path, **not** real current
forecasts. Stage 4: exact keyed-provider labels and paper export completed; no
real paper rows or verified hosted persistence. Stage 5: offline tests, compile,
startup and secret checks run; account-backed/hosted checks remain outstanding.

New modules: `current_results.py`, `current_soccer.py`, `current_results_ui.py`.
Routing/status changes: `app.py`, `pipeline.py`, `slate.py`, `multi_readiness.py`,
`research_state.py`, `workspace_ui.py`. Tracking/privacy: `processing.py`,
`persistence.py`, `analyst_config.py`. Tests: `test_current_results.py`,
`conftest.py`. Documentation: this guide, README, readiness review, verification
matrix and evidence JSON. Model/source snapshots, approval policies, navigation
registry and existing workflows remain unchanged.

Additional cost: none incurred; no paid service enabled. Next step: configure and
verify the free results feed, inspect real gaps and exact aliases, then allow
research forecasts only where all unchanged gates pass. Do not add more models
to compensate for missing current outcomes.
