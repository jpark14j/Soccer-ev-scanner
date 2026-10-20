# Automatic updates and separate accuracy

The existing private four-hour job, five-page interface, models, provider hold,
nine-credit ceiling and paid-AI restrictions are preserved. Only Performance
Tracker adds a compact Soccer / NBA / MLB / Mixed sports selector.

## Failure isolation

A Bundesliga transport or validation failure no longer prevents the other sports,
pregame recording or verified settlement from running. The failed attempt and
partial-run status are saved in the same fenced checkpoint. Accepted inputs retain
their original observation and expiry timestamps. Failed attempts have a three-hour
retry interval. The existing next-UTC-date recheck for successfully fetched
same-day withheld finals remains; failures cannot use that exception repeatedly.
Storage, frozen-asset or protected-ledger failures still stop the checkpoint.

## NBA fixture recovery

If the primary Sporting Events calendar is temporarily unavailable, the existing
SportScore daily adapter can verify a bounded upcoming window against the retained
reviewed calendar. The calendar is then an identity registry, not a current feed.
Every displayed fallback fixture must match actual daily teams, date and exact
UTC kickoff. Future mismatches are quarantined; their original records stay
immutable and pending. They do not prevent unrelated verified future games from
processing. A later calendar download alone cannot clear known disagreements.

All earlier required NBA games still need reconciled finals. Missing or conflicting
past inputs, expired receipts, changed historical tipoffs and insufficient model
evidence continue to block inference. The source receipt graph preserves the old
registry timestamp and each actual daily observation. No old timestamp is reset.

Actual daily responses included exactly-next-midnight fixtures in both adjacent
NBA day queries. The adapter discards that exclusive end boundary from the earlier
date, retains it in its own UTC-date query, and requires exact fixture reconciliation.
It does not move a kickoff, infer a timezone or accept other out-of-date rows.
The URL allowlist now includes the 2027 portion of the already supported 2026–27
season. Unsupported new seasons/postseason models are not activated automatically.

The fixed public-request bound is unchanged. Successful current receipt caches and
three-hour request cooldowns are reused; the four-hour schedule is not increased.
No Odds API or paid-AI request is part of this path.

## Real source review

OpenLigaDB's discovery endpoint identifies EPL `pl` (5996) and `pl1` (5993).
On October 19 at approximately 9:13 PM Toronto, `pl` returned 380 fixtures but only
60 finished matches, including an unfinished Tottenham–Coventry match with no
final score. `pl1` returned no fixtures. The existing SportScore snapshot had 69
prior-date finals but still labeled that match live. Neither supplied its final.
The soccer model updates shared league state, so silently omitting that result
would change the validated input definition even for other teams. Its gates remain.

The fresh Sporting Events MLB JSON request returned HTTP 403. No access control
was bypassed. Its last previously accessible export contained four context
headings without game-level teams/times/finals; Retrosheet history ends in 2025.
No permitted current/postseason alternative has been established. Historical
regular-season evidence does not authorize 2026 postseason probabilities.

Eight actual SportScore NBA daily receipts were obtained and replayed offline
against genuine persisted data. After handling the exact midnight overlap,
44 eligible experimental estimates were produced; four inconsistent future
fixture identities were quarantined. That rehearsal made no network requests,
created no hosted forecasts and did not establish live settlement or accuracy.

## Accuracy and settlement

Each sport's three metrics count only first genuinely recorded pregame decisions
with verified binary outcomes. Refresh versions do not inflate the denominator.
Every parlay leg must win. Pending, void, partial and unresolved outcomes do not
count as settled. Backtests are excluded. Experimental and validated categories
remain separate; mixed-sport legs are classified together and cannot enter an
individual sport's totals. Unknown classifications are excluded from sport totals.
Older same-game records without a sport field use their exact registered
competition's sport; unknown league names are never guessed or defaulted to Soccer.

At the hosted read-only audit, none of the 253 actual forecast versions had reached
kickoff. Accuracy remains unavailable, not zero or an invented success rate.
Deterministic settlement/recovery tests are distinct from real-world verification.
Repeated successful scheduled runs and readbacks demonstrate those cycles only,
not long-term availability of external providers or permanent future reliability.
