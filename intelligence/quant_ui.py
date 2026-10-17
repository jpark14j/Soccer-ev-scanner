"""Simple final result and collapsed offline research evidence; no API calls."""
import json
from pathlib import Path
import streamlit as st
from intelligence.analyst_config import load_config
from intelligence.chat_privacy import redact,redact_data
from intelligence.markets import selection_label
from intelligence.domain import digest
from intelligence.quant_decision import decide


def render_best(analysis,books,secret=None):
    sensitive=load_config(secret).sensitive_values;safe=lambda s:redact(str(s),sensitive)
    result=decide(analysis,books)
    st.subheader("Today's Best-Supported Bet")
    st.caption('APPROVED OPPORTUNITY · evaluated separately from experimental research')
    best=result['best']
    if not best:
        st.info('NO QUALIFYING BET — the available evidence does not support an approved selection or ticket.')
        st.caption('Experimental research is shown separately. A high estimated win probability alone never triggers this result.')
    else:
        st.write('**'+best['format']+'**')
        for q in best['quotes']:st.text(safe(q.event+' · '+q.league+' · '+q.commence_time+' · '+selection_label(q)))
        st.write(safe(best['quotes'][0].bookmaker_name)+f" · verified observed decimal {best['odds']:.2f}")
        st.caption(safe(best['why']))
        st.caption(f"Estimate {best['probability']:.1%}; supplied uncertainty {best['lower']:.1%}–{best['upper']:.1%}; estimated EV {best['ev']:+.1%}. Source "+safe(best['source_updated_at']))
        st.caption('Publication evidence passes the existing gates; outcomes and profits are never guaranteed. No wager is placed.')
    with st.expander('Decision evidence and format limitations'):
        st.json(redact_data({k:v for k,v in result.items() if k!='best'},sensitive))
        st.caption('Singles, SGP, multi-game and mixed tickets face the same evidence/value ranking rule. Current SGP/parlay approval still requires supported leg validation, joint calibration, actual ticket prices and operator rules. No adapter currently supplies those ticket requirements.')


def render_evaluation():
    with st.expander('Quantitative model challengers · offline held-out research'):
        from intelligence.quant_evaluation import DESTINATION,POLICY
        from intelligence.data_adapters import ROOT
        try:
            report=json.loads(DESTINATION.read_text());checksum=report.pop('sha256')
            code=digest({n:(ROOT/'intelligence'/n).read_text() for n in ('quant_models.py','quant_evaluation.py','score_distribution.py')})
            if digest(report)!=checksum or code!=report['candidate_code_sha256'] or digest(json.loads(POLICY.read_text()))!=report['policy_sha256']:raise ValueError()
        except (OSError,ValueError,KeyError):
            st.info('No matching reproducible challenger report is available. No model is promoted.');return
        st.caption('No frozen model is replaced. Test data is held out from challenger fitting/calibration, but was examined earlier in the project; independent prospective confirmation and market-price evidence are missing.')
        rows=[]
        for league,r in report['leagues'].items():
            if r.get('blocked'):st.text(league+': '+r['blocked'])
            for market,task in r.get('markets',{}).items():
                for method,m in task['methods'].items():
                    rows.append({'League':league,'Market':market,'Method':method,'Calibration n':task['calibration_n'],'Test n':task['test_n'],
                        'Brier':m['metrics']['binary_brier']['value'],'Log loss':m['metrics']['log_loss']['value'],
                        'ECE':m['ece'],'Brier difference interval vs frozen':m['minus_frozen']['binary_brier']['interval']})
        st.dataframe(rows,hide_index=True)
        st.caption('Lower Brier/log loss is better. ECE depends on binning and sample size; score improvements do not imply betting profit. Difference intervals that include zero do not establish improvement.')
        with st.expander('Full reproducible evidence, joint-event diagnostics and limitations'):
            st.json(report)
    render_phase6_evaluation()
    render_joint_validation()


def render_phase6_evaluation():
    with st.expander('Phase 6 calibration, annual refit and joint settlement research'):
        from intelligence.phase6_evaluation import DESTINATION,POLICY
        from intelligence.data_adapters import ROOT
        try:
            r=json.loads(DESTINATION.read_text());checksum=r.pop('sha256')
            p=json.loads(POLICY.read_text())
            code=digest({name:(ROOT/'intelligence'/name).read_text() for name in ('phase6_evaluation.py','quant_models.py','score_distribution.py','quant_evaluation.py')})
            if digest(r)!=checksum or digest(p)!=r['policy_sha256'] or code!=r['code_sha256']:raise ValueError()
        except (ValueError,KeyError,OSError):
            st.info('No matching Phase 6 evaluation report is available; no model is activated.');return
        st.caption('Additional calibration and annual-refit challengers use prior data only. Reused project test dates and incomplete later seasons prevent independent approval; no frozen model changes.')
        rows=[]
        for league,v in r['leagues'].items():
            if v.get('blocked'):st.text(league+': '+v['blocked'])
            for market,t in v.get('markets',{}).items():
                for method,m in t['methods'].items():
                    rows.append({'League':league,'Market':market,'Method':method,'Test n':t['test_n'],
                        'Brier':m['metrics']['binary_brier']['value'],'Log loss':m['metrics']['log_loss']['value'],'ECE':m['ece'],
                        'Brier difference interval vs frozen':m['minus_frozen']['binary_brier']['interval']})
        st.dataframe(rows,hide_index=True)
        st.caption('Approval blockers remain separate: uncertain predictive gains; calibration/sample limits; per-event current inputs; eligible market coverage; unverified operator settlement; and missing actual combined prices. Research estimates do not satisfy these publication requirements automatically.')
        with st.expander('Joint-state calibration, partial settlements and complete Phase 6 evidence'):
            st.json(r)


def render_joint_validation():
    with st.expander('Joint research · simpler baseline, sensitivity and stability'):
        from intelligence.joint_validation import DESTINATION
        try:
            r=json.loads(DESTINATION.read_text());checksum=r.pop('sha256')
            if digest(r)!=checksum or r['code_sha256']!=digest(Path(__file__).with_name('joint_validation.py').read_text()):raise ValueError()
        except (OSError,KeyError,ValueError):st.info('No matching joint research report. No model or ticket is approved.');return
        st.caption('Existing score parameters replayed against a training-only coherent league baseline. These test dates were previously inspected; sensitivity ranges are scenarios, not confidence intervals.')
        rows=[]
        for league,v in r['leagues'].items():
            for task,t in v['tasks'].items():
                rows.append({'League':league,'Joint target':task,'Test n':t['n'],
                    'All-full-win Brier':t['all_full_win']['model']['binary_brier']['value'],
                    'Paired difference interval vs league baseline':t['all_full_win']['minus_training_league_baseline']['binary_brier']['interval'],
                    'Median scenario range width':t['sensitivity_range_width_quantiles'][1]})
        st.dataframe(rows,hide_index=True)
        st.caption('Zero approved joint models. No observed executable combined ticket, parlay EV or cross-game independence claim.')
        with st.expander('Joint settlement scores, calibration bins and quarter stability'):st.json(r)
