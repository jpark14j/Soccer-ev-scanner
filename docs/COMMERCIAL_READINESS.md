# Commercialization review and remaining external requirements

Reviewed 2026-10-15 Toronto. This is implementation research, not legal clearance
or a representation that the software is production-ready.

The product supplies analytics and never accepts stakes or places wagers. Before
selling subscriptions or entering affiliate arrangements, determine the applicable
Ontario/Canadian classification, registration, advertising and consumer-protection
obligations for the actual business model. Do not assume being an analytics app
exempts every activity or creates sportsbook authorization.

The iGO directory distinguishes contracted private operators from OLG. Brand
regulation and jurisdiction-specific feed rights are separate questions. The app
uses dated evidence and excludes unknown feed jurisdictions. Extend the registry
only after reviewing the official directory again, not based on book logos.
Source: https://www.igamingontario.ca/en/operator/operators

AGCO advertising requirements address misleading claims, minors/vulnerable people,
inducements and athlete/celebrity participation. Do not use guaranteed-profit,
risk-free or safe-bet claims, bonuses/affiliate incentives or athlete endorsements
without evaluating the relevant standards and actual arrangement. The full current
AGCO standards page could not be retrieved in this session; **complete a current
standards review before launch**, rather than treating this summary as verified
compliance. Official AGCO-issued releases reviewed:
- https://www.globenewswire.com/news-release/2023/08/29/2733572/0/en/AGCO-to-ban-athletes-in-Ontario-s-igaming-advertising-to-protect-minors.html
- https://www.globenewswire.com/news-release/2025/03/26/3049852/0/en/agco-issues-110-000-in-penalties-to-betmgm-canada-for-offering-cash-to-induce-new-gambling-customers.html

For subscriber personal information, assess PIPEDA: meaningful consent, identified
purposes, limited collection/use/retention, safeguards, access/correction, accountability
and breach handling. Do not put subscriber IDs, chat IDs, questions or credentials
in the public Git ledger. The implementation adds no user accounts or subscriber
PII collection. Future hosted model calls need clear disclosure of transmitted data.
Sources:
- https://www.priv.gc.ca/en/privacy-topics/privacy-laws-in-canada/the-personal-information-protection-and-electronic-documents-act-pipeda/pipeda-compliance-help/guide_org/
- https://www.priv.gc.ca/en/privacy-topics/privacy-for-businesses/appropriate-handling-of-personal-information/collecting-personal-information-and-consent/consent/gl_omc_201805/

Commercial subscriber messages may engage CASL consent, sender identification and
unsubscribe requirements. The current Telegram configuration is the existing
owner's single destination; it is not a subscriber consent/notification platform.
Source: https://crtc.gc.ca/eng/com500/guide.htm

Obtain explicit rights for statistics, historical odds, training, stored results,
display, notifications and any future commercial API. The Odds API permits analytical
applications but prohibits raw-feed redistribution. The free football-data policy
is for private personal/academic use and light downloads; it is unsuitable as the
unlicensed basis for this commercial project. Default commercial downloads are
therefore disabled. See `PROVIDERS.md` for primary sources and candidate costs.

The UI displays Ontario 19+, uncertainty, limit-setting/no-loss-chasing messaging
and ConnexOntario contact information. Source:
https://connexontario.ca/our-services/gambling-treatment/

## Concrete external decisions needed next

1. Continue using the reviewed free archive sources and completed-result
   collection in FREE_DATA.md; no paid statistics subscription is authorized.
   For current missing fields, verify an appropriate free feed or use properly
   licensed local historical files with observation-time provenance. Required contextual/prop fields are in
   `DATA_CONTRACTS.md`. Prices/coverage need supplier quotes; no fee is approved.
2. Obtain timestamped pregame historical odds for independent market benchmarking
   and backtests. Existing unknown-time CSV averages cannot establish tradable EV.
3. Ask alternative odds providers for written Ontario operator/market mappings,
   live state/suspension semantics, actual parlay quote support and subscriber/API
   rights. Global sportsbook names alone are insufficient. No purchase is made.
4. Choose durable deployment storage and a model validation/release process. SQLite
   plus Git-derived archives is a low-cost starting point for the owner, not a
   concurrent multi-user commercial service.
5. If generative conversation is desired, approve a specific low-cost language model
   and monthly token cap before adding credentials/enabling calls. The current local
   analyst has zero model API cost. An approved LLM must summarize these verified
   records and cannot invent odds, injuries, forecasts or settlement results.

Optional paid intent routing is prepared in `intelligence/llm.py` and disabled.
GPT-4.1 mini advertises $0.40/M input and $1.60/M output tokens: 2,000 input +
500 output tokens would cost $0.0016/answer ($1.60/1,000), before tax/extras.
Routing is capped at 200 output tokens. Proposed local monthly cap: $5 USD.
Enable only after explicit approval, credential/network setup and actual API test.
Source: https://developers.openai.com/api/docs/models/gpt-4.1-mini

No paid service, subscription, production secret or production deployment was
changed. Live forecasting, validated player props and executable parlay discovery
remain incomplete because their essential data/pricing evidence is unavailable.
