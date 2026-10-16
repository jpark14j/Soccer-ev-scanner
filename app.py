"""Existing Streamlit entry point: verified markets and evidence-gated analysis."""
import os
from pathlib import Path
from dataclasses import asdict
import json
import pandas as pd
import streamlit as st
from intelligence.domain import utcnow
from intelligence.ev import qualify
from intelligence.parlays import analyze, NO_PARLAYS
from intelligence.performance import metrics, breakdown
from intelligence.pipeline import configured_store, publish_current, run_analysis, Analysis
from intelligence.providers import LEAGUES, PROP_MARKETS
from intelligence.registry import load_registry

st.set_page_config(page_title='Sports Intelligence | Ontario',page_icon='⚽',layout='wide')
st.markdown('''<style>
.block-container {max-width:1200px;padding-top:2rem;}
[data-testid="stMetricValue"] {font-size:1.8rem;}
[data-testid="stSidebar"] {border-right:1px solid #263545;}
</style>''',unsafe_allow_html=True)
PAGES = ['AI Dashboard','Best Opportunities','AI Parlay Builder','NBA Analytics',
         'Soccer Analytics','MLB Analytics','Live Markets','AI Assistant','Performance Tracker','Settings']
registry = load_registry()
store = configured_store()


def secret(name):
    value = os.getenv(name,'')
    if value:
        return value
    try:
        return st.secrets.get(name,'')
    except (FileNotFoundError,st.errors.StreamlitSecretNotFoundError):
        return ''


key = secret('ODDS_API_KEY')
with st.sidebar:
    st.title('Sports Intelligence')
    st.caption('ONTARIO · NBA / SOCCER / MLB')
    page = st.radio('Workspace',PAGES,label_visibility='collapsed')
    leagues = st.multiselect('Competitions',list(LEAGUES),default=list(LEAGUES))
    books = st.multiselect('Sportsbooks in view',sorted(b['name'] for b in registry['books']),
                           default=sorted(b['name'] for b in registry['books']))
    # Provider titles vary; filter using the registry key rather than display text.
    book_keys = {b['odds_api_key'] for b in registry['books'] if b['name'] in books and b['odds_api_key']}
    st.caption('Quotes: The Odds API. Statistical estimates are separately labeled.')
    st.caption('19+ in Ontario. Analysis only. No wagers are placed.')


@st.cache_data(ttl=1800,show_spinner=False)
def load_analysis(api_key,competitions,db_path):
    return run_analysis(api_key,list(competitions),store=configured_store())


st.title(page)
st.caption('Real market observations · transparent model evidence · no forced recommendations')
if not key:
    st.info('Add ODDS_API_KEY in Streamlit Secrets or the environment to retrieve markets. Credentials are never stored in the repository.')
    result = Analysis()
else:
    with st.spinner('Loading available markets and checking model evidence…'):
        result = load_analysis(key,tuple(leagues),store.path)

if st.button('Refresh analysis',help='Uses the shared provider cache and daily credit cap; does not force chargeable polling.'):
    load_analysis.clear()
    st.rerun()

if result.checked_at:
    st.caption(f'Analysis loaded {result.checked_at}. Individual quote source times appear below. Provider cache: 30 minutes by default; recommendations expire after five minutes.')
for warning in result.warnings:
    st.warning(warning)
for error in result.errors:
    st.warning(error)


def current_opportunities(sport=None):
    now = utcnow()
    return [o for o in result.opportunities if o.quote.bookmaker in book_keys
            and (sport is None or o.quote.sport==sport) and qualify(o.quote,o.estimate,now)[0]]


def show_opportunities(opportunities):
    if not opportunities:
        st.info('No current opportunities meet the minimum analytical requirements. Missing evidence and expired quotes do not qualify.')
    for o in opportunities[:20]:
        q,e = o.quote,o.estimate
        with st.container(border=True):
            st.subheader(f'{q.selection} · {q.event}')
            st.caption(f'{q.sport} / {q.league} · {q.market} · {q.bookmaker_name}')
            a,b,c,d = st.columns(4)
            a.metric('Observed decimal odds',f'{q.odds:.2f}')
            b.metric('Model probability',f'{e.probability:.1%}')
            c.metric('Estimated EV',f'{o.ev:+.1%}')
            d.metric('Conservative EV',f'{o.conservative_ev:+.1%}')
            st.write(f'Qualifies because its validated model and current Ontario quote pass the uncertainty-adjusted EV threshold. Rank score: {o.score:.4f} = conservative EV × (1 − interval width).')
            st.caption(f'Empirical interval: {e.lower:.1%}–{e.upper:.1%} · model {e.model_version} · source update {q.source_updated_at} · received {q.received_at}')
            st.write('Risks: ' + '; '.join(e.risk_factors))


