# Four-page workspace and preview guide

2026-10-16, America/Toronto. Development branch and Draft PR #1 only.

The same `app.py` now has four top-level destinations. Analytics, quotas, secrets,
model gates and immutable ledgers remain in their existing modules. No model was
retuned, approved or promoted; paid AI remains disabled.

The [Phase 4 guide](PHASE4_PARLAY_INTELLIGENCE.md) updates the parlay experience:
**AI Parlay Intelligence** sits above the Singles/Parlays tabs on Best Picks &
Parlays. It shows model-favored outcomes and evidence-ranked 2/3-leg research;
opposing outcomes stay in details. The earlier price-only selector is now under
**Parlays → Unsupported and price-only research · full existing generator**.
The four destinations and all advanced tools are preserved.

| Destination | What to use it for |
| --- | --- |
| AI Dashboard | Today's concise singles/parlay research, current-price coverage, source timestamps and Data & Model Health |
| Best Picks & Parlays | Central model-first AI Parlay Intelligence, followed by the preserved Singles / Parlays tabs and advanced research tools |
| Performance Tracker | Prospective paper results, published hypothetical records and held-out evaluations in separate tabs |
| Settings & Research Tools | A secondary Research tool selector containing all advanced modules |

## Evidence labels

**Approved opportunity** requires the existing quote, model, uncertainty and EV
publication gates. There are no newly approved models. **Experimental /
research-only** means a source-backed estimate exists but does not establish
approved forecasting skill or a betting advantage. **Price-only research** means
an individual selection has a current observed price but no supported model
probability. **Blocked / unavailable** identifies expired/unverified prices or
rejected model inputs; those cards are inspection-only.

Best Picks & Parlays shows the exact selection, observed odds/book/source time,
model evidence and reasons. Equivalent prices are compared within matching
evidence categories; stale higher odds cannot replace a current quote. Ranking
uses qualification, model support, supplied uncertainty and freshness. Equal-
evidence ties do not establish predictive superiority. No output minimum is forced.
The sportsbook break-even number is explicitly **not a predicted win probability**.

Parlay filters can select sport, book, market, leg count, price-based risk category
and leg evidence status. The risk categories are proxies, not empirical measures
of safety. Joint probability, executable combined quotes, sportsbook acceptance and
parlay EV remain unverified. The theoretical odds product never becomes an offer.
The whole-slate sportsbook optimizer, same-game selector, bankroll scenarios and
qualified-leg builder remain available in expanders on the Parlays tab.

## Previous pages: where they went

| Previous page | Current location |
| --- | --- |
| AI Dashboard | AI Dashboard |
| Best Selections by Game / Best Opportunities | Best Picks & Parlays → Singles |
| Daily Parlay Research / AI Parlay Builder | Best Picks & Parlays → Parlays |
| Performance Tracker | Performance Tracker, three evidence tabs |
| Research Operations | Settings & Research Tools → Research tool → Research Operations |
| Advanced Markets | Settings & Research Tools → Research tool → Advanced Markets |
| NBA / Soccer / MLB Analytics | Settings & Research Tools → Research tool → the sport module |
| Live Markets | Settings & Research Tools → Research tool → Live Markets |
| AI Assistant | Settings & Research Tools → Research tool → AI Assistant |
| Settings | Settings & Research Tools → Research tool → Settings |
| Model/data diagnostics | Settings & Research Tools → Research tool → Model & Data Diagnostics |

Legacy stage reports describe earlier navigation. This guide is the current map.
Raw odds remain collapsed in advanced views and the Singles audit expander. Home
has no raw table. Two-column filter/metric rows and full-width cards keep the main
views compact; the Streamlit sidebar is available from its menu on small screens.
Automated Streamlit interactions are tested; a real mobile-browser visual review
has not been completed from this environment.

## Navigation does not buy another scan

On first open the app uses the existing shared cache and capped scan. It saves the
result in the browser's server-side session. Changing top-level pages, tools, tabs,
sportsbook view or research filters reuses that snapshot **even after the 30-minute
scan-cache TTL**. Price source/receipt timestamps are never reset; five-minute
quote expiry is still checked on rendering and recommendations fail closed.

