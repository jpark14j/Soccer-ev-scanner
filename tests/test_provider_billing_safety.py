"""Billing failures must never retry or silently restore a provider allowance."""
from unittest.mock import Mock
import json
import pytest
import requests
from conftest import NOW
from intelligence.providers import OddsAPI,ProviderError
from intelligence.data_settings import load_settings
from intelligence.quota import quota_details
from intelligence.request_guard import blocked


@pytest.mark.parametrize('configured',['10','10000','-1','1.5'])
def test_settings_cannot_raise_existing_nine_credit_ceiling(monkeypatch,configured):
    monkeypatch.setenv('ODDS_DAILY_CREDITS',configured)
    assert load_settings().daily_limit==0


def test_legacy_reservations_are_capped_even_with_large_explicit_limit(store):
    assert store.reserve(9,10000,NOW)
    assert not store.reserve(1,10000,NOW)
    assert quota_details(store,10000,NOW)['limit']==9
    assert quota_details(store,10000,NOW)['remaining']==0


@pytest.mark.parametrize('shared',[False,True])
def test_timeout_holds_requests_without_retry_or_refund(store,shared):
    authority=Mock() if shared else None
    if shared:
        authority.reserve.return_value={'day':NOW.date().isoformat(),'used':1}
        authority.charge.return_value=None
        store.request_authority=authority
    transport=Mock();transport.get.side_effect=requests.Timeout('secret-api-key URL')
    api=OddsAPI('secret-api-key',store,session=transport)
    with pytest.raises(ProviderError,match='billing is unknown') as error:api.odds('NBA')
    assert 'secret-api-key' not in str(error.value)
    assert transport.get.call_count==1
    with pytest.raises(ProviderError):api.events('NBA')
    assert transport.get.call_count==1
    with store.connect() as db:assert blocked(db)
    if shared:authority.charge.assert_called_once_with(None)
    assert quota_details(store,9)['remaining']==0
    with store.connect() as db:
        assert db.execute('SELECT sum(used) FROM budget').fetchone()[0]==1
        assert 'secret-api-key' not in repr([tuple(r) for r in db.execute('SELECT * FROM recovery_guard_events')])


@pytest.mark.parametrize('header',[None,'credential-reflection', '-1','1.5','99999999999999','٢'])
def test_missing_or_invalid_billing_header_holds_and_closes(store,header):
    response=Mock(status_code=200,headers={'x-requests-last':header})
    transport=Mock();transport.get.return_value=response
    with pytest.raises(ProviderError,match='unverifiable'):OddsAPI('test-key',store,session=transport).odds('NBA')
    response.close.assert_called_once();response.json.assert_not_called()
    assert quota_details(store,9)['recovery_hold']


def test_unexpected_charge_retained_and_no_server_error_retry(store):
    response=Mock(status_code=503,headers={'x-requests-last':'3'})
    transport=Mock();transport.get.return_value=response
    with pytest.raises(ProviderError,match='unexpected'):OddsAPI('test-key',store,session=transport).odds('NBA')
    assert transport.get.call_count==1
    response.close.assert_called_once()
    assert quota_details(store,9)['used']==3
    assert quota_details(store,9)['recovery_hold']


def test_known_charge_server_failure_is_not_automatically_retried(store):
    response=Mock(status_code=503,headers={'x-requests-last':'1'})
    transport=Mock();transport.get.return_value=response
    with pytest.raises(ProviderError,match='HTTP 503'):OddsAPI('test-key',store,session=transport).odds('NBA')
    assert transport.get.call_count==1
    response.close.assert_called_once()
    assert quota_details(store,9)['used']==1


def test_quota_header_reflection_is_not_persisted(store):
    response=Mock(status_code=200,headers={'x-requests-last':'1','x-requests-remaining':'test-key','x-requests-used':'test-key'})
    response.json.return_value=[]
    result=OddsAPI('test-key',store,session=Mock(get=Mock(return_value=response))).odds('NBA')
    assert result['credits_remaining'] is None
    cached=store.cached('provider-quota-observation',60)
    assert cached['used'] is None and 'test-key' not in json.dumps(cached)
    response.close.assert_called_once()


def test_recent_account_exhaustion_blocks_transport_but_not_cached_quotes(store):
    from intelligence.domain import digest
    store.cache('provider-quota-observation',{'account_fingerprint':digest('test-key'),'remaining':0})
    transport=Mock()
    with pytest.raises(ProviderError,match='account allowance'):
        OddsAPI('test-key',store,session=transport).odds('NBA')
    transport.get.assert_not_called()
    assert quota_details(store,9)['used']==0
    # A different account observation must not be treated as this account's quota.
    store.cache('provider-quota-observation',{'account_fingerprint':digest('other-account'),'remaining':0})
    response=Mock(status_code=200,headers={'x-requests-last':'1','x-requests-remaining':'0'})
    response.json.return_value=[]
    transport.get.return_value=response
    api=OddsAPI('test-key',store,session=transport)
    saved=api.odds('NBA')
    assert api.odds('NBA')==saved and transport.get.call_count==1


def test_legacy_monthly_usage_blocks_even_when_daily_reservations_are_empty(store):
    from datetime import timedelta
    with store.connect() as db:
        db.execute('INSERT INTO budget VALUES(?,?)',((NOW-timedelta(days=1)).date().isoformat(),279))
    assert not store.reserve(1,9,NOW)
    info=quota_details(store,9,NOW)
    assert info['used']==0 and info['monthly_reserved']==279 and info['remaining']==0
    # The next calendar month starts a new LOCAL ledger period only.
    later=NOW.replace(month=11,day=1)
    assert store.reserve(1,9,later)


def test_legacy_refresh_control_rejects_above_nine_instead_of_claiming_extra_allowance(store,monkeypatch):
    from intelligence.research_refresh import credit_status
    monkeypatch.setenv('ODDS_DAILY_CREDITS','16')
    with pytest.raises(ProviderError,match='invalid'):credit_status(store)
