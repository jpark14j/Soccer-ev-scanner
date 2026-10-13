"""Soccer Picks — mobile-first, explainable market-consensus research prototype."""
import itertools
from datetime import datetime, timezone
import requests
import streamlit as st

st.set_page_config(page_title="Soccer Picks | Ontario", page_icon="⚽", layout="centered")
SPORTS = {"Premier League":"soccer_epl", "La Liga":"soccer_spain_la_liga", "Bundesliga":"soccer_germany_bundesliga", "Serie A":"soccer_italy_serie_a", "Ligue 1":"soccer_france_ligue_one", "MLS":"soccer_usa_mls", "Champions League":"soccer_uefa_champs_league"}
TARGET = "betmgm_ca_on"
MIN_PEERS = 3
MIN_EDGE = 0.01  # conservative display threshold, not a validated model edge

st.markdown("""<style>
.block-container {padding-top: 1.5rem; max-width: 760px;}
[data-testid="stMetricValue"] {font-size: 1.6rem;}
</style>""", unsafe_allow_html=True)
st.title("⚽ Soccer Picks")
st.caption("One tap. A few picks to review. No forced bets.")
st.info("**Research prototype:** probabilities come from other sportsbooks, not a tested team model. Estimates are not guaranteed winning chances.")

try:
    KEY = st.secrets.get("ODDS_API_KEY", "")
except Exception:
    KEY = ""
if not KEY:
    st.error("Add ODDS_API_KEY to Streamlit Settings → Secrets. Never publish your key in GitHub.")
    st.stop()

with st.expander("⚙️ Leagues", expanded=False):
    leagues = st.multiselect("Scan these leagues", list(SPORTS), default=["Premier League", "La Liga", "Bundesliga", "Serie A"])


def read_market(event, league):
    home, away = event.get("home_team"), event.get("away_team")
    if not home or not away:
        return []
    names = (home, "Draw", away)
    books = {}
    for book in event.get("bookmakers", []):
        for market in book.get("markets", []):
            if market.get("key") != "h2h":
                continue
            prices = {x.get("name"): x.get("price") for x in market.get("outcomes", [])}
            if all(isinstance(prices.get(n), (float, int)) and prices[n] > 1 for n in names):
                books[book.get("key")] = prices
            break
    if TARGET not in books:
        return []
    peers = [p for k, p in books.items() if k != TARGET]
    if len(peers) < MIN_PEERS:
        return []
    probabilities = []
    for prices in peers:
        implied = {n: 1 / prices[n] for n in names}
        total = sum(implied.values())
        probabilities.append({n: implied[n] / total for n in names})
    rows = []
    for selection in names:
        p = sum(x[selection] for x in probabilities) / len(probabilities)
        odds = books[TARGET][selection]
        rows.append({"event_id": event.get("id", f"{home}-{away}-{event.get('commence_time')}"),
                     "league": league, "match": f"{home} vs {away}", "kickoff": event.get("commence_time", ""),
                     "selection": selection, "odds": odds, "prob": p, "edge": p * odds - 1,
                     "peers": len(peers)})
    return rows


def scan(leagues):
    rows, errors = [], []
    now = datetime.now(timezone.utc)
    for league in leagues:
        try:
            response = requests.get(f"https://api.the-odds-api.com/v4/sports/{SPORTS[league]}/odds/",
                                    params={"apiKey": KEY, "regions": "ca", "markets": "h2h", "oddsFormat": "decimal"}, timeout=25)
            response.raise_for_status()
            for event in response.json():
                try:
                    kickoff = datetime.fromisoformat(event.get("commence_time", "").replace("Z", "+00:00"))
                    if kickoff <= now:
                        continue
                    rows.extend(read_market(event, league))
                except (ValueError, TypeError):
                    continue
        except (requests.RequestException, ValueError, TypeError) as exc:
            errors.append(f"{league}: {str(exc)[:130]}")
    return rows, errors, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def shortlist(rows):
    """Rank singles and two-leg parlays together; never force either bet type."""
    qualified = [r for r in rows if r["edge"] >= MIN_EDGE and r["peers"] >= MIN_PEERS]
    # One selection per event for parlay construction; avoid duplicate/opposing legs.
    singles = sorted(qualified, key=lambda r: (r["edge"] * (r["prob"] ** 0.5), r["prob"]), reverse=True)
    choices = []
    for row in singles[:35]:
        choices.append({"kind": "Single", "legs": [row], "prob": row["prob"],
                        "odds": row["odds"], "edge": row["edge"],
                        "score": row["edge"] * (row["prob"] ** 0.5)})
    # Construct parlays from different matches only. Avoid very low-probability combinations.
    for a, b in itertools.combinations(singles[:35], 2):
        if a["event_id"] == b["event_id"]:
            continue
        prob = a["prob"] * b["prob"]
        if prob < 0.25:
            continue
        odds = a["odds"] * b["odds"]
        edge = prob * odds - 1
        if edge < MIN_EDGE:
            continue
        choices.append({"kind": "2-leg parlay", "legs": [a, b], "prob": prob,
                        "odds": odds, "edge": edge,
                        # Small complexity discount: estimated parlay probabilities are less robust.
                        "score": 0.75 * edge * (prob ** 0.5)})
    choices.sort(key=lambda c: (c["score"], c["prob"]), reverse=True)
    # Limit repetition of the same match across recommendations.
    output, seen_events = [], set()
    for choice in choices:
        event_ids = {leg["event_id"] for leg in choice["legs"]}
        if event_ids & seen_events:
            continue
        output.append(choice)
        seen_events.update(event_ids)
        if len(output) == 3:
            break
    return output


