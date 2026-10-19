"""Real local Postgres + SQLite; HTTP is a fake transport, NOT hosted Supabase.

The shipping migration executes in Postgres. No sports or remote service calls.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import base64,json,sqlite3,subprocess,sys,uuid
import pytest
import psycopg
from psycopg.types.json import Jsonb
from intelligence.shared_state import Config,Client,StateError,snapshot,materialize,pull_replica,open_replica
from intelligence.storage import Store
from intelligence.domain import utcnow,digest
from intelligence.background import bootstrap,run_background,run_id
from intelligence.current_results import _reserve

TOKEN='synthetic_read_capability_0123456789abcdef'
def fake_jwt(role):return 'syntheticHEADER.'+base64.urlsafe_b64encode(json.dumps({'role':role}).encode()).decode().rstrip('=')+'.syntheticSIGNATURE'
WRITER=fake_jwt('service_role')
READER=fake_jwt('anon')
CONFIG=Config(True,True,'https://'+'a'*20+'.supabase.co',READER,TOKEN,WRITER)


@pytest.fixture(scope='module')
def postgres(tmp_path_factory):
    import pgserver
    server=pgserver.get_server(tmp_path_factory.mktemp('postgres-control'),cleanup_mode='stop')
    with psycopg.connect(server.get_uri(),autocommit=True) as db:
        for role in ('anon','authenticated','service_role'):
            db.execute('CREATE ROLE '+role)
    yield server
    server.cleanup()


class Response:
    def __init__(self,value,status=200):self.raw=json.dumps(value,default=str).encode();self.status_code=status
    def iter_content(self,n):
        for i in range(0,len(self.raw),n):yield self.raw[i:i+n]
    def close(self):pass


class Transport:
    def __init__(self,uri):self.uri=uri;self.calls=[];self.clock=None
    def post(self,url,**kwargs):
        self.calls.append(url);assert kwargs['allow_redirects'] is False
        name=url.rsplit('/',1)[1];p=kwargs['json'];key=kwargs['headers']['apikey']
        assert key in (WRITER,READER)
        with psycopg.connect(self.uri) as db:
            if self.clock:db.execute("SELECT set_config('research_test.now',%s,false)",(self.clock,))
            db.execute('SET ROLE '+('service_role' if key==WRITER else 'anon'))
            if name=='research_control':
                value=db.execute('SELECT public.research_control(%s,%s,%s,%s)',(p['p_action'],p['p_owner'],p['p_fence'],Jsonb(p['p_data']))).fetchone()[0]
            elif name=='research_state_read':value=db.execute('SELECT public.research_state_read(%s)',(p['p_token'],)).fetchone()[0]
            else:value=db.execute('SELECT public.research_state_view()').fetchone()[0]
        return Response(value)
    def close(self):pass


@pytest.fixture
def remote(postgres):
    name='state_'+uuid.uuid4().hex
    with psycopg.connect(postgres.get_uri(),autocommit=True) as db:db.execute('CREATE DATABASE '+name)
    uri=postgres.get_uri(database=name)
    sql=Path('migrations/010_shared_research.sql').read_text()
    with psycopg.connect(uri,autocommit=True) as db:
        db.execute(sql)
        db.execute('UPDATE public.research_control_state SET reader_hash=%s',(sha256(TOKEN.encode()).hexdigest(),))
    yield Transport(uri)


def writer(remote):return Client(CONFIG,writer=True,session=remote)
def reader(remote):return Client(CONFIG,session=remote)


def release(remote):
    # Simulated explicit operator review; never performed by shipped worker/UI.
    with psycopg.connect(remote.uri) as db:db.execute('UPDATE public.research_control_state SET held=false')


def test_migration_reapplies_and_reader_has_no_write_privileges(remote):
    with psycopg.connect(remote.uri,autocommit=True) as db:db.execute(Path('migrations/010_shared_research.sql').read_text())
    assert reader(remote).read()['held'] is True
    with pytest.raises(StateError):reader(remote).control('acquire',{'run_id':digest('forbidden')})
    with psycopg.connect(remote.uri) as db:
        db.execute('SET ROLE anon')
        with pytest.raises(psycopg.errors.InsufficientPrivilege):db.execute("UPDATE research_control_state SET held=false")
    with psycopg.connect(remote.uri) as db:
        db.execute('SET ROLE anon')
        with pytest.raises(psycopg.errors.InsufficientPrivilege):db.execute("SELECT research_control('fail',%s,0,'{}')",('a'*32,))


def test_disabled_status_and_invalid_origins_never_call_transport(remote):
    assert run_background()=={'status':'disabled','provider_requests':0}
    for c in (Config(),replace(CONFIG,url='https://localhost'),replace(CONFIG,reviewed=False)):
        with pytest.raises(StateError):Client(c,writer=True,session=remote).acquire(digest('disabled'))
    assert not remote.calls and WRITER not in repr(CONFIG) and TOKEN not in repr(CONFIG)


def test_bootstrap_readback_independent_process_and_read_only_replica(remote,store,tmp_path):
    store.cache('genuine-existing-data',{'value':17});assert store.reserve(8,9)
    result=bootstrap(store.path,writer(remote));assert result['shared_readback_verified']
    assert reader(remote).read()['held']  # Bootstrap does not release usage hold.
    directory=tmp_path/'replica';pointer=pull_replica(directory,CONFIG,reader(remote))
    view=open_replica(directory,tmp_path/'fallback.sqlite3')
    assert view.cached('genuine-existing-data',3600)=={'value':17}
    assert not view.reserve(1,9) and not _reserve(view,utcnow()) and not view.authorize_discovery()
    result=subprocess.run([sys.executable,'-c','import sqlite3,sys,json;d=sqlite3.connect(sys.argv[1]);print(json.loads(d.execute("SELECT payload FROM cache WHERE key=?",("genuine-existing-data",)).fetchone()[0])["value"])',pointer['path']],capture_output=True,text=True,check=True)
    assert result.stdout.strip()=='17'
    assert sha256(Path(pointer['path']).read_bytes()).hexdigest()==pointer['manifest']['sha256']
    # Reading and local diagnostics cannot rewrite the authoritative head.
    view.cache('local-only',{'not':'committed'});assert reader(remote).read()['generation']==1
    with closing(sqlite3.connect(pointer['path'])) as db:assert not db.execute("SELECT 1 FROM cache WHERE key='local-only'").fetchone()


def test_writer_fencing_and_durable_budget_concurrency(remote,store,tmp_path):
    bootstrap(store.path,writer(remote));release(remote)
    authority=writer(remote);authority.acquire(digest('concurrency'))
    with pytest.raises(StateError,match='writer_busy'):writer(remote).acquire(digest('other-worker'))
    guarded=Store(tmp_path/'writer.sqlite3',request_authority=authority)
    with ThreadPoolExecutor(max_workers=12) as pool:allowed=list(pool.map(lambda _:guarded.reserve(1,9),range(18)))
    assert sum(allowed)==9
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(lambda _:_reserve(guarded,utcnow()),range(10)))
    assert sum(results)==6
    assert not guarded.reserve(1,9)
    # Lose this process before a SQLite checkpoint: write-ahead usage survives.
    authority.control('fail');next_writer=writer(remote);head=next_writer.acquire(digest('after-crash'))
    assert next(b['used'] for b in head['budgets'] if b['provider']=='odds')==9
    recovered=Store(tmp_path/'empty-after-crash.sqlite3',request_authority=next_writer)
    assert not recovered.reserve(1,9) and not _reserve(recovered,utcnow())
    with pytest.raises(StateError,match='lease_lost'):authority.control('checkpoint',{})


def test_unexpected_and_unknown_provider_costs_hold_all_requests(remote,store):
    bootstrap(store.path,writer(remote));release(remote);a=writer(remote);a.acquire(digest('cost'))
    assert a.reserve('odds',1);assert a.charge(3) is None
    head=reader(remote).read();assert head['held']
    assert next(b['used'] for b in head['budgets'] if b['provider']=='odds')==3
    assert not a.reserve('results',1)
    release(remote);a.held=False;assert a.reserve('odds',1);assert not a.charge(None)
    assert reader(remote).read()['held']


def test_duplicate_cycles_checkpoint_readback_and_failure_keep_previous_success(remote,store,monkeypatch):
    bootstrap(store.path,writer(remote));release(remote)
    monkeypatch.setenv('RESEARCH_WORKER_ENABLED','1');monkeypatch.setenv('RESEARCH_DATA_RIGHTS_VERIFIED','1');monkeypatch.setenv('PAID_ANALYST_APPROVED','0')
    monkeypatch.setenv('RESEARCH_BUDGET_SCOPE_REVIEWED','1')
    now=utcnow()
    def cycle(s,key,at):s.cache('worker-success',{'genuine_test_fixture':True});return {'new_forward_labels':0},[]
    result=run_background(client=writer(remote),now=now,cycle_fn=cycle)
    assert result['shared_readback_verified'] and result['generation']==2
    with pytest.raises(StateError,match='duplicate_run'):run_background(client=writer(remote),now=now,cycle_fn=cycle)
    before=reader(remote).read()['snapshot']
    def fail(*args):raise RuntimeError('simulated process failure, no secrets')
    with pytest.raises(RuntimeError):run_background(client=writer(remote),now=now+timedelta(hours=1),cycle_fn=fail)
    after=reader(remote).read();assert after['snapshot']==before
    assert after['heartbeat']['status']=='failed' and after['heartbeat']['last_success_at']


def test_corrupt_replica_and_missed_commit_cannot_replace_success(remote,store,tmp_path):
    bootstrap(store.path,writer(remote));release(remote)
    directory=tmp_path/'replicas';pointer=pull_replica(directory,CONFIG,reader(remote))
    a=writer(remote);a.acquire(digest('missed-pregame'))
    with pytest.raises(StateError,match='missed_pregame_commit'):
        a.control('checkpoint',snapshot(store)|{'expected_generation':1,'run_id':digest('missed-pregame'),
            'prospective_deadline':(utcnow()-timedelta(minutes=1)).isoformat(),'publications':[],'summary':{}})
    assert reader(remote).read()['generation']==1
    head=reader(remote).read();head['snapshot']['compressed']='corrupted'
    with pytest.raises(StateError):materialize(head,tmp_path/'bad.sqlite3')
    assert json.loads((directory/'head.json').read_text())==pointer and not (tmp_path/'bad.sqlite3').exists()


def test_actual_rpc_error_never_exposes_key_or_body(remote):
    import requests
    def fail(*args,**kwargs):raise requests.ConnectionError(WRITER+' '+TOKEN)
    remote.post=fail
    with pytest.raises(StateError) as e:writer(remote).acquire(digest('no-network'))
    assert WRITER not in str(e.value) and TOKEN not in str(e.value)


def test_utc_boundary_reset_and_expired_writer_fencing_in_real_postgres(remote,store):
    # Replace ONLY the wall-clock dependency for this deterministic edge test.
    # All other tests execute the shipping migration without this test seam.
    with psycopg.connect(remote.uri) as db:
        db.execute("CREATE FUNCTION public.research_test_clock() RETURNS timestamptz LANGUAGE sql AS $$ SELECT current_setting('research_test.now')::timestamptz $$")
        body=db.execute("SELECT pg_get_functiondef('public.research_control(text,text,bigint,jsonb)'::regprocedure)").fetchone()[0]
        db.execute(body.replace('clock_timestamp()','public.research_test_clock()'))
    remote.clock='2026-10-17T23:50:00Z';bootstrap(store.path,writer(remote));release(remote)
    a=writer(remote);a.acquire(digest('midnight'))
    assert a.reserve('odds',9)
    remote.clock='2026-10-17T23:59:30Z';assert not a.reserve('results',1)
    remote.clock='2026-10-18T00:00:30Z';assert not a.reserve('results',1)
    remote.clock='2026-10-18T00:02:00Z';assert a.reserve('odds',1)
    remote.clock='2026-10-18T00:06:00Z';assert not a.reserve('results',1)
    b=writer(remote);b.acquire(digest('expired-run-recovery'))
    assert b.reserve('odds',8) and not b.reserve('odds',1)
    assert not a.reserve('results',1)  # Prior owner never regains authority.


def test_independent_worker_runs_real_research_publication_and_replica_ui(remote,store,quote,monkeypatch,tmp_path):
    from unittest.mock import patch
    from test_master_workflow import research_slate
    from tests_helpers import event_payload
    from intelligence.providers import LEAGUES
    from intelligence.background import cycle
    from intelligence.publication_journal import performance,records
    bootstrap(store.path,writer(remote));release(remote)
    monkeypatch.setenv('RESEARCH_WORKER_ENABLED','1');monkeypatch.setenv('RESEARCH_DATA_RIGHTS_VERIFIED','1')
    monkeypatch.setenv('RESEARCH_BUDGET_SCOPE_REVIEWED','1');monkeypatch.setenv('PAID_ANALYST_APPROVED','0')
    # Next-round replay fixtures can be six days away after the current round.
    monkeypatch.setenv('SLATE_WINDOW_HOURS','168')
    def model_cycle(s,key,at):
        a=research_slate(s,quote,monkeypatch)
        for q in a.quotes:
            raw=event_payload(q,point=q.point);raw['data']['sport_key']=LEAGUES[q.league][1];raw['data']=[raw['data']]
            s.cache('event-snapshot-'+q.league+'-'+q.event_id+'-'+q.market,raw)
        # Existing helper created accepted synthetic results; no external source.
        with patch('intelligence.current_results.current',return_value=([],{'ok':False,'failure_code':'synthetic_no_refresh'})):
            return cycle(s,'',at)
    result=run_background(client=writer(remote),cycle_fn=model_cycle)
    assert result['shared_readback_verified'] and result['summary']['model_estimates']>=3
    assert result['summary']['new_publications']>=2
    directory=tmp_path/'preview-replica';pull_replica(directory,CONFIG,reader(remote))
    view=open_replica(directory,tmp_path/'fallback.sqlite3')
    assert performance(view)['published_committed_pregame']>=2
    original=[r['payload'] for r in records(view)]
    from streamlit.testing.v1 import AppTest
    from ui_navigation import navigate
    for name,value in {'RESEARCH_SHARED_STATE_ENABLED':'1','RESEARCH_STATE_USE_REVIEWED':'1',
        'RESEARCH_STATE_URL':CONFIG.url,'RESEARCH_STATE_READER_KEY':READER,'RESEARCH_STATE_READ_TOKEN':TOKEN,
        'RESEARCH_REPLICA_DIR':str(directory),'INTELLIGENCE_DB':str(tmp_path/'fallback.sqlite3')}.items():monkeypatch.setenv(name,value)
    with patch('intelligence.shared_state.requests.Session',return_value=remote),patch('intelligence.providers.OddsAPI._fetch',side_effect=AssertionError('No sportsbook requests on pages')),patch('openai.OpenAI',side_effect=AssertionError('Paid AI disabled')):
        app=AppTest.from_file(Path('app.py').resolve(),default_timeout=40).run();assert not app.exception
        navigate(app,'Research Operations')  # Refresh controls moved out of everyday pages.
        assert next(b for b in app.button if b.label=='Refresh analysis').disabled
        for page in ('Best Picks & Parlays','Performance Tracker','Research Operations','AI Assistant','AI Dashboard'):
            navigate(app,page);assert not app.exception,page
    assert records(view) and [r['payload'] for r in records(view)]==original
    assert reader(remote).read()['generation']==2  # Browsing did not publish.


def test_odds_timeout_sets_durable_hold_without_checkpoint_or_second_transport(remote,store,tmp_path):
    """An ambiguous paid request must remain reserved even if SQLite is lost."""
    from unittest.mock import Mock
    import requests
    from intelligence.providers import OddsAPI,ProviderError
    bootstrap(store.path,writer(remote));release(remote)  # Isolated local PG fixture only.
    authority=writer(remote);authority.acquire(digest('synthetic-timeout-only'))
    guarded=Store(tmp_path/'uncommitted.sqlite3',request_authority=authority)
    transport=Mock();transport.get.side_effect=requests.Timeout('synthetic-secret-in-url')
    with pytest.raises(ProviderError,match='billing is unknown'):
        OddsAPI('synthetic-secret-in-url',guarded,session=transport).odds('NBA')
    head=reader(remote).read()
    assert head['held'] is True and head['generation']==1
    assert any(r['provider']=='odds' and r['used']==1 for r in head['budgets'])
    with psycopg.connect(remote.uri) as db:
        reservations=db.execute('SELECT reserved,actual FROM public.research_reservations').fetchall()
    assert reservations==[(1,None)]  # Unknown is never marked free or refunded.
    with pytest.raises(ProviderError):OddsAPI('synthetic-secret-in-url',guarded,session=transport).events('NBA')
    assert transport.get.call_count==1
