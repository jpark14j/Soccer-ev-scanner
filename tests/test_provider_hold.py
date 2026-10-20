"""Synthetic/local-Postgres hold review only; no hosted release or API call."""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
import json
import pytest,yaml,psycopg
from intelligence.domain import utcnow,parse_time
from intelligence.provider_hold import review,worker_configuration
from intelligence.shared_state import snapshot,replica_revision,StateError,pull_replica,open_replica
from intelligence.background import bootstrap
from test_shared_control import postgres,remote,writer,reader,CONFIG

SETTINGS={'manual_enabled':True,'data_rights_reviewed':True,'account_scope_reviewed':True,
    'actions_usage_reviewed':True,'automatic_worker_enabled':False,'schedule_enabled':False,
    'paid_ai_enabled':False,'odds_secret_present':True,'results_secret_present':False,
    'results_enabled':False,'results_use_reviewed':False}


def identity(store):
    with store.connect() as db:return db.execute('SELECT instance FROM store_identity WHERE id=1').fetchone()[0]


def envelope(store):
    return {'generation':2,'held':True,'server_at':utcnow().isoformat(),'lease_until':None,
        'heartbeat':{},'budgets':[],'snapshot':snapshot(store)|{'generation':2}}


class ReadOnly:
    def __init__(self,e):self.envelope=e;self.reads=0
    def read(self):self.reads+=1;return self.envelope


def test_review_is_one_read_and_never_releases_reserves_or_collects(store):
    c=ReadOnly(envelope(store));before=deepcopy(c.envelope)
    with patch('intelligence.providers.OddsAPI',side_effect=AssertionError('No provider')):
        result=review(client=c,expected_instance=identity(store),settings=SETTINGS)
    assert c.reads==1 and c.envelope==before
    assert result['provider_budget_hold'] is True and 'remote_provider_hold' in result['manual_blockers']
    assert result['remote_writes']==result['sports_provider_requests']==result['paid_ai_requests']==0
    assert result['hold_release_authorized'] is False and result['external_account_remaining'] is None
    assert result['conservative_proposal_available'] and 'release_approved boolean := false' in result['proposed_operator_sql']
    with store.connect() as db:assert db.execute('SELECT count(*) FROM budget').fetchone()[0]==0


@pytest.mark.parametrize('problem',['active','local_hold','rights','scope','actions','automatic','paid'])
def test_unsafe_or_unreviewed_conditions_cannot_prepare_release_sql(store,problem):
    e=envelope(store);settings=dict(SETTINGS)
    if problem=='active':e['lease_until']=(utcnow()+timedelta(minutes=10)).isoformat()
    if problem=='local_hold':
        from intelligence.request_guard import hold
        with store.connect() as db:hold(db,'Synthetic restored store')
        e=envelope(store)
    for name,flag in [('rights','data_rights_reviewed'),('scope','account_scope_reviewed'),('actions','actions_usage_reviewed')]:
        if problem==name:settings[flag]=False
    if problem=='automatic':settings['automatic_worker_enabled']=True
    if problem=='paid':settings['paid_ai_enabled']=True
    r=review(client=ReadOnly(e),expected_instance=identity(store),settings=settings)
    assert not r['conservative_proposal_available'] and r['proposed_operator_sql'] is None
    assert r['manual_blockers'] and not r['hold_release_authorized']


def test_saved_and_remote_counts_are_separate_and_rotating_key_never_resets_them(store):
    day=utcnow().date().isoformat()
    with store.connect() as db:db.execute('INSERT INTO budget VALUES(?,7)',(day,))
    e=envelope(store);e['budgets']=[{'day':day,'provider':'odds','used':9}]
    r=review(client=ReadOnly(e),expected_instance=identity(store),settings=SETTINGS)
    assert r['saved_local_reservations']['odds']==7 and r['worker_budget_reservations']['odds']['used']==9
    assert 'current_day_odds_allowance_exhausted' in r['manual_blockers']
    assert r['external_account_remaining'] is None and 'does not reset' in r['rotation_note']


def test_worker_flags_and_presence_are_booleans_and_never_return_secrets(monkeypatch):
    secret='synthetic-private-credential-only'
    monkeypatch.setenv('ODDS_API_KEY',secret)
    monkeypatch.setenv('RESEARCH_ODDS_KEY_CONFIGURED','true')
    monkeypatch.setenv('RESEARCH_RESULTS_TOKEN_CONFIGURED','false')
    monkeypatch.setenv('RESEARCH_DATA_RIGHTS_VERIFIED','1')
    r=worker_configuration()
    assert r['odds_secret_present'] is True and not r['results_secret_present'] and r['data_rights_reviewed']
    assert secret not in json.dumps(r) and all(type(v) is bool for v in r.values())


def test_wrong_store_cannot_prepare_a_proposal(store):
    with pytest.raises(StateError,match='identity differs'):
        review(client=ReadOnly(envelope(store)),expected_instance='0'*32,settings=SETTINGS)


def test_fresh_accepted_results_are_inspected_without_ingestion_or_schema_writes(store):
    from test_readiness_ranking import cached_source
    now=utcnow();cached_source(store,'Premier League',now)
    e=envelope(store)
    with patch('intelligence.event_data.ensure_events',side_effect=AssertionError('No schema creation')):
        r=review(client=ReadOnly(e),expected_instance=identity(store),settings=SETTINGS)
    s=r['current_results']['Premier League']
    assert s['available'] and s['fresh'] and s['accepted_journal_snapshot']
    assert 'no provider' in s['scope']


