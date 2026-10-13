"""Soccer Picks — mobile-first, explainable market-consensus research prototype."""
import itertools
import io
import math
import difflib
import pandas as pd
from datetime import datetime, timezone
import requests
import streamlit as st

st.set_page_config(page_title="Soccer Picks | Ontario", page_icon="⚽", layout="centered")
SPORTS = {"Premier League":"soccer_epl", "La Liga":"soccer_spain_la_liga", "Bundesliga":"soccer_germany_bundesliga", "Serie A":"soccer_italy_serie_a", "Ligue 1":"soccer_france_ligue_one", "MLS":"soccer_usa_mls", "Champions League":"soccer_uefa_champs_league"}
TARGET = "betmgm_ca_on"
MIN_PEERS = 3
MIN_EDGE = 0.01  # indicative price gap, not a validated betting edge
HISTORY_LEAGUES = {"Premier League": "E0", "La Liga": "SP1", "Bundesliga": "D1", "Serie A": "I1", "Ligue 1": "F1"}
HISTORY_SEASONS = ("2425", "2526", "2627")
ALIASES = {"manchester united":"man united", "manchester city":"man city", "tottenham hotspur":"tottenham", "newcastle united":"newcastle", "west ham united":"west ham", "wolverhampton wanderers":"wolves", "brighton and hove albion":"brighton", "nottingham forest":"nottm forest", "internazionale":"inter", "inter milan":"inter", "ac milan":"milan", "atletico madrid":"ath madrid", "athletic club":"ath bilbao", "real betis":"betis", "bayern munich":"bayern munich", "borussia dortmund":"dortmund", "rb leipzig":"rb leipzig", "bayer leverkusen":"leverkusen", "paris saint germain":"paris sg", "olympique marseille":"marseille", "olympique lyonnais":"lyon", "as roma":"roma", "juventus turin":"juventus", "ssc napoli":"napoli", "hellas verona":"verona"}


st.markdown("""<style>
.block-container {padding-top: 1.5rem; max-width: 760px;}
[data-testid="stMetricValue"] {font-size: 1.6rem;}
</style>""", unsafe_allow_html=True)
st.title("⚽ Soccer Picks")
st.caption("One tap. A few picks to review. No forced bets.")
st.info("**Experimental research tool:** uses historical match results to cross-check sportsbook estimates where data is available. The model is not backtested or validated; no wins are guaranteed.")

try:
    KEY = st.secrets.get("ODDS_API_KEY", "")
except Exception:
    KEY = ""
if not KEY:
    st.error("Add ODDS_API_KEY to Streamlit Settings → Secrets. Never publish your key in GitHub.")
    st.stop()

with st.expander("⚙️ Leagues", expanded=False):
    leagues = st.multiselect("Scan these leagues", list(SPORTS), default=["Premier League", "La Liga", "Bundesliga", "Serie A"])


