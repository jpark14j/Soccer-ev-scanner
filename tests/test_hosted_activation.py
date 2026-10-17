"""Synthetic storage/fixture tests; no hosted credentials or provider requests."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
import json,yaml,pytest
from intelligence.domain import utcnow
from intelligence.storage import Store
from intelligence.background import bootstrap,collect_supported,LEAGUES
from intelligence.hosted_checks import verify_shared,storage_check
from intelligence.shared_state import snapshot,StateError
from test_shared_control import postgres,remote,reader,writer,CONFIG,READER,TOKEN
from tests_helpers import event_payload


def instance(store):
    with store.connect() as db:return db.execute('SELECT instance FROM store_identity WHERE id=1').fetchone()[0]


def test_fresh_reader_verification_uses_two_restores_without_writes(remote,store):
    store.cache('synthetic-proof',{'value':'retained'});bootstrap(store.path,writer(remote))
    before=reader(remote).read();remote.calls.clear()
    r=verify_shared(client=reader(remote),expected_instance=instance(store))
    assert r['generation']==1 and r['independent_restores']==2 and r['remote_writes']==0
    assert r['sports_provider_requests']==r['paid_ai_requests']==0
    assert len(remote.calls)==2 and all(x.endswith('research_state_read') for x in remote.calls)
    assert reader(remote).read()['snapshot']==before['snapshot']
    assert not r['preview_restart_verified'] and not r['recurring_operation_verified']


def test_storage_rehearsal_preserves_rows_budgets_and_hold_without_a_research_cycle(remote,store):
    with store.connect() as db:
        db.execute('INSERT INTO publications VALUES(?,?,?,?)',('synthetic-existing',utcnow().isoformat(),'synthetic test','{}'))
    bootstrap(store.path,writer(remote));before=reader(remote).read()
    with patch('intelligence.background.cycle',side_effect=AssertionError('Never run research in storage check')):
        r=storage_check(client=writer(remote),expected_instance=instance(store))
    after=reader(remote).read()
    assert r['generation']==2 and r['record_counts_preserved'] and r['provider_hold_preserved']
    assert r['record_counts']['publications']==1 and r['sports_provider_requests']==0
    assert after['held'] is before['held'] is True and after['budgets']==before['budgets']
    assert after['publication_receipts']==before['publication_receipts']
    assert after['heartbeat']['summary']['mode']=='storage-only verification'


def test_wrong_store_and_failed_asset_review_cannot_replace_the_head(remote,store):
    bootstrap(store.path,writer(remote));before=reader(remote).read()['snapshot']
    with pytest.raises(StateError,match='identity differs'):
        verify_shared(client=reader(remote),expected_instance='0'*32)
    with patch('intelligence.background.verify_assets',side_effect=StateError('Reviewed asset mismatch')):
        with pytest.raises(StateError,match='asset mismatch'):
            storage_check(client=writer(remote),expected_instance=instance(store))
    after=reader(remote).read();assert after['generation']==1 and after['held']
    assert after['snapshot']==before


def test_same_generation_cannot_return_changed_content(store):
    first=snapshot(store);store.cache('synthetic-change',{'changed':True});second=snapshot(store)
    envelopes=[{'generation':1,'held':True,'snapshot':body|{'generation':1}} for body in (first,second)]
    class Client:
        def read(self):return envelopes.pop(0)
    with pytest.raises(StateError,match='changed its checksum'):
        verify_shared(client=Client(),expected_instance=instance(store))


def test_research_cannot_use_a_different_store_even_with_enable_flags(remote,store,monkeypatch):
    from intelligence.background import run_background
    bootstrap(store.path,writer(remote))
    for name in ('RESEARCH_WORKER_ENABLED','RESEARCH_DATA_RIGHTS_VERIFIED','RESEARCH_BUDGET_SCOPE_REVIEWED'):
        monkeypatch.setenv(name,'1')
    monkeypatch.setenv('RESEARCH_EXPECTED_STORE_INSTANCE','0'*32)
    with pytest.raises(StateError,match='unexpected store'):
        run_background(client=writer(remote),cycle_fn=lambda *a:pytest.fail('Research cycle must stay blocked'))
    assert reader(remote).read()['generation']==1 and reader(remote).read()['held']


def test_storage_rehearsal_cannot_initialize_an_empty_authority(remote,store):
    with pytest.raises(StateError,match='bootstrap'):
        storage_check(client=writer(remote),expected_instance=instance(store))
    head=reader(remote).read();assert head['generation']==0 and head['snapshot'] is None and head['held']


def test_preview_can_run_fresh_read_check_with_reader_credentials_only(remote,store,tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    from ui_navigation import navigate
    bootstrap(store.path,writer(remote))
    for k,v in {'RESEARCH_SHARED_STATE_ENABLED':'1','RESEARCH_STATE_USE_REVIEWED':'1',
        'RESEARCH_STATE_URL':CONFIG.url,'RESEARCH_STATE_READER_KEY':READER,'RESEARCH_STATE_READ_TOKEN':TOKEN,
        'RESEARCH_STATE_SERVICE_KEY':'','RESEARCH_REPLICA_DIR':str(tmp_path/'replica'),
        'INTELLIGENCE_DB':str(tmp_path/'fallback.sqlite3'),'PAID_ANALYST_APPROVED':'0',
        'RESEARCH_WORKER_ENABLED':'0'}.items():monkeypatch.setenv(k,v)
    with patch('intelligence.shared_state.requests.Session',return_value=remote):
        app=AppTest.from_file(Path('app.py').resolve(),default_timeout=40).run()
        navigate(app,'Research Operations')
        next(b for b in app.button if b.key=='verify_fresh_shared_reads').click().run()
        assert not app.exception
        assert any('fresh shared-state reads verified' in x.value for x in app.json)
        assert any('Storage checkpoint available' in x.value for x in app.markdown)
    assert reader(remote).read()['generation']==1 and reader(remote).read()['held']


def test_cached_multisport_search_includes_future_dates_without_new_odds_requests(store,quote,monkeypatch):
    from intelligence.pipeline import run_analysis
    from intelligence.book_optimizer import scoped_quotes,best_by_game
    from intelligence.providers import LEAGUES as MAPPING
    now=utcnow();quotes=[]
    for league,sport,days in [('NBA','NBA',1),('Premier League','Soccer',3),('MLB','MLB',6),('Bundesliga','Soccer',9)]:
        q=replace(quote,league=league,sport=sport,event_id='synthetic-'+str(days),
            commence_time=(now+timedelta(days=days)).isoformat(),source_updated_at=now.isoformat(),received_at=now.isoformat())
        raw=event_payload(q);raw['data']['sport_key']=MAPPING[league][1];raw['data']=[raw['data']]
        store.cache('last-success-'+league+'-h2h',raw,now);quotes.append(q)
    # A discovered MLB fixture remains visible even if no market was retrieved.
    game={'id':'synthetic-without-price','sport_key':MAPPING['MLB'][1],'home_team':'Boston','away_team':'Toronto',
        'commence_time':(now+timedelta(days=5)).isoformat()}
    store.cache('background-discovery-MLB',{'data':[game],'received_at':now.isoformat()},now)
    with patch('intelligence.pipeline.evaluate_quotes',side_effect=lambda a,*x,**k:a),\
         patch('intelligence.cached_research.record_and_label',side_effect=lambda a,*x,**k:a):
        analysis=run_analysis('',LEAGUES,store=store,cached_only=True,window_hours=168)
    assert {q.event_id for q in scoped_quotes(analysis)}=={q.event_id for q in quotes[:3]}
    assert {e['event_id'] for e in analysis.slate['events']}=={q.event_id for q in quotes[:3]}|{game['id']}
    assert len(best_by_game(analysis))==4 and not analysis.estimates
    assert analysis.slate['network_requests']==0


def test_worker_discovers_all_three_sports_and_never_spends_over_nine(store):
    from intelligence.providers import LEAGUES as MAPPING,ProviderError
    now=utcnow()
    class Provider:
        def __init__(self):self.discovery=[];self.prices=[]
        def events(self,league):
            self.discovery.append(league)
            return {'received_at':now.isoformat(),'data':[{'id':'synthetic-'+str(i),'sport_key':MAPPING[league][1],
                'home_team':'Home','away_team':'Away','commence_time':(now+timedelta(days=days,minutes=i)).isoformat()}
                for i,days in enumerate([1,3,6,9]*4)]}
        def odds(self,league,markets):
            if not store.reserve(1,9,now):raise ProviderError('test cap')
            self.prices.append((league,markets));return {'data':[],'received_at':now.isoformat()}
        def event_odds(self,league,event,markets):return self.odds(league,markets)
    p=Provider();audit=collect_supported(store,'synthetic',now,p,window_hours=168)
    assert p.discovery==list(LEAGUES) and len(p.prices)==9
    assert ('NBA',('h2h',)) in p.prices and ('MLB',('h2h',)) in p.prices
    assert all(r['upcoming_events']==12 for r in audit if r['status']=='provider event discovery')
    with store.connect() as db:assert db.execute('SELECT used FROM budget WHERE day=?',(now.date().isoformat(),)).fetchone()[0]==9
    previous=list(p.discovery);collect_supported(store,'synthetic',now,p,window_hours=168)
    assert p.discovery==previous  # No needless discovery once allowance is gone.


def test_private_worker_template_is_pinned_and_defaults_to_no_activation():
    source=Path('deploy/private_worker.yml').read_text();w=yaml.safe_load(source)
    trigger=w.get('on',w.get(True));job=w['jobs']['research'];step=job['steps'][-1]
    assert trigger['workflow_dispatch']['inputs']['operation']['default']=='verify'
    assert w['permissions']=={'contents':'read'} and job['timeout-minutes']==12
    assert "RESEARCH_ACTIONS_FREE_TIER_REVIEWED == '1'" in job['if']
    assert "RESEARCH_SCHEDULE_ENABLED == '1'" in job['if']
    assert job['steps'][1]['with']['persist-credentials'] is False
    assert step['env']['PAID_ANALYST_APPROVED']=='0' and step['env']['ODDS_DAILY_CREDITS']=='9'
    assert "inputs.operation == 'research'" in step['env']['ODDS_API_KEY']
    assert 'held=false' not in source and 'TELEGRAM_BOT_TOKEN' not in source
