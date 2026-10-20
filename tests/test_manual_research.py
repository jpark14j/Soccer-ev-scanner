"""Synthetic manual requests. No real GitHub dispatch or provider HTTP occurs."""
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
import base64,json
import pytest,requests,yaml
from conftest import NOW
from intelligence.manual_research import (Config,DispatchClient,ManualError,IDENTITY,configuration,
    unlock,authorized,preflight,request_research,poll)

CODE='ab'*32
TOKEN='github_pat_SYNTHETIC_MANUAL_TEST_NOT_REAL_1234567890'
COMMIT='c'*40
CONFIG=Config(True,TOKEN,sha256(CODE.encode()).hexdigest(),COMMIT)


@pytest.fixture
def replica(store):
    store.read_replica=True
    store.shared_status={'manifest':{'store_instance':IDENTITY},'verified_at':NOW.isoformat(),
        'envelope':{'generation':2,'held':False,'heartbeat':{}}}
    return store


def owner():
    state={};assert unlock(state,CODE,CONFIG,NOW);return state


class Response:
    def __init__(self,data=None,status=200):self.status_code=status;self.raw=json.dumps(data).encode();self.closed=False
    def iter_content(self,n):
        for i in range(0,len(self.raw),n):yield self.raw[i:i+n]
    def close(self):self.closed=True


class GitHub:
    def __init__(self):self.calls=[];self.private=True;self.pin=COMMIT;self.timeout=False;self.runs=[]
    def request(self,method,url,**kwargs):
        self.calls.append((method,url,kwargs))
        assert url.startswith('https://api.github.com/repos/jpark14j/sports-ai-private-recovery')
        assert kwargs['allow_redirects'] is False and kwargs['stream'] is True
        assert kwargs['headers']['Authorization']=='Bearer '+TOKEN
        if method=='POST':
            if self.timeout:raise requests.Timeout('Do not print '+TOKEN)
            return Response(status=204)
        if '/contents/' in url:
            return Response({'encoding':'base64','content':base64.b64encode(('RESEARCH_APP_COMMIT: '+self.pin+'\n').encode()).decode()})
        if '/runs?' in url:return Response({'workflow_runs':self.runs})
        return Response({'private':self.private})


def test_default_disabled_and_unauthorized_cannot_construct_transport(replica,monkeypatch):
    monkeypatch.delenv('RESEARCH_MANUAL_ENABLED',raising=False)
    assert configuration(lambda _: '').enabled is False
    with patch('intelligence.manual_research.requests.Session',side_effect=AssertionError('No network')):
        for c,state in ((Config(),{}),(CONFIG,{})):
            with pytest.raises(ManualError):request_research(c,state,replica,NOW)
            assert 'pending' not in state


def test_owner_authentication_requires_high_entropy_code_expires_and_rotates():
    state={}
    assert not unlock(state,'password',CONFIG,NOW)
    assert not unlock(state,'a'*64,CONFIG,NOW)
    assert unlock(state,CODE,CONFIG,NOW) and authorized(state,CONFIG,NOW)
    assert not authorized(state,CONFIG,NOW+timedelta(minutes=11))
    assert not authorized(state,replace(CONFIG,github_token=TOKEN+'different'),NOW)
    assert all(x not in repr(CONFIG) for x in (TOKEN,CONFIG.owner_hash))
    assert all(x not in json.dumps(state) for x in (CODE,TOKEN))


@pytest.mark.parametrize('problem',['hold','unknown_hold','stale_sync','wrong_identity','local_mode','cap','recovery'])
def test_all_budget_storage_and_hold_gates_block_before_github(replica,problem):
    from intelligence.request_guard import hold
    if problem=='hold':replica.shared_status['envelope']['held']=True
    if problem=='unknown_hold':replica.shared_status['envelope'].pop('held')
    if problem=='stale_sync':replica.shared_status['verified_at']=(NOW-timedelta(minutes=6)).isoformat()
    if problem=='wrong_identity':replica.shared_status['manifest']['store_instance']='0'*32
    if problem=='local_mode':replica.read_replica=False
    if problem=='cap':
        with replica.connect() as db:db.execute('INSERT INTO budget VALUES(?,9)',(NOW.date().isoformat(),))
    if problem=='recovery':
        with replica.connect() as db:hold(db,'Synthetic test hold',NOW)
    state=owner();session=GitHub()
    with pytest.raises(ManualError):request_research(CONFIG,state,replica,NOW,DispatchClient(CONFIG,session))
    assert not session.calls and 'pending' not in state


def test_authenticated_request_dispatches_only_the_reviewed_private_workflow(replica):
    state=owner();session=GitHub()
    rid=request_research(CONFIG,state,replica,NOW,DispatchClient(CONFIG,session))
    assert len(rid)==32 and state['pending']['phase']=='queued'
    assert [x[0] for x in session.calls]==['GET','GET','POST']
    payload=session.calls[-1][2]['json']
    assert payload=={'ref':'main','inputs':{'operation':'manual-research','request_id':rid,'expected_app_commit':COMMIT}}
    assert all(x not in json.dumps(state) for x in (TOKEN,CODE,CONFIG.owner_hash))
    with replica.connect() as db:assert db.execute('SELECT count(*) FROM budget').fetchone()[0]==0
    with pytest.raises(ManualError,match='already awaiting'):request_research(CONFIG,state,replica,NOW,DispatchClient(CONFIG,session))
    assert len(session.calls)==3


