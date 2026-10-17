"""Everyday research screens. Saved evidence only; no provider or paid AI calls."""
from dataclasses import replace
from datetime import timedelta
from zoneinfo import ZoneInfo
import sqlite3
import streamlit as st
from intelligence.domain import utcnow,parse_time
from intelligence.markets import selection_label,CATALOG
from intelligence.analyst_config import load_config
from intelligence.chat_privacy import redact
from intelligence.research_top import select_top,SourceChecks
from intelligence.research_ranking import RANKINGS,rank_research
from intelligence.research_state import APPROVED

LOCAL=ZoneInfo('America/Toronto')


def friendly_time(value):
    try:return parse_time(value).astimezone(LOCAL).strftime('%a, %b %d · %I:%M %p %Z')
    except (ValueError,TypeError):return 'Time unavailable'


def saved_games(analysis,window_hours=48,now=None):
    """Future dates included, with stale observations never promoted to prices."""
    now=now or utcnow()
    end=parse_time(analysis.slate['window_end']) if analysis.slate.get('window_end') else now+timedelta(hours=window_hours)
    events={}
    for row in analysis.slate.get('events',[]):
        try:
            if now<parse_time(row['start'])<=end:
                events[(row['sport'],row['league'],row['event_id'])]=dict(row)
        except (ValueError,TypeError,KeyError):continue
    for q in analysis.quotes:
        if now<parse_time(q.commence_time)<=end:
            events.setdefault((q.sport,q.league,q.event_id),{'sport':q.sport,'league':q.league,
                'event_id':q.event_id,'event':q.event,'start':q.commence_time})
    return sorted(events.values(),key=lambda r:(parse_time(r['start']),r['league'],r['event_id']))


def research_view(analysis,store,books,leagues,now=None):
    """Reuse existing gates; do not turn prices or marginal estimates into bets."""
    now=now or utcnow()
    scoped=replace(analysis,quotes=[q for q in analysis.quotes if q.league in leagues])
    top=select_top(scoped,store,books,now,leagues)
    rows=top['shared_rankings']['rankings'][RANKINGS[1]]
    checks=SourceChecks(store,now)
    approved=[row for row in rank_research(scoped,books,now)['rankings'][RANKINGS[1]]
              if row[0]==APPROVED and not checks.check(row[1])]
    singles=sorted(approved+rows,key=lambda row:(row[0]!=APPROVED,-row[1].estimate.probability,row[1].quote.id))
    return top,singles


def data_status(analysis,books,now=None):
    from intelligence.parlay_research import quote_problem
    from intelligence.book_optimizer import scoped_quotes
    now=now or utcnow()
    visible=[q for q in scoped_quotes(analysis,now) if q.bookmaker in books]
    current=[q for q in visible if not quote_problem(q,now)]
    if current:return 'Up to date','Current observed prices are available. Model support varies by game and market.'
    if visible:return 'Waiting for fresh odds','Saved prices are out of date or unavailable for current research.'
    return 'Research unavailable','No current prices are saved for the selected competitions and sportsbooks.'


def safe_text(w):
    sensitive=load_config(w.secret).sensitive_values
    return lambda value:redact(str(value),sensitive)


def single_card(leg,safe,approved=False,key='single',offers=()):
    q,e=leg.quote,leg.estimate
    with st.container(border=True):
        st.text(safe(q.event))
        st.caption(safe(q.sport+' · '+q.league)+' · '+friendly_time(q.commence_time))
        st.write('**'+safe(CATALOG[q.market].name)+'**')
        st.text(safe(selection_label(q)))
        st.write(safe(q.bookmaker_name)+f' · decimal odds **{q.odds:.2f}**')
        st.caption('Odds observed '+friendly_time(q.source_updated_at))
        st.write(f'Estimated chance: **{e.probability:.0%}** · uncertainty range {e.lower:.0%}–{e.upper:.0%}')
        st.caption('Approved opportunity' if approved else 'Experimental research · not an approved betting opportunity')
        st.write('The model favors this outcome. Its estimated chance alone does not establish good value at this price.')
        with st.expander('Why this pick?'):
            st.write('This is a market-specific statistical estimate, separate from the sportsbook price. The range comes from historical calibration; it is not a guarantee about this game.')
            st.write(f'Sportsbook break-even chance: {1/q.odds:.0%}. A model difference is not a verified betting advantage.')
            for reason in leg.blockers:st.text(safe(reason))
            st.caption('Injuries, lineups and other missing information may affect the outcome. Check the sportsbook’s exact rules and current price.')
            if offers:
                st.write('Other observed outcomes and prices:')
                for offer in offers:
                    text=selection_label(offer.quote)+' · '+offer.quote.bookmaker_name+f' · {offer.quote.odds:.2f}'
                    if offer.estimate:text+=f' · model estimate {offer.estimate.probability:.0%}'
                    st.text(safe(text))


