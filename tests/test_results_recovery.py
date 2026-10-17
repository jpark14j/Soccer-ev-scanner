"""Synthetic provider responses only; recoverability never resets verification."""
from datetime import timedelta
from unittest.mock import patch
import sqlite3
import pytest
import requests
from intelligence.domain import utcnow
from intelligence.current_results import current,cached_status,cache_key,season_at,TTL
from intelligence.results_journal import latest
from intelligence.storage import Store
from intelligence.cached_research import synchronize
from intelligence.pipeline import Analysis,evaluate_quotes
from test_current_results import CONFIG,Session,Response,payload
from test_readiness_ranking import enable,supported_quote


@pytest.mark.parametrize('kind',['timeout','connection','http','schema','reflected_credential'])
def test_failed_refresh_retains_accepted_success_and_does_not_reactivate_it(store,kind):
    now=utcnow();events,meta=current(store,'Bundesliga',now,CONFIG,Session(Response(payload(now=now))))
    later=now+timedelta(seconds=TTL+1)
    session=Session(Response(status_code=500) if kind=='http' else Response({'invalid':'schema'}))
    if kind=='reflected_credential':session=Session(Response(raw=CONFIG.token.encode()))
    if kind in ('timeout','connection'):
        session.get=lambda *a,**k:(_ for _ in ()).throw(requests.Timeout(CONFIG.token) if kind=='timeout' else requests.ConnectionError(CONFIG.token))
    out,failed=current(store,'Bundesliga',later,CONFIG,session)
    assert not out and not failed['ok'] and failed['failure_code']
    saved=latest(store,'Bundesliga',season_at(now))
    assert saved['sha256']==meta['sha256'] and saved['checked_at']==now.isoformat()
    state=cached_status(store,'Bundesliga',later)
    assert not state['ok'] and state['last_success']['sha256']==meta['sha256']
    assert not state['last_success']['fresh'] and state['retained_normalized']['completed_observations']>0
    assert CONFIG.token not in str(state)
    with patch('intelligence.current_results.requests.Session.get',side_effect=AssertionError('No retry')):
        assert not current(store,'Bundesliga',later,CONFIG,allow_fetch=False)[0]
    with store.connect() as db:assert db.execute('SELECT count(*) FROM football_data_requests').fetchone()[0]==2


def test_legacy_success_is_preserved_before_failed_refresh(store):
    now=utcnow();current(store,'Bundesliga',now,CONFIG,Session(Response(payload(now=now))))
    with store.connect() as db:
        db.execute('DROP TRIGGER soccer_snapshot_no_delete');db.execute('DELETE FROM accepted_soccer_snapshots')
    later=now+timedelta(seconds=TTL+1)
    current(store,'Bundesliga',later,CONFIG,Session(Response(status_code=503)))
    assert latest(store,'Bundesliga',season_at(now))['checked_at']==now.isoformat()


def test_same_disk_restart_and_missing_cache_recover_without_http_or_timestamp_reset(store):
    now=utcnow();events,meta=current(store,'Bundesliga',now,CONFIG,Session(Response(payload(now=now))))
    with store.connect() as db:db.execute('DELETE FROM cache WHERE key=?',(cache_key('Bundesliga',season_at(now)),))
    other=Store(store.path)
    with patch('intelligence.current_results.requests.Session.get',side_effect=AssertionError('No HTTP')):
        recovered,state=current(other,'Bundesliga',now+timedelta(minutes=1),CONFIG,allow_fetch=False)
        assert recovered and state['checked_at']==meta['checked_at'] and state['sha256']==meta['sha256']
        assert not current(other,'Bundesliga',now+timedelta(seconds=TTL),CONFIG,allow_fetch=False)[0]
    assert cached_status(other,'Bundesliga',now+timedelta(minutes=1))['cache_recoverable_without_HTTP']
    with store.connect() as db:
        assert db.execute('SELECT count(*) FROM football_data_requests').fetchone()[0]==1
        with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM accepted_soccer_snapshots')


