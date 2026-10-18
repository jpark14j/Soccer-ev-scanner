"""Synthetic UI evidence only. These tests never obtain real provider prices."""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
import pytest
from conftest import NOW
from intelligence.domain import utcnow
from intelligence.pipeline import Analysis
from intelligence.quota import quota_details
from intelligence.consumer_ui import data_status,saved_games,research_view,friendly_time
from intelligence.navigation import PAGES
from test_readiness_ranking import research_analysis
from test_parlay_intelligence import opposed


def test_replica_zero_usable_is_not_local_exhaustion_and_remote_hold_is_separate(store):
    store.read_replica=True
    store.shared_status={'envelope':{'held':True}}
    q=quota_details(store,9,NOW)
    assert q['used']==0 and q['local_remaining']==9 and q['remaining']==0
    assert not q['local_exhausted'] and q['availability_reason']=='read_only_replica'
    assert q['remote_provider_hold'] and q['external_account_remaining'] is None
    with store.connect() as db:assert db.execute('SELECT count(*) FROM budget').fetchone()[0]==0


def test_hold_and_exhaustion_still_block_requests(store):
    assert store.reserve(9,9,NOW)
    q=quota_details(store,9,NOW)
    assert q['local_exhausted'] and q['remaining']==0 and q['availability_reason']=='local_cap'
    from intelligence.request_guard import hold
    with store.connect() as db:hold(db,'Synthetic hold',NOW)
    q=quota_details(store,9,NOW)
    assert q['recovery_hold'] and q['remaining']==0


def test_read_only_banner_does_not_describe_unused_budget_as_exhausted(store):
    from streamlit.testing.v1 import AppTest
    script=f'''from intelligence.storage import Store
from intelligence.market_ui import quota_banner
from intelligence.data_settings import load_settings
s=Store({store.path!r},read_replica=True)
s.shared_status={{'envelope':{{'held':True}}}}
quota_banner(s,load_settings())
'''
    app=AppTest.from_string(script).run()
    assert not app.exception
    assert any('0/9; 9 below the local cap' in c.value for c in app.caption)
    assert any('read-only' in x.value and 'not evidence of an exhausted' in x.value for x in app.info)
    assert any('remote provider budget hold is active' in x.value.lower() for x in app.info)
    assert not any('local odds budget is exhausted' in x.value.lower() for x in app.info)


def test_upcoming_saved_dates_and_all_sports_without_prices_or_requests(quote):
    qs=[replace(quote,event_id=sport,league=league,sport=sport,commence_time=(NOW+timedelta(days=days)).isoformat())
        for sport,league,days in [('NBA','NBA',1),('Soccer','Premier League',3),('MLB','MLB',6)]]
    a=Analysis(quotes=qs,slate={'window_end':(NOW+timedelta(days=7)).isoformat(),'events':[
        {'sport':'MLB','league':'MLB','event_id':'unpriced','event':'Synthetic saved fixture','start':(NOW+timedelta(days=5)).isoformat()},
        {'sport':'NBA','league':'NBA','event_id':'outside','event':'Outside','start':(NOW+timedelta(days=8)).isoformat()}]})
    games=saved_games(a,168,NOW)
    assert [g['event_id'] for g in games]==['NBA','Soccer','unpriced','MLB']
    assert 'EDT' in friendly_time(qs[0].commence_time)


def test_saved_stale_price_cannot_be_a_supported_pick_or_current_status(store,quote):
    a=research_analysis(quote,[(.7,.6,.8,1.8,100)],NOW)
    a.quotes=[replace(a.quotes[0],source_updated_at=(NOW-timedelta(minutes=10)).isoformat())]
    top,rows=research_view(a,store,{quote.bookmaker},['NBA'],NOW)
    assert not rows and top['parlay'] is None
    assert data_status(a,{quote.bookmaker},NOW)[0]=='Waiting for fresh odds'


