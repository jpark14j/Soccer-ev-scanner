# Free-first data decisions

The user confirmed no paid statistics/historical-odds subscriptions and directed
continued free-first development without purchases. No new account, trial or paid
API was enabled. Free access does not imply commercial redistribution rights.

## Implemented and actually exercised

**FiveThirtyEight NBA history:** publisher repository declares CC BY 4.0 for data
unless otherwise noted; the NBA README credits game information to Basketball-
Reference. The pinned archive used ends June 16, 2015. The importer keeps 3,940
home-game records from its last three seasons, with IDs, dates and final scores;
it discards neutral-site games and Elo forecasts. It retains source/revision,
attribution, modification description and normalized content hash. This is useful
for reproducible historical research, not a current NBA statistics feed or blanket
third-party rights clearance. No raw dataset is committed or exported.

**Retrosheet MLB game logs:** Retrosheet explicitly permits commercial products
subject to its attribution notice. The importer uses the Chadwick Baseball Bureau
mirror's documented `official` branch at a pinned commit. 7,276 completed records
from 2023–2025 were ingested through September 28, 2025. Game IDs preserve double-
headers. Resumed-game completion metadata is excluded to avoid attributing later
results to the original day. The importer retains Retrosheet attribution, source
URLs, revision and content hash. No raw dataset is committed or redistributed.
The UI displays source manifest attribution when those local files are selected.

**Current completed results:** The existing Odds API scores endpoint was tested
with NBA and MLB. It returned no completed NBA records and three completed MLB
records in the sample. The shared pipeline accumulates completed results locally
once per 24 hours for these two sports, when supported. It requires final status,
exact teams, valid scores and source/receipt timestamps; it never guesses results
from prices. Each source snapshot is retained. This is a growing local dataset,
not a full historical archive or independently verified settlement source.

Scores cost two existing-account credits per sport with a three-day lookback.
Nine daily h2h competitions plus NBA/MLB scores is approximately 13 credits/day,
390 per 30 days, before retries or props. Default daily local reservation cap is
16; at most 496 reservations in a 31-day month for one shared database. Other
clients/deployments share account quota but have separate local counters. The
provider's billing plan is not inferred. Set `COLLECT_RESULTS=0` to use odds only.
Do not assume a failed/skipped runner can recover results older than three days.
Local collected raw results are ignored by Git and require persistent storage.

Commands (downloads are explicit, not repeated on every UI render):

```bash
python -m intelligence.cli import-free-history --sport NBA
python -m intelligence.cli import-free-history --sport MLB
HISTORY_DIR=data/research/history MODEL_DIR=data/research/models \
  python -m intelligence.cli evaluate --league NBA --source 'actual source manifest reference'
HISTORY_DIR=data/research/history MODEL_DIR=data/research/models \
  python -m intelligence.cli evaluate --league MLB --source 'actual source manifest reference'
```

Pinned downloads are cached. Existing datasets are not overwritten. Both genuine
historical evaluations remained in research status: neither has a timestamped
sportsbook baseline, and both datasets are too old for current publication. A
maximum dataset age check supplements quote expiry. No old archive generates a
current qualifying recommendation.

Primary sources:
- https://github.com/fivethirtyeight/data/blob/master/README.md
- https://github.com/fivethirtyeight/data/blob/master/LICENSE
- https://github.com/fivethirtyeight/data/blob/master/nba-elo/README.md
- https://www.retrosheet.org/notice.txt
- https://github.com/chadwickbureau/retrosheet/blob/master/README.md
- https://the-odds-api.com/liveapi/guides/v4/#get-scores

## Current free refresh options investigated, not connected

BALLDONTLIE's NBA documentation lists free teams/players/games with a five-request-
per-minute limit and a required free-account API key. Player game statistics,
injuries, lineups and props are outside that free tier. Its current terms permit
specified personal/commercial analytics uses with restrictions on competition,
unaltered resale, tiers and third-party rights. A free account/credential and
runtime domain authorization would be needed to verify this feed. No account or
payment-method trial was started.
- https://docs.balldontlie.io/
- https://www.balldontlie.io/terms.html

MLB's public digital-property terms restrict use; merely finding an endpoint or a
permissively licensed Python wrapper does not grant commercial data rights. No
unofficial live scraping or access-control bypass was added. Retrosheet remains
the clearer free historical MLB choice. Current, legally usable player context
and synchronized live state are still missing.
- https://www.mlb.com/official-information/terms-of-use

The pre-existing football-data free source is personal/academic, light-download
research only, disabled by default for the commercial path. No free source is
represented as a substitute for Ontario-specific odds, timestamped historical
market evidence or actual combined parlay pricing.
# Focused EPL source update — 2026-10-16

`openfootball/football.json` explicitly dedicates its data to the public domain
under CC0. Seven pinned seasons, source hashes and derived fitted state are now
used for EPL BTTS / exactly 2.5-goal research. This does not grant commercial rights
to sportsbook feeds or other providers. The current public result file is incomplete
and ends September 20; downloads do not make its results current. No current-results
account was created. See [evaluation, source limits and preview steps](EPL_PREDICTIONS.md).
