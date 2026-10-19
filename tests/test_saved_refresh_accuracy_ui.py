"""Saved-only refresh and accuracy UI: no passwords, provider or workflow I/O."""
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
import pytest
from streamlit.testing.v1 import AppTest
from intelligence.domain import utcnow
from intelligence.consumer_ui import render_performance
from test_consumer_ui import consumer_app
from test_prediction_accuracy import prepare


def test_find_button_has_no_passcode_and_opens_saved_predictions(consumer_app):
    app,scans=consumer_app
    assert not app.exception and not app.text_input
    assert all(e.label.lower()!='private research access' for e in app.expander)
    button=next(b for b in app.button if b.label=='Find Best Bets Now')
    assert not button.disabled
    with patch('intelligence.manual_research.request_research',side_effect=AssertionError('No dispatch')):
        with patch('intelligence.providers.OddsAPI',side_effect=AssertionError('No provider')):
            button.click().run()
    assert not app.exception and app.sidebar.radio[0].value=='Best Picks & Parlays'
    assert any('Showing saved predictions' in c.value for c in app.caption)
    # A cache-only replay is allowed; no quote retrieval is invoked.
    assert scans.call_count<=2


def test_performance_displays_exactly_three_accuracy_metrics_and_no_finances(tmp_path):
    path=tmp_path/'accuracy.sqlite3'
    script=f'''from types import SimpleNamespace
from intelligence.storage import Store
from intelligence.consumer_ui import render_performance
render_performance(SimpleNamespace(store=Store({str(path)!r})))'''
    app=AppTest.from_string(script).run()
    assert not app.exception and len(app.metric)==3
    assert [m.label for m in app.metric]==['Singles Accuracy (%)','2-Leg Parlay Accuracy (%)','3-Leg Parlay Accuracy (%)']
    assert all(m.value=='Not enough results yet' for m in app.metric)
    text=' '.join(str(x.value) for group in (app.caption,app.markdown,app.info) for x in group)
    assert all(t not in text.lower() for t in ('profit','roi','bankroll','paper return'))


def test_refresh_callback_only_clears_saved_caches_and_is_throttled(tmp_path):
    script='''import streamlit as st
from types import SimpleNamespace
from intelligence.manual_research_ui import render
st.session_state.setdefault('sync_calls',0)
def sync():st.session_state['sync_calls']+=1
render(SimpleNamespace(sync_saved=sync))
'''
    app=AppTest.from_string(script).run();app.button[0].click().run()
    assert not app.exception and app.session_state['sync_calls']==1
    app.button[0].click().run()
    assert not app.exception and app.session_state['sync_calls']==1