def test_fresh_cache_cannot_hide_missing_storage_or_permissions(store):
    class Broken:
        def cached(self,*a):raise sqlite3.OperationalError('private path '+CONFIG.token)
        def connect(self):raise sqlite3.OperationalError(CONFIG.token)
    result=current(Broken(),'Bundesliga',config=CONFIG)[1]
    assert result['failure_code']=='storage' and CONFIG.token not in str(result)
    assert cached_status(Broken(),'Bundesliga')['failure_code']=='storage'
    disabled=CONFIG.__class__(False,CONFIG.token,True)
    assert 'disabled' in current(store,'Bundesliga',config=disabled)[1]['problem']


@pytest.mark.parametrize('league',['Premier League','Bundesliga','Ligue 1'])
def test_new_session_rechecks_failed_inference_after_other_session_saves_results(store,quote,monkeypatch,league):
    enable(monkeypatch);now=utcnow()
    # Obtain a matching synthetic fixture, then reproduce a stale shared analysis
    # with failed/missing prepared input. No source snapshot was used by it.
    q,_=supported_quote(store,quote,league,now)
    old=Analysis(quotes=[q],focused_model={'problem':'No cached results'} if league=='Premier League' else {},
        expanded_models={league:{'problem':'No cached results'}} if league!='Premier League' else {},
        research=[{'quote_id':q.id,'blockers':['No cached results']}])
    snapshot={'analysis':old,'stored_at':'original scan'}
    with (patch('intelligence.providers.OddsAPI.odds',side_effect=AssertionError('No odds')),
         patch('intelligence.current_results.requests.Session.get',side_effect=AssertionError('No results'))):
        fresh=synchronize(snapshot,store)
    assert fresh is not old and q.id in fresh.estimates and snapshot['stored_at']=='original scan'
    assert not fresh.estimates[q.id].validated and not fresh.opportunities
    assert synchronize(snapshot,store) is fresh


def test_store_identity_survives_reopen_but_not_an_actual_new_disk(store,tmp_path):
    from intelligence.persistence import storage_status,backup_store
    identity=storage_status(store)['store_identity']
    assert storage_status(Store(store.path))['store_identity']==identity
    assert storage_status(Store(tmp_path/'different.sqlite3'))['store_identity']!=identity
    now=utcnow();current(store,'Bundesliga',now,CONFIG,Session(Response(payload(now=now))))
    backup_store(store,tmp_path/'private-backup.sqlite3')
    assert latest(Store(tmp_path/'private-backup.sqlite3'),'Bundesliga',season_at(now))


def test_cached_schedule_becoming_past_is_not_hidden_by_fresh_receipt(store):
    now=utcnow().replace(hour=23,minute=40,second=0,microsecond=0)
    events,meta=current(store,'Bundesliga',now,CONFIG,Session(Response(payload(now=now))))
    assert meta['ok'] and any(e.status=='scheduled' and e.event_date==now.date().isoformat() for e in events)
    later=now+timedelta(minutes=30)
    _,fresh_meta=current(store,'Bundesliga',later,CONFIG,allow_fetch=False)
    assert fresh_meta['coverage']['unresolved_past']>0 and fresh_meta['checked_at']==meta['checked_at']
    assert cached_status(store,'Bundesliga',later)['last_success']['coverage']['unresolved_past']>0


def test_empty_environment_credential_does_not_shadow_streamlit_secret(monkeypatch):
    from intelligence.current_results import secret
    monkeypatch.setenv('FOOTBALL_DATA_TOKEN','')
    with patch('streamlit.secrets',{'FOOTBALL_DATA_TOKEN':CONFIG.token}):
        assert secret('FOOTBALL_DATA_TOKEN')==CONFIG.token


def test_store_uses_configured_secret_path_before_first_odds_secret_lookup(tmp_path,monkeypatch):
    from intelligence.pipeline import configured_store
    monkeypatch.delenv('INTELLIGENCE_DB',raising=False)
    monkeypatch.delenv('PREDICTION_LEDGER_DIR',raising=False)
    config={'INTELLIGENCE_DB':str(tmp_path/'from-secrets.sqlite3'),'PREDICTION_LEDGER_DIR':str(tmp_path/'empty-ledger')}
    saved=configured_store(config.get)
    assert saved.path==config['INTELLIGENCE_DB']
    monkeypatch.setenv('INTELLIGENCE_DB',str(tmp_path/'explicit-env.sqlite3'))
    assert configured_store(config.get).path==str(tmp_path/'explicit-env.sqlite3')
