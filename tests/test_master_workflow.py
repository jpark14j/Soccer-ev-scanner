"""End-to-end software replay from synthetic provider fixtures, not live picks."""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
import pytest
from intelligence.domain import utcnow,parse_time
from intelligence.pipeline import Analysis,run_analysis,evaluate_quotes
from intelligence.storage import Store
from intelligence.forward_testing import lock_protocol,records
from intelligence.processing import record_shadow_forecasts
from intelligence.model_reliability import scorecards
from intelligence.research_top import select_top
from intelligence.quant_decision import decide
from test_readiness_ranking import enable,supported_quote
from test_forward_evaluation import save_final
from tests_helpers import event_payload
from ui_navigation import navigate


def research_slate(store,quote,monkeypatch):
    enable(monkeypatch);now=utcnow();lock_protocol(store,now-timedelta(seconds=20))
    epl,_=supported_quote(store,quote,'Premier League',now)
    de,_=supported_quote(store,quote,'Bundesliga',now)
    total=replace(epl,market='totals',point=2.5,selection='Over')
    a=evaluate_quotes(Analysis(quotes=[epl,total,de]),store,allow_results_fetch=False)
    favored=[]
    for q in a.quotes:
        if a.estimates[q.id].probability<=.5:q=replace(q,selection='No' if q.market=='btts' else 'Under')
        favored.append(q)
    return evaluate_quotes(Analysis(quotes=favored),store,allow_results_fetch=False)


def test_whole_workflow_records_ranks_reconciles_and_keeps_approval_blocked(store,quote,monkeypatch):
    a=research_slate(store,quote,monkeypatch)
    record_shadow_forecasts(a,store);before=records(store)
    assert len(before)==3 and record_shadow_forecasts(a,store)==0
    top=select_top(a,store)
    assert top['recommended'] and top['parlay'] and top['risk_rankings']['most_likely']
    assert all(top['format_candidates'][kind] for kind in ('Same-game parlay','Multi-game parlay','Mixed parlay'))
    assert top['parlay'].research.joint_probability is None and top['parlay'].research.combined_odds is None
    assert decide(a)['best'] is None and not any(r['payload']['betting_approved'] for r in before)
    later=max(parse_time(q.commence_time) for q in a.quotes)+timedelta(days=1)
    for league in ('Premier League','Bundesliga'):
        q=next(q for q in a.quotes if q.league==league and q.market=='btts')
        # Force an explicit test miss and hit; these are simulated software data.
        score=0 if (q.selection=='Yes')==(league=='Premier League') else 1
        save_final(store,q,score,score,later)
    from intelligence.forward_testing import reconcile
    assert reconcile(store,later)['labeled']==3
    after=records(store);assert [r['payload'] for r in after]==[r['payload'] for r in before]
    assert {'win','loss'}<={r['label']['outcome'] for r in after}
    report=scorecards(store,later)
    assert report['recorded']==report['labeled']==3 and all(c['state']=='Under forward evaluation' for c in report['groups'])
    assert all(not c['betting_opportunity_approved'] and c['review_blockers'] for c in report['groups'])
    from intelligence.llm import PaidAnalyst
    from intelligence.analyst_config import AnalystConfig
    reply=PaidAnalyst(store,AnalystConfig()).respond('How is forward performance measured?',Analysis(),now=later)
    assert '3 first pregame' in reply.content and not reply.paid_attempted and reply.mode=='Local · rule-based'


def test_saved_only_analysis_cannot_construct_provider_or_spend_even_on_first_load(store,quote,monkeypatch):
    now=utcnow();q=replace(quote,source_updated_at=now.isoformat(),received_at=now.isoformat(),commence_time=(now+timedelta(days=1)).isoformat())
    payload=event_payload(q);payload['data']=[payload['data']];store.cache('last-success-NBA',payload,now)
    with patch('intelligence.pipeline.OddsAPI',side_effect=AssertionError('No provider construction')),patch('intelligence.current_results.requests.Session.get',side_effect=AssertionError('No results request')):
        a=run_analysis('synthetic-only',['NBA'],store=store,autonomous=True,cached_only=True)
    assert a.quotes==[q] and a.slate['cached_only'] and a.slate['network_requests']==0
    with store.connect() as db:assert db.execute('SELECT count(*) FROM budget').fetchone()[0]==0


