"""Publication-only qualification with a separate recorded research display.

Experimental cards never qualify as positive-EV bets. No requests, model training,
manual approval switches or fair-price substitution.
The original publication, suspension, source and genuine ticket gates all apply.
"""
from dataclasses import replace
import sqlite3
from intelligence.domain import utcnow,parse_time
from intelligence.parlay_research import leg_evidence
from intelligence.research_top import SourceChecks
from intelligence.quant_decision import decide

EMPTY = 'No statistically supported positive-EV bets available right now.'
LABELS = ('BEST SINGLE PREDICTION','BEST 2-LEG PREDICTION','BEST 3-LEG PREDICTION')


def shortlist(analysis,store,books,leagues,now=None,combined_prices=(),joint_estimates=()):
    now=now or utcnow();checks=SourceChecks(store,now);allowed=[]
    for q in analysis.quotes:
        if q.league not in leagues or q.bookmaker not in books:continue
        leg=leg_evidence(q,analysis,now)
        if (not leg.estimate or leg.blockers or leg.model_status!='validated'
            or (now-parse_time(leg.estimate.training_end)).days>90 or checks.check(leg)):continue
        allowed.append(q)
    result=decide(replace(analysis,quotes=allowed),books,now,combined_prices,joint_estimates)
    # decide orders all formats by conservative EV penalized by uncertainty,
    # then narrower uncertainty and estimated probability. No payout objective.
    # Extremely large apparent edges need independent price/model review; do
    # not let a bad price dominate an otherwise conservative shortlist.
    options=[o for o in result['options'] if o['ev']<=.5]
    winners={n:next((o for o in options if len(o['quotes'])==n),None) for n in (1,2,3)}
    return {'winners':winners,'qualified':sum(v is not None for v in winners.values()),
        'blockers':result['blockers'],'method':result['method']}


def render(w,safe):
    import streamlit as st
    from intelligence.consumer_ui import friendly_time
    from intelligence.markets import selection_label,CATALOG
    result=shortlist(w.analysis,w.store,w.book_keys,w.leagues)
    from intelligence.prediction_accuracy import home_choices
    try:experimental=home_choices(w.store,w.leagues)
    except (sqlite3.Error,OSError,ValueError,KeyError,TypeError):
        experimental={n:None for n in (1,2,3)}
        st.caption('Saved experimental predictions are unavailable until their records can be verified.')
    for size,label in enumerate(LABELS,1):
        st.subheader(label)
        choice=result['winners'][size]
        if not choice:
            r=experimental[size]
            if r:
                with st.container(border=True):
                    st.text(safe(r['event']+' · '+r['league']))
                    st.caption(friendly_time(r['kickoff']))
                    for leg in r.get('legs') or [r]:
                        market={'h2h':'Match winner','btts':'Both teams to score','totals':'Total goals'}.get(leg['market'],leg['market'])
                        st.text(safe(market+' · '+leg['selection']+(f" {leg['point']}" if leg.get('point') is not None else '')))
                    p=r.get('joint_probability',r.get('probability'))
                    st.write(f"Estimated chance **{p:.1%}** · Experimental prediction")
                    st.caption('Historically tested model, unapproved. No verified sportsbook price or EV. Estimates can be wrong.')
                    st.caption('Recorded before kickoff · '+friendly_time(r['recorded_at']))
            continue
        with st.container(border=True):
            for q in choice['quotes']:
                st.text(safe(q.event+' · '+CATALOG[q.market].name+' · '+selection_label(q)))
                st.caption(friendly_time(q.commence_time))
            q=choice['quotes'][0]
            st.write(f"Estimated chance **{choice['probability']:.1%}** · actual decimal **{choice['odds']:.2f}** · estimated EV **{choice['ev']:+.1%}**")
            st.caption(safe(q.bookmaker_name)+' · odds observed '+friendly_time(choice['source_updated_at']))
            st.write('Current source, approved model, uncertainty and price checks passed. Estimates can be wrong.')
    if not result['qualified']:st.info(EMPTY)
    return result