def show_markets(sport=None,live=False):
    now = utcnow()
    quotes = [q for q in result.quotes if q.bookmaker in book_keys and (sport is None or q.sport==sport)]
    if live:
        quotes = [q for q in quotes if 'in-play' in q.status(now)]
    research = {r['quote_id']:r for r in result.research}
    table = []
    for q in quotes:
        r = research.get(q.id,{})
        table.append({'Sport':q.sport,'Event':q.event,'Market':q.market,
                      'Participant':q.participant,'Selection':q.selection,'Line':q.point,
                      'Sportsbook':q.bookmaker_name,'Observed odds':q.odds,
                      'Source update':q.source_updated_at,'Received':q.received_at,
                      'Status':q.status(now),'Model estimate (research unless validated)':r.get('probability'),
                      'Model validated':r.get('validated',False)})
    if table:
        st.dataframe(pd.DataFrame(table),hide_index=True,use_container_width=True)
    else:
        st.info('No markets returned for this view. Availability depends on the provider, current events and account entitlements.')
    st.caption('Provider-observed prices are not an execution guarantee. Confirm current price, rules and suspension status at the Ontario sportsbook.')


@st.fragment(run_every='60s')
def dashboard():
    # Recheck quote expiry without any network calls on this timer.
    opportunities = current_opportunities()
    current = [q for q in result.quotes if q.bookmaker in book_keys and q.status()=='current']
    a,b,c = st.columns(3)
    a.metric('Qualifying singles',len(opportunities))
    b.metric('Current Ontario quotes',len(current))
    c.metric('Books observed',len({q.bookmaker for q in current}))
    show_opportunities(opportunities)
    st.subheader('Analytical readiness')
    st.dataframe(pd.DataFrame([
        {'Sport':'NBA','Markets':'Real provider feed','Model':'Normal margin candidate; licensed history and validation required'},
        {'Sport':'Soccer','Markets':'Real provider feed','Model':'Historical-goals Poisson candidate; chronological evaluation available'},
        {'Sport':'MLB','Markets':'Real provider feed','Model':'Run-count Poisson candidate; licensed history and validation required'}]),hide_index=True,use_container_width=True)
    st.info(NO_PARLAYS)
    with st.expander('Why selections did not qualify'):
        st.json(result.exclusions)


# A displayed recommendation gets a permanent immutable publication record. Cached
# quotes are checked again immediately before publication.
published = publish_current(result,store)
if published:
    from intelligence.ledger import archive
    archive(store,os.getenv('PREDICTION_LEDGER_DIR','ledger'))
if page=='AI Dashboard':
    dashboard()
elif page=='Best Opportunities':
    show_opportunities(current_opportunities())
    st.caption('The best available qualifying price is selected per equivalent selection. Market-implied probabilities are comparison baselines, never treated as independently estimated truth.')
elif page=='AI Parlay Builder':
    st.info(NO_PARLAYS)
    eligible = current_opportunities()
    chosen = st.multiselect('Qualifying legs to evaluate',range(len(eligible)),
                            format_func=lambda i:f'{eligible[i].quote.sport}: {eligible[i].quote.event} / {eligible[i].quote.selection}')
    if 2<=len(chosen)<=6:
        analysis = analyze([eligible[i] for i in chosen])
        lower,upper = analysis['probability_bounds']
        st.write(f'Theoretical joint probability bounds: {lower:.1%}–{upper:.1%}.')
        st.caption(analysis['reason']+'. No executable combined price or parlay EV is asserted.')
    st.write('Lower-variance, balanced and higher-variance categories require a validated joint model, sportsbook restrictions, and an actual combined quote. Different games or sports do not establish independence.')