def test_research_view_reuses_favored_sides_and_never_approves_joint_probability(store,quote):
    a=opposed(research_analysis(quote,[(.7,.6,.8,1.8,100)]*3,NOW))
    top,rows=research_view(a,store,{quote.bookmaker},['NBA'],NOW)
    assert len(rows)==3 and all(leg.estimate.probability==.7 for _,leg in rows)
    assert top['parlay'] and top['parlay'].research.joint_probability is None
    assert top['parlay'].research.parlay_ev is None and not top['parlay'].research.executable


@pytest.fixture
def consumer_app(tmp_path,monkeypatch,quote):
    from streamlit.testing.v1 import AppTest
    now=utcnow();a=opposed(research_analysis(quote,[(.7,.6,.8,1.8,100)]*3,now))
    monkeypatch.setenv('INTELLIGENCE_DB',str(tmp_path/'consumer.sqlite3'))
    monkeypatch.setenv('ODDS_API_KEY','synthetic-private-key-only')
    monkeypatch.setenv('OPENAI_API_KEY','sk-test-NEVER-A-REAL-CONSUMER-KEY')
    monkeypatch.setenv('PAID_ANALYST_APPROVED','0')
    monkeypatch.setenv('PREDICTION_LEDGER_DIR',str(tmp_path/'empty-ledger'))
    a.errors=['Synthetic technical problem: database worker failure']
    with patch('intelligence.pipeline.run_analysis',return_value=a) as scans,patch('openai.OpenAI',side_effect=AssertionError('No paid AI')):
        app=AppTest.from_file(Path('app.py').resolve(),default_timeout=40).run()
        assert not app.exception
        yield app,scans


def test_everyday_pages_hide_admin_diagnostics_and_never_scan_on_navigation(consumer_app):
    app,scans=consumer_app
    assert app.sidebar.radio[0].options==[p.name for p in PAGES]
    assert app.sidebar.radio[0].value=='Home'
    assert {'Best Single Pick','Best Parlay','Upcoming Games','Other Opportunities'}<={s.value for s in app.subheader}
    for name in ('Home','Best Picks & Parlays','Upcoming Games','Performance Tracker'):
        app.sidebar.radio[0].set_value(name).run()
        assert not app.exception and not app.json and not app.dataframe
        text=' '.join(str(x.value) for group in (app.text,app.caption,app.info,app.markdown) for x in group)
        assert all(word not in text for word in ('Local odds reservations','Supabase','database worker failure','synthetic-private-key-only','sk-test-NEVER-A-REAL-CONSUMER-KEY'))
        assert not any(b.label=='Refresh analysis' for b in app.button)
    assert scans.call_count==1


def test_simple_parlay_is_theoretical_and_leg_filter_works(consumer_app):
    app,scans=consumer_app;app.sidebar.radio[0].set_value('Best Picks & Parlays').run()
    assert any('theoretical only' in x.value for x in app.markdown)
    assert any('combined sportsbook ticket has not been verified' in x.value.lower() for x in app.warning)
    assert any('Combined win probability and parlay value are unavailable' in x.value for x in app.caption)
    next(m for m in app.multiselect if m.key=='simple_parlay_sizes').set_value([3]).run()
    assert not app.exception and any('3-leg experimental' in x.value for x in app.markdown)
    next(m for m in app.multiselect if m.key=='simple_picks_sports').set_value(['MLB']).run()
    assert not app.exception and any('No supported selections' in x.value for x in app.info)
    assert scans.call_count==1


def test_home_shows_supported_two_and_three_leg_candidates_without_opposing_price_picks(consumer_app):
    app,_=consumer_app
    assert any('2-leg experimental parlay' in x.value for x in app.markdown)
    assert any('3-leg experimental parlay' in x.value for x in app.markdown)
    assert not any(e.label=='Experimental market research · model evidence incomplete' for e in app.expander)


def test_assistant_remains_free_and_admin_tools_stay_separate(consumer_app):
    app,scans=consumer_app;app.sidebar.radio[0].set_value('Settings').run()
    exp=next(e for e in app.expander if e.label=='Admin / Developer Tools')
    assert not exp.proto.expanded
    next(t for t in app.toggle if t.key=='consumer_assistant_open').set_value(True).run()
    app.chat_input[0].set_value('What research is available?').run()
    assert not app.exception and len(app.chat_message)==2 and scans.call_count==1
