"""Concise model-first cards; explanations are deterministic and evidence-based."""
from dataclasses import replace
import streamlit as st
from intelligence.domain import utcnow
from intelligence.analyst_config import load_config
from intelligence.chat_privacy import redact,redact_data
from intelligence.markets import selection_label
from intelligence.parlay_research import SPORTS
from intelligence.parlay_intelligence import generate,explain_leg,binary_market
from intelligence.research_ranking import comparison


def leg_card(leg, group, safe, sensitive=()):
    q,e=leg.quote,leg.estimate
    st.write('**'+safe(q.event)+'** · '+safe(q.sport+' · '+q.league))
    st.caption('Kickoff (UTC): '+safe(q.commence_time))
    st.text(safe(selection_label(q)))
    st.write(f'Model estimate {e.probability:.1%} · supplied envelope {e.lower:.1%}–{e.upper:.1%}')
    st.caption(safe(f'{q.bookmaker_name} · observed individual decimal {q.odds:.2f} · source update {q.source_updated_at} · received {q.received_at}'))
    st.caption('Model status: experimental / research-only. A high individual estimate does not establish betting value.')
    with st.expander('Why this leg? Evidence, opposing outcomes and risks'):
        for line in explain_leg(leg):st.text(safe(line))
        gap=comparison(leg);lo,hi=gap['difference_envelope']
        st.write(f"Sportsbook break-even {gap['sportsbook_break_even']:.1%}; model difference {100*gap['difference']:+.1f} percentage points; envelope {100*lo:+.1f} to {100*hi:+.1f} points. Unvalidated comparison, not EV.")
        st.caption('Current observed opposing outcomes and equivalent sportsbook prices:')
        for offer in group.offers:
            probability=f'{offer.estimate.probability:.1%}' if offer.estimate else 'no model estimate'
            st.text(safe(f'{selection_label(offer.quote)} · {offer.quote.bookmaker_name} · decimal {offer.quote.odds:.2f} · model {probability} · source {offer.quote.source_updated_at}'))
        for risk in leg.blockers:st.text(safe(risk))
        st.json(redact_data({'model_version':e.model_version,'model_input_history_through':e.training_end,
            'calibration_bin_n':leg.model_details.get('calibration_bin_n'),'test_n':leg.model_details.get('test_n'),
            'data_source':leg.model_details.get('data_source'),'source_checked_at':leg.model_details.get('source_checked_at'),
            'model_code_sha256':leg.model_details.get('model_code_sha256'),'data_sha256':leg.model_details.get('data_sha256')},sensitive))


def candidate_card(item, group_map, safe, sensitive=()):
    candidate=item.research
    with st.container(border=True):
        st.write(f'**{len(candidate.legs)}-leg model-backed research**')
        if any(item.dependence[k] for k in ('shared_game_pairs','shared_team_pairs','shared_player_pairs')):
            st.warning('Linked alternative: shared game, team or player. Joint dependence and same-game acceptance are unverified.')
        for leg in candidate.legs:
            key,_=binary_market(leg.quote)
            group=next(g for g in group_map.values() if g.market_key==key)
            leg_card(leg,group,safe,sensitive)
        st.write(f'Theoretical individual-odds product: {candidate.theoretical_odds:.2f}. Combined sportsbook ticket: **unverified**.')
        st.caption('All displayed individual prices are observed at the same Ontario sportsbook. Multiplying them does not establish an available parlay price.')
        st.caption('Joint win probability: unavailable. Parlay EV: unavailable. No approved ticket or validated joint model.')
        st.caption(item.dependence['note'])
        with st.expander('Why this combination? Missing evidence and dependencies'):
            st.write('The default shortlist uses different games without known shared-team/player links. Within each leg count it ranks stronger individual lower envelopes and model estimates first, then uncertainty, calibration support and freshness. It does not rank a validated parlay win probability or maximize payout.')
            for link in item.dependence['known_links']:st.text(safe(link))
            for risk in candidate.blockers:st.text(safe(risk))
            if candidate.probability_bounds is not None:
                lo,hi=candidate.probability_bounds
                st.caption(f'Logical joint bounds conditional on the unvalidated marginal estimates: {lo:.1%}–{hi:.1%}. These are not a calibrated parlay forecast or confidence interval.')


