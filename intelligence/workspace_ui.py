"""Workspace renderers reuse existing analytics and explicit request callbacks."""
from dataclasses import dataclass,field,replace
from pathlib import Path
import json
import streamlit as st
import pandas as pd
from intelligence.navigation import TOOLS,destination


@dataclass
class Workspace:
    analysis: object
    store: object
    settings: object
    book_keys: set
    leagues: list
    key: str = field(repr=False)
    secret: object
    refresh: object
    markets: object
    opportunities: object


def render_picks(w):
    from intelligence.top_research_ui import render_summary,active_analysis
    w=replace(w,analysis=active_analysis(w.analysis,w.store))
    from intelligence.domain import parse_time
    from zoneinfo import ZoneInfo
    window=w.analysis.slate
    if window.get('window_start') and window.get('window_end'):
        local=ZoneInfo('America/Toronto')
        start=parse_time(window['window_start']).astimezone(local);end=parse_time(window['window_end']).astimezone(local)
        st.caption(f"Upcoming-game window: {window.get('window_hours',w.settings.window_hours)} hours · "
            f"{start:%b %d, %I:%M %p %Z} to {end:%b %d, %I:%M %p %Z}. Includes future dates; "
            'saved fixtures and prices may be incomplete. No provider requests occur when opening this page.')
    @st.fragment(run_every='60s')
    def top_research():
        render_summary(active_analysis(w.analysis,w.store),w.store,w.book_keys,w.secret,w.settings.daily_limit,w.leagues)
    top_research()
    from intelligence.parlay_intelligence_ui import render_intelligence
    render_intelligence(w.analysis,w.store,w.book_keys,w.secret)
    singles,parlays=st.tabs(['Singles','Parlays'])
    with singles:
        from intelligence.research_views import render_singles
        render_singles(w.analysis,w.book_keys,w.secret)
        w.markets()
    with parlays:
        from intelligence.parlay_ui import render_research
        with st.expander('Unsupported and price-only research · full existing generator',expanded=False):
            render_research(w.analysis,w.store,w.book_keys,w.leagues,bool(w.key),w.refresh,w.secret,w.settings.daily_limit)
        with st.expander('Sportsbook shortlist and whole-slate search'):
            from intelligence.slate_views import render_books
            render_books(w.analysis,w.book_keys,w.secret,'parlay_book_preference')
        with st.expander('Bankroll and qualified-leg diagnostics'):
            render_qualified_builder(w)


def render_qualified_builder(w):
    from intelligence.parlays import analyze
    from intelligence.risk_ui import render_bankroll
    eligible=w.opportunities()
    render_bankroll(eligible)
    st.subheader('Qualified-leg diagnostic builder')
    st.caption('Requires qualified singles; it never promotes research into a recommendation.')
    chosen=st.multiselect('Qualifying legs to evaluate',range(len(eligible)),
        format_func=lambda i:f'{eligible[i].quote.sport}: {eligible[i].quote.event} / {eligible[i].quote.selection}')
    if 2<=len(chosen)<=6:
        result=analyze([eligible[i] for i in chosen]);lower,upper=result['probability_bounds']
        st.write(f'Theoretical joint probability bounds: {lower:.1%}–{upper:.1%}.')
        st.caption(result['reason']+'. No executable combined price or parlay EV is asserted.')
    st.caption('Different events or sports do not establish independence. Validated joint evidence, verified operator rules and actual combined pricing are required for a qualifying ticket.')


def render_tools(w):
    name=st.selectbox('Research tool',[d.name for d in TOOLS],key='research_tool')
    tool=destination(name,TOOLS).renderer
    st.caption('Tools share the current scan. Switching tools does not retrieve prices; request buttons remain explicit and quota-limited.')
    if tool=='operations':
        from intelligence.operations_ui import render_operations
        render_operations(w.analysis,w.store,w.secret)
    elif tool=='markets':
        from intelligence.market_ui import render_markets
        render_markets(w.analysis,w.store,w.leagues,w.book_keys,w.key,w.settings,w.refresh,w.secret)
    elif tool=='sport':
        render_sport(w,name.split()[0])
    elif tool=='live':
        st.warning('Live recommendations are unavailable. Current odds alone do not supply verified game clock, score, player state, latency or suspension information. Pregame models are never applied in play.')
        w.markets(live=True)
    elif tool=='assistant':
        from intelligence.chat_ui import render_assistant
        render_assistant(w.analysis,w.store,w.secret)
    elif tool=='diagnostics':
        from intelligence.quant_ui import render_evaluation
        render_evaluation()
        from intelligence.research_views import render_health
        from intelligence.slate_views import render_focused_model
        render_health(w.analysis,w.store,w.secret)
        render_focused_model(w.analysis)
        with st.expander('Data collection and processing audit'):
            st.json({'slate':w.analysis.slate,'processing':w.analysis.processing,
                'errors':w.analysis.errors,'warnings':w.analysis.warnings,'exclusions':w.analysis.exclusions})
        w.markets()
    else:
        render_settings(w)


