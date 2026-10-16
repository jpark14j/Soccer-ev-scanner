# Verification matrix

Local automated tests use clearly synthetic fixtures and block outbound requests.
They verify software behavior, not betting profitability or feed-wide correctness.
The live smoke evidence is separately recorded with actual response/source times.

| Requested check | Result / evidence |
| --- | --- |
| Real odds retrieval | Actual The Odds API responses for NBA, MLB and all seven soccer competitions; 2,331 normalized quotes including non-Ontario records, six Ontario keys observed; `evidence/odds-retrieval.json`. |
| Ontario availability | Official iGO snapshot + documented Ontario provider keys, expiry tested. No US/global substitution. Actual operator execution/geolocation not tested. |
| NBA analysis | Distinct research candidate, probability mass, missing-history and future-data tests pass. Real free archive evaluation completed on 701 test games, but data ends in 2015 and has no sportsbook baseline; model remains research. |
| Soccer analysis | Original Poisson candidate retained/refactored, date-leakage tests pass. Genuine Premier League chronological evaluation remains research, not market-beating evidence. |
| MLB analysis | Distinct run-count candidate and future-data tests pass. Real Retrosheet archive evaluation completed on 1,494 test games; data ends in 2025 and lacks a sportsbook baseline. Pitcher/lineup/weather inputs absent. |
| Player props | Contract/participant/line normalization and count formula tests pass. One actual NBA points and one MLB strikeout event request returned no Ontario quotes. No validated prop recommendations. |
| Free history / scores | Published-licence NBA/MLB imports, doubleheaders, resumed-game exclusion and chronology tests pass. Real existing-provider scores request returned 0 completed NBA / 3 MLB records; no results inferred. |
| Expected value | Numerical example 0.60 × 1.90 − 1 = 0.14, boundary/invalid-value and push-return tests pass. |
| Parlay correlation | Frechet bounds, non-independent supplied joint estimate, mutually exclusive/duplicate-leg rejection tested. No fitted correlation model connected. |
| Genuine combined prices | Exact book/leg/restriction/time gate tested; missing combined quote yields theoretical status with no odds/EV. No live combined quote provider verified. |
| Live updates | Observed in-play prices can be listed. No score/clock/state/latency feed or validated live model; live forecasts deliberately disabled, never described as verified. |
| Stale quotes | Source/receipt/future/suspension and publication-time expiration checks pass; cache never resets source time. |
| Telegram | Message formatting, token-redaction, schedule, pending-state/delivery claims, no-duplicate mechanics tested. Actual send not tested: Telegram secrets unavailable in this environment. |
| Conversational model | Local grounded mode and disabled paid router, budget/approval and strict-output checks tested. No actual paid API call or free-form factual generation verified. |
| GitHub Actions | YAML, branch guard, archive-before-send and pinned actions inspected/tested. Remote CI outcome must be observed on the pushed branch/PR. Daily production job not invoked. |
| Streamlit | All ten sections plus missing-key startup pass AppTest; local server `/_stcore/health` returned HTTP 200 `ok`. Existing production deployment not changed/tested. |
| Credential security | Secrets excluded from Git, no literal credentials added, sanitized provider/Telegram errors tested. Existing production secrets not read/changed. |
| History accuracy | Append-only publication/settlement triggers, deduplication, real-source requirement, losing record metrics, archive restore/tamper checks pass. No actual settled forward predictions exist. |
| Existing features | Same repo/app entrypoint, soccer aliases/results candidate, league selection, market comparison and daily Telegram path retained. Raw odds CSV export removed for licensing; unvalidated picks and multiplied parlays intentionally replaced by evidence gates. |

The evaluation artifact records real scores (multiclass Brier and log loss), source,
data/code hash, calibration/test sizes and promotion blockers. These are predictive
research diagnostics, not ROI, a calibrated true event probability, or a profit claim.
Do not tune candidates on this test period and reuse it as an untouched test again.
A new model version needs a new genuinely held-out evaluation.

Further checks requiring credentials/contracts/deployment: actual Telegram acceptance,
remote daily job and its commit permissions, persistent Streamlit ledger and backups,
operator-level price execution/market rules, historical market timing, licensed NBA/
MLB/prop datasets, score/state synchronization, live latency/suspension handling,
combined parlay pricing, subscriber privacy/consent, and commercial rights.
