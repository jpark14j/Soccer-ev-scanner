# Soccer EV Scanner — prototype

Mobile-friendly Streamlit dashboard for Toronto, Ontario. It runs **only when the user presses Find +EV Bets**. No Telegram or background scanning.

## Run locally (optional)
`pip install -r requirements.txt`
`streamlit run app.py`

## Publish online
1. Create a GitHub repository and upload `app.py` and `requirements.txt`.
2. Sign in to Streamlit Community Cloud and deploy that repository with `app.py` as the entry point.
3. Open the deployed URL on a phone and add it to the Home Screen if desired.

## Data source status
**No live sportsbook API is connected.** The demo is fictional. To use uploaded data, prepare a CSV with:
`event_id,kickoff,league,match,market,selection,book,decimal_odds,fair_probability`

- `kickoff`: ISO 8601 timestamp including timezone (e.g. `2026-10-15T19:00:00-04:00`)
- `decimal_odds`: >1
- `fair_probability`: between 0 and 1, estimated independently
- `event_id`: identical for markets from the same match

The prototype computes estimated EV and indicative independent-event parlays. Parlay payouts are **not** verified with DraftKings. A provider supporting Ontario-specific odds and player props must be verified before live functionality is possible.
