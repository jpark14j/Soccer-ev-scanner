# Historical and live data contracts

## Completed game results

For each competition, place a licensed CSV in `HISTORY_DIR`:
`nba.csv`, `mlb.csv`, `premier_league.csv`, `la_liga.csv`, `bundesliga.csv`,
`serie_a.csv`, `ligue_1.csv`, `mls.csv`, `champions_league.csv`.

Required columns: `Date` (day/month/year), `HomeTeam`, `AwayTeam`, `FTHG` (final
home goals/points/runs), `FTAG` (final away goals/points/runs). Dates are normalized;
all same-day results are withheld from pregame features. Scores must be completed,
nonnegative integers. Conflicting duplicate results are rejected, identical overlap
is deduplicated, future dates and NBA/MLB ties are excluded. Explicit canonical
team aliases are necessary; no fuzzy match supplies a recommendation.

A same-stem `.source.json` is required:

```json
{
  "source": "actual licensed supplier/dataset reference",
  "license_reference": "actual agreement or permission reference",
  "commercial_use": true
}
```

This is the operator's provenance assertion, not independent legal verification.
Do not put contracts, confidential terms or API credentials in a public repository.

Optional baseline fields: `AvgH`, `AvgD` (soccer), `AvgA`. They are used only for
benchmarking, never as model predictors. To establish pregame timing, supply real
`market_observed_at` and `commence_time` timezone-aware timestamps. Unknown-time
historical odds cannot promote a model or establish executable betting returns.
Historical source integrity, timezone mapping and licence need separate review.

## Props and contextual features still required

Licensed per-player logs with stable player/team/event IDs; actual availability
and observation timestamps; confirmed/expected minutes and lineups; NBA pace,
usage and efficiency; soccer provider-measured xG/xGA, shots, injuries, suspensions,
fixtures; MLB starter/bullpen/batter metrics, handedness, park, weather and lineups.
Expected values from a goal-count model must never be labeled measured xG.

A count-distribution utility is implemented and tested; it is not a validated prop
model. NBA double/triple doubles need joint event modeling, not Poisson reuse.
Pitcher strikeouts require exposure/innings and lineup context. Batter markets
need plate appearances and outcome distributions. No automatic odds-derived
probability may substitute for missing player statistics.

## Live and parlays

Live requires verified current scores, clock/inning/possession/state, player events,
sequence and latency metadata, suspension status and a separately validated in-game
model. The current provider adapter cannot establish these, so live forecasts are
disabled. Schedule-start time alone does not prove a game is actually in progress.

A parlay feed must return exact book, leg IDs, combined decimal price, observed
source time, restriction acceptance and provenance. Correlated joint estimates
must be fitted and tested for the exact combination/domain. No such feed/model is
connected. Cross-sport or different-event legs are not assumed independent.
