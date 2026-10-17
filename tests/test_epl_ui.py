from ui_navigation import navigate
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from intelligence.domain import utcnow
from intelligence.pipeline import Analysis,evaluate_quotes
from intelligence.epl_forecasts import forecast
from test_epl_predictions import soccer_quote,synthetic_artifact


def test_preview_pages_show_calibrated_research_and_source_gap(tmp_path,monkeypatch,quote):
    from streamlit.testing.v1 import AppTest
    from intelligence.storage import Store
    monkeypatch.setenv('ODDS_API_KEY','synthetic-ui-only')
    monkeypatch.setenv('PAID_ANALYST_APPROVED','0')
    monkeypatch.setenv('INTELLIGENCE_DB',str(tmp_path/'ui.sqlite3'))
    monkeypatch.setenv('PREDICTION_LEDGER_DIR',str(tmp_path/'empty-ledger'))
    now=utcnow();q=soccer_quote(quote,now)
    a=synthetic_artifact(q,now)
    with patch('intelligence.epl_forecasts.prepare',return_value=a):
        result=evaluate_quotes(Analysis(quotes=[q]),Store(tmp_path/'model.sqlite3'))
    with patch('intelligence.pipeline.run_analysis',return_value=result):
        app=AppTest.from_file(Path('app.py').resolve(),default_timeout=40).run()
        assert not app.exception
        navigate(app,'AI Dashboard')
        assert any('Model estimate' in t.value for t in app.markdown)
        assert any('epl-goal-strength-1' in t.value and 'prediction' in t.value for t in app.caption)
        assert any('No credible high-probability' in t.value for t in app.caption)
        assert all(not e.proto.expanded for e in app.expander if e.label=='Advanced Details / Raw Market Data')
        navigate(app,'Soccer Analytics')
        assert not app.exception and any(t.value=='Prediction evidence' for t in app.subheader)
        navigate(app,'Performance Tracker')
        assert not app.exception
        assert any('Premier League calibrated' in e.label for e in app.expander)
        navigate(app,'AI Assistant')
        assert not app.exception


def test_source_gap_cards_explain_missing_probability(tmp_path,monkeypatch,quote):
    from streamlit.testing.v1 import AppTest
    from intelligence.storage import Store
    q=soccer_quote(quote,utcnow())
    result=evaluate_quotes(Analysis(quotes=[q]),Store(tmp_path/'model.sqlite3'))
    assert q.id not in result.estimates
    monkeypatch.setenv('ODDS_API_KEY','synthetic-ui-only')
    monkeypatch.setenv('INTELLIGENCE_DB',str(tmp_path/'ui.sqlite3'))
    with patch('intelligence.pipeline.run_analysis',return_value=result):
        app=AppTest.from_file(Path('app.py').resolve(),default_timeout=40).run()
    assert not app.exception
    navigate(app,'AI Dashboard')
    assert any(s.value=='Data & Model Health' for s in app.subheader)
    assert any('past EPL fixtures have no source score' in t.value for t in app.markdown)
    navigate(app,'Best Picks & Parlays')
    assert any('Forecast blocked: Latest source result' in t.value for t in app.caption)