def show_pick(choice, number):
    with st.container(border=True):
        st.markdown(f"### #{number} · {choice['kind']}")
        for i, leg in enumerate(choice["legs"], 1):
            prefix = f"Leg {i}: " if len(choice["legs"]) > 1 else ""
            st.markdown(f"{prefix}**{leg['selection']}** · {leg['match']} ({leg['league']})")
            st.caption(f"Kickoff: {leg['kickoff']}")
        left, right = st.columns(2)
        left.metric("BetMGM odds", f"{choice['odds']:.2f}")
        right.metric("Est. chance", f"{choice['prob']:.0%}")
        if len(choice["legs"]) == 1:
            st.write(f"**Why shown:** {choice['legs'][0]['peers']} comparison sportsbooks imply a slightly better chance than BetMGM's price suggests.")
        else:
            st.write("**Why shown:** Both legs passed the same market-price checks individually. Different matches only; combined chance assumes independence.")
        st.caption(f"Indicative market-based edge: {choice['edge']:+.1%}. Not a verified advantage or validated prediction.")

if st.button("🔎 Find My Best Picks", type="primary", use_container_width=True):
    if not leagues:
        st.warning("Choose at least one league in Settings.")
    else:
        with st.spinner("Checking BetMGM Ontario and comparison prices…"):
            st.session_state.latest = scan(leagues)

if "latest" in st.session_state:
    rows, errors, timestamp = st.session_state.latest
    st.caption(f"Last checked: {timestamp} · {len(set(r['event_id'] for r in rows))} comparable matches")
    for error in errors:
        st.warning(error)
    picks = shortlist(rows)
    st.subheader("🏆 Best picks")
    if picks:
        st.caption("Singles and parlays compete in one ranking. Only opportunities passing price checks appear; up to three are shown.")
        for index, pick in enumerate(picks, 1):
            show_pick(pick, index)
    else:
        st.success("**No strong picks right now.** Nothing passed the minimum price checks. Check again later.")
    with st.expander("How this works · important limitations"):
        st.write("This prototype estimates outcome probabilities using other Canadian sportsbooks' complete 1X2 markets after removing their margin. It requires at least three comparison books and a 1% indicative price difference. It then ranks singles and eligible two-leg parlays together, showing up to three without repeating matches. Parlay chances multiply individual estimates and assume different-match outcomes are independent. These estimates are **not validated win probabilities**, and the ranking is not a trained AI model. It does not yet use team statistics, injury news, xG, or backtesting. A high chance does not necessarily mean good value. Prices can change. The app does not place bets.")
    import csv
    import io
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["league", "match", "kickoff", "selection", "odds", "market_probability", "indicative_edge", "reference_books"])
    writer.writeheader()
    for r in rows:
        writer.writerow({"league": r["league"], "match": r["match"], "kickoff": r["kickoff"], "selection": r["selection"], "odds": r["odds"], "market_probability": round(r["prob"], 5), "indicative_edge": round(r["edge"], 5), "reference_books": r["peers"]})
    st.download_button("Export analysis (CSV)", data=buffer.getvalue(), file_name="soccer_research.csv", mime="text/csv")
else:
    st.write("Tap the button to scan live soccer odds and see up to three simple recommendations.")

st.divider()
st.caption("18+ only where legal. This is a research tool, not financial advice or a promise of winnings. No bets are placed. Check local rules and sportsbook terms.")