Use **Refresh analysis** for an explicitly requested new scan. It still honors the
provider retrieval cache, shared store and existing local credit cap. Changing
sidebar **Competitions** changes scan scope and may start another capped scan;
use the Singles/Parlays sport filters for free inspection of already retrieved
markets. Changing connection/quota/scan configuration also invalidates scope.
Reopening a new browser session can use or refill the shared cache. Streamlit is
not a background scheduler, and a full browser reload may create a new session.

Advanced request/discovery buttons remain explicit, cost-labeled and quota-limited.
The 60-second dashboard/parlay fragments recheck expiry; they do not fetch prices
or sports results. Rendering Data & Model Health only reads existing observations.
Refreshes, odds budget and shared caching are unchanged; no fresh database is used
to bypass a spent cap. Paid AI requires its existing separate approval/key/consent
gates, and navigation alone never invokes it.

## Data readiness and performance

The [free-results review](FREE_RESULTS_READINESS.md) records investigated providers,
licensing, identifiers, update limits and unresolved access/coverage. No alternative
source was verified sufficiently to activate. Current OpenFootball results remain
incomplete and old: 45 completed current-season games through September 20, with
15 earlier fixture scores missing. The model stays blocked for affected inputs.
The dashboard shows the last cached source check separately from result dates;
bundle-generation time is labeled as snapshot evidence, not a fresh live check.
Cached conflicts/license failures are displayed and never used to activate inference.

`epl-goal-strength-1`, its policy, fitted artifact, chronological splits and genuine
363/368 calibration/test counts are unchanged. Brier/calibration/log loss, baseline
comparisons, intervals, versions and sample counts are in **Held-out model
evaluations**. Historical classification accuracy is not betting profit or win rate.
**Prospective paper research** shows real immutable recorded/labeled/hit/miss counts,
including losses, separate from historical tests. **Published hypothetical records**
retains the original forward/backtest ledger and standardized-stake analytics.
There is no actual-wager import or automatic wagering. Community Cloud off-host
ledger durability remains unverified; model/software test passes do not establish
predictive advantage.

## Exact preview steps

1. Open [your separate preview](https://soccer-ev-scanner-preview-jp.streamlit.app/).
   It must still use `development/verified-sports-intelligence` and `app.py`.
   Let Community Cloud rebuild after the branch update. If needed, select
   **Manage app → Reboot app** on this preview only; do not touch production.
2. Confirm the sidebar has exactly the four destination names in the table above.
   Keep all Secrets, `PAID_ANALYST_APPROVED = "0"` and the odds cap unchanged.
3. On **AI Dashboard**, read **Today's Research** and **Data & Model Health**.
   Empty research or source-gap messages are expected when inputs do not qualify.
4. Open **Best Picks & Parlays → Singles**. Change **Sports**, **Sportsbooks**,
   **Market** and **Evidence status**. Check that price-only cards do not claim a
   model probability. Select Approved opportunity alone; an empty result is valid.
5. On Best Picks & Parlays first inspect **AI Parlay Intelligence** and its
   **Parlay research controls**. Select 2 or 3 legs; open evidence details for
   opposing outcomes and missing dependencies. The older **Market, event and
   evidence filters** remain inside **Parlays → Unsupported and price-only
   research · full existing generator**. All combined products remain theoretical.
   Missing compatible current prices/evidence must produce an empty shortlist.
6. Open **Performance Tracker**. Inspect the three tabs, then **Held-out model
   evaluations → Premier League calibrated BTTS / goals 2.5**. The test count is
   368 and the model is research-only. Historical matches do not inflate paper counts.
7. Open **Settings & Research Tools**. Use **Research tool** to visit Advanced
   Markets, a sport module, Research Operations, Live Markets, AI Assistant and
   Model & Data Diagnostics. The assistant retains free local rule-based mode.
8. Return to the dashboard and filters. Navigation alone should leave the local
   odds reservations unchanged. Only use explicit request buttons when you intend
   a capped refresh; old quotes do not become current just by changing pages.

The local server and automated Streamlit UI are checked separately from the hosted
preview. The hosted URL cannot be reached through this execution environment's
proxy, so its rebuilt browser UI is not claimed as verified here.
