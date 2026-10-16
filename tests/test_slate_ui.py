from ui_navigation import navigate
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from conftest import NOW
from intelligence.domain import utcnow
from intelligence.pipeline import Analysis
from intelligence.llm import PaidAnalyst
from intelligence.analyst_config import AnalystConfig


def test_default_dashboard_has_cards_and_collapsed_raw_odds(tmp_path,monkeypatch,quote):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('ODDS_API_KEY','synthetic-ui-only');monkeypatch.setenv('PAID_ANALYST_APPROVED','0')
    monkeypatch.setenv('INTELLIGENCE_DB',str(tmp_path/'ui.sqlite3'))
    now=utcnow();q=replace(quote,source_updated_at=(now-timedelta(seconds=30)).isoformat(),
        received_at=(now-timedelta(seconds=10)).isoformat(),commence_time=(now+timedelta(days=1)).isoformat())
    q2=replace(q,event_id='second-card',home='Other Home',away='Other Away',event='Other Home vs Other Away',selection='Other Home')
    with patch('intelligence.pipeline.run_analysis',return_value=Analysis(quotes=[q,q2])):
        app=AppTest.from_file(Path('app.py').resolve(),default_timeout=40).run()
        assert not app.exception
        assert any(m.label=='Games discovered / observed' for m in app.metric)
        assert any('No qualifying parlay opportunities' in m.value for m in app.info)
        raw=[e for e in app.expander if e.label=='Advanced Details / Raw Market Data']
        assert not raw and not app.dataframe  # Home uses concise cards; no raw table.
        navigate(app,'Best Selections by Game')
        raw=[e for e in app.expander if e.label=='Advanced Details / Raw Market Data']
        assert raw and all(not e.proto.expanded for e in raw)
        navigate(app,'Research Operations')
        assert not app.exception and any('not an always-running' in m.value for m in app.info)


def test_assistant_knows_games_and_the_requested_sportsbook(store,quote):
    second=replace(quote,event_id='other',event='Other game',home='Other Home',away='Other Away',selection='Other Home')
    otherbook=[replace(q,bookmaker='pointsbetca',bookmaker_name='PointsBet') for q in (quote,second)]
    analysis=Analysis(quotes=[quote,second,*otherbook])
    analyst=PaidAnalyst(store,AnalystConfig())
    reply=analyst.respond('Which games did you analyze?',analysis,now=NOW)
    assert 'Home vs Away' in reply.content and 'observations evaluated' in reply.content
    reply=analyst.respond('What is the best-supported parlay research candidate for BetMGM?',analysis,now=NOW)
    assert 'BetMGM' in reply.content and 'No Qualifying Parlay' in reply.content
    assert not reply.paid_attempted and 'not an executable quote' in reply.content


def test_performance_cards_show_real_ledger_losses_with_their_sample(tmp_path,monkeypatch,opportunity):
    from streamlit.testing.v1 import AppTest
    from intelligence.storage import Store
    db=tmp_path/'performance.sqlite3';store=Store(db)
    id=store.publish(opportunity,now=NOW)
    store.settle(id,'loss','Synthetic software-test final','https://example.test/synthetic-result',now=NOW+timedelta(days=2))
    monkeypatch.setenv('INTELLIGENCE_DB',str(db));monkeypatch.setenv('ODDS_API_KEY','synthetic-ui-only')
    monkeypatch.setenv('PREDICTION_LEDGER_DIR',str(tmp_path/'empty-ledger'))
    with patch('intelligence.pipeline.run_analysis',return_value=Analysis()):
        app=AppTest.from_file(Path('app.py').resolve()).run()
        navigate(app,'Performance Tracker')
    assert not app.exception
    assert next(m for m in app.metric if m.label=='Losses').value=='1'
    assert any('Decisive sample: 1' in c.value for c in app.caption)