@pytest.mark.parametrize('failure',['public','pin','schedule'])
def test_repo_privacy_revision_and_manual_only_checks_prevent_dispatch(replica,failure):
    state=owner();session=GitHub()
    if failure=='public':session.private=False
    if failure=='pin':session.pin='d'*40
    if failure=='schedule':session.pin=COMMIT+'\n  schedule:\n'
    with pytest.raises(ManualError):request_research(CONFIG,state,replica,NOW,DispatchClient(CONFIG,session))
    assert not any(method=='POST' for method,_,_ in session.calls)


def test_ambiguous_delivery_is_not_retried_or_reported_as_success(replica):
    state=owner();session=GitHub();session.timeout=True
    with pytest.raises(ManualError) as e:request_research(CONFIG,state,replica,NOW,DispatchClient(CONFIG,session))
    assert TOKEN not in str(e.value) and state['pending']['phase']=='unconfirmed'
    with pytest.raises(ManualError):request_research(CONFIG,state,replica,NOW+timedelta(seconds=20),DispatchClient(CONFIG,session))
    assert sum(method=='POST' for method,_,_ in session.calls)==1


def test_status_is_throttled_and_success_requires_matching_committed_snapshot(replica):
    state=owner();session=GitHub();client=DispatchClient(CONFIG,session)
    rid=request_research(CONFIG,state,replica,NOW,client)
    session.runs=[{'display_title':'Manual research '+rid,'event':'workflow_dispatch','head_branch':'main',
        'status':'completed','conclusion':'success'}]
    assert poll(CONFIG,state,replica,NOW,client)=='awaiting_saved_results'
    before=len(session.calls);poll(CONFIG,state,replica,NOW+timedelta(seconds=10),client)
    assert len(session.calls)==before
    replica.shared_status['envelope'].update(generation=3,heartbeat={'summary':{'manual_request_id':rid}})
    assert poll(CONFIG,state,replica,NOW+timedelta(seconds=20),client)=='synced' and len(session.calls)==before


@pytest.mark.parametrize('status',[302,401,403,422,429,500])
def test_transport_errors_do_not_read_bodies_or_expose_tokens(status):
    class Bad(Response):
        def iter_content(self,n):pytest.fail('Never read an error body')
    class Session:
        def request(self,*a,**k):return Bad(TOKEN,status)
    with pytest.raises(ManualError) as e:DispatchClient(CONFIG,Session()).dispatch('f'*32)
    assert TOKEN not in str(e.value)


def test_workflow_has_no_schedule_and_manual_guards_run_before_checkout():
    source=Path('deploy/private_worker.yml').read_text();w=yaml.safe_load(source)
    trigger=w.get('on',w.get(True));job=w['jobs']['research'];check=job['steps'][0]
    assert set(trigger)=={'workflow_dispatch'}
    assert trigger['workflow_dispatch']['inputs']['operation']['default']=='verify'
    assert "github.event_name == 'workflow_dispatch'" in job['if']
    assert 'expected_app_commit' in trigger['workflow_dispatch']['inputs']
    assert all(s in check['run'] for s in ('RESEARCH_REQUEST_ID','EXPECTED_APP_COMMIT','AUTOMATIC_WORKER','AUTOMATIC_SCHEDULE','RESEARCH_DATA_RIGHTS_VERIFIED','RESEARCH_BUDGET_SCOPE_REVIEWED'))
    env=job['steps'][-1]['env']
    assert env['RESEARCH_WORKER_ENABLED']==env['RESEARCH_SCHEDULE_ENABLED']==env['PAID_ANALYST_APPROVED']=='0'
    assert env['ODDS_DAILY_CREDITS']=='9' and '--manual "$RESEARCH_REQUEST_ID"' in job['steps'][-1]['run']
    assert 'held=false' not in source and 'RESEARCH_MANUAL_GITHUB_TOKEN' not in source


def test_manual_credentials_are_redacted_from_chat_and_nested_evidence(monkeypatch):
    from intelligence.analyst_config import load_config
    from intelligence.chat_privacy import redact_data,validate_input,InvalidChatInput
    monkeypatch.setenv('RESEARCH_MANUAL_GITHUB_TOKEN',TOKEN)
    monkeypatch.setenv('RESEARCH_MANUAL_OWNER_HASH',CONFIG.owner_hash)
    c=load_config()
    assert TOKEN in c.sensitive_values and CONFIG.owner_hash in c.sensitive_values
    with pytest.raises(InvalidChatInput):validate_input(TOKEN,c)
    safe=redact_data({'nested':{'token':TOKEN,'owner':CONFIG.owner_hash,'probability':.65}},c.sensitive_values)
    assert TOKEN not in str(safe) and CONFIG.owner_hash not in str(safe) and safe['nested']['probability']==.65
