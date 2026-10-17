# Advanced markets and parlay intelligence — 2026-10-16

This increment extends the existing development branch and `app.py`. It does not
change production, merge Draft PR #1, purchase data or enable OpenAI. Keep
`PAID_ANALYST_APPROVED = "0"`. All candidate combinations remain research, not
qualified betting recommendations.

## Audit and actual provider access

The previous selector primarily refreshed moneylines, could not inspect event
props, hid stale observations from research, and did not read Streamlit Secrets
for its local credit cap. A manual refresh could repeat equivalent market requests.
The new path shares canonical request caching, a transactional fetch lease,
market-specific saved responses, explicit search scope and secure data settings.

The provider's [market catalog](https://the-odds-api.com/sports-odds-data/betting-markets.html)
and [v4 documentation](https://the-odds-api.com/liveapi/guides/v4/) distinguish
featured markets from per-event markets. A documented key is not proof of Ontario
coverage. Only actual exact Ontario feed keys in the reviewed registry count.
There is no substitution of US/global prices.

Actual observations at **2026-10-16 16:58 UTC / 12:58 EDT**:

| Query | Current Ontario observations at capture | Observed Ontario keys |
| --- | --- | --- |
| NBA spreads + game totals | 204 spreads, 168 totals | `betmgm_ca_on`, `betrivers_ca_on`, `pointsbetca`, `proline_ca_on`, `sportsinteraction_ca_on` |
| MLB run lines | 10 | `betano_ca_on`, `betmgm_ca_on`, `pointsbetca`, `proline_ca_on`, `sportsinteraction_ca_on` |
| MLB pitcher strikeouts, one event | 6 | `betmgm_ca_on`, `pointsbetca`, `sportsinteraction_ca_on` |
| Premier League BTTS, one event | 4 | `betmgm_ca_on`, `sportsinteraction_ca_on` |
| NBA player points, one event | 0 | None returned; not evidence of universal unavailability |

See [the dated access record](evidence/advanced-market-access.json). These are
historical verification observations, not prices available now. Moneylines across
all three sports were verified in the previous increment. NBA rebounds/assists/
threes, soccer totals/handicaps and MLB totals/batter props have adapter/catalog
support but were **not live-verified in this increment**. Corners keys are absent
from the current published catalog; requests require exact current event discovery.
Asian-style quarter-line settlement and operator-specific scope remain unverified.
No authorized combined-parlay price endpoint is connected.

## Preview steps and the 9/9 budget

1. Open **https://soccer-ev-scanner-preview-jp.streamlit.app/** after its development
   branch rebuild. Select **Advanced Markets**. Keep the preview on
   `development/verified-sports-intelligence`, entrypoint `app.py`.
2. Select one competition and one featured market for a narrow search. The button
   shows maximum local credits and a specific disabled reason. Filters do not fetch.
3. For props/BTTS, choose an upcoming event. **Load upcoming event list** costs zero
   provider credits; **Discover Ontario market keys** reserves one. Then explicitly
   retrieve one event market. Neither selecting an event nor opening the page
   automatically scans player markets.
4. Use **Include stale / historical** to inspect saved observations. Source and
   receipt times never reset. Stale prices cannot enter current candidates. Saved
   featured/event responses can be restored for seven days on the same disk.
5. Open **Daily Parlay Research** or **AI Parlay Builder**. Filter market types,
   sports, books, 2/3 legs and price-based risk category. **Research event scope →
   One selected event** inspects same-game combinations. All legs must use one book.
   Up to three distinct event sets appear only when compatible current quotes exist.
6. Inspect each English selection, participant, direction, line, price, source time,
   unknown settlement scope and qualification blockers. Optional bankroll analysis
   is below the selector. Performance and local Assistant use the same data.

The UI defaults to **9 local credits per UTC day**, three competitions (NBA, Premier
League, MLB), 30-minute cache and no automatic result collection. Existing explicit
environment/Streamlit Secrets settings are honored, including a cap of zero.
This lowers the former UI default; it never raises an existing configured limit.
The scheduled CLI's existing 16-credit/default-result behavior is unchanged.

At 9/9, chargeable searches remain disabled. The banner shows the exact next UTC
midnight and Toronto equivalent: e.g. **2026-10-17 00:00 UTC = October 16, 20:00 EDT**.
In winter UTC midnight is 19:00 EST. This is the local counter reset, not the
provider's account/billing reset. No counter is cleared and no cap is raised to
work around exhaustion. Separate deployments share account quota, not local caps.

Featured cost is selected markets × Canadian region. Event queries reserve up to
the requested market count; the provider documents billing by markets actually
returned (an empty response can cost zero). Reservations are conservatively not
refunded. Retries count. Canonical market order, at least 60 seconds of shared cache
even after a manual click, a 60-second UI cooldown, current-market reuse and
database fetch leases reduce duplicates. No browser filter triggers polling.

The real audit used six additional local reservations, moving **3/9 to 9/9**;
reported provider cost was five, because NBA points returned nothing. No historical
endpoint, subscription or OpenAI call was used. The provider advertises a free
500-credit tier; the user's billing plan and commercial redistribution rights have
not been independently verified. Do not infer rights from access or free pricing.

## Models and genuine chronological research

New score models use prior-day-only team history and exact team aliases:

| Sport | Research method | Important missing inputs |
| --- | --- | --- |
| NBA | Shrunk recent scored/allowed means, home advantage, paired empirical score residuals preserving observed score dependence | Pace, usage, minutes, injuries, lineups, rest/travel and player logs |
| Soccer | Poisson attacking/defending goal strengths and score grid | Measured xG, availability, lineups, rest/congestion; independent team goal counts are unvalidated |
| MLB | Poisson run strengths conditioned on non-tie finals | Starting pitcher, bullpen, batter matchups, park/weather, lineups and explicit extra-innings model |

NBA uses up to 30 recent games per team and 1,200 league games with shrinkage.
These are team-score models, never player-prop models. Props/corners have no
connected source-backed forecast. Integer/quarter-line observations remain
inspectable, but their push/partial-settlement probabilities are not estimated.
Same-game scenarios intersect compatible score outcomes; they do not multiply leg
probabilities. Cross-game independence is never assumed.

Real local licence-manifest/hash-checked archives were evaluated. First 60% of
dates warm up the model, next 20% fit temperature calibration, final 20% evaluate
without test-set calibration selection. Models update only with results preceding
the simulated forecast day. These archive periods have also been used for earlier
baseline research; they are exploratory out-of-sample diagnostics, not a fresh
independent confirmation or a reusable lockbox for model selection.

The predeclared tasks below use **fixed diagnostic thresholds**, not invented
historical sportsbook lines. Brier here sums both class errors; usual binary Brier
is half this value.

| Task | Test games | Brier | Log loss |
| --- | --- | --- | --- |
| NBA home margin greater than 5.5 | 701 | 0.451698 | 0.644714 |
| NBA total greater than 220.5 | 701 | 0.232548 | 0.386135 |
| MLB home margin greater than 1.5 | 1,494 | 0.467520 | 0.659972 |
| MLB total greater than 8.5 | 1,494 | 0.505735 | 0.699453 |

The [NBA](evidence/nba-advanced-research.json) and
[MLB](evidence/mlb-advanced-research.json) reports include code/data hashes, source,
calibration/test counts, simple baselines, calibration bins/gap and conditional
Wilson intervals. NBA total classification accuracy merely matches its simple
majority baseline; MLB run-line classification trails its baseline. Classification
accuracy is **not betting win rate**. No historical prices means betting win rate,
ROI and P&L are unavailable. No advantage or approved model is established.

NBA data ends in **2015**, MLB in **2025**. New soccer score-market code is
unit-tested but has no new genuine advanced-market evaluation; existing soccer h2h
research remains separate. There is no approved player model or held-out joint
parlay validation. New forecasts remain `validated=False` with a full 0–1 envelope,
not a fabricated event-specific confidence interval. Historical report calibration
is not silently applied to every current line. Live forecasting remains disabled.

Reproduce after importing permitted history as documented in [FREE_DATA.md](FREE_DATA.md):

```bash
python -m intelligence.cli evaluate-markets --league NBA
python -m intelligence.cli evaluate-markets --league MLB
```

Default output is private `data/research/advanced_models`. Source CSVs are ignored
by Git and do not automatically exist on Community Cloud. The UI works without
them and explains missing forecasts. Do not upload data without appropriate rights.

## Parlay, performance, assistant and bankroll boundaries

Mixed h2h/spread/total/BTTS/returned-prop candidates use only current Ontario single
observations. Contradictory score constraints, opposing/nested shared-player counts
and obvious threes/points contradictions are rejected. Same-event, shared-team and
shared-player dependence is flagged. Across games remains unknown. The ranking
rewards evidence quality, interval width and freshness, not larger payouts.

An optional **unvalidated same-game score-model scenario** requires supported
full-event legs and the same model/context. It is not the approved joint estimate.
Theoretical multiplied odds stay separate from executable prices. No parlay EV,
qualified recommendation or published prediction exists without valid joint
evidence, a genuine combined quote and operator rules/acceptance verification.

The immutable performance ledger retains losses and separates forward/backtest
records. It shows counts, settled outcomes, one-unit hypothetical P&L/ROI, drawdown,
calibration and sport/market/model/parlay-size breakdowns. Empty 2/3-leg records do
not become invented results. Win-rate Wilson intervals assume independent event
outcomes and are suppressed with shared-event records. ROI intervals use a seeded
UTC-day-block bootstrap, require 30 settled days, and still assume stationary,
sufficiently independent day blocks. They are historical uncertainty, not a future
profit guarantee. Actual closing prices/settlement evidence must be recorded;
unavailable accepted-parlay rules and price histories cannot be simulated away.

The local rule-based Assistant can discuss actual props, candidates, research
reports, bankroll limitations and quota, with sport-aware follow-ups. Missing
probabilities, old history, absent pricing and lack of validated edge are explicit.
The optional OpenAI path uses the same evidence; paid requests remain disabled.

Bankroll analysis is opt-in, uses CAD hypothetical loss examples, and labels its
0.5% per-bet / 2% total caps as assumptions. Fractional Kelly requires a validated
probability, current observed single price and interval width at most 0.15. It uses
the lower probability, quarter Kelly, a cap and a sensitivity table; nonpositive
lower-bound EV blocks it. Research parlays have no eligible Kelly estimate. No
amount is guaranteed profitable and no wager can be placed through this app.

## Verification and next evidence

See [verification](VERIFICATION.md) and the latest evidence JSON for software
tests, actual provider access and a historical captured-response UI replay.
The external Community Cloud build/browser cannot be verified from the restricted
execution environment. A local test is not a claim of cloud deployment success.

Next substantive requirements: current licensed team/player/context history,
timestamped historical sportsbook lines/prices, operator-specific settlement and
parlay restrictions, an independently held-out calibrated joint model, genuine
combined-price access and a durable loss-inclusive forward record. No new paid
service is required for the implemented research functionality; future access and
commercial rights require a separate decision.