def test_actual_app_pages_and_filters_use_saved_data_without_provider_calls(tmp_path,quote,monkeypatch):
    from streamlit.testing.v1 import AppTest
    path=tmp_path/'preview.sqlite3';store=Store(path)
    monkeypatch.setenv('INTELLIGENCE_DB',str(path));monkeypatch.setenv('PREDICTION_LEDGER_DIR',str(tmp_path/'empty-ledger'))
    monkeypatch.setenv('ODDS_API_KEY','synthetic-only');monkeypatch.setenv('PAID_ANALYST_APPROVED','0')
    a=research_slate(store,quote,monkeypatch)
    # Saved raw provider fixtures, never a mocked top-pick result.
    for q in a.quotes:
        from intelligence.providers import LEAGUES
        r=event_payload(q,point=q.point);r['data']['sport_key']=LEAGUES[q.league][1];r['data']=[r['data']]
        store.cache('event-snapshot-'+q.league+'-'+q.event_id+'-'+q.market,r)
    with patch('intelligence.pipeline.OddsAPI',side_effect=AssertionError('No provider on render')),patch('intelligence.providers.OddsAPI._get',side_effect=AssertionError('No odds requests')),patch('openai.OpenAI',side_effect=AssertionError('No paid AI')):
        app=AppTest.from_file(Path('app.py').resolve(),default_timeout=40).run()
        assert not app.exception
        competitions=next(m for m in app.sidebar.multiselect if m.label=='Competitions')
        competitions.set_value(['Premier League','Bundesliga']).run()
        assert not app.exception and app.session_state['_research_snapshot']['analysis'].slate['cached_only']
        assert any(s.value=='Best Risk-Adjusted Research Opportunity' for s in app.subheader)
        assert any(s.value=='Model Reliability' for s in app.subheader)
        for page in ('Best Picks & Parlays','Performance Tracker','Research Operations','AI Assistant','AI Dashboard'):
            navigate(app,page);assert not app.exception,page
        next(b for b in app.button if b.key=='cached_research_recheck').click().run()
        assert not app.exception
    with store.connect() as db:assert db.execute('SELECT count(*) FROM budget').fetchone()[0]==0
    assert len(records(store))>=3


def test_same_path_store_generation_invalidates_session_and_function_cache(tmp_path,quote,monkeypatch):
    from streamlit.testing.v1 import AppTest
    path=tmp_path/'same-path.sqlite3';monkeypatch.setenv('INTELLIGENCE_DB',str(path))
    monkeypatch.setenv('ODDS_API_KEY','synthetic-only');monkeypatch.setenv('PREDICTION_LEDGER_DIR',str(tmp_path/'no-ledger'))
    with patch('intelligence.providers.OddsAPI._get',side_effect=AssertionError('No request')):
        app=AppTest.from_file(Path('app.py').resolve(),default_timeout=40).run();assert not app.exception
        old=app.session_state['_research_snapshot']['scope'][-1]
        # Simulate the generation-marker change from a recreated database,
        # preserving the path. New saved data must replace the empty snapshot.
        from uuid import uuid4
        new=Store(path);generation=uuid4().hex
        with new.connect() as db:db.execute('UPDATE store_identity SET instance=? WHERE id=1',(generation,))
        now=utcnow();q=replace(quote,event_id='new-generation',received_at=now.isoformat(),source_updated_at=now.isoformat(),commence_time=(now+timedelta(days=1)).isoformat())
        raw=event_payload(q);raw['data']=[raw['data']];new.cache('last-success-NBA',raw,now)
        app.run()
        assert not app.exception and app.session_state['_research_snapshot']['scope'][-1]!=old
        assert app.session_state['_research_snapshot']['analysis'].quotes==[q]


def test_expired_registry_approval_never_becomes_current_after_a_refresh(store):
    from test_lifecycle import synthetic_report
    from conftest import NOW
    from intelligence.lifecycle import register_artifact,change_champion,active_champion
    report=synthetic_report();identifier=register_artifact(store,report)
    evidence={'fresh_unseen_period_verified':True,'commercial_data_rights_verified':True,'operator_scope_verified':True,
        'forward_decisions':100,'paired_improvement_lower':.001,'verification_source':'https://example.test/independent-audit'}
    change_champion(store,identifier,evidence,'https://example.test/review',now=NOW)
    assert active_champion(store,'NBA','h2h',league='NBA',now=NOW)
    assert active_champion(store,'NBA','h2h',league='NBA',now=NOW+timedelta(days=11)) is None


def test_reviewed_suspension_invalidates_other_sessions_without_provider_calls(store,quote,monkeypatch):
    from test_lifecycle import synthetic_report
    from intelligence.lifecycle import register_artifact,change_champion
    from intelligence.cached_research import synchronize
    from intelligence.domain import digest
    from intelligence.model_reliability import status_for
    a=research_slate(store,quote,monkeypatch)
    snapshot={'analysis':a,'scope':(('Premier League','Bundesliga'),),'stored_at':'original session load'}
    synchronize(snapshot,store)
    q=next(q for q in a.quotes if q.league=='Premier League' and q.market=='btts');e=a.estimates[q.id]
    r=synthetic_report()|{'sport':q.sport,'league':q.league,'market':q.market,'model_version':e.model_version}
    r['evidence_id']=digest({k:v for k,v in r.items() if k!='evidence_id'})
    identifier=register_artifact(store,r)
    change_champion(store,identifier,{},'https://example.test/reviewed-suspension','suspend')
    with patch('intelligence.providers.OddsAPI._get',side_effect=AssertionError('No odds request')):
        updated=synchronize(snapshot,store)
    assert q.id not in updated.estimates and updated.advanced_details[q.id]['suspended']
    assert snapshot['stored_at']=='original session load'
    assert status_for(store,q.sport,q.league,q.market,e.model_version,evidence_id=e.evidence_id)['state']=='Suspended'
