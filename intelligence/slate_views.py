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
    st.caption(f'Break-even including margin: {leg.implied_probability:.1%}. Model: {leg.model_status}.')
    if leg.estimate:
        st.write(f'Model estimate {leg.estimate.probability:.1%}; supplied envelope {leg.estimate.lower:.1%}–{leg.estimate.upper:.1%}. '+('Validated leg evidence; ticket rules still need checking.' if leg.model_status=='validated' else 'Unvalidated research forecast; not a reliable true probability.'))
    else:
        st.caption('No defensible model probability, confidence or EV is available.')
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
    render_games(analysis,books,secret_getter,max_games=3)
    render_books(analysis,books,secret_getter,'dashboard_book_preference')
