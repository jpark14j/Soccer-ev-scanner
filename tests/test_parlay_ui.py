from ui_navigation import navigate
"""Streamlit integration using synthetic quotes only; no external requests."""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
import pytest
from intelligence.domain import utcnow
from intelligence.pipeline import Analysis


@pytest.fixture
def research_app(tmp_path,monkeypatch,quote):
    from streamlit.testing.v1 import AppTest
    now=utcnow()
    monkeypatch.setenv('INTELLIGENCE_DB',str(tmp_path/'ui.sqlite3'))
    monkeypatch.setenv('ODDS_API_KEY','fixture-odds-key')
    monkeypatch.setenv('PAID_ANALYST_APPROVED','0')
    monkeypatch.setenv('COLLECT_RESULTS','0')
    qs=[]
    for n,sport in enumerate(('NBA','Soccer','MLB')):
        qs.append(replace(quote,sport=sport,league=sport if sport!='Soccer' else 'Premier League',
            event_id=f'ui-event-{n}',event=f'Home {n} vs Away {n}',home=f'Home {n}',away=f'Away {n}',selection=f'Home {n}',
            commence_time=(now+timedelta(days=1)).isoformat(),source_updated_at=(now-timedelta(seconds=30)).isoformat(),
            received_at=(now-timedelta(seconds=15)).isoformat()))
    analysis=Analysis(quotes=qs,checked_at=now.isoformat())
    with patch('intelligence.pipeline.run_analysis',return_value=analysis):
        app=AppTest.from_file(Path('app.py').resolve(),default_timeout=30).run()
        navigate(app,'Daily Parlay Research')
        assert not app.exception
        yield app,analysis


def control(app,label):
    return next(m for m in app.multiselect if m.label==label)


def parlay_tables(app):
    return [d.value for d in app.dataframe if 'Individual decimal odds' in d.value]


def test_daily_research_displays_real_fixture_leg_fields_and_theoretical_prices(research_app):
    app,_=research_app
    tables=parlay_tables(app)
    assert len(tables)==3 and all('Individual decimal odds' in table for table in tables)
    assert any('Theoretical all-win odds product' in m.value for m in app.markdown)
    assert any('not calculated' in m.value for m in app.markdown)
    assert all('Source timestamp' in table and 'Model estimate' in table for table in tables)


def test_ui_filters_sports_legs_books_and_risk_without_network(research_app):
    app,_=research_app
    control(app,'Number of legs').set_value([3]).run()
    assert not app.exception and len(parlay_tables(app))==1 and len(parlay_tables(app)[0])==3
    control(app,'Research sports').set_value(['NBA']).run()
    assert not app.exception and not parlay_tables(app)
    control(app,'Research sports').set_value(['NBA','Soccer','MLB']).run()
    control(app,'Risk category · price proxy').set_value(['Lower-variance']).run()
    assert not app.exception and not parlay_tables(app)
    control(app,'Research sportsbooks').set_value([]).run()
    assert not app.exception and not parlay_tables(app)


def test_existing_parlay_page_and_assistant_still_work(research_app):
    app,_=research_app
    navigate(app,'AI Parlay Builder')
    assert not app.exception and len(parlay_tables(app))==3
    navigate(app,'AI Assistant')
    app.chat_input[0].set_value('What about parlay research?').run()
    assert not app.exception
    messages=app.session_state['_analyst_conversation_v2']['messages']
    assert 'Daily Parlay Research' in messages[-1]['content']
    assert messages[-1]['mode']=='Local · rule-based'


def test_research_page_expires_stale_quotes_without_relabeling_current(research_app):
    app,analysis=research_app
    later=utcnow()+timedelta(minutes=6)
    with patch('intelligence.parlay_research.utcnow',return_value=later):
        app.run()
    assert not app.exception and not parlay_tables(app)
    assert any('No current parlay research candidates' in i.value for i in app.info)


def test_explicit_refresh_updates_shared_snapshot_without_repeating_calls(research_app):
    app,analysis=research_app
    control(app,'Research sports').set_value(['NBA']).run()
    with patch('intelligence.research_refresh.refresh_research',return_value=analysis) as refresh:
        next(b for b in app.button if b.key=='research_refresh').click().run()
        assert not app.exception and refresh.call_count==1
        assert refresh.call_args.args[2]==['NBA']
        assert app.session_state['_research_snapshot']['analysis'].quotes==analysis.quotes
        navigate(app,'MLB Analytics')
        assert not app.exception and refresh.call_count==1
