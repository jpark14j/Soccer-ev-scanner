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
h1 {letter-spacing:-0.03em;}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:14px;}
[data-testid="stMetricValue"] {font-size:1.8rem;}
[data-testid="stSidebar"] {border-right:1px solid #263545;}
@media (max-width:640px) {.block-container {padding:1.2rem 1rem;} h1 {font-size:1.9rem;}}
</style>''',unsafe_allow_html=True)
from intelligence.navigation import PAGES,destination
registry = load_registry()


def secret(name):
    value = os.getenv(name,'')
    if value:
        return value
    try:
        return st.secrets.get(name,'')
    except (FileNotFoundError,st.errors.StreamlitSecretNotFoundError):
        return ''


from intelligence.shared_state import configuration as shared_configuration,StateError
shared_config=shared_configuration(secret)
shared_problem=None
if shared_config.enabled:
    @st.cache_data(ttl=300,show_spinner=False)
    def sync_shared_state(scope,directory,_config):
        from intelligence.shared_state import pull_replica
        return pull_replica(directory,_config)
    try:
        sync_shared_state((shared_config.url,digest((shared_config.reader_key,shared_config.reader_token))),
            os.getenv('RESEARCH_REPLICA_DIR') or secret('RESEARCH_REPLICA_DIR') or 'data/shared-replica',shared_config)
    except (StateError,OSError,ValueError):
        shared_problem='Shared-state synchronization unavailable. The last verified saved replica is retained; no sports-provider requests are made.'
store = configured_store(secret)
if shared_problem:st.info('Saved research could not be updated. The last verified copy is kept; no picks are created from missing data.')
from intelligence.data_settings import load_settings
data_settings=load_settings(secret)
from intelligence.current_results import configuration as results_configuration
results_config=results_configuration(secret)
key = secret('ODDS_API_KEY')
with st.sidebar:
    st.title('Sports Intelligence')
    st.caption('ONTARIO · NBA / SOCCER / MLB')
    if st.session_state.get('workspace') not in {d.name for d in PAGES}:
        st.session_state['workspace']='Settings' if st.session_state.get('workspace')=='Settings & Research Tools' else 'Home'
    page = st.radio('Workspace',[d.name for d in PAGES],label_visibility='collapsed',key='workspace')
    leagues = st.multiselect('Competitions',list(LEAGUES),default=['NBA','Premier League','Bundesliga','Ligue 1','MLB'])
    books = st.multiselect('Sportsbooks in view',sorted(b['name'] for b in registry['books']),
                           default=sorted(b['name'] for b in registry['books']))
    # Provider titles vary; filter using the registry key rather than display text.
    book_keys = {b['odds_api_key'] for b in registry['books'] if b['name'] in books and b['odds_api_key']}
    st.caption('Sportsbook prices and model estimates are shown separately.')
    st.caption('19+ in Ontario. Analysis only. No wagers are placed.')


@st.cache_data(ttl=1800,show_spinner=False)
def load_analysis(api_key,competitions,db_path,cap,ttl,collect_results,window_hours,results_scope,store_instance,read_replica=False):
    from intelligence.storage import Store
    data_store=Store(db_path,read_replica=read_replica)
    return run_analysis(api_key,list(competitions),store=data_store,collect_results=False,autonomous=True,window_hours=window_hours,cached_only=True)


st.title(page)
st.caption('Evidence-supported sports research · no forced picks')
results_scope=(results_config.enabled,results_config.use_reviewed,digest(results_config.token))
with store.connect() as identity_db:store_instance=identity_db.execute('SELECT instance FROM store_identity WHERE id=1').fetchone()[0]
snapshot_scope=(tuple(leagues),digest(key),store.path,data_settings.daily_limit,data_settings.cache_seconds,data_settings.collect_results,data_settings.window_hours,results_scope,store_instance)
snapshot=st.session_state.get('_research_snapshot')
if snapshot and snapshot.get('scope')==snapshot_scope:
    result=snapshot['analysis']
else:
    with st.spinner('Loading saved research…'):
        result = load_analysis(key,tuple(leagues),store.path,data_settings.daily_limit,data_settings.cache_seconds,data_settings.collect_results,data_settings.window_hours,results_scope,store_instance,getattr(store,'read_replica',False))

if not snapshot or snapshot.get('scope')!=snapshot_scope:
    st.session_state['_research_snapshot']={'scope':snapshot_scope,'analysis':result,'stored_at':utcnow().isoformat()}
from intelligence.cached_research import synchronize
result=synchronize(st.session_state['_research_snapshot'],store)

def render_admin_status():
    if shared_problem:st.info(shared_problem)
    if not key:st.info('ODDS_API_KEY is not configured. Saved data is still available; use private Secrets only.')
    st.caption('Opening pages and changing filters use saved data without provider requests. Prices expire after five minutes; Refresh analysis is an explicit capped retrieval.')
    if getattr(store,'read_replica',False):st.caption('Shared mode · read-only dashboard replica. Committed worker state is checked at most every five minutes; no app visit creates a publication or spends sports-provider credits.')

    from intelligence.quota import quota_details
    refresh_quota=quota_details(store,data_settings.daily_limit)
    if st.button('Refresh analysis',help='Explicit provider retrieval using the shared cache and existing cap.',disabled=not key or bool(data_settings.errors) or refresh_quota['remaining']==0):
        from intelligence.providers import OddsAPI
        with st.spinner('Explicit retrieval within the existing credit cap…'):
            fresh=run_analysis(key,list(leagues),store=store,provider=OddsAPI(key,store,daily_limit=data_settings.daily_limit,ttl=data_settings.cache_seconds),
                collect_results=data_settings.collect_results,autonomous=True,window_hours=data_settings.window_hours)
        st.session_state['_research_snapshot']={'scope':snapshot_scope,'analysis':fresh,'stored_at':utcnow().isoformat()}
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
    from intelligence.cached_research import record_and_label
    fresh=record_and_label(fresh,store)
    st.session_state['_research_snapshot']={'scope':snapshot_scope,'analysis':fresh,'stored_at':utcnow().isoformat()}


# Recheck existing publication gates; browsing pages never creates new API requests.
published=publish_current(result,store)
if published:
    from intelligence.ledger import archive
    archive(store,os.getenv('PREDICTION_LEDGER_DIR','ledger'))
from intelligence.workspace_ui import Workspace,render_tools
st.markdown('<a href="https://sportscore.com/" rel="dofollow" title="Sports data by SportScore">Powered by SportScore</a> · <a href="https://sporting-events.org/data/nba/">NBA fixtures: Sporting Events</a>',unsafe_allow_html=True)
from intelligence import consumer_ui
workspace=Workspace(result,store,data_settings,book_keys,leagues,key,secret,refresh_selected,show_markets,current_opportunities,
    sync_saved=sync_shared_state.clear if shared_config.enabled else None)
route=destination(page).renderer

def admin(w):
    render_admin_status()
    render_tools(w)

if route in ('home','picks','games','performance'):
    @st.fragment(run_every='60s')
    def research_page():
        from dataclasses import replace
        from intelligence.top_research_ui import active_analysis
        if shared_config.enabled:
            try:
                synced=sync_shared_state((shared_config.url,digest((shared_config.reader_key,shared_config.reader_token))),
                    os.getenv('RESEARCH_REPLICA_DIR') or secret('RESEARCH_REPLICA_DIR') or 'data/shared-replica',shared_config)
                from intelligence.shared_state import replica_revision
                if replica_revision(synced)!=replica_revision(getattr(store,'shared_status',{})):
                    st.rerun()  # Load the new verified replica without any sports request.
            except (StateError,OSError,ValueError):
                st.info('Saved research could not be updated. The last verified copy is kept.')
        current=replace(workspace,analysis=active_analysis(result,store))
        {'home':consumer_ui.render_home,'picks':consumer_ui.render_picks,'games':consumer_ui.render_games,'performance':consumer_ui.render_performance}[route](current)
    research_page()
else:consumer_ui.render_settings(workspace,admin)

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