def render_sport(w,sport):
    if sport=='Soccer':
        from intelligence.slate_views import render_focused_model
        render_focused_model(w.analysis)
    from intelligence.slate_views import render_games
    from intelligence.research_views import render_single
    from intelligence.research_state import singles,APPROVED
    for state,leg in singles(w.analysis,w.book_keys,sports=[sport],statuses=[APPROVED]):
        render_single(state,leg,w.secret)
    render_games(replace(w.analysis,quotes=[q for q in w.analysis.quotes if q.sport==sport],
        slate={**w.analysis.slate,'events':[e for e in w.analysis.slate.get('events',[]) if e['sport']==sport]}),w.book_keys,w.secret)
    w.markets(sport)
    evidence_file=Path('docs/evidence')/({'NBA':'nba-research.json','MLB':'mlb-research.json','Soccer':'premier-league-research.json'}[sport])
    if evidence_file.exists():
        with st.expander('Historical research evaluation — not forward performance'):
            evidence=json.loads(evidence_file.read_text())
            st.write(f'Data through {evidence["data_end"]}; held-out test events: {evidence["test_n"]}. Status: research only.')
            st.caption('Earlier project models reused these archive periods; this is not independent fresh confirmation or betting profitability.')
            st.json({'diagnostic_scores':evidence['metrics'],'simple_baseline':evidence.get('simple_baseline_metrics'),
                'market_baseline':evidence['baseline_metrics'],'publication_blockers':evidence['promotion_blockers']})
    st.caption('Player-prop ingestion is available through the event endpoint. Forecasting requires licensed player history, availability and market-specific validation; it is not enabled.')


def render_settings(w):
    from intelligence.registry import load_registry
    from intelligence.analyst_config import load_config
    from intelligence.markets import CATALOG
    registry=load_registry();config=load_config(w.secret)
    st.write('Competition and sportsbook view preferences are in the sidebar and last for this browser session.')
    st.write(f'Local daily credit cap: {w.settings.daily_limit}. Retrieval cache: {w.settings.cache_seconds} seconds. No subscriptions are purchased by the application.')
    st.write(f'Ontario directory effective date: {registry["directory_as_of"]}. Review expires {registry["review_expires_at"]}. Expired evidence disables eligibility.')
    with st.expander('Ontario sportsbook registry'):
        st.dataframe(pd.DataFrame(registry['books']),hide_index=True,use_container_width=True)
        st.link_button('Official Ontario directory',registry['source'])
    st.subheader('Connections')
    st.write({'Odds key configured':bool(w.key),'Telegram bot configured':bool(w.secret('TELEGRAM_BOT_TOKEN')),
        'Paid conversational API':'Configured; session consent required' if config.paid_ready else 'Disabled or unconfigured',
        'NBA/MLB historical data':'Free research imports / licensed files / locally collected completed results'})
    st.caption('Scheduling and Telegram preferences use environment variables documented in README. API keys belong in Streamlit Secrets or GitHub Actions Secrets.')
    from intelligence.current_results_ui import render as render_results
    render_results(w)
    with st.expander('Additional market requests'):
        st.dataframe(pd.DataFrame([{'Provider key':m.key,'Market':m.name,'Sports':', '.join(m.sports),
            'Published provider documentation':m.documented} for m in CATALOG.values()]),hide_index=True,use_container_width=True)
        st.caption('Documented support is not account or Ontario availability. Select Advanced Markets in Research tool for scoped price searches. Every request remains subject to quota.')
