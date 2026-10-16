"""Concise game/book cards; raw observations stay behind collapsed audit views."""
import streamlit as st
from intelligence.domain import utcnow,parse_time
from intelligence.book_optimizer import best_by_game,optimize_by_book,scoped_quotes
from intelligence.markets import selection_label,CATALOG,scope
from intelligence.chat_privacy import redact
from intelligence.analyst_config import load_config
from intelligence.quota import quota_details
from intelligence.ev import qualify


def selection_card(leg,safe):
    q=leg.quote
    st.text(safe(selection_label(q)))
    st.caption(safe(f'{CATALOG[q.market].name} · {q.bookmaker_name} · individual decimal {q.odds:.2f} · source {q.source_updated_at}'))
    st.caption(f'Sportsbook break-even including margin: {leg.implied_probability:.1%} (not a win forecast). Model: {leg.model_status}.')
    if leg.estimate:
        st.write(f'Model estimate {leg.estimate.probability:.1%}; supplied envelope {leg.estimate.lower:.1%}–{leg.estimate.upper:.1%}. '+('Validated leg evidence; ticket rules still need checking.' if leg.model_status=='validated' else 'Unvalidated research forecast; not a reliable true probability.'))
        d=leg.model_details
        st.caption(safe(f'Model {leg.estimate.model_version} · prediction {d.get("prediction_at","not recorded")} · history through {leg.estimate.training_end} · historical games {d.get("history_n","unavailable")} · calibration n={d.get("calibration_n",0)} · test n={d.get("test_n",0)}'))
        from intelligence.research_ranking import comparison
        gap=comparison(leg);lo,hi=gap['difference_envelope']
        st.caption(f"Research model minus sportsbook break-even: {100*gap['difference']:+.1f} percentage points; supplied envelope {100*lo:+.1f} to {100*hi:+.1f}. Not established betting value or EV.")
        if gap['difference']<=0:
            st.caption('The model estimate is at or below this price’s break-even percentage. This does not support a positive-value claim.')
        elif lo<=0:
            st.caption('The supplied uncertainty envelope includes zero or a negative difference.')
    else:
        st.caption('No defensible model probability, confidence or EV is available.')
        if leg.model_details.get('blockers'):
            st.caption(safe('Forecast blocked: '+leg.model_details['blockers'][0]))
    if leg.estimated_ev is not None:
        st.write(f'Estimated single EV {leg.estimated_ev:+.1%}; not parlay EV.')


def render_games(analysis,books,secret_getter=None,max_games=6):
    sensitive=load_config(secret_getter).sensitive_values
    safe=lambda text:redact(str(text),sensitive)
    games=best_by_game(analysis,books)
    st.subheader('Best Selections by Game')
    st.caption('At most two evidence-ranked selections per game. No model-validation evidence means research only; equal-evidence selections have no established statistical advantage.')
    if not games:
        st.info('No games have been discovered or observed for this view. No events or selections are invented.')
    for game in games[:max_games]:
        event=game['event']
        with st.container(border=True):
            st.subheader(safe(event['event']))
            st.caption(safe(f"{event['sport']} · {event['league']} · starts {event['start']} · {game['observations_evaluated']} current observations evaluated · {game['market_types']} market types"))
            if not game['selections']:
                st.write('No current eligible selections. Markets may be unscanned, stale, missing or outside Ontario coverage.')
            for leg in game['selections']:
                selection_card(leg,safe)
            with st.expander('Evidence, alternatives and missing requirements'):
                st.write(game['reason'])
                for leg in game['selections']:
                    st.text(safe(scope(leg.quote)))
                    for blocker in leg.blockers:
                        st.text(safe(blocker))
                    st.json({k:v for k,v in leg.model_details.items() if k!='quote_id'})
    if len(games)>max_games:
        st.caption(f'{len(games)-max_games} more games are available in Best Selections by Game. All are considered by the shortlist, including games not displayed here.')


def render_books(analysis,books,secret_getter=None,widget_key='book_preference'):
    sensitive=load_config(secret_getter).sensitive_values;safe=lambda text:redact(str(text),sensitive)
    st.subheader('Sportsbook Parlay Shortlist')
    preference=st.radio('Parlay preference',['2 legs','3 legs','2 or 3 legs'],horizontal=True,key=widget_key)
    counts=(2,3) if preference=='2 or 3 legs' else (int(preference[0]),)
    rows=optimize_by_book(analysis,books,counts)
    if not rows:
        st.info('No Qualifying Parlay. No Ontario sportsbook observations are available in this scan window.')
    for row in rows:
        with st.container(border=True):
            st.subheader(safe(row['name']))
            st.write('**'+row['qualification_status']+'**')
            st.caption(f"{row['eligible_singles_scored']} eligible singles scored across {row['events_considered']} games; {row['combinations_evaluated']} combinations evaluated.")
            if row['qualified']:
                evidence,candidate=row['qualified']
                st.write(f"Verified combined decimal {evidence['odds']:.2f} · validated joint estimate {evidence['probability']:.1%} · estimated EV {evidence['ev']:+.1%}")
                for leg in candidate.legs:
                    st.text(safe(f'{leg.quote.event} · {leg.quote.commence_time} · {selection_label(leg.quote)}'))
            else:
                st.caption('Missing validated joint probabilities, genuine combined quotes and verified operator restrictions. No research candidate is recommended as a wager.')
            candidate=row['research']
            if candidate:
                with st.expander('Strongest available research candidate — unvalidated'):
                    for leg in candidate.legs:
                        st.text(safe(f'{leg.quote.sport} · {leg.quote.event} · starts {leg.quote.commence_time}'))
                        selection_card(leg,safe)
                    st.write(f'Theoretical all-win odds product: {candidate.theoretical_odds:.2f}. Not an executable sportsbook offer.')
                    st.write('Validated joint probability: unavailable. Parlay EV: unavailable. Candidate historical betting record: unavailable.')
                    st.write(candidate.rank_explanation)
                    for warning in candidate.warnings:
                        st.text(safe(warning))
                    for blocker in candidate.blockers:
                        st.text(safe(blocker))
                    if candidate.scenario_joint:
                        st.caption(f"Unvalidated same-game score scenario {candidate.scenario_joint['probability']:.1%}; not a calibrated joint probability.")
            with st.expander('Search method and exclusions'):
                st.write(row['search_method']+'. No global optimality or profitable edge is claimed.')
                st.json(row['rejections'])


