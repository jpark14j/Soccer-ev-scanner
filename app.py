import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timezone

st.set_page_config(page_title="BetMGM Ontario Soccer EV Scanner", page_icon="⚽", layout="wide")
st.title("⚽ BetMGM Ontario Soccer EV Scanner")
st.caption("Live sportsbook quotes on demand. Estimates are not guarantees; no bets are placed.")
SPORTS = {"Premier League":"soccer_epl", "La Liga":"soccer_spain_la_liga", "Bundesliga":"soccer_germany_bundesliga", "Serie A":"soccer_italy_serie_a", "Ligue 1":"soccer_france_ligue_one", "MLS":"soccer_usa_mls", "Champions League":"soccer_uefa_champs_league"}
TARGET = "betmgm_ca_on"

try:
    api_key = st.secrets.get("ODDS_API_KEY", "")
except Exception:
    api_key = ""
if not api_key:
    st.error("Missing ODDS_API_KEY. Add it in your Streamlit app Settings → Secrets, then reload.")
    st.stop()

leagues = st.multiselect("Choose soccer leagues", list(SPORTS), default=["Premier League", "La Liga", "Bundesliga", "Serie A"])
threshold = st.slider("Highlight estimated EV at or above (%)", 0.0, 20.0, 0.0, 0.5)
st.info("BetMGM Ontario is the target bookmaker. Fair probabilities are approximated from other Canadian bookmakers' complete 1X2 markets after removing margin. This is not an independent predictive model.")

def scan():
    results, quotes, errors = [], [], []
    for league in leagues:
        try:
            response = requests.get(f"https://api.the-odds-api.com/v4/sports/{SPORTS[league]}/odds/", params={"apiKey":api_key,"regions":"ca","markets":"h2h","oddsFormat":"decimal"}, timeout=25)
            response.raise_for_status()
            for event in response.json():
                if event.get("commence_time", "") <= datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"):
                    continue
                home, away = event.get("home_team"), event.get("away_team")
                if not home or not away:
                    continue
                outcome_names = [home, "Draw", away]
                books = {}
                for book in event.get("bookmakers", []):
                    markets = [m for m in book.get("markets", []) if m.get("key") == "h2h"]
                    if not markets:
                        continue
                    prices = {o.get("name"): o.get("price") for o in markets[0].get("outcomes", [])}
                    if not all(isinstance(prices.get(n), (int, float)) and prices[n] > 1 for n in outcome_names):
                        continue
                    books[book["key"]] = (book.get("title", book["key"]), prices)
                    for name in outcome_names:
                        quotes.append({"League":league,"Match":f"{home} vs {away}","Kickoff (UTC)":event.get("commence_time"),"Sportsbook":book.get("title",book["key"]),"Selection":name,"Decimal odds":prices[name]})
                if TARGET not in books:
                    continue
                peers = [prices for key, (_, prices) in books.items() if key != TARGET]
                if not peers:
                    for name in outcome_names:
                        results.append({"League":league,"Match":f"{home} vs {away}","Kickoff (UTC)":event.get("commence_time"),"Selection":name,"BetMGM Ontario odds":books[TARGET][1][name],"Estimated fair probability (%)":None,"Estimated EV (%)":None,"Reference books":0})
                    continue
                fair_per_peer = []
                for prices in peers:
                    raw = {n:1/prices[n] for n in outcome_names}
                    total = sum(raw.values())
                    fair_per_peer.append({n:raw[n]/total for n in outcome_names})
                for name in outcome_names:
                    fair = sum(p[name] for p in fair_per_peer)/len(fair_per_peer)
                    odds = books[TARGET][1][name]
                    ev = (fair*odds-1)*100
                    results.append({"League":league,"Match":f"{home} vs {away}","Kickoff (UTC)":event.get("commence_time"),"Selection":name,"BetMGM Ontario odds":odds,"Estimated fair probability (%)":round(fair*100,2),"Estimated EV (%)":round(ev,2),"Reference books":len(peers)})
        except requests.HTTPError as e:
            errors.append(f"{league}: API HTTP {e.response.status_code} — {e.response.text[:180]}")
        except requests.RequestException as e:
            errors.append(f"{league}: connection issue — {e}")
        except (ValueError, KeyError, TypeError) as e:
            errors.append(f"{league}: unexpected data — {e}")
    return results, quotes, errors

if st.button("🔎 Find +EV Bets", type="primary"):
    if not leagues:
        st.warning("Select at least one league.")
    else:
        with st.spinner("Checking live Ontario soccer markets..."):
            st.session_state.scan_data = scan()

if "scan_data" in st.session_state:
    results, quotes, errors = st.session_state.scan_data
    for error in errors:
        st.warning(error)
    if quotes:
        st.success(f"Fetched {len(quotes)} live Canadian sportsbook quotes. BetMGM opportunities are shown only where reference books have comparable odds.")
        if results:
            df = pd.DataFrame(results).sort_values("Estimated EV (%)", ascending=False, na_position="last")
            st.subheader("All BetMGM Ontario selections — highest estimated EV first")
            positive = int((df["Estimated EV (%)"] >= threshold).sum())
            unavailable = int(df["Estimated EV (%)"].isna().sum())
            st.caption(f"{len(df)} BetMGM selections • {positive} at or above +{threshold:.1f}% estimated EV • {unavailable} without enough reference data. Green means the *estimate* meets your threshold, not a guaranteed edge.")
            def highlight_ev(row):
                value = row["Estimated EV (%)"]
                color = "background-color: #d9f4df; color: #165c2c" if pd.notna(value) and value >= threshold else ""
                return [color if col == "Estimated EV (%)" else "" for col in row.index]
            st.dataframe(df.style.apply(highlight_ev, axis=1).format({"Estimated fair probability (%)":"{:.2f}","Estimated EV (%)":"{:+.2f}"}, na_rep="N/A"), hide_index=True, use_container_width=True)
            st.download_button("Download all BetMGM estimates (CSV)", df.to_csv(index=False), "betmgm_all_estimates.csv", "text/csv")
        else:
            st.info("No BetMGM Ontario selections were returned for the chosen leagues. Try another league or scan later.")
        with st.expander("View all returned Canadian sportsbook odds"):
            st.dataframe(pd.DataFrame(quotes), hide_index=True, use_container_width=True)
    else:
        st.info("No usable Ontario soccer odds returned. Check API coverage, selected leagues, and any errors above.")

st.divider()
st.subheader("Manual BetMGM bet checker")
manual_odds = st.number_input("BetMGM decimal odds", min_value=1.01, value=2.10, step=0.01)
manual_prob = st.number_input("Your independently estimated win probability (%)", min_value=0.01, max_value=99.99, value=50.0, step=0.5)
if st.button("Calculate manual EV"):
    st.metric("Estimated EV", f"{(manual_prob/100*manual_odds-1)*100:+.2f}%")
st.caption("All BetMGM 1X2 selections are displayed, including negative estimated EV; N/A means insufficient comparison data. Only 1X2 soccer singles are automatically evaluated. Player props and parlays are not automatically scanned; same-game parlay legs may be correlated. API availability and quote freshness vary. Betting involves risk.")
