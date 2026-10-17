from ui_navigation import navigate
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import pytest
from intelligence.pipeline import run_analysis, Analysis
from intelligence.providers import ProviderError
from intelligence.storage import Store


class Provider:
    def odds(self,league,markets):
        return {'data':[],'received_at':'2026-10-16T02:00:00Z'}


def test_multi_sport_pipeline_handles_no_markets_honestly(store):
    result=run_analysis('test',['NBA','MLB','Premier League'],store,Provider())
    assert result.errors==[] and result.opportunities==[] and result.quotes==[]


def test_provider_failure_is_reported_not_simulated(store):
    class BadProvider:
        def odds(self,*args): raise ProviderError('Provider access unavailable')
    result=run_analysis('test',['NBA'],store,BadProvider())
    assert result.errors and result.opportunities==[]


def test_existing_scanner_helpers_still_import():
    import scanner_core
    assert 'Premier League' in scanner_core.SPORTS
    assert scanner_core.canonical('Manchester United')=='man united'
    assert scanner_core.shortlist([{'edge':.5,'model_prob':.9}])==[]


def test_workflow_branch_guard_and_persist_before_send():
    import yaml
    text=Path('.github/workflows/telegram_alerts.yml').read_text()
    workflow=yaml.safe_load(text)
    job=workflow['jobs']['morning-digest']
    assert 'default_branch' in job['if']
    names=[s.get('name') for s in job['steps']]
    assert names.index('Persist reservation before sending') < names.index('Send daily digest')
    assert names.index('Persist predictions before sending') < names.index('Send daily digest')
    assert 'secrets.ODDS_API_KEY' in text
    assert 'ODDS_API_KEY' not in str(workflow['jobs'].get('tests',''))
    assert Path('.github/workflows/ci.yml').exists()


def test_all_streamlit_sections_render_without_external_calls(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('INTELLIGENCE_DB',str(tmp_path/'ui.sqlite3'))
    monkeypatch.setenv('ODDS_API_KEY','test-fixture-only')
    with patch('intelligence.pipeline.run_analysis',return_value=Analysis()):
        app=AppTest.from_file(Path('app.py').resolve(),default_timeout=20).run()
        assert not app.exception
        for page in ['Best Opportunities','AI Parlay Builder','NBA Analytics','Soccer Analytics',
                     'MLB Analytics','Live Markets','AI Assistant','Performance Tracker','Settings']:
            navigate(app,page)
            assert not app.exception, page


def test_no_secret_ui_still_renders(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('INTELLIGENCE_DB',str(tmp_path/'ui-empty.sqlite3'))
    monkeypatch.setenv('ODDS_API_KEY','')
    app=AppTest.from_file(Path('app.py').resolve(),default_timeout=20).run()
    assert not app.exception
    assert any('No supported single' in info.value for info in app.info)
    navigate(app,'Settings')
    assert any('ODDS_API_KEY' in info.value for info in app.info)