def render_intelligence(analysis, store, books, secret_getter=None):
    sensitive=load_config(secret_getter).sensitive_values
    safe=lambda s:redact(str(s),sensitive)
    st.subheader('AI Parlay Intelligence')
    st.caption('Automatic statistical research with local, rule-based explanations. No paid language-model request is used. Experimental candidates are not approved betting recommendations.')
    sports=st.multiselect('Model-research sports',SPORTS,default=list(SPORTS),key='intelligence_sports')
    with st.expander('Parlay research controls'):
        sizes=st.multiselect('Model-backed leg counts',[2,3],default=[2,3],key='intelligence_sizes')
        linked=st.checkbox('Include known linked-game/team/player alternatives',value=False,key='intelligence_linked')
        st.caption('Linked combinations can appear only as alternative research. Separate games still have unmeasured dependence. Sportsbooks in view are controlled in the sidebar.')

    @st.fragment(run_every='60s')
    def show():
        scoped=replace(analysis,quotes=[q for q in analysis.quotes if q.sport in sports])
        report=generate(scoped,books,include_linked=linked,max_per_size=1)
        group_map={g.id:g for g in report.groups}
        st.caption(f'{report.eligible_model_groups} favored markets pass existing research evidence checks; {report.searched_model_groups} markets searched. Prices are rechecked for expiry without API requests.')
        st.subheader('1. Highest estimated win probability')
        st.caption('Preferred individual outcomes are above 50% in their binary model. This is a model preference, not proof they will win. Parlay ordering compares individual evidence; joint winning chances are unknown.')
        selected=[c for c in report.two_leg+report.three_leg if len(c.group_ids) in sizes]
        if not selected:
            st.info('No model-backed parlay candidates meet the current evidence, price and dependency requirements. No selection is forced.')
        for item in selected:candidate_card(item,group_map,safe,sensitive)
        with st.expander('Preferred individual selections · one side per binary market'):
            if not report.favored:st.info('No model-favored selections pass the current research evidence checks.')
            for group in report.favored[:6]:
                with st.container(border=True):leg_card(group.preferred,group,safe,sensitive)
        st.subheader('2. Strongest potential value · unvalidated comparisons')
        st.caption('Only favored outcomes with supported estimates above the observed break-even percentage appear here. This does not establish a betting edge or parlay EV; uncertainty can include a negative difference.')
        if not report.potential_value:
            st.info('No evidence-supported positive model-versus-price difference is available for the favored outcomes.')
        for group in report.potential_value[:3]:
            with st.container(border=True):leg_card(group.preferred,group,safe,sensitive)
        st.subheader('3. Alternative experimental research candidates')
        alternatives=[c for c in report.alternatives if len(c.group_ids) in sizes]
        if not alternatives:st.info('No additional model-backed combination meets the selected research requirements.')
        for item in alternatives[:min(2,3-len(selected))]:candidate_card(item,group_map,safe,sensitive)
        with st.expander('Selection exclusions, opposing outcomes and search method'):
            st.write(report.method)
            st.caption('The best current single price is compared only within the same favored outcome. A parlay uses one sportsbook for all legs; cross-book prices are never multiplied into a ticket.')
            st.write(f'{report.examined_combinations} combinations examined. No independence approximation or multiplied win probability is displayed.')
            st.json(redact_data(report.exclusions,sensitive))
            for group in report.groups:
                if not group.research_eligible:
                    st.text(safe(group.problem))
                    for leg in group.offers:
                        p=f'{leg.estimate.probability:.1%}' if leg.estimate else 'unavailable'
                        st.text(safe(f'{leg.quote.event} · {selection_label(leg.quote)} · {leg.quote.bookmaker_name} · decimal {leg.quote.odds:.2f} · model {p} · source {leg.quote.source_updated_at}'))
    show()
    with st.expander('Sport and model coverage · what is still missing'):
        from intelligence.diagnostics import competition_diagnostics
        for row in competition_diagnostics(analysis,store):
            if row['competition'] in ('Premier League','Bundesliga','Ligue 1','La Liga','Serie A','NBA','MLB'):
                st.text(safe(row['competition']+': '+row['current_forecast']))
        st.caption('EPL: BTTS / total goals 2.5; Bundesliga: BTTS; Ligue 1: total goals 2.5. All are experimental. La Liga and Serie A need their own complete historical evaluation and frozen model; current results alone are not a model.')
        st.caption('NBA needs current reconciled game history and validated sport/market models; props additionally need permitted player logs, minutes and availability. MLB needs current permitted results, pitcher/lineup/park context and its own validation. Old archives and sportsbook implied probabilities do not fill these gaps.')
