"""Concise shared views for the four-page workspace; all filtering is read-only."""
from dataclasses import replace
import streamlit as st
from intelligence.domain import utcnow
from intelligence.analyst_config import load_config
from intelligence.chat_privacy import redact,redact_data
from intelligence.markets import CATALOG
from intelligence.registry import load_registry
from intelligence.research_state import EVIDENCE_STATES,APPROVED,EXPERIMENTAL,PRICE_ONLY,BLOCKED,singles,model_health
from intelligence.slate_views import selection_card


def render_single(state,leg,secret_getter=None):
    sensitive=load_config(secret_getter).sensitive_values
    safe=lambda value:redact(str(value),sensitive)
    with st.container(border=True):
        st.write('**'+safe(leg.quote.event)+'**')
        st.caption(safe(f'{leg.quote.sport} · {state} · starts {leg.quote.commence_time}'))
        selection_card(leg,safe)
        if state==BLOCKED:
            st.caption('Inspection only. '+safe(leg.quote.status())+'; no current recommendation is supported.')
        if state==PRICE_ONLY:
            st.caption('Price comparison only. No win probability, confidence or betting advantage is established.')
        with st.expander('Why this evidence status?'):
            for blocker in leg.blockers:
                st.text(safe(blocker))
            st.caption('Ranking uses qualification, model evidence, supplied uncertainty and freshness. Equal-evidence price choices have no demonstrated predictive advantage.')
            st.json(redact_data({k:v for k,v in leg.model_details.items() if k!='quote_id'},sensitive))


def render_health(analysis,store,secret_getter=None):
    health=model_health(analysis,store)
    health=redact_data(health,load_config(secret_getter).sensitive_values)
    st.subheader('Data & Model Health')
    st.caption('Latest observed odds source: '+(health['latest_odds_source'] or 'unavailable')+
        ' · receipt: '+(health['latest_odds_receipt'] or 'unavailable')+'. Each selection is checked separately for expiry.')
    st.caption('Sports results checked: '+(health['source_checked_at'] or 'unavailable')+
        ' ('+health['source_check_kind']+'); latest completed EPL result: '+(health['source_latest'] or 'unavailable')+'. A download date is not a result date.')
    for reason in health['reasons']:
        st.write('• '+reason)
    if st.button('Recheck saved research · no API calls',key='cached_research_recheck'):
        from intelligence.cached_research import recheck
        from intelligence.diagnostics import results_revision
        snapshot=st.session_state.get('_research_snapshot')
        if snapshot:
            snapshot['analysis']=recheck(analysis,store)
            snapshot['results_revision']=results_revision(store)
            st.rerun()
    for row in health['competitions']:
        if row['competition'] in ('Premier League','Bundesliga','Ligue 1'):
            st.caption(f"{row['competition']} · current source: {row['current_source']} · completed: {row['current_completed'] if row['current_completed'] is not None else 'unavailable'} · latest result: {row['latest_result'] or 'unavailable'} · {row['current_forecast']} · model approval: {row['validation']}")
    inventory=health['quote_inventory']
    st.caption(f"Saved-scan price inventory: {inventory['current_eligible']} currently eligible; {inventory['stale_upcoming_in_window']} stale upcoming observations; {inventory['outside_window_or_started_inspection']} outside-window/started observations for inspection. Counts cover the full saved scan, before sportsbook view filters. They count prices/selections, not games; diagnostics make no API request.")
    with st.expander('Model, source and coverage diagnostics'):
        st.json(health)
        render_competitions(analysis,store)
        st.write(inventory['note'])
    if st.button('Prepare readiness evidence export',key='readiness_export'):
        from intelligence.diagnostics import readiness_export
        import json
        payload=redact_data(readiness_export(analysis,store),load_config(secret_getter).sensitive_values)
        st.download_button('Download readiness evidence JSON',json.dumps(payload,indent=2),
            file_name='forecast-readiness.json',mime='application/json',key='readiness_download')
    return health


def render_rankings(analysis,books,secret_getter=None,widget_key='dashboard_ranking',limit=3):
    from intelligence.research_ranking import rank_research,RANKINGS
    report=rank_research(analysis,books)
    name=st.selectbox('Research ranking',RANKINGS,key=widget_key)
    st.caption(report['descriptions'][name])
    st.caption(report['requirements'])
    rows=report['rankings'][name]
    if not rows:
        st.info('No selections meet the evidence requirements for this research ranking. No recommendation is forced.')
    for state,leg in rows[:limit]:
        render_single(state,leg,secret_getter)
    with st.expander('Research ranking exclusions'):
        st.json(report['exclusions'])
    return rows


