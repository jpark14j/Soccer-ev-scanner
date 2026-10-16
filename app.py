"""Existing Streamlit entry point: verified markets and evidence-gated analysis."""
import os
from pathlib import Path
import json
import pandas as pd
import streamlit as st
from intelligence.domain import digest,parse_time,utcnow
from intelligence.ev import qualify
from intelligence.pipeline import configured_store, publish_current, run_analysis, Analysis
from intelligence.providers import LEAGUES
from intelligence.registry import load_registry
from intelligence.markets import selection_label,scope

st.set_page_config(page_title='Sports Intelligence | Ontario',page_icon='⚽',layout='wide')
st.markdown('''<style>
.block-container {max-width:1200px;padding-top:2rem;}
[data-testid="stMetricValue"] {font-size:1.8rem;}
[data-testid="stSidebar"] {border-right:1px solid #263545;}
</style>''',unsafe_allow_html=True)
from intelligence.navigation import PAGES,destination
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


from intelligence.data_settings import load_settings
data_settings=load_settings(secret)
from intelligence.current_results import configuration as results_configuration
results_config=results_configuration(secret)
key = secret('ODDS_API_KEY')
with st.sidebar:
    st.title('Sports Intelligence')
    st.caption('ONTARIO · NBA / SOCCER / MLB')
    page = st.radio('Workspace',[d.name for d in PAGES],label_visibility='collapsed',key='workspace')
    leagues = st.multiselect('Competitions',list(LEAGUES),default=['NBA','Premier League','MLB'])
    books = st.multiselect('Sportsbooks in view',sorted(b['name'] for b in registry['books']),
                           default=sorted(b['name'] for b in registry['books']))
    # Provider titles vary; filter using the registry key rather than display text.
    book_keys = {b['odds_api_key'] for b in registry['books'] if b['name'] in books and b['odds_api_key']}
    st.caption('Quotes: The Odds API. Statistical estimates are separately labeled.')
    st.caption('19+ in Ontario. Analysis only. No wagers are placed.')


@st.cache_data(ttl=1800,show_spinner=False)
def load_analysis(api_key,competitions,db_path,cap,ttl,collect_results,window_hours,results_scope):
    from intelligence.providers import OddsAPI
    data_store=configured_store()
    provider=OddsAPI(api_key,data_store,daily_limit=cap,ttl=ttl)
    return run_analysis(api_key,list(competitions),store=data_store,provider=provider,collect_results=collect_results,autonomous=True,window_hours=window_hours)


st.title(page)
st.caption('Real market observations · transparent model evidence · no forced recommendations')
results_scope=(results_config.enabled,results_config.use_reviewed,digest(results_config.token))
snapshot_scope=(tuple(leagues),digest(key),store.path,data_settings.daily_limit,data_settings.cache_seconds,data_settings.collect_results,data_settings.window_hours,results_scope)
snapshot=st.session_state.get('_research_snapshot')
if snapshot and snapshot.get('scope')==snapshot_scope:
    result=snapshot['analysis']
elif not key:
    st.info('Add ODDS_API_KEY in Streamlit Secrets or the environment to retrieve markets. Credentials are never stored in the repository.')
    result = Analysis()
else:
    with st.spinner('Loading available markets and checking model evidence…'):
        result = load_analysis(key,tuple(leagues),store.path,data_settings.daily_limit,data_settings.cache_seconds,data_settings.collect_results,data_settings.window_hours,results_scope)

if not snapshot or snapshot.get('scope')!=snapshot_scope:
    st.session_state['_research_snapshot']={'scope':snapshot_scope,'analysis':result,'stored_at':utcnow().isoformat()}
st.caption('Pages and filters reuse this session’s scan. Prices still expire after five minutes; use Refresh analysis to request an updated capped scan.')

if st.button('Refresh analysis',help='Uses the shared provider cache and daily credit cap; does not force chargeable polling.'):
    st.session_state.pop('_research_snapshot',None)
    load_analysis.clear()
    st.rerun()

