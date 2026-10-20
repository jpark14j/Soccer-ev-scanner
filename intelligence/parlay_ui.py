"""Daily research UI: actual single prices, explicitly theoretical combinations."""
import pandas as pd
import streamlit as st
from dataclasses import replace
from intelligence.analyst_config import load_config
from intelligence.chat_privacy import redact
from intelligence.domain import utcnow,parse_time
from intelligence.parlay_research import SPORTS,select_candidates
from intelligence.parlays import CATEGORIES,NO_PARLAYS
from intelligence.registry import load_registry
from intelligence.research_refresh import credit_status
from intelligence.providers import LEAGUES,ProviderError
from intelligence.markets import CATALOG,selection_label,scope
from intelligence.quota import quota_details,refresh_reason


def render_research(analysis,store,book_keys,leagues,has_key,refresh_callback,secret_getter=None,daily_limit=None):
    sensitive=load_config(secret_getter).sensitive_values
    st.subheader('Daily Parlay Research')
    st.info('Research candidates help you inspect real selections together. They are not qualified betting recommendations. Combined prices below are theoretical, not confirmed available at a sportsbook.')
    a,b=st.columns(2)
    sports=a.multiselect('Research sports',SPORTS,default=list(SPORTS),key='research_sports')
    registry=load_registry()
    names={item['odds_api_key']:item['name'] for item in registry['books'] if item.get('odds_api_key') in book_keys}
    selected_books=b.multiselect('Research sportsbooks',sorted(names),default=sorted(names),
                                 format_func=lambda key:names[key],key='research_books')
    a,b=st.columns(2)
    counts=a.multiselect('Number of legs',[2,3],default=[2,3],key='research_legs')
    categories=b.multiselect('Risk category · price proxy',CATEGORIES,default=list(CATEGORIES),key='research_categories')
    st.caption('Price-based labels, not measured risk: Lower-variance = 2 legs, each ≤ 1.80; Balanced = other products ≤ 6.00; Higher-variance = products > 6.00. These labels do not establish win probabilities or safety.')
    with st.expander('Market, event and evidence filters'):
        market_types=st.multiselect('Parlay market types',list(CATALOG),default=list(CATALOG),format_func=lambda m:CATALOG[m].name,key='research_market_types')
        from intelligence.research_state import EVIDENCE_STATES,evidence_state
        evidence=st.multiselect('Parlay leg evidence status',EVIDENCE_STATES,default=list(EVIDENCE_STATES),key='research_evidence')
        competitions=st.multiselect('Parlay competitions',list(LEAGUES),default=list(LEAGUES),key='research_competitions')
        event_ids=None
        event_scope=st.radio('Research event scope',['Across available events','One selected event'],horizontal=True,key='research_event_scope')
        if event_scope=='One selected event':
            events={q.event_id:f'{q.sport} · {q.event} · {q.commence_time}' for q in analysis.quotes if q.sport in sports and q.bookmaker in selected_books and q.status()=='current'}
            if events:
                event_ids=[st.selectbox('Same-game research event',sorted(events),format_func=lambda id:redact(events[id],sensitive),key='research_single_event')]
            else:
                event_ids=[]
                st.caption('No current event can be selected. Stale observations remain inspection-only in Advanced Markets.')
    st.caption('Open Settings & Research Tools → Advanced Markets to retrieve spreads, totals, BTTS or documented event props. Only actually observed current Ontario selections can enter this selector; unvalidated props remain price research.')
    selected_leagues=[league for league in leagues if LEAGUES[league][0] in sports]
    with st.expander('Get current prices and inspect search coverage'):
        try:
            used,limit=credit_status(store,limit=daily_limit)
        except Exception:
            used,limit=0,0
            st.warning('Local provider quota information is unavailable or misconfigured. Refresh is disabled until it is fixed.')
        reset=quota_details(store,limit)
        st.caption(f'Next local reset: {reset["next_reset_toronto"]} · {reset["next_reset_utc"]}. The provider account reset may differ.')
        st.write(f'Local provider quota reserved today (UTC): {used}/{limit}. Selected competitions: {", ".join(selected_leagues) or "none"}.')
        st.write('A refresh requests match-winner (h2h) prices only for these competitions. It uses the existing provider account, skips completed-result collection and keeps the daily cap. No subscription or paid AI request is made. Retries also reserve credits.')
        last=st.session_state.get('_research_refresh_at')
        cooldown=bool(last and (utcnow()-parse_time(last)).total_seconds()<60)
        if st.button(f'Refresh selected odds · minimum {len(selected_leagues)} local credits',key='research_refresh',
                     disabled=not has_key or not selected_leagues or cooldown or limit-used<len(selected_leagues)):
            st.session_state['_research_refresh_at']=utcnow().isoformat()
            try:
                with st.spinner('Retrieving provider observations and rechecking research evidence…'):
                    refresh_callback(selected_leagues)
            except ProviderError as exc:
                st.warning(str(exc))
            except Exception:
                st.warning('The research refresh could not complete. Check provider and data configuration; no unverified answer is substituted.')
            else:
                st.rerun()
        if cooldown:
            st.caption('Refresh is limited to once per minute per session. Filters never trigger fresh provider requests.')
        if not has_key:
            st.caption('No odds credential configured. Add your existing ODDS_API_KEY to this preview’s Secrets; no model API key is needed.')
        elif limit-used<len(selected_leagues):
            st.caption('The local daily cap cannot cover this refresh. Narrow the selected sports/competitions or wait for the next UTC day. No cap is raised automatically.')
    # Recompute expiry every minute without making any data-provider request.
    @st.fragment(run_every='60s')
    def show():
        from intelligence.book_optimizer import scoped_quotes
        filtered=replace(analysis,quotes=[q for q in scoped_quotes(analysis) if q.league in competitions and evidence_state(q,analysis)[0] in evidence])
        result=select_candidates(filtered,sports=sports,bookmakers=selected_books,leg_counts=counts,categories=categories,markets=market_types,event_ids=event_ids)
        st.caption(f'Checked {result.checked_at}. {result.eligible_quotes} eligible individual quotes; searched {result.searched_quotes} quotes and {result.examined_combinations} combinations. At most 24 legs per sportsbook are searched, balanced across sports/events; this is not an exhaustive optimizer.')
        if not result.candidates:
            st.info('No current parlay research candidates match these filters. At least two compatible, current Ontario selections at the same sportsbook are required. Review coverage below or refresh selected odds when quota permits.')
        for index,candidate in enumerate(result.candidates,1):
            with st.container(border=True):
                q=candidate.legs[0].quote
                st.subheader(redact(f'Research candidate {index} · {len(candidate.legs)} legs · {q.bookmaker_name}',sensitive))
                st.caption(f'{candidate.category} · price-based research label · not a validated risk estimate')
                st.caption('Leg evidence: '+', '.join(dict.fromkeys(evidence_state(leg.quote,analysis)[0] for leg in candidate.legs))+'. No approved combined ticket exists.')
                st.write(f'Theoretical all-win odds product: **{candidate.theoretical_odds:.2f}**. This is arithmetic on individual prices, not a sportsbook combined quote or an executable offer.')
                rows=[]
                for leg in candidate.legs:
                    quote,e=leg.quote,leg.estimate
                    rows.append({'Sport':quote.sport,'Event':quote.event,'Event start (UTC)':quote.commence_time,'Market':quote.market,
                        'Selection':selection_label(quote),'Settlement scope':scope(quote),'Line':quote.point,'Sportsbook':quote.bookmaker_name,
                        'Individual decimal odds':quote.odds,'Market implied probability':f'{leg.implied_probability:.1%}',
                        'Source timestamp':quote.source_updated_at,'Received':quote.received_at,
                        'Model estimate':f'{e.probability:.1%} ({leg.model_status})' if e else 'Unavailable',
                        'Model history through':e.training_end if e else 'Unavailable',
                        'Model envelope':f'{e.lower:.1%}–{e.upper:.1%}' if e else 'Unavailable',
                        'Unvalidated model minus break-even (pp)':round(100*(e.probability-leg.implied_probability),2) if e else None,
                        'Individual EV':f'{leg.estimated_ev:+.1%}' if leg.estimated_ev is not None else 'Not supported'})
                rows=[{k:redact(v,sensitive) if isinstance(v,str) else v for k,v in row.items()} for row in rows]
                for row in rows:
                    st.text(str(row.get('Event',''))+' · '+str(row.get('Selection',''))+' · decimal '+str(row.get('Individual decimal odds','')))
                with st.expander('Advanced Details / Raw Market Data',expanded=False):
                    st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
                st.write('**Joint win probability:** unavailable. **Parlay EV:** not calculated. **Actual combined price:** unavailable. **Sportsbook acceptance/restrictions:** unverified.')
                st.caption('Implied probabilities are 1 ÷ individual odds and contain bookmaker margin. They are not model forecasts and are never multiplied into a joint probability.')
                st.caption('Individual model-versus-price differences are research disagreements, not validated betting edges. High marginal probabilities do not approve a parlay.')
                if candidate.probability_bounds is not None:
                    lo,hi=candidate.probability_bounds
                    lower,upper=candidate.uncertainty_bounds
                    st.write(f'Conditional dependence-free bounds using supplied model point estimates: {lo:.1%}–{hi:.1%}; allowing their supplied envelopes: {lower:.1%}–{upper:.1%}. These are mathematical bounds, not an estimated parlay probability or calibrated parlay confidence interval. Unvalidated inputs remain research only.')
                if candidate.scenario_joint:
                    scenario=candidate.scenario_joint
                    st.write(f'Unvalidated same-game score-model scenario: {scenario["probability"]:.1%} conditional on {scenario["model_version"]}. This retains same-game score dependence; it is not a validated joint estimate or betting recommendation.')
                    st.caption(scenario['method']+' · '+scenario['reason'])
                st.write('**Why displayed:** '+candidate.rank_explanation)
                with st.expander('What must be verified before this can qualify'):
                    for blocker in candidate.blockers:
                        st.text(redact('• '+blocker,sensitive))
                    for warning in candidate.warnings:
                        st.text('• '+warning)
                    for i,leg in enumerate(candidate.legs,1):
                        if leg.estimate:
                            st.write(redact(f'Leg {i} model {leg.estimate.model_version}, history through {leg.estimate.training_end}; status {leg.model_status}.',sensitive))
                            st.json({k:redact(v,sensitive) if isinstance(v,str) else v for k,v in leg.model_details.items() if k in ('calibration_n','test_n','calibration_bin_n','calibration_gap','diagnostic_scores','interval_basis','data_source','history_n','method')})
        st.info(NO_PARLAYS+' Research candidates above are kept separate from the published prediction/performance ledger.')
        with st.expander('Coverage and exclusion details'):
            st.json(result.exclusions)
            st.caption(f'{result.candidate_count} compatible combinations passed the research filters before ranking/diversity; at most three distinct event sets are displayed. Current, Ontario-provenance quotes are an entry requirement. Missing or older-than-five-minute source/receipt timestamps never qualify for the research selector.')
    show()
