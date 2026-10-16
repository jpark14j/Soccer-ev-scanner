# Ontario data provider decision

Reviewed 2026-10-15 Toronto. Documentation is evidence of advertised capability,
not a guarantee that an individual event/market/book is returned or executable.

## Recommended initial adapter: existing The Odds API account

Official sources:
- https://the-odds-api.com/sports-odds-data/bookmaker-apis.html
- https://the-odds-api.com/liveapi/guides/v4/
- https://the-odds-api.com/sports-odds-data/update-intervals.html
- https://the-odds-api.com/#pricing
- https://the-odds-api.com/terms-and-conditions.html
- https://www.igamingontario.ca/en/operator/operators

The iGO directory states its listing is accurate as of September 1, 2026. The
checked-in registry records that effective date separately from our review date,
expires after 30 days, and includes all sports-betting entries observed, plus
OLG PROLINE+ under its separate legal basis. It is a reviewed snapshot, not an
ongoing certification. Review the official directory again before extending it.

The configured provider documents `betano_ca_on`, `betmgm_ca_on`,
`betrivers_ca_on`, `pointsbetca`, `sportsinteraction_ca_on`, `proline_ca_on`, and
paid-only `bet99_ca_on`. These are the intersection of documented Ontario feeds
and the reviewed directory/OLG basis. No operator is preferred. `playnow_ca` is
not Ontario. `draftkings`, `fanduel`, `williamhill_us`, `pinnacle`, and `bet365_au`
are **not** accepted substitutes for Ontario feeds. The named operators may be
regulated in Ontario while lacking a documented Ontario key in this provider.
See every reviewed operator and limitation in `config/ontario_books.json`.

NBA, MLB and the seven configured soccer competitions are documented sports.
Featured pregame/in-play h2h, spreads and totals use the sport odds endpoint;
additional markets/props use individual event odds. Props depend on sport/book;
US prop coverage does not establish Ontario coverage. Double/triple doubles,
goalscorers, shots, corners, cards and first-five markets are not guaranteed.
The adapter can request documented market keys and surfaces empty/denied responses.
No stats, injuries, confirmed lineup, play-by-play or universal suspension feed
is supplied by this adapter. It cannot support reliable live recommendations alone.

Advertised source cadence: featured pregame 60s/in-play 40s; additional markets
60s/60s, with intervals changing near start. These are not latency guarantees.
Historical featured snapshots start June 2020; additional markets after May 2023;
historical endpoints are paid-plan only. We do not call historical endpoints.

Advertised monthly USD pricing when reviewed: free 500 credits, $30/20K,
$59/100K, $119/5M, $249/15M. Existing account entitlements remain unverified until
a real response. Default h2h for 9 competitions once daily is about 270 credits
per 30 days; three featured markets would be about 810, excluding retries and
props. Default local cap is 12 credits/day and cache is 30 minutes. Actual
provider headers are captured; multiple deployments have separate local budgets
and share account quota. No automatic upgrade or paid API is enabled.

Current terms permit analytical apps, commercial display, retention and model
training, but prohibit redistribution as a standalone raw feed. Remove raw odds
exports; an eventual commercial API needs separate licensing. Obtain provider
confirmation of the subscriber product and archive terms before commercialization.

## Alternative providers investigated

| Requirement | Sportradar Odds Comparison | SportsGameOdds |
| --- | --- | --- |
| Ontario book-specific prices | Not established by public pages reviewed; obtain written coverage matrix and sample responses | Global book names/IDs published; Ontario price jurisdiction not established |
| NBA / soccer / MLB | Prematch/live/props products advertised; exact contract coverage required | NBA/MLB and soccer leagues advertised; varies by plan |
| Player props | US-focused props lists NBA/MLB and top soccer; global Core separate | Advertised; Ontario-specific availability unverified |
| Pregame / live | Separate comparison products; score/state feed also needed | Advertised; plan and market dependent |
| Historical | Contract/access confirmation required | Pro advertises historical; scope/retention must be confirmed |
| Cadence | Endpoint TTL/SLA and contract dependent; not verified | Advertised free 10m, Rookie 3m, Pro sub-minute; not SLA |
| Cost | Sales quote; no reliable public amount established | Advertised $0, Rookie $99/month, Pro $299/month; currency/contract to confirm |
| Commercial licensing | Written product/redistribution terms required | Limited, revocable subscription licence; exact subscriber/API rights require confirmation |

Sources:
- https://developer.sportradar.com/odds/reference/intro
- https://developer.sportradar.com/odds/reference/oc-prematch-overview
- https://developer.sportradar.com/odds/reference/oc-live-odds-overview
- https://developer.sportradar.com/odds/reference/oc-player-props-overview
- https://sportsgameodds.com/bookmakers
- https://sportsgameodds.com/pricing
- https://sportsgameodds.com/terms

Do not buy another feed based only on global book logos. Request a dated matrix
of Ontario operator × sport × market × pregame/live, jurisdiction identifiers,
update latency/suspension semantics, historical depth, combined parlay pricing and
restrictions, commercial display/training/retention/redistribution rights, and a
fixed-cost quote. No alternative account or subscription was created.