def render_dashboard(analysis,store,settings,books,secret_getter=None):
    now=utcnow();quotes=[q for q in scoped_quotes(analysis,now) if q.bookmaker in books]
    current=[q for q in quotes if q.status(now)=='current' and q.jurisdiction=='CA-ON']
    games=best_by_game(analysis,books,now)
    estimated={q.event_id for q in current if q.id in analysis.estimates or q.id in analysis.advanced_estimates}
    slate=analysis.slate
    a,b,c,d=st.columns(4)
    a.metric('Games discovered / observed',len(games))
    b.metric('Games with current markets',len({q.event_id for q in current}))
    c.metric('Games with model research',len(estimated))
    d.metric('Ontario books observed',len({q.bookmaker for q in current}))
    a,b,c,d=st.columns(4)
    a.metric('Game-market groups evaluated',len({(q.event_id,q.market) for q in current}))
    b.metric('Qualified singles',sum(o.quote.bookmaker in books and qualify(o.quote,o.estimate,now)[0] is not None for o in analysis.opportunities))
    info=quota_details(store,settings.daily_limit,now)
    c.metric('Local credits reserved',f"{info['used']}/{info['limit']}")
    d.metric('Approved parlay models','0')  # No approved joint-model adapter exists.
    latest=max((parse_time(q.received_at) for q in quotes),default=None)
    st.caption('Last successful odds receipt: '+(latest.isoformat() if latest else 'unavailable')+'. This is not a freshness guarantee; source/receipt expiry is checked separately.')
    st.info('Model status: research only; no new model is approved for recommendations. Coverage is partial. Missing current prices, player context, calibrated joint probabilities and combined pricing prevent qualification.')
    if slate:
        skipped=sum('not requested' in q['status'] for q in slate['queries'])
        st.caption(f"Automatic scan window: {slate['window_start']} to {slate['window_end']}. {len(slate['queries'])} market tasks assessed; {skipped} not requested. Cached or empty queries are not complete market coverage.")
    with st.expander('Coverage gaps and scan audit'):
        st.json({'discovery':slate.get('discovery',[]),'market_tasks':slate.get('queries',[]),
            'gaps':slate.get('gaps',[]),'processing':analysis.processing,'errors':analysis.errors,
            'warnings':analysis.warnings,'exclusions':analysis.exclusions})
    render_focused_model(analysis)
    render_games(analysis,books,secret_getter,max_games=3)
    render_books(analysis,books,secret_getter,'dashboard_book_preference')


def render_focused_model(analysis):
    from intelligence.epl_forecasts import load_artifact,high_probability_research
    artifact=load_artifact()
    st.subheader('Prediction evidence')
    if not artifact:
        st.info('Focused EPL artifact is missing or differs from the current model code. No forecast is inferred.')
        return
    source=analysis.focused_model or artifact
    if source.get('problem'):
        st.warning(source['problem'])
    else:
        st.caption(f"{artifact['model_version']} · Premier League BTTS and total goals 2.5 · research only · source results through {source['state']['latest']} · no approved betting model")
    with st.expander('Chronological model evaluation and current input gaps'):
        for market,task in artifact['tasks'].items():
            period=task['periods']['held_out'];m=period['model'];base=period['constant_baseline']
            st.write(f"{market}: calibration n={task['calibration_n']}; test n={m['n']} ({period['start']} to {period['end']}). Binary Brier {m['binary_brier']['value']:.4f}; constant baseline {base['binary_brier']['value']:.4f}; log loss {m['log_loss']['value']:.4f}; classification accuracy {m['classification_accuracy']['value']:.1%}.")
        st.caption('Historical classification accuracy is not betting win rate. No market-beating or profitable advantage is established. Full intervals, calibration bins and later-period drift diagnostics are in Performance Tracker.')
        blockers=list(dict.fromkeys(b for row in analysis.research if row.get('model')==artifact['model_version'] for b in row.get('blockers',[])))
        for blocker in blockers:
            st.text(blocker)
        if not blockers:
            st.caption('No current supported quote has been evaluated in this view. A fresh Ontario EPL BTTS or exactly 2.5-goal total and complete recent public results are required.')
    st.caption('High-probability research shortlist: estimated probability ≥65%, envelope lower bound ≥60%, width ≤25%, adequate calibration support and independent evidence required. High win probability does not imply positive EV.')
    shortlist=high_probability_research(analysis)
    if not shortlist:
        st.info('No credible high-probability selections qualify. Exploratory backtests do not establish independent forecasting reliability.')
    for q,e,d in shortlist:
        st.write(f'{q.event} · {q.selection} · research estimate {e.probability:.1%} · envelope {e.lower:.1%}–{e.upper:.1%}; no approved betting EV.')
