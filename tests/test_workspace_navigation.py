"""Synthetic UI/ledger observations verify usability and spend guards, not skill."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
import pytest
from intelligence.domain import utcnow
from intelligence.navigation import PAGES,TOOLS
from intelligence.pipeline import Analysis
from intelligence.storage import Store
from intelligence.research_state import (APPROVED,EXPERIMENTAL,PRICE_ONLY,BLOCKED,
    evidence_state,singles,model_health)
from intelligence.epl_forecasts import load_artifact,prepare,forecast
from intelligence.processing import record_shadow_forecasts
from test_epl_predictions import soccer_quote
from ui_navigation import navigate


@pytest.fixture
def workspace_app(tmp_path,monkeypatch,quote):
    from streamlit.testing.v1 import AppTest
    now=utcnow();q=replace(quote,source_updated_at=(now-timedelta(seconds=30)).isoformat(),
        received_at=(now-timedelta(seconds=10)).isoformat(),commence_time=(now+timedelta(days=1)).isoformat())
    path=tmp_path/'workspace.sqlite3'
    monkeypatch.setenv('INTELLIGENCE_DB',str(path));monkeypatch.setenv('ODDS_API_KEY','synthetic-ui-key-only')
    monkeypatch.setenv('ODDS_DAILY_CREDITS','9');monkeypatch.setenv('PAID_ANALYST_APPROVED','0')
    monkeypatch.setenv('PREDICTION_LEDGER_DIR',str(tmp_path/'empty-ledger'))
    store=Store(path);result=Analysis(quotes=[q],checked_at=now.isoformat())
    def scan(*args,**kwargs):
        assert store.reserve(1,9)
        return result
    with patch('intelligence.pipeline.run_analysis',side_effect=scan) as scans, \
         patch('openai.OpenAI',side_effect=AssertionError('No paid AI construction')):
        app=AppTest.from_file(Path('app.py').resolve(),default_timeout=40).run()
        assert not app.exception
        yield app,store,result,scans


def test_exactly_five_top_level_destinations_and_every_tool_accessible(workspace_app):
    app,_,_,_=workspace_app
    assert list(app.sidebar.radio[0].options)==[p.name for p in PAGES]==[
        'Home','Best Picks & Parlays','Upcoming Games','Performance Tracker','Settings']
    assert app.sidebar.radio[0].value=='Home'
    assert not app.dataframe
    navigate(app,'Settings & Research Tools')
    selector=next(s for s in app.selectbox if s.key=='research_tool')
    assert list(selector.options)==[t.name for t in TOOLS]
    for tool in TOOLS:
        navigate(app,tool.name)
        assert not app.exception,tool.name
    navigate(app,'Best Picks & Parlays')
    assert [t.label for t in app.tabs]==['Singles','Parlays']
    assert any(s.value=='Qualified-leg diagnostic builder' for s in app.subheader)
    assert any(e.label=='Sportsbook shortlist and whole-slate search' for e in app.expander)


def test_navigation_after_old_cache_cannot_silently_fetch_or_spend(workspace_app):
    import streamlit as st
    app,store,_,scans=workspace_app
    snapshot=app.session_state['_research_snapshot']
    old=(utcnow()-timedelta(days=2)).isoformat();snapshot['stored_at']=old
    app.session_state['_research_snapshot']=snapshot
    st.cache_data.clear()  # Simulate expiry independently of navigation.
    before=store.connect().execute('SELECT used FROM budget').fetchone()[0]
    for name in ['Best Picks & Parlays','Performance Tracker',*[t.name for t in TOOLS],'AI Dashboard']:
        navigate(app,name)
    assert scans.call_count==1
    with store.connect() as db:assert db.execute('SELECT used FROM budget').fetchone()[0]==before==1
    assert app.session_state['_research_snapshot']['stored_at']==old
    # A user-requested refresh is distinct from navigation and still uses the cap.
    next(b for b in app.button if b.label=='Refresh analysis').click().run()
    assert not app.exception and scans.call_count==2


def test_filtering_singles_does_not_call_provider_and_labels_price_only(workspace_app):
    app,_,_,scans=workspace_app;navigate(app,'Best Picks & Parlays')
    assert any('Price-only research' in c.value for c in app.caption)
    assert any('not a win forecast' in c.value for c in app.caption)
    next(m for m in app.multiselect if m.key=='picks_evidence').set_value([APPROVED]).run()
    assert not app.exception and scans.call_count==1
    assert any('No selections match' in i.value for i in app.info)
    next(m for m in app.multiselect if m.key=='research_evidence').set_value([EXPERIMENTAL]).run()
    assert not app.exception and scans.call_count==1


def test_categories_separate_unapproved_models_prices_stale_and_rejected_inputs(quote,estimate):
    from conftest import NOW
    analysis=Analysis(quotes=[quote])
    assert evidence_state(quote,analysis,NOW)[0]==PRICE_ONLY
    analysis.estimates[quote.id]=replace(estimate,validated=False)
    assert evidence_state(quote,analysis,NOW)[0]==EXPERIMENTAL
    analysis.estimates[quote.id]=estimate
    assert evidence_state(quote,analysis,NOW)[0]==APPROVED  # Synthetic validated fixture only.
    stale=replace(quote,source_updated_at=(NOW-timedelta(minutes=10)).isoformat())
    assert evidence_state(stale,analysis,NOW)[0]==BLOCKED
    q=soccer_quote(quote,NOW)
    analysis=Analysis(quotes=[q],research=[{'quote_id':q.id,'model':'epl-goal-strength-1','blockers':['Missing past fixture score']}])
    assert evidence_state(q,analysis,NOW)[0]==BLOCKED
    assert not singles(analysis,statuses=[APPROVED,EXPERIMENTAL],now=NOW)


def test_equivalent_price_comparison_does_not_choose_stale_better_odds(quote):
    from conftest import NOW
    stale=replace(quote,odds=5.,bookmaker='pointsbetca',bookmaker_name='PointsBet',
        source_updated_at=(NOW-timedelta(minutes=10)).isoformat())
    rows=singles(Analysis(quotes=[stale,quote]),now=NOW)
    assert len(rows)==1 and rows[0][1].quote==quote and rows[0][0]==PRICE_ONLY


def test_data_health_is_read_only_and_honest_about_missing_results(store):
    before=load_artifact()
    with patch('intelligence.epl_forecasts.refresh',side_effect=AssertionError('Health views never fetch')):
        health=model_health(Analysis(),store)
    assert health['unresolved_scores']==15 and health['source_latest']=='2026-09-20'
    assert health['model_status']=='research-only'
    assert health['source_check_kind']=='existing analysis / bundled snapshot'
    assert any('21-day' in s for s in health['reasons'])
    assert any('No current Ontario price' in s for s in health['reasons'])
    assert load_artifact()==before


def test_cached_conflicting_results_are_visible_and_cannot_activate_forecasts(store,quote):
    now=utcnow();a=load_artifact()
    store.cache('epl-public-v1-'+a['artifact_sha256'],{'ok':False,'checked_at':now.isoformat(),
        'reason':'Public history removed or revised an existing result; rebuild/review required'},now)
    prepared=prepare(store,now,allow_refresh=True)
    assert 'problem' in prepared
    q=soccer_quote(quote,now)
    e,details=forecast(q,prepared,now)
    assert e is None and 'revised' in details['blockers'][0]
    health=model_health(Analysis(focused_model=prepared),store,now)
    assert 'revised' in health['source_problem'] and any('revised' in s for s in health['reasons'])
    assert load_artifact()==a


def test_missing_results_stay_blocked_even_with_fresh_market(store,quote):
    now=utcnow();q=soccer_quote(quote,now);a=prepare(store,now,allow_refresh=False)
    e,d=forecast(q,a,now)
    analysis=Analysis(quotes=[q],focused_model=a,research=[d],advanced_details={q.id:d})
    assert not e and evidence_state(q,analysis,now)[0]==BLOCKED
    assert not singles(analysis,statuses=[APPROVED,EXPERIMENTAL],now=now)
    assert not analysis.opportunities


def test_performance_counts_paper_hits_and_misses_separately_from_backtests(tmp_path,monkeypatch,quote,estimate):
    from streamlit.testing.v1 import AppTest
    from conftest import NOW
    store=Store(tmp_path/'performance.sqlite3')
    second=replace(quote,event_id='second-paper-fixture')
    analysis=Analysis(quotes=[quote,second],estimates={q.id:replace(estimate,validated=False) for q in (quote,second)})
    assert record_shadow_forecasts(analysis,store,NOW)==2
    with store.connect() as db:
        rows=db.execute('SELECT id FROM shadow_forecasts ORDER BY id').fetchall()
        for r,result in zip(rows,('hit','miss')):
            db.execute('INSERT INTO shadow_outcomes VALUES(?,?,?,?)',(r['id'],(NOW+timedelta(days=2)).isoformat(),result,'Synthetic test source'))
    monkeypatch.setenv('INTELLIGENCE_DB',store.path);monkeypatch.setenv('ODDS_API_KEY','')
    monkeypatch.setenv('PREDICTION_LEDGER_DIR',str(tmp_path/'empty-ledger'))
    app=AppTest.from_file(Path('app.py').resolve()).run();navigate(app,'Performance Tracker')
    assert [t.label for t in app.tabs]==['Prospective paper research','Published hypothetical records','Held-out model evaluations']
    values={m.label:m.value for m in app.metric}
    assert values['Paper forecasts recorded']=='2' and values['Paper forecasts with result labels']=='2'
    assert values['Paper target hits']==values['Paper target misses']=='1'
    assert values['Published predictions']=='0'
    assert load_artifact()['coverage']['test_eligible']==368


def test_nested_diagnostics_redact_credentials_without_changing_numbers():
    from intelligence.chat_privacy import redact_data
    original={'nested':[{'risk':'fixture-private-key-only','probability':.61}],'Bearer fake-token':'token'}
    safe=redact_data(original,('fixture-private-key-only',))
    assert 'fixture-private-key-only' not in repr(safe) and 'fake-token' not in repr(safe)
    assert safe['nested'][0]['probability']==.61