def parlay_card(item,safe):
    c=item.research
    with st.container(border=True):
        st.write(f'**{len(c.legs)}-leg experimental parlay**')
        for leg in c.legs:
            q,e=leg.quote,leg.estimate
            st.text(safe(q.event))
            st.caption(safe(q.sport+' · '+q.league)+' · '+friendly_time(q.commence_time))
            st.text(safe(CATALOG[q.market].name+' · '+selection_label(q)))
            st.write(safe(q.bookmaker_name)+f' · decimal {q.odds:.2f} · estimated chance {e.probability:.0%}')
            st.caption(f'Uncertainty {e.lower:.0%}–{e.upper:.0%} · odds observed '+friendly_time(q.source_updated_at))
        st.write(f'Individual-price multiplication: **{c.theoretical_odds:.2f} — theoretical only**')
        st.warning('A combined sportsbook ticket has not been verified. These legs may not be accepted together at this price.')
        st.caption('Combined win probability and parlay value are unavailable. Different games can still be connected; independence has not been established.')
        with st.expander('Why this parlay?'):
            st.write('Each leg passed the existing research checks. Candidates favor stronger individual evidence and narrower uncertainty, rather than larger payouts. No approved joint model is available.')
            for link in item.dependence['known_links']:st.text(safe(link))
            for reason in c.blockers:st.text(safe(reason))


def render_games(w,limit=None,filters=True):
    from intelligence.parlay_research import quote_problem
    games=[r for r in saved_games(w.analysis,w.settings.window_hours) if r['league'] in w.leagues]
    safe=safe_text(w)
    if filters:
        sports=st.multiselect('Sports',['NBA','Soccer','MLB'],default=['NBA','Soccer','MLB'],key='upcoming_sports')
        games=[r for r in games if r['sport'] in sports]
        dates=sorted({parse_time(r['start']).astimezone(LOCAL).date() for r in games})
        chosen=st.multiselect('Game dates',dates,format_func=lambda d:d.strftime('%a, %b %d'),key='upcoming_dates')
        if chosen:games=[r for r in games if parse_time(r['start']).astimezone(LOCAL).date() in chosen]
    st.caption(f'Looking ahead {w.settings.window_hours} hours · times shown in Ontario. Saved coverage may be incomplete.')
    if not games:st.info('No upcoming games are saved for this view yet. Games will appear after an authorized research update.');return
    for game in games[:limit] if limit else games:
        with st.container(border=True):
            st.text(safe(game['event']))
            st.caption(safe(game['sport']+' · '+game['league'])+' · '+friendly_time(game['start']))
            quotes=[q for q in w.analysis.quotes if (q.sport,q.league,q.event_id)==(game['sport'],game['league'],game['event_id']) and q.bookmaker in w.book_keys]
            current=[q for q in quotes if not quote_problem(q,utcnow())]
            st.caption('Observed prices available; research checks still apply.' if current else 'Waiting for fresh, eligible sportsbook prices.')
    if limit and len(games)>limit:st.caption('More games are available on Upcoming Games.')


def render_home(w):
    safe=safe_text(w);top,rows=research_view(w.analysis,w.store,w.book_keys,w.leagues)
    status,message=data_status(w.analysis,w.book_keys)
    st.caption('NBA · Soccer · MLB | Ontario sportsbook research')
    st.write('**Data status: '+status+'**');st.caption(message)
    left,right=st.columns(2)
    with left:
        st.subheader('Best Single Pick')
        if rows:single_card(rows[0][1],safe,rows[0][0]==APPROVED)
        else:st.info('No supported single qualifies right now. We’ll show one when current prices and sufficient model evidence are available.')
    with right:
        st.subheader('Best Parlay')
        if top['parlay']:parlay_card(top['parlay'],safe)
        else:st.info('No qualifying parlay opportunities identified today.')
    st.subheader('Upcoming Games');render_games(w,limit=3,filters=False)
    st.subheader('Other Opportunities')
    if len(rows)<2:st.caption('No additional supported selections right now.')
    for state,leg in rows[1:3]:single_card(leg,safe,state==APPROVED)


