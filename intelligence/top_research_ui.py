"""Short experimental answers with expandable technical evidence. No paid AI."""
import streamlit as st
from intelligence.domain import utcnow
from intelligence.analyst_config import load_config
from intelligence.chat_privacy import redact,redact_data
from intelligence.markets import selection_label
from intelligence.research_top import select_top,value_status,risk_tags
from intelligence.research_ranking import comparison,RANKINGS
from intelligence.parlay_intelligence import explain_leg
from intelligence.odds_diagnostics import inspect_odds


def active_analysis(analysis,store):
    from intelligence.cached_research import synchronize
    saved=st.session_state.get('_research_snapshot')
    return synchronize(saved,store) if saved else analysis


def render_summary(analysis,store,books,secret=None,cap=9,leagues=None):
    now=utcnow();sensitive=load_config(secret).sensitive_values
    safe=lambda value:redact(str(value),sensitive)
    result=select_top(analysis,store,books,now,leagues)
    audit=inspect_odds(analysis,store,books,now,cap)
    from intelligence.publication_journal import overall
    overall_pick=overall(result)
    st.subheader("Today's Best Overall AI Pick")
    if overall_pick['winner']=='single':
        st.write('**Best Overall Research Pick · single · experimental**')
        st.caption(overall_pick['reason'])
    else:
        st.info('No defensible overall single-versus-parlay winner. '+overall_pick['reason'])
    st.subheader("AI's Top Research Pick — Experimental")
    st.caption('Local statistical-model and rule-based research summary; no generative AI request.')
    risk=result.get('risk_rankings',{})
    leg=result.get('recommended') or result['pick'];model_only=result['model_only']
    st.caption('TOP AI SINGLE · '+risk.get('default_mode','Existing evidence-first research'))
    if leg:
        q,e=leg.quote,leg.estimate;gap=comparison(leg)
        with st.container(border=True):
            st.write('**'+safe(q.event)+'** · '+safe(q.sport+' · '+q.league))
            st.text(safe(selection_label(q)))
            st.write(f'Model estimate **{e.probability:.1%}** · calibration range {e.lower:.1%}–{e.upper:.1%}')
            st.write(safe(q.bookmaker_name)+f' · observed individual decimal **{q.odds:.2f}**')
            st.write(f"Sportsbook break-even {gap['sportsbook_break_even']:.1%} · model difference {100*gap['difference']:+.1f} percentage points")
            st.caption(value_status(leg)+'. This comparison is not approved betting EV.')
            st.text(safe(explain_leg(leg)[0]))
            st.caption('Selected for evidence quality and supported uncertainty. Experimental / unapproved; no proven betting advantage.')
            st.caption(safe('Kickoff UTC '+q.commence_time+' · odds source '+q.source_updated_at+' · received '+q.received_at))
            with st.expander('Why this research pick? Evidence, alternatives and risks'):
                for line in explain_leg(leg)[1:]:st.text(safe(line))
                st.json(redact_data({'model_version':e.model_version,'calibration_bucket':leg.model_details.get('calibration_bin_n'),
                    'calibration_n':leg.model_details.get('calibration_n'),'test_n':leg.model_details.get('test_n'),
                    'known_risk_categories':risk_tags(leg),'comparison':gap,'blockers':leg.blockers,'ranking':result['method']},sensitive))
    elif model_only:
        q,e=model_only.quote,model_only.estimate
        with st.container(border=True):
            st.write('**Model-only research forecast · previously computed · unapproved**')
            st.write(safe(q.event)+' · '+safe(q.sport+' · '+q.league))
            st.text(safe(selection_label(q)))
            st.write(f'Model estimate {e.probability:.1%} · calibration range {e.lower:.1%}–{e.upper:.1%}')
            st.caption(safe('Forecast recorded '+model_only.model_details['prediction_at']+' · kickoff UTC '+q.commence_time))
            st.caption('The same verified model inputs and fixture still match. A current sportsbook price is unavailable, so no odds, break-even comparison, value or betting recommendation is shown.')
            with st.expander('Model-only evidence and limitations'):
                st.json(redact_data({'model':e.model_version,'data_sha256':model_only.model_details.get('data_sha256'),
                    'source_checked_at':model_only.model_details.get('source_checked_at'),'blockers':model_only.blockers},sensitive))
    else:
        reasons=result['input_blockers'] or result['exclusions'] or result['model_only_exclusions']
        reason=next(iter(reasons),'No supported, calibrated current model estimate and eligible observed price are available')
        st.info('No eligible experimental top pick: '+safe(reason)+'.')
        if not analysis.quotes:st.caption('Fresh football results alone do not supply an event-specific prediction or current odds. Saved verified forecasts are checked separately.')

    st.subheader("AI's Top Research Parlay")
    st.caption('TOP AI PARLAY · supported marginal evidence; joint success remains unvalidated')
    item=result['parlay']
    if item:
        c=item.research
        with st.container(border=True):
            st.write(f'**{len(c.legs)}-leg multi-game research · experimental / unapproved**')
            for l in c.legs:
                q,e=l.quote,l.estimate
                st.text(safe(f'{q.sport} · {q.league} · {q.event} · {selection_label(q)}'))
                st.caption(safe(f'{q.bookmaker_name} · decimal {q.odds:.2f} · model {e.probability:.1%} ({e.lower:.1%}–{e.upper:.1%}) · kickoff {q.commence_time} · source {q.source_updated_at}'))
            st.write(f'Individual-odds product {c.theoretical_odds:.2f} · **theoretical; combined ticket unverified**')
            st.caption('Joint win probability and parlay EV unavailable. Different games do not establish independence.')
            with st.expander('Why this parlay? Dependencies and missing evidence'):
                st.write(result['parlay_method'])
                for line in (*item.dependence['known_links'],*c.blockers):st.text(safe(line))
                st.caption('Same-game and mixed formats require independently tested joint evidence; they are excluded from this default summary.')
    else:
        st.info('No supported top research parlay: at least two compatible, current model-backed favored selections at one sportsbook are required. Known shared-game/team/player links stay outside this summary.')

    st.subheader('Best Risk-Adjusted Research Opportunity')
    best=risk.get('best_risk_adjusted')
    if best:
        from intelligence.risk_research import sensitivity
        evidence=sensitivity(best)
        st.write(safe(best.quote.event+' · '+selection_label(best.quote)))
        st.caption(safe(best.quote.bookmaker_name)+f' · observed decimal {best.quote.odds:.2f} · source '+safe(best.quote.source_updated_at))
        st.caption('The entire supplied historical calibration range is above break-even. This is experimental price sensitivity, not independently validated EV.')
        with st.expander('Risk ranking method, downside and missing sensitivity'):
            st.json(redact_data(evidence,sensitive));st.write(risk['method'])
            for line in risk['limitations']:st.text(safe(line))
    else:
        st.info('Risk-adjusted value is not established. The top single falls back to supported model probability when available; no value selection is forced.')

    from intelligence.quant_ui import render_best
    render_best(analysis,books,secret)
    st.subheader('Model Reliability')
    reference=leg or model_only
    if reference:
        from intelligence.model_reliability import status_for
        q,e=reference.quote,reference.estimate
        reliability=status_for(store,q.sport,q.league,q.market,e.model_version,now,point=q.point,evidence_id=e.evidence_id)
        st.write(reliability['state']+' · '+safe(q.league+' · '+q.market+' · '+e.model_version))
        st.caption('Research rankings never approve a model or ticket. Forward records: '+str(reliability.get('recorded','unavailable'))+'.')
        with st.expander('Selected model reliability and missing evidence'):st.json(redact_data(reliability,sensitive))
    else:st.caption('No current research model is selected. Inspect scoped forward scorecards in Performance Tracker; no reliability or approval is inferred from missing data.')
    with st.expander('Three research rankings and compatible parlay formats'):
        from intelligence.risk_research import MOST_LIKELY,RISK_ADJUSTED,PARLAY
        st.write('**'+MOST_LIKELY+'**')
        for l in risk.get('most_likely',[])[:3]:st.text(safe(f'{l.quote.event} · {selection_label(l.quote)} · model {l.estimate.probability:.1%}'))
        st.write('**'+RISK_ADJUSTED+'**')
        for l in risk.get('risk_adjusted',[])[:3]:st.text(safe(l.quote.event+' · '+selection_label(l.quote)))
        st.write('**'+PARLAY+'** · marginal evidence only; no joint win ranking')
        from intelligence.joint_research import analyze
        for kind,items in result.get('format_candidates',{}).items():
            st.write(kind)
            if not items:st.caption('No compatible model-backed combination currently available.')
            for item in items[:1]:
                for l in item.research.legs:st.text(safe(l.quote.event+' · '+selection_label(l.quote)))
                st.json(redact_data(analyze(item.research.legs,now),sensitive))

    if audit.get('code')!='current_prices_available':
        st.caption(safe(audit['message']))
        st.caption('Next action: '+safe(audit['next_action']))
    with st.expander('Odds availability, distinct rankings and selection exclusions'):
        st.json(redact_data(audit,sensitive))
        st.write(result['method'])
        for name in RANKINGS:
            st.write('**'+name+'**')
            for _,l in result['shared_rankings']['rankings'][name][:3]:
                st.text(safe(f'{l.quote.event} · {selection_label(l.quote)} · model {l.estimate.probability:.1%}'))
        st.json(redact_data({'input_requirements':result['input_blockers'],'research':result['exclusions'],'model_only':result['model_only_exclusions'],'parlays':result['parlay_exclusions']},sensitive))
    return result