if result.checked_at:
    st.caption(f'Analysis loaded {result.checked_at}. Individual quote source times appear below. Provider cache: 30 minutes by default; recommendations expire after five minutes.')
from intelligence.market_ui import quota_banner
result.quota=quota_banner(store,data_settings)
for error in data_settings.errors:
    st.warning(error)
if result.errors or result.warnings:
    with st.expander('Collection warnings and coverage limitations'):
        for warning in dict.fromkeys(result.warnings+result.errors):
            st.text(warning)


def current_opportunities(sport=None):
    now = utcnow()
    return [o for o in result.opportunities if o.quote.bookmaker in book_keys
            and (sport is None or o.quote.sport==sport) and qualify(o.quote,o.estimate,now)[0]]



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
                      'Participant':q.participant,'Selection':selection_label(q),'Settlement scope':scope(q),'Line':q.point,
                      'Sportsbook':q.bookmaker_name,'Observed odds':q.odds,
                      'Source update':q.source_updated_at,'Received':q.received_at,
                      'Status':q.status(now),'Model estimate (research unless validated)':r.get('probability'),
                      'Model validated':r.get('validated',False),'Model version':r.get('model'),
                      'Model history through':r.get('training_end'),'Probability envelope':(r.get('lower'),r.get('upper')) if r.get('probability') is not None else None})
    with st.expander('Advanced Details / Raw Market Data',expanded=False):
        if table:
            from intelligence.chat_privacy import redact_data
            from intelligence.analyst_config import load_config
            st.dataframe(pd.DataFrame(redact_data(table,load_config(secret).sensitive_values)),hide_index=True,use_container_width=True)
        else:
            st.info('No market observations match this view.')
        st.caption('Historical/stale prices are inspection-only. Provider observations are not execution guarantees; settlement scope remains unverified.')


def refresh_selected(selected_leagues,markets=('h2h',),event_id=None,discovered=()):
    from intelligence.research_refresh import refresh_research,refresh_event
    fresh=(refresh_event(result,key,selected_leagues[0],event_id,markets,store,limit=data_settings.daily_limit,discovered=discovered) if event_id else
        refresh_research(result,key,selected_leagues,store,markets=markets,limit=data_settings.daily_limit))
    st.session_state['_research_snapshot']={'scope':snapshot_scope,'analysis':fresh,'stored_at':utcnow().isoformat()}


# Recheck existing publication gates; browsing pages never creates new API requests.
published=publish_current(result,store)
if published:
    from intelligence.ledger import archive
    archive(store,os.getenv('PREDICTION_LEDGER_DIR','ledger'))
from intelligence.workspace_ui import Workspace,render_picks,render_tools
workspace=Workspace(result,store,data_settings,book_keys,leagues,key,secret,refresh_selected,show_markets,current_opportunities)
route=destination(page).renderer
if route=='dashboard':
    @st.fragment(run_every='60s')
    def dashboard():
        from intelligence.research_views import render_daily_dashboard
        render_daily_dashboard(result,store,data_settings,book_keys,secret)
    dashboard()
elif route=='picks':
    render_picks(workspace)
elif route=='performance':
    from intelligence.performance_ui import render_performance
    render_performance(store)
else:
    render_tools(workspace)

for manifest in Path(os.getenv('HISTORY_DIR','data/history')).glob('*.source.json'):
    try:
        attribution=json.loads(manifest.read_text()).get('attribution')
        if attribution:
            st.caption(attribution)
    except (OSError,ValueError):
        pass
st.divider()
from intelligence.free_history import RETRO_ATTRIBUTION
st.caption(RETRO_ATTRIBUTION)
st.caption('19+ · Ontario · Statistical estimates can be wrong. Positive estimated EV does not predict an individual win. Set limits; never chase losses. Support: ConnexOntario 1-866-531-2600 / connexontario.ca. No automatic wagering.')
