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
    best=result['best']
    if not best:
        st.info('NO QUALIFYING BET — the available evidence does not support an approved selection or ticket.')
        st.caption('Experimental research remains below. A high estimated win probability alone never triggers this result.')
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
