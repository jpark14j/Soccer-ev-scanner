from ui_navigation import navigate
"""Conversation end-to-end through Streamlit's AppTest, with no network."""
from pathlib import Path
from unittest.mock import patch
from datetime import timedelta
import pytest
from intelligence.chat_ui import STATE, COUNT, CONSENT
from intelligence.domain import utcnow
from conftest import OPENAI_TEST_KEY as KEY


@pytest.fixture
def chat(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('INTELLIGENCE_DB',str(tmp_path/'chat.sqlite3'))
    monkeypatch.setenv('ODDS_API_KEY','')
    monkeypatch.setenv('OPENAI_API_KEY',KEY)
    monkeypatch.setenv('PAID_ANALYST_APPROVED','0')
    app=AppTest.from_file(Path('app.py').resolve(),default_timeout=20).run()
    navigate(app,'AI Assistant')
    assert not app.exception
    return app


def button(app,label):
    return next(b for b in app.button if b.label==label)


def test_chat_round_trip_followups_clear_and_no_paid_construction(chat):
    with patch('openai.OpenAI',side_effect=AssertionError('No external AI')):
        chat.chat_input[0].set_value('What NBA information is available?').run()
        assert not chat.exception
        assert len(chat.chat_message)==2
        assert chat.session_state[STATE]['messages'][-1]['sport']=='NBA'
        chat.chat_input[0].set_value('What about prices?').run()
        assert not chat.exception and len(chat.chat_message)==4
        assert chat.session_state[STATE]['messages'][-1]['sport']=='NBA'
        assert chat.session_state[STATE]['messages'][-1]['mode']=='Local · rule-based'
        button(chat,'Clear conversation').click().run()
        assert not chat.exception and not chat.session_state[STATE]['messages']
        assert chat.session_state[COUNT]==0 and chat.session_state[CONSENT] is False


def test_suggested_followup_is_a_working_local_question(chat):
    button(chat,'What opportunities currently qualify?').click().run()
    assert not chat.exception and len(chat.chat_message)==2
    assert 'No current opportunities' in chat.session_state[STATE]['messages'][-1]['content']


def test_secret_input_is_not_added_to_displayed_or_stored_chat(chat):
    chat.chat_input[0].set_value('Here is my key '+KEY).run()
    assert not chat.exception and not chat.session_state[STATE]['messages']
    assert any('credential' in e.value for e in chat.error)
    assert all(KEY not in str(t.value) for t in chat.text)


def test_idle_history_expires_and_clear_does_not_reset_session_limit(chat):
    chat.chat_input[0].set_value('NBA').run()
    state=chat.session_state[STATE]
    state['last_activity']=(utcnow()-timedelta(minutes=31)).isoformat()
    chat.session_state[STATE]=state
    chat.session_state[COUNT]=7
    chat.run()
    assert not chat.exception and not chat.session_state[STATE]['messages']
    button(chat,'Clear conversation').click().run()
    assert chat.session_state[COUNT]==7


def test_configured_paid_mode_still_needs_session_consent(chat,monkeypatch):
    monkeypatch.setenv('PAID_ANALYST_APPROVED','1')
    chat.run()
    assert not chat.exception and not chat.checkbox[0].value
    chat.chat_input[0].set_value('NBA').run()
    assert not chat.exception
    assert chat.session_state[STATE]['messages'][-1]['mode']=='Local · rule-based'
    assert chat.session_state[COUNT]==0
    button(chat,'Clear conversation').click().run()
    assert not chat.exception and chat.session_state[CONSENT] is False


def test_key_is_not_displayed_in_settings_or_chat(chat):
    assert KEY not in str(chat.get('text'))+str(chat.get('info'))
    navigate(chat,'Settings')
    assert not chat.exception
    assert KEY not in ''.join(str(element.value) for element in chat.markdown)


def test_unexpected_context_failure_does_not_show_exception_or_secret(chat):
    with patch('intelligence.chat_ui.PaidAnalyst.respond',side_effect=RuntimeError(KEY)):
        chat.chat_input[0].set_value('NBA').run()
    assert not chat.exception
    assert KEY not in repr(chat.session_state[STATE]['messages'])
    assert 'temporarily unavailable' in chat.session_state[STATE]['messages'][-1]['content']


def test_session_consent_and_clear_do_not_trigger_an_api_call(chat,monkeypatch):
    monkeypatch.setenv('PAID_ANALYST_APPROVED','1')
    with patch('openai.OpenAI',side_effect=AssertionError('Consent alone must not make a call')):
        chat.run()
        chat.checkbox[0].check().run()
        assert not chat.exception and chat.session_state[CONSENT] is True
        button(chat,'Clear conversation').click().run()
        assert not chat.exception and chat.session_state[CONSENT] is False
        assert chat.session_state[COUNT]==0
