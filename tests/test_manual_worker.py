"""Real local Postgres budget/fencing; providers and GitHub stay offline."""
from unittest.mock import patch
import pytest
from intelligence.background import bootstrap,run_manual
from intelligence.shared_state import StateError
from test_shared_control import postgres,remote,writer,reader,release

REQUEST='d'*32


def enable(monkeypatch,store):
    with store.connect() as db:identity=db.execute('SELECT instance FROM store_identity WHERE id=1').fetchone()[0]
    for k,v in {'RESEARCH_MANUAL_ENABLED':'1','RESEARCH_WORKER_ENABLED':'0','RESEARCH_SCHEDULE_ENABLED':'0',
        'PAID_ANALYST_APPROVED':'0','RESEARCH_DATA_RIGHTS_VERIFIED':'1','RESEARCH_BUDGET_SCOPE_REVIEWED':'1',
        'ODDS_API_KEY':'synthetic-never-real','RESEARCH_EXPECTED_STORE_INSTANCE':identity}.items():monkeypatch.setenv(k,v)


@pytest.mark.parametrize(('name','value'),[('RESEARCH_MANUAL_ENABLED','0'),('RESEARCH_SCHEDULE_ENABLED','1'),
    ('RESEARCH_WORKER_ENABLED','1'),('PAID_ANALYST_APPROVED','1'),('RESEARCH_DATA_RIGHTS_VERIFIED','0'),
    ('RESEARCH_BUDGET_SCOPE_REVIEWED','0'),('ODDS_API_KEY',''),('RESEARCH_EXPECTED_STORE_INSTANCE','')])
def test_manual_flags_credentials_and_permissions_block_before_remote(store,monkeypatch,name,value):
    enable(monkeypatch,store);monkeypatch.setenv(name,value)
    with patch('intelligence.background.Client',side_effect=AssertionError('No remote operation')):
        with pytest.raises(StateError):run_manual(REQUEST)


def test_remote_hold_cannot_be_released_by_manual_request(remote,store,monkeypatch):
    enable(monkeypatch,store);bootstrap(store.path,writer(remote))
    with pytest.raises(StateError,match='remote provider hold'):
        run_manual(REQUEST,client=writer(remote),cycle_fn=lambda *a:pytest.fail('No provider cycle'))
    head=reader(remote).read();assert head['held'] and head['generation']==1 and not head['budgets']


def test_exhausted_local_budget_cannot_start_a_manual_provider_cycle(remote,store,monkeypatch):
    from intelligence.domain import utcnow
    enable(monkeypatch,store);assert store.reserve(9,9,utcnow());bootstrap(store.path,writer(remote));release(remote)
    with pytest.raises(StateError,match='allowance unavailable'):
        run_manual(REQUEST,client=writer(remote),cycle_fn=lambda *a:pytest.fail('No provider cycle'))
    assert reader(remote).read()['generation']==1


def test_explicit_manual_cycle_commits_request_identity_and_duplicate_is_blocked(remote,store,monkeypatch):
    enable(monkeypatch,store);bootstrap(store.path,writer(remote));release(remote)
    def cycle(s,key,now):
        assert s.reserve(1,9,now) and s.observed_charge('1')
        s.cache('synthetic-manual-result',{'research':'synthetic test only'})
        return {'new_forward_labels':0},[]
    result=run_manual(REQUEST,client=writer(remote),cycle_fn=cycle)
    head=reader(remote).read()
    assert result['status']=='committed' and result['shared_readback_verified'] and head['generation']==2
    assert head['heartbeat']['summary']['manual_request_id']==REQUEST and not head['held']
    assert any(b['provider']=='odds' and b['used']==1 for b in head['budgets'])
    with pytest.raises(StateError,match='duplicate_run'):run_manual(REQUEST,client=writer(remote),cycle_fn=cycle)
    assert reader(remote).read()['generation']==2


def test_failed_commit_readback_is_not_reported_as_completed_research(remote,store,monkeypatch):
    enable(monkeypatch,store);bootstrap(store.path,writer(remote));release(remote)
    stale=reader(remote).read();client=writer(remote)
    with patch.object(client,'read',return_value=stale):
        with pytest.raises(StateError,match='readback was not verified'):
            run_manual(REQUEST,client=client,cycle_fn=lambda *a:({},[]))
    assert reader(remote).read()['generation']==2