def test_control_revision_changes_without_a_new_snapshot_and_ignores_read_clocks():
    p={'manifest':{'sha256':'a'*64},'verified_at':utcnow().isoformat(),
        'envelope':{'generation':2,'held':True,'heartbeat':{},'budgets':[]}}
    same=deepcopy(p);same['verified_at']='later';same['envelope']['server_at']='later'
    assert replica_revision(p)==replica_revision(same)
    for field,value in [('held',False),('budgets',[{'day':'2026-10-18','provider':'odds','used':1}]),
        ('heartbeat',{'status':'failed'}),('lease_until','2026-10-18T23:00:00+00:00')]:
        changed=deepcopy(p);changed['envelope'][field]=value
        assert replica_revision(p)!=replica_revision(changed)
    p['envelope']['budgets']=[{'day':'2026-10-18','provider':name,'used':1} for name in ('odds','results')]
    same=deepcopy(p);same['envelope']['budgets'].reverse()
    assert replica_revision(p)==replica_revision(same)


def test_same_generation_control_change_updates_replica_without_writing_or_requesting_odds(remote,store,tmp_path):
    bootstrap(store.path,writer(remote));directory=tmp_path/'replica'
    pull_replica(directory,CONFIG,reader(remote));before=open_replica(directory,tmp_path/'fallback')
    first=replica_revision(before.shared_status)
    # Simulated operator action in test Postgres only, not hosted Supabase.
    with psycopg.connect(remote.uri) as db:
        db.execute('UPDATE research_control_state SET held=false')
        db.execute("INSERT INTO research_provider_budget VALUES((now() AT TIME ZONE 'UTC')::date,'odds',3)")
    remote.calls.clear()
    pull_replica(directory,CONFIG,reader(remote));after=open_replica(directory,tmp_path/'fallback')
    assert before.shared_status['envelope']['generation']==after.shared_status['envelope']['generation']==1
    assert before.shared_status['manifest']==after.shared_status['manifest']
    assert first!=replica_revision(after.shared_status) and after.shared_status['envelope']['held'] is False
    assert len(remote.calls)==1 and remote.calls[0].endswith('research_state_read')
    assert not after.reserve(1,9)  # The refreshed dashboard remains read-only.


def test_hold_review_workflow_mode_cannot_receive_sports_provider_keys():
    w=yaml.safe_load(Path('deploy/private_worker.yml').read_text());trigger=w.get('on',w.get(True))
    assert 'hold-review' in trigger['workflow_dispatch']['inputs']['operation']['options']
    env=w['jobs']['research']['steps'][-1]['env']
    assert "inputs.operation == 'manual-research'" in env['ODDS_API_KEY']
    assert "inputs.operation == 'manual-research'" in env['FOOTBALL_DATA_TOKEN']
    assert env['RESEARCH_ODDS_KEY_CONFIGURED']=="${{ secrets.ODDS_API_KEY != '' }}"
    assert '--review-hold' in w['jobs']['research']['steps'][-1]['run']


def report(remote,store):
    bootstrap(store.path,writer(remote))
    return review(client=writer(remote),expected_instance=identity(store),settings=SETTINGS)


def test_actual_postgres_review_and_unapproved_sql_preserve_hold_and_all_rows(remote,store):
    r=report(remote,store);before=reader(remote).read();remote.calls.clear()
    r=review(client=writer(remote),expected_instance=identity(store),settings=SETTINGS)
    assert len(remote.calls)==1 and remote.calls[0].endswith('research_state_view')
    with psycopg.connect(remote.uri,autocommit=True) as db:
        with pytest.raises(psycopg.errors.RaiseException,match='approval required'):db.execute(r['proposed_operator_sql'])
        db.execute('ROLLBACK')
    after=reader(remote).read()
    assert after['generation']==before['generation'] and after['held'] and after['budgets']==before['budgets']
    assert after['snapshot']==before['snapshot']


def approved_sql(r):return r['proposed_operator_sql'].replace('release_approved boolean := false','release_approved boolean := true')


def test_approved_proposal_only_in_synthetic_postgres_preserves_overcounts_and_reserves_full_day(remote,store):
    r=report(remote,store)
    with psycopg.connect(remote.uri,autocommit=True) as db:
        db.execute("INSERT INTO research_provider_budget VALUES(%s,'odds',10)",(r['utc_day'],))
        db.execute(approved_sql(r))
    after=reader(remote).read()
    assert after['generation']==1 and not after['held']
    assert {b['provider']:b['used'] for b in after['budgets']}=={'odds':10,'results':6,'discovery':12}
    c=writer(remote);c.acquire('d'*64)
    assert c.reserve('odds',1) is None and c.reserve('results',1) is None and c.reserve('discovery',1) is None


@pytest.mark.parametrize('change',['lease','generation','checksum','unreconciled','expired'])
def test_prepared_sql_refuses_changed_or_uncertain_state_before_release(remote,store,change):
    r=report(remote,store)
    with psycopg.connect(remote.uri,autocommit=True) as db:
        if change=='lease':db.execute("UPDATE research_control_state SET owner=%s,lease_until=now()+interval '10 minutes'",('a'*32,))
        if change=='generation':db.execute('UPDATE research_control_state SET generation=2')
        if change=='checksum':db.execute("UPDATE research_state_snapshots SET manifest=jsonb_set(manifest,'{sha256}',to_jsonb(%s::text))",('f'*64,))
        if change=='unreconciled':db.execute("INSERT INTO research_reservations VALUES(%s,%s,'odds',1,NULL,%s)",('b'*32,r['utc_day'],'c'*32))
        sql=approved_sql(r)
        if change=='expired':sql=sql.replace(r['server_at'],(parse_time(r['server_at'])-timedelta(hours=1)).isoformat())
        with pytest.raises(psycopg.errors.RaiseException):db.execute(sql)
        db.execute('ROLLBACK')
    assert reader(remote).read()['held']


