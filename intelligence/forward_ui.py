"""Concise prospective scorecards; legacy paper/backtests remain separate."""
import json
import sqlite3
import streamlit as st
from intelligence.model_reliability import scorecards
from intelligence.analyst_config import load_config
from intelligence.chat_privacy import redact_data


def render_forward(store,secret=None):
    st.subheader('Forward evaluation and model reliability')
    try:report=scorecards(store)
    except (sqlite3.Error,OSError,ValueError,KeyError,TypeError):
        st.info('Forward scorecard unavailable; inspect storage/protocol integrity. No reliability or approval is inferred.');return
    safe=lambda value:redact_data(value,load_config(secret).sensitive_values)
    a,b,c=st.columns(3)
    a.metric('First pregame contracts',report['recorded']);b.metric('Verified target labels',report['labeled']);c.metric('Quarantined records',report['quarantined'])
    st.caption('One first record per event/contract/model/protocol across books and opposing sides. Legacy paper records and backtests below are separate, potentially overlapping logs; their counts must not be added.')
    if not report['groups']:st.info('No eligible prospective contracts recorded yet. Models remain experimental; future games and exact verified results are required.')
    for card in report['groups']:
        s=card['scope']
        st.write('**'+s['league']+' · '+s['market']+' · '+card['state']+'**')
        st.caption(f"{card['scores']['n']} scored prospective contracts · {card['independent_pregame_records']} eligible pregame records · model {s['model_version']}")
        if card['review_blockers']:st.caption(card['review_blockers'][0])
    with st.expander('Protocol, precision/power, calibration and complete reliability evidence'):
        st.json(safe(report))
        st.caption('Hypothetical score-contract returns are distinct from accepted-ticket returns. No operator execution, void treatment or profitability is established. Planning counts assume IID information; dependence and actual precision govern review.')
    st.download_button('Download forward scorecards · no API calls',json.dumps(safe(report),indent=2),file_name='forward-scorecards.json',mime='application/json',key='forward_scorecard_export')
