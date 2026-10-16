# Initial technical audit

Audit date: 2026-10-15 (Toronto). Baseline: `8e78990` on `origin/main`.
Development branch: `development/verified-sports-intelligence`. All seven tracked
files were reviewed, including the existing digest state and workflow. No AGENTS.md
instructions were present. No production secrets were changed.

## Architecture and working features

`app.py` is a single Streamlit screen. `scanner_core.py` duplicates most of its
logic for `telegram_alerts.py`. The Odds API v4 supplies real Canadian-region h2h
quotes; football-data.co.uk supplies full-time goals for five European leagues.
The UI selects seven soccer competitions, caches history for six hours, compares
BetMGM to three peers, exports CSV, and shows up to three singles/two-leg parlays.
The headless workflow scans four leagues, sends a Toronto morning Telegram digest,
and commits its last delivery date. The two UTC schedules handle daylight saving.

## Findings ordered by importance

| Priority | Finding | Consequence / required change |
| --- | --- | --- |
| Critical | Poisson parameters and thresholds have no held-out validation or calibration. | Positive price differences must not be published as validated EV. Add chronological evaluation and model promotion gates. |
| Critical | Parlay probabilities and odds are multiplied, with no joint model, restrictions or combined quote. | Remove executable parlay recommendations until supporting evidence exists. Allow clearly theoretical bounds. |
| High | API failures include `str(exc)` containing query URLs. | An Odds API key may appear in UI/log output. Use sanitized errors; do not log response URLs. |
| High | Book/market `last_update` discarded; only scan time displayed. | Old quotes can appear current. Preserve source and receipt times; expire on every render/publication. |
| High | BetMGM is hardcoded; Canadian-region peers are not checked against Ontario directory. | Add evidence-backed jurisdiction registry; never map US book keys onto Ontario prices. |
| High | UI/headless selection logic differs and duplicates hundreds of lines. | Shared ingestion, models, eligibility and reporting services. |
| High | No immutable prediction/result ledger or settlement system. | No independently auditable performance or complete losing history. Add append-only publication and evidence-backed settlement records. |
| High | No tests/CI; loose dependency versions. | Add numerical, contract, workflow, UI and notification tests before merge. |
| Medium | History can include same-day results when predicting earlier matches; future seasons are hardcoded. | Date-only data must exclude the entire event day; derive seasons and deduplicate matches. |
| Medium | Fuzzy team matching may silently attach wrong history. | Exact canonical aliases only by default. |
| Medium | Goal-rate estimates named xG. | These are goal-derived rates, not measured provider expected goals. Rename in UI. |
| Medium | Telegram send and subsequent state commit are not atomic. | Crash after acceptance can duplicate delivery; persist pending/accepted state, fail closed on uncertain delivery, retain concurrency lock. |
| Medium | Broad contents write scope, actions use mutable version tags, no branch guard. | Restrict scheduled sending to default branch; separate read-only CI, pin actions, explicit persistence paths. |

## Data credibility

Quotes are requested from a real API; they are not hardcoded. The audit alone does
not verify a current response, subscription entitlements, every sportsbook's
Ontario eligibility, market suspension status, or accuracy of provider updates.
Peer probabilities are normalized inverse odds (a market baseline), not independent
truth. The independent model uses historical goals, home/away means, fixed prior
strength 10, 24-match windows, 8-match minima and arbitrary rate bounds. It excludes
injuries, lineups, player data, fixture congestion, measured xG, and bookmaker
dependence. MLS and Champions League have no usable history adapter. NBA, MLB,
props, live prediction, conversational AI and performance metrics do not exist.

## Preservation and rollout

Retain Streamlit `app.py`, `scanner_core.py` public soccer helpers, Telegram bot
secret names, digest state, and existing workflow path. Refactor on the development
branch only. No production deploy, secret rotation, wager placement, paid signup or
unverified model promotion is authorized by this audit. Review and test before merge.

## Baseline verification

Working tree was clean and local baseline matched `origin/main`. No automated
tests existed. Scheduled runs are not verified from source inspection. Live
credentials, provider contracts, remote Actions execution and Streamlit deployment
require separate checks; they must not be reported as passed from this audit.