@st.cache_data(ttl=21600, show_spinner=False)
def load_history(league):
    """Historical match results from public football-data.co.uk CSVs; no credentials required."""
    code = HISTORY_LEAGUES.get(league)
    if not code:
        return pd.DataFrame()
    frames = []
    for season in HISTORY_SEASONS:
        url = f"https://www.football-data.co.uk/mmz4281/{season}/{code}.csv"
        try:
            response = requests.get(url, timeout=12, headers={"User-Agent": "SoccerPicksResearch/1.0"})
            response.raise_for_status()
            df = pd.read_csv(io.BytesIO(response.content), on_bad_lines="skip")
            needed = {"Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"}
            if needed.issubset(df.columns):
                frames.append(df[list(needed)].copy())
        except (requests.RequestException, ValueError, pd.errors.ParserError):
            continue
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    for col in ("FTHG", "FTAG"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"])
    df = df[(df.FTHG >= 0) & (df.FTAG >= 0)].sort_values("date")
    return df


def canonical(name):
    import re
    cleaned = re.sub(r"[^a-z0-9 ]", "", str(name).lower()).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return ALIASES.get(cleaned, cleaned)


def match_team(name, options):
    index = {canonical(option): option for option in options}
    key = canonical(name)
    if key in index:
        return index[key]
    matches = difflib.get_close_matches(key, list(index), n=2, cutoff=0.86)
    # Reject ambiguous fuzzy matches rather than attach the wrong team's statistics.
    if len(matches) != 1:
        return None
    return index[matches[0]]


def poisson_1x2(home_xg, away_xg, max_goals=12):
    def pmf(rate):
        return [math.exp(-rate) * rate**k / math.factorial(k) for k in range(max_goals + 1)]
    h, a = pmf(home_xg), pmf(away_xg)
    home_win = sum(h[i] * a[j] for i in range(len(h)) for j in range(i))
    draw = sum(h[i] * a[i] for i in range(len(h)))
    away_win = sum(h[i] * a[j] for i in range(len(h)) for j in range(i + 1, len(h)))
    total = home_win + draw + away_win
    return [home_win / total, draw / total, away_win / total]


def independent_prediction(history, home_name, away_name, kickoff):
    """Simple shrinkage Poisson strength model; explicitly unvalidated."""
    if history.empty:
        return None
    try:
        cutoff = pd.Timestamp(datetime.fromisoformat(kickoff.replace("Z", "+00:00"))).tz_localize(None)
    except (TypeError, ValueError):
        return None
    past = history[history.date < cutoff].copy()
    if len(past) < 80:
        return None
    teams = set(past.HomeTeam) | set(past.AwayTeam)
    home = match_team(home_name, teams)
    away = match_team(away_name, teams)
    if home is None or away is None or home == away:
        return None
    home_games = past[past.HomeTeam == home].tail(24)
    away_games = past[past.AwayTeam == away].tail(24)
    if len(home_games) < 8 or len(away_games) < 8:
        return None
    league_home = float(past.FTHG.tail(450).mean())
    league_away = float(past.FTAG.tail(450).mean())
    if min(league_home, league_away) <= 0:
        return None
    # Shrink toward league average to avoid overreacting to small samples.
    prior = 10
    home_scored = (home_games.FTHG.sum() + prior * league_home) / (len(home_games) + prior)
    home_allowed = (home_games.FTAG.sum() + prior * league_away) / (len(home_games) + prior)
    away_scored = (away_games.FTAG.sum() + prior * league_away) / (len(away_games) + prior)
    away_allowed = (away_games.FTHG.sum() + prior * league_home) / (len(away_games) + prior)
    expected_home = min(4.0, max(0.2, home_scored * away_allowed / league_home))
    expected_away = min(4.0, max(0.2, away_scored * home_allowed / league_away))
    probs = poisson_1x2(expected_home, expected_away)
    return {"probabilities": probs, "home_xg": expected_home, "away_xg": expected_away,
            "home_games": len(home_games), "away_games": len(away_games)}


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
                     "peers": len(peers), "home": home, "away": away})
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
    qualified = [r for r in rows if r["edge"] >= MIN_EDGE and r["peers"] >= MIN_PEERS and r.get("model_prob") is not None and r["model_prob"] >= r["prob"]]
    # Require an independent historical-results model to agree with the market signal.
    # Conservative ranking uses the lower of model and market probabilities.
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
            st.write("**Why shown:** Historical team-results model agrees with the price comparison. Neither estimate is validated.")
        else:
            st.write("**Why shown:** Both matches passed the price checks and independent historical-results cross-check. Combined chance assumes independence.")
        st.caption(f"Indicative price difference: {choice['edge']:+.1%}. Estimated chance uses conservative market/model comparison. Unvalidated; not a verified advantage.")

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
    # Fetch team results only when the user scans. Fail closed when data is missing.
    if rows:
        with st.spinner("Cross-checking historical team performance…"):
            histories = {league: load_history(league) for league in set(r["league"] for r in rows)}
            predictions = {}
            for row in rows:
                key = (row["event_id"], row["league"])
                if key not in predictions:
                    predictions[key] = independent_prediction(histories[row["league"]], row["home"], row["away"], row["kickoff"])
                model = predictions[key]
                if model:
                    index = 0 if row["selection"] == row["home"] else 1 if row["selection"] == "Draw" else 2
                    row["model_prob"] = model["probabilities"][index]
                    row["model_xg"] = (model["home_xg"], model["away_xg"])
                    row["prob"] = min(row["prob"], row["model_prob"])
                    row["edge"] = row["prob"] * row["odds"] - 1
                else:
                    row["model_prob"] = None
    picks = shortlist(rows)
    st.subheader("🏆 Best picks")
    if picks:
        st.caption("Singles and parlays compete in one ranking. Only opportunities passing price checks appear; up to three are shown.")
        for index, pick in enumerate(picks, 1):
            show_pick(pick, index)
    else:
        st.success("**No strong picks right now.** Nothing passed both the sportsbook price checks and the historical-results cross-check. Check again later.")
    with st.expander("How this works · important limitations"):
        st.write("The app checks BetMGM Ontario against at least three other Canadian sportsbooks, then independently estimates match probabilities from historical league results (football-data.co.uk) using a basic home/away Poisson goals model. It only shows picks where the two methods agree and the conservative estimate passes a 1% indicative price check. Some leagues, newly promoted teams, and cup matches may have no usable history. **The model has not been backtested, calibrated, or shown to beat the market.** Historical goals are not provider xG; injuries, lineups, and player props are not included. Two-leg parlay probabilities assume independence, which may not hold. Data and odds may be stale; verify before acting. No bets are placed.")
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