def render_picks(w):
    safe=safe_text(w)
    sports=st.multiselect('Sports to research',['NBA','Soccer','MLB'],default=['NBA','Soccer','MLB'],key='simple_picks_sports')
    w=replace(w,analysis=replace(w.analysis,quotes=[q for q in w.analysis.quotes if q.sport in sports]))
    top,rows=research_view(w.analysis,w.store,w.book_keys,w.leagues)
    from intelligence.parlay_intelligence import selection_groups
    groups,_=selection_groups(w.analysis,w.book_keys)
    offers={g.preferred.quote.id:g.offers for g in groups if g.preferred}
    st.caption('Model estimates are experimental unless explicitly approved. Higher chance of winning does not mean better betting value.')
    st.subheader('Highest estimated win probability')
    if not rows:st.info('No supported selections are available right now.')
    for state,leg in rows[:3]:single_card(leg,safe,state==APPROVED,offers=offers.get(leg.quote.id,()))
    st.subheader('Strongest potential value')
    from intelligence.ev import qualify
    valued=[qualify(leg.quote,leg.estimate,utcnow())[0] for state,leg in rows if state==APPROVED]
    valued=[v for v in valued if v]
    if not valued:st.info('No approved positive-value opportunity is established. Experimental model differences are not confirmed value.')
    for v in sorted(valued,key=lambda v:-v.conservative_ev)[:3]:
        st.text(safe(v.quote.event+' · '+selection_label(v.quote)));st.write(f'Estimated EV {v.ev:+.1%}; conservative estimate {v.conservative_ev:+.1%}. Estimates can be wrong.')
    st.subheader('Parlay research')
    sizes=st.multiselect('Number of legs',[2,3],default=[2,3],key='simple_parlay_sizes')
    pool=[p for values in top['format_candidates'].values() for p in values]
    if top['parlay']:pool.append(top['parlay'])
    candidates=[];seen=set()
    for p in sorted(pool,key=lambda p:p.evidence_rank):
        signature=tuple(sorted(l.quote.id for l in p.research.legs))
        if (len(p.research.legs) in sizes and signature not in seen
            and not any(p.dependence[k] for k in ('shared_game_pairs','shared_team_pairs','shared_player_pairs'))):
            candidates.append(p);seen.add(signature)
        if len(candidates)==3:break
    if not candidates:st.info('No qualifying parlay opportunities identified today.')
    for item in candidates:parlay_card(item,safe)
    st.subheader('Alternative experimental research')
    st.caption('Unsupported price-only combinations and full research controls are available in Settings → Admin / Developer Tools. They are never promoted to betting recommendations.')


def render_performance(w):
    from intelligence.publication_journal import performance
    from intelligence.model_reliability import scorecards
    safe=safe_text(w)
    st.caption('Genuine pregame research records. Paper results are hypothetical and are never actual winnings.')
    try:report=performance(w.store);reliability=scorecards(w.store)
    except (sqlite3.Error,OSError,ValueError,KeyError,TypeError):
        st.info('Saved performance is unavailable right now. No results are estimated or filled in.');return
    a,b,c=st.columns(3)
    a.metric('Predictions recorded',report['published_committed_pregame']);b.metric('Wins after verified results',report['wins']);c.metric('Losses after verified results',report['losses'])
    a,b,c=st.columns(3)
    a.metric('Pending games',report['pending']);b.metric('Paper single profit / loss',f"{report['paper_net_units']:+.2f} units" if report['paper_net_units'] is not None else 'Not available')
    c.metric('Paper single return',f"{report['paper_roi']:.1%}" if report['paper_roi'] is not None else 'Not available')
    st.caption('Paper singles use one hypothetical unit at the recorded price. Parlay money returns are unavailable without verified combined prices. Shared legs can make results dependent.')
    if not report['published_committed_pregame']:st.info('No genuine published pregame predictions have been recorded yet. Historical matches and backtests are not counted as predictions.')
    st.subheader('Model reliability')
    st.write(f"{reliability['recorded']} distinct forecasts recorded · {reliability['labeled']} matched to verified results.")
    st.caption('These are a separate forecast log; do not add them to published-pick counts. Models remain experimental unless their approval requirements pass.')
    if not reliability['groups']:st.info('There is not enough forward evidence to report model reliability yet.')
    for card in reliability['groups']:
        st.text(safe(card['scope']['league']+' · '+card['scope']['market']+' · '+card['state']))
        st.caption(f"{card['scores']['n']} scored forecasts. Calibration compares estimated chances with how often outcomes actually occurred; small samples are inconclusive.")
    st.caption('Historical model studies, calibration details and older paper logs remain in Settings → Admin / Developer Tools → Detailed Performance.')


def render_settings(w,admin):
    st.subheader('Your research preferences')
    st.write('Choose competitions and sportsbooks in the sidebar. Preferences apply to this browser session.')
    st.caption('Research covers upcoming games across the configured date window. Saved prices expire quickly; out-of-date prices are excluded from picks.')
    st.subheader('Research assistant')
    if st.toggle('Ask about saved research',key='consumer_assistant_open'):
        from intelligence.chat_ui import render_assistant
        render_assistant(w.analysis,w.store,w.secret)
    st.subheader('Responsible research')
    st.write('19+ in Ontario. Analysis only. No bets are placed. Estimates can be wrong; never bet more than you can afford to lose.')
    with st.expander('Admin / Developer Tools',expanded=False):
        st.caption('Owner tools and detailed diagnostics. Opening this section does not request sports data.')
        admin(w)