def render_daily_dashboard(analysis,store,settings,books,secret_getter=None):
    from intelligence.book_optimizer import best_by_game,scoped_quotes
    from intelligence.epl_forecasts import high_probability_research
    now=utcnow();quotes=[q for q in scoped_quotes(analysis,now) if q.bookmaker in books]
    current=[q for q in quotes if q.status(now)=='current' and q.jurisdiction=='CA-ON']
    games=best_by_game(analysis,books,now)
    rows=singles(analysis,books,now=now)
    a,b=st.columns(2);c,d=st.columns(2)
    a.metric('Games discovered / observed',len(games))
    b.metric('Games with current markets',len({q.event_id for q in current}))
    c.metric('Games with model research',len({leg.quote.event_id for state,leg in rows if state in (APPROVED,EXPERIMENTAL)}))
    d.metric('Qualified singles',sum(state==APPROVED for state,_ in rows))
    st.caption(f'{len(current)} current Ontario individual-price observations across {len({q.bookmaker for q in current})} books and {len({(q.event_id,q.market) for q in current})} event/market groups. Coverage is partial, not the full sports calendar.')
    st.subheader("Today's Research")
    from intelligence.quant_ui import render_best
    render_best(analysis,books,secret_getter)
    st.caption('Approved = publication gates pass; experimental = an unapproved model estimate; price-only = observed selection with no supported forecast; blocked = missing or invalid inputs. Break-even percentages are not predicted win probabilities.')
    st.write('**Singles**')
    render_rankings(analysis,books,secret_getter)
    with st.expander('All experimental estimates and price observations · inspection only'):
        display=[row for row in rows if row[0]!=BLOCKED][:3]
        if not display:
            st.info('No current singles research is supported by this snapshot. Missing or stale data never creates a pick.')
        for state,leg in display:
            render_single(state,leg,secret_getter)
    st.write('**Parlays**')
    from intelligence.parlay_intelligence import generate
    intelligence=generate(analysis,books,now,max_per_size=1)
    st.info('No qualifying parlay opportunities identified today. Model-backed candidates remain experimental.')
    candidates=[item.research for item in intelligence.two_leg+intelligence.three_leg]
    if candidates:
        candidate=candidates[0];safe=lambda s:redact(str(s),load_config(secret_getter).sensitive_values)
        st.caption('Exploratory research only. No validated joint probability, accepted combined price or parlay EV is available.')
        with st.container(border=True):
            st.write(f'{len(candidate.legs)} legs · '+safe(candidate.legs[0].quote.bookmaker_name))
            for leg in candidate.legs:
                from intelligence.markets import selection_label
                st.text(safe(f'{leg.quote.event} · {selection_label(leg.quote)} · individual decimal {leg.quote.odds:.2f} · source {leg.quote.source_updated_at}'))
            st.write(f'Theoretical odds product {candidate.theoretical_odds:.2f} — not an executable sportsbook offer.')
            with st.expander('Parlay research limitations'):
                st.write(candidate.rank_explanation)
                for text in (*candidate.blockers,*candidate.warnings):st.text(safe(text))
    else:
        st.info('No compatible current model-backed parlay is available. Price-only combinations remain in Best Picks & Parlays → Unsupported and price-only research.')
    st.caption('Open Best Picks & Parlays for the model-first research dashboard, opposing outcomes and complete explanations.')
    st.caption('High-probability shortlist: '+('research evidence available; review Best Picks & Parlays' if high_probability_research(analysis,now) else 'No credible high-probability selections qualify. Independent model evidence is missing.'))
    render_health(analysis,store,secret_getter)
    with st.expander('Scan audit and processing details'):
        st.json(redact_data({'scan':analysis.slate,'processing':analysis.processing,'exclusions':analysis.exclusions},load_config(secret_getter).sensitive_values))


def render_singles(analysis,books,secret_getter=None):
    registry=load_registry();names={r['odds_api_key']:r['name'] for r in registry['books'] if r.get('odds_api_key') in books}
    a,b=st.columns(2)
    sports=a.multiselect('Sports',['NBA','Soccer','MLB'],default=['NBA','Soccer','MLB'],key='picks_sports')
    selected=b.multiselect('Sportsbooks',sorted(names),default=sorted(names),format_func=lambda k:names[k],key='picks_books')
    a,b=st.columns(2)
    market=a.selectbox('Market',['All markets',*CATALOG],format_func=lambda k:CATALOG[k].name if k in CATALOG else k,key='picks_market')
    markets=None if market=='All markets' else [market]
    statuses=b.multiselect('Evidence status',EVIDENCE_STATES,default=list(EVIDENCE_STATES),key='picks_evidence')
    from intelligence.competitions import COMPETITIONS
    competition=st.selectbox('Competition',['All observed competitions',*COMPETITIONS],key='picks_competition')
    if competition!='All observed competitions':
        analysis=replace(analysis,quotes=[q for q in analysis.quotes if q.league==competition])
    st.caption('Filters only inspect this scan. Research estimates and market break-even percentages are separate; price-only observations are not forecasts.')
    count=st.selectbox('Selections to display',[6,12,30,100],key='picks_count')
    rows=singles(analysis,selected,sports,markets,statuses)
    st.caption(f'{len(rows)} equivalent selections after filtering and price comparison. Ranked by evidence and freshness; no minimum number is forced.')
    if not rows:st.info('No selections match these filters. No selection or probability is invented.')
    filtered=replace(analysis,quotes=[leg.quote for _,leg in rows])
    render_rankings(filtered,selected,secret_getter,'picks_ranking',count)
    with st.expander('All filtered observations · inspection only'):
        for state,leg in rows[:count]:render_single(state,leg,secret_getter)


def render_competitions(analysis,store):
    from intelligence.multi_readiness import readiness
    rows=readiness(analysis,store)
    active=[r for r in rows if r['coverage']!='Discovery target; no dataset integrated']
    st.caption('Historical coverage is not current-input readiness. Soccer cups/national teams are discovery targets; no cross-league strengths are transferred.')
    st.json({'ingested_competitions':active,'targets_without_data':[r['competition'] for r in rows if r not in active]})