elif page in ('NBA Analytics','Soccer Analytics','MLB Analytics'):
    sport = page.split()[0]
    show_opportunities(current_opportunities(sport))
    st.subheader('Observed markets and research estimates')
    show_markets(sport)
    evidence_file=Path('docs/evidence')/({'NBA':'nba-research.json','MLB':'mlb-research.json','Soccer':'premier-league-research.json'}[sport])
    if evidence_file.exists():
        with st.expander('Historical research evaluation — not forward performance'):
            evidence=json.loads(evidence_file.read_text())
            st.write(f'Data through {evidence["data_end"]}; untouched test events: {evidence["test_n"]}. Status: research only.')
            st.json({'diagnostic_scores':evidence['metrics'],'simple_baseline':evidence.get('simple_baseline_metrics'),'market_baseline':evidence['baseline_metrics'],'publication_blockers':evidence['promotion_blockers']})
    st.caption('Player-prop ingestion is available through the event endpoint. Prop forecasting requires licensed player history, availability inputs and market-specific validation; it is not enabled.')
elif page=='Live Markets':
    st.warning('Live recommendations are unavailable. Current odds alone do not supply verified game clock, score, player state, latency or suspension information. Pregame models are never applied in play.')
    show_markets(live=True)
elif page=='AI Assistant':
    from intelligence.chat_ui import render_assistant
    render_assistant(result,store,secret)
elif page=='Performance Tracker':
    origin = st.radio('Record type',['forward','backtest'],horizontal=True)
    records = store.records(origin)
    summary = metrics(records)
    if not records:
        st.info('No published predictions in this ledger. Performance metrics will appear only after genuine publications and evidence-backed settlements.')
    else:
        st.json(summary)
        dimension = st.selectbox('Break down by',['sport','market','model_version'])
        st.json(breakdown(records,dimension))
        st.dataframe(pd.DataFrame([{'Published':r['at'],'Sport':r['payload']['quote']['sport'],
                                   'Event':r['payload']['quote']['event'],'Selection':r['payload']['quote']['selection'],
                                   'Outcome':r['outcome'],'Result evidence':r['source']} for r in records]),hide_index=True,use_container_width=True)
    st.warning('This Streamlit instance needs persistent storage and backups before publication to subscribers. The scheduled workflow archives derived predictions in GitHub; Streamlit local files are not automatically pushed.')
    st.caption('One hypothetical unit per selection. Pushes return stake; voids excluded from turnover. Brier/log loss exclude pushes and voids. Closing-line value needs an evidenced closing price. Losses remain recorded.')
elif page=='Settings':
    st.write('Competition and sportsbook view preferences are in the sidebar and last for this browser session.')
    st.write(f'Local daily credit cap: {os.getenv("ODDS_DAILY_CREDITS","16")}. Default retrieval cache: 30 minutes. No subscriptions are purchased by the application.')
    st.write(f'Ontario directory effective date: {registry["directory_as_of"]}. Review expires {registry["review_expires_at"]}. Expired evidence disables eligibility.')
    st.dataframe(pd.DataFrame(registry['books']),hide_index=True,use_container_width=True)
    st.link_button('Official Ontario directory',registry['source'])
    from intelligence.analyst_config import load_config
    analyst_config = load_config(secret)
    st.subheader('Connections')
    st.write({'Odds key configured':bool(key),'Telegram bot configured':bool(secret('TELEGRAM_BOT_TOKEN')),
              'Paid conversational API':'Configured; session consent required' if analyst_config.paid_ready else 'Disabled or unconfigured','NBA/MLB historical data':'Free research imports / licensed files / locally collected completed results'})
    st.caption('Scheduling and Telegram preferences use environment variables documented in README. API keys belong in Streamlit Secrets or GitHub Actions Secrets.')
    st.subheader('Additional market requests')
    st.json(PROP_MARKETS)
    st.caption('These are provider request keys, not claims of Ontario availability. Event-specific requests consume quota and are opt-in through the adapter.')

for manifest in Path(os.getenv('HISTORY_DIR','data/history')).glob('*.source.json'):
    try:
        attribution=json.loads(manifest.read_text()).get('attribution')
        if attribution:
            st.caption(attribution)
    except (OSError,ValueError):
        pass
st.divider()
st.caption('19+ · Ontario · Statistical estimates can be wrong. Positive estimated EV does not predict an individual win. Set limits; never chase losses. Support: ConnexOntario 1-866-531-2600 / connexontario.ca. No automatic wagering.')
