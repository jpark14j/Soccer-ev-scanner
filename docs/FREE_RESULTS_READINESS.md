# Free Premier League current-results readiness

**Phase 3A follow-up:** a secure, disabled-by-default football-data.org adapter and
frozen-model bridge now exist. Actual authenticated current coverage remains
unverified and all current gaps persist. See the [setup, source evidence and
preview guide](PHASE3A_CURRENT_RESULTS.md); the review below records the earlier
selection state, not a claim that its integration is still absent.

Reviewed October 16, 2026 (Ontario time). No account was created, token requested,
subscription purchased, paid endpoint enabled or odds credit cap increased.
Free access and public reachability do not automatically grant commercial rights.
The objective is a complete reliable result target, not replacing gaps with zeros.

| Source | Rights/access | Coverage, delay and identifiers | Decision / limitation |
| --- | --- | --- | --- |
| [OpenFootball JSON](https://github.com/openfootball/football.json) | Publisher CC0 dedication; no account. Grant is not blanket third-party rights clearance | EPL seasonal home/away pairing + exact source date; explicit team aliases. Community input; generated-file time is not score recency and no completeness SLA exists | Existing adapter retained. Re-read current JSON: 45 scored games, latest September 20; 15 older fixtures unscored. Not adequate for current forecasts |
| [footballcsv/england](https://github.com/footballcsv/england) and [upstream Football.TXT](https://github.com/openfootball/england) | Publisher public-domain dedication, no account | Export/shared upstream, seasonal team pairing/date rather than an interchangeable provider event ID. No verified lower-latency independent source | Mirror does not establish independent confirmation. Current CSV path was unavailable; upstream had the same gap in the preceding audit. Not used to fill scores |
| [OpenLigaDB official project](https://github.com/OpenLigaDB/OpenLigaDB-Samples), [service](https://www.openligadb.de/), [licensing](https://www.openligadb.de/lizenz) | Public no-account API; homepage states database data uses ODbL. Do not confuse sample-code Apache license with data rights | Community-maintained leagues; numeric league/team/match IDs and match dates. Homepage lists EPL 2026/27, but complete current fixture/results payload and actual delay could not be verified here | Promising candidate, **not integrated/activated**. Runtime host is outside this environment's allowed destinations and web reads did not yield a usable EPL payload/license text. Need exact league identification, completeness/conflict testing and ODbL attribution/share-alike obligations reviewed before mixing databases or commercial redistribution |
| [Football-data.org free plan](https://www.football-data.org/pricing), [API documentation](https://docs.football-data.org/general/v4/competition.html) | Free plan requires registration/authentication for EPL matches. No account exists; none created. Commercial/redistribution terms still need review | Listed free tier: 12 competitions, delayed scores/schedules, 10 calls/minute. Competition/team/match IDs; completed status and explicit score periods need reconciliation | Not enabled. No promise of historical gap repair, actual delay or production data rights without account-level verification |
| [TheSportsDB API](https://www.thesportsdb.com/api.php), [current terms](https://www.thesportsdb.com/docs_terms_of_use.php) | Official endpoints allow development lookup; production-key and app-store rules differ, API resale needs permission. Artwork permissions are separate | Crowdsourced event/team IDs and dates. Free access does not establish complete EPL results or an update guarantee; dedicated production key/V2 features are premium | Not enabled. No new paid key, use of a shared development key as a production credential, or assumption of commercially cleared data |
| [Football-data.co.uk policy](https://football-data.co.uk/contact.php) | Free files intended for personal betting/academic use with limited automated download; no general commercial training rights assumed | EPL CSV dates/team labels and scores; lacks interchangeable provider event IDs. Policy allows at most twice-weekly automated download for its intended free use | Existing personal feed remains disabled. Not imported to unblock this commercial-intent product |
| [Existing The Odds API scores](https://the-odds-api.com/liveapi/guides/v4/#get-scores) | Existing authorized credential, existing account rights only. Completed-event retrieval reserves 2 credits within the same cap | Provider event IDs match odds IDs. Documented completed window is at most 3 days; score coverage is sport-specific | Existing capped result handling retained. Cannot recover September / October 10–12 gaps on October 16 from this window; no extra requests or cap change made. Soccer score-period/operator scope still needs verification |

The current OpenFootball JSON was read again through the GitHub connector during
this phase, not inferred from a file-modification time. Past missing dates:
September 5 (2), September 12 (2), September 20 (1), October 10 (6), October 11 (3),
October 12 (1). Future fixtures are not classified as missing completed results.
The frozen historical evaluation and fitted artifact were not rebuilt or tuned.

No alternative met all of account-free access, verified adequate current coverage,
reviewed rights and tested runtime reconciliation during this phase. This is a
verification limitation, not a claim that no such service exists. The practical
next step is to verify OpenLigaDB's exact EPL season feed and ODbL obligations, or
obtain permission for another complete source; do not register/purchase anything
automatically. Until then, preserve the existing missing-score and freshness gates.

Any future adapter must remain separate from the frozen historical report: record
source URL/license/receipt/content hash, map explicit team IDs/names and dates,
reject duplicates/future/unconfirmed results, report conflicting scores without
silently overwriting them, cache bounded requests/failures, and prove sample
coverage before using results as live features. Source-target paper labels must
remain separate from operator settlement and actual wager performance.
