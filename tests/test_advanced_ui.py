from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
import pytest
from intelligence.domain import utcnow
from intelligence.storage import Store
from intelligence.pipeline import Analysis
from intelligence.analyst_config import AnalystConfig
from intelligence.llm import PaidAnalyst
from conftest import NOW


@pytest.fixture
def advanced_app(tmp_path,monkeypatch,quote):
    from streamlit.testing.v1 import AppTest
    db=tmp_path/'advanced-ui.sqlite3'
    monkeypatch.setenv('INTELLIGENCE_DB',str(db));monkeypatch.setenv('ODDS_API_KEY','fixture-private-odds-key')
    monkeypatch.setenv('ODDS_DAILY_CREDITS','9');monkeypatch.setenv('PAID_ANALYST_APPROVED','0')
    now=utcnow()
    q=replace(quote,source_updated_at=(now-timedelta(hours=1)).isoformat(),received_at=(now-timedelta(minutes=59)).isoformat(),
        commence_time=(now+timedelta(days=1)).isoformat())
    store=Store(db);store.reserve(9,9)
    analysis=Analysis(quotes=[q],checked_at=now.isoformat())
    with patch('intelligence.pipeline.run_analysis',return_value=analysis):
        app=AppTest.from_file(Path('app.py').resolve(),default_timeout=30).run()
        app.sidebar.radio[0].set_value('Advanced Markets').run()
        assert not app.exception
        yield app,analysis,store


def test_exhausted_preview_cap_shows_toronto_reset_and_disabled_reasons(advanced_app):
    app,_,_=advanced_app
    assert any('9/9' in c.value and 'next local reset' in c.value.lower() for c in app.caption)
    assert any('EDT' in c.value and 'credits' in c.value for c in app.caption)
    for key in ('market_fetch_featured','market_discover','market_fetch_event'):
        assert next(b for b in app.button if b.key==key).disabled
    assert not next(b for b in app.button if b.key=='market_list_events').disabled


def test_stale_observations_visible_but_never_labeled_current_actionable(advanced_app):
    app,_,_=advanced_app
    assert len(app.dataframe)==1
    rows=app.dataframe[0].value
    assert set(rows['Status'])=={'stale'}
    assert all('never actionable' in text for text in rows['Use'])
    next(r for r in app.radio if r.label=='Prices to inspect').set_value('Current only').run()
    assert not app.exception and not app.dataframe


def test_no_secret_in_english_data_view_or_scope(advanced_app):
    app,_,_=advanced_app
    assert all('fixture-private-odds-key' not in str(frame.value) for frame in app.dataframe)
    assert all('unverified' in text for text in app.dataframe[0].value['Settlement scope'])


def test_performance_and_optional_risk_controls_work_with_no_fake_returns(advanced_app):
    app,_,_=advanced_app
    app.sidebar.radio[0].set_value('Performance Tracker').run()
    assert not app.exception
    assert any('No published predictions' in i.value for i in app.info)
    assert any('not a betting win rate' in c.value for c in app.caption)
    app.sidebar.radio[0].set_value('Daily Parlay Research').run()
    next(c for c in app.checkbox if c.label=='Enable hypothetical bankroll analysis').check().run()
    assert not app.exception
    assert any('Kelly unavailable' in m.value for m in app.markdown)
    assert len(app.table)>=1


def test_assistant_uses_observed_props_without_inventing_estimates(store,quote):
    q=replace(quote,sport='MLB',league='MLB',market='pitcher_strikeouts',participant='Fixture Pitcher',selection='Over',point=4.5)
    reply=PaidAnalyst(store,AnalystConfig()).respond('Analyze MLB pitcher props with the strongest statistical evidence',Analysis(quotes=[q]),now=NOW)
    assert 'Fixture Pitcher' in reply.content and '4.5 strikeouts' in reply.content
    assert '1.90' in reply.content and 'No prop currently has sufficient' in reply.content
    assert reply.mode=='Local · rule-based' and not reply.paid_attempted


def test_assistant_explains_current_parlay_candidates_and_missing_prices(store,quote):
    second=replace(quote,event_id='fixture-second',home='Other Home',away='Other Away',selection='Other Home',event='Other Home vs Other Away')
    reply=PaidAnalyst(store,AnalystConfig()).respond('Find best-supported two-leg and three-leg NBA parlay candidates',Analysis(quotes=[quote,second]),now=NOW)
    assert 'Research candidate' in reply.content and 'Theoretical' in reply.content
    assert 'actual combined' in reply.content and 'not a sportsbook offer' in reply.content
    assert reply.mode=='Local · rule-based'
