from dataclasses import replace
from datetime import datetime,timezone,timedelta
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import pytest
from conftest import NOW
from intelligence.data_settings import load_settings
from intelligence.markets import selection_label,scope,CATALOG
from intelligence.quota import reset_info,quota_details,refresh_reason
from intelligence.providers import OddsAPI,ProviderError
from intelligence.pipeline import Analysis,run_analysis
from intelligence.research_refresh import featured_plan,refresh_event


def test_secrets_and_explicit_zero_cap_are_honored(monkeypatch):
    monkeypatch.delenv('ODDS_DAILY_CREDITS',raising=False)
    cfg=load_settings(lambda name:{'ODDS_DAILY_CREDITS':'9'}.get(name,''))
    assert cfg.daily_limit==9 and not cfg.collect_results
    monkeypatch.setenv('ODDS_DAILY_CREDITS','0')
    assert load_settings(lambda name:'9').daily_limit==0
    monkeypatch.setenv('ODDS_DAILY_CREDITS','do-not-echo-this')
    cfg=load_settings()
    assert cfg.daily_limit==0 and 'do-not-echo-this' not in repr(cfg)


def test_reset_is_next_utc_midnight_and_toronto_dst_correct():
    oct=reset_info(NOW)
    assert oct['next_reset_utc']=='2026-10-17T00:00:00+00:00'
    assert oct['next_reset_toronto']=='2026-10-16 20:00 EDT'
    winter=reset_info(datetime(2026,2,3,12,tzinfo=timezone.utc))
    assert winter['next_reset_toronto']=='2026-02-03 19:00 EST'
    midnight=reset_info(datetime(2026,10,16,tzinfo=timezone.utc))
    assert midnight['seconds_until_reset']==86400


def test_exhausted_quota_explains_reset_without_resetting_or_raising(store):
    store.reserve(9,9,NOW)
    info=quota_details(store,9,NOW)
    reason=refresh_reason(key_configured=True,selection_count=1,cost=1,quota=info)
    assert info['remaining']==0 and '20:00 EDT' in reason and 'cap has not been raised' in reason
    assert quota_details(store,9,NOW)['used']==9
    assert quota_details(store,9,NOW+timedelta(days=1))['used']==0


def test_clear_english_labels_and_scope_do_not_claim_verified_settlement(quote):
    prop=replace(quote,market='player_points',participant='Test Player',selection='Over',point=25.5)
    assert selection_label(prop)=='Test Player — Over 25.5 points'
    runline=replace(quote,sport='MLB',market='spreads',point=-1.5)
    assert 'Home -1.5' in selection_label(runline) and 'run line' in selection_label(runline)
    asian=replace(quote,sport='Soccer',market='spreads',point=-.25)
    assert 'quarter-line/Asian' in scope(asian) and 'unverified' in scope(prop)
    assert not CATALOG['totals_corners'].documented


class Response:
    status_code=200;headers={'x-requests-last':'1'}
    def json(self):return []


def test_reordered_markets_and_immediate_forced_refresh_reuse_one_request(store):
    class Session:
        calls=0
        def get(self,*args,**kwargs):self.calls+=1;return Response()
    s=Session(); api=OddsAPI('fixture',store,daily_limit=9,ttl=0,session=s)
    first=api.odds('NBA',('spreads','totals'))
    second=api.odds('NBA',('totals','spreads'))
    assert s.calls==1 and first['received_at']==second['received_at']
    assert quota_details(store,9)['used']==2


def test_concurrent_duplicate_fetch_does_not_spend_twice(store):
    entered=threading.Event();release=threading.Event()
    class Session:
        calls=0
        def get(self,*args,**kwargs):
            self.calls+=1;entered.set();release.wait(2);return Response()
    session=Session(); api=OddsAPI('fixture',store,session=session)
    with ThreadPoolExecutor(max_workers=2) as pool:
        one=pool.submit(api.odds,'NBA')
        assert entered.wait(2)
        with pytest.raises(ProviderError,match='already refreshing'):
            api.odds('NBA')
        release.set();one.result()
    assert session.calls==1 and quota_details(store,9)['used']==1


def test_featured_plan_reuses_current_markets_and_scopes_missing_search(quote):
    a=Analysis(quotes=[quote])
    assert featured_plan(a,['NBA'],['h2h','totals'],NOW)==[('NBA',('totals',))]
    assert featured_plan(a,['NBA'],['h2h'],NOW)==[]


def test_undocumented_corners_require_discovery_before_transport(store,quote):
    with patch('intelligence.research_refresh.OddsAPI') as api:
        with pytest.raises(ProviderError,match='discovery'):
            refresh_event(Analysis(),'fixture','Premier League','event',['totals_corners'],store)
        api.assert_not_called()


def test_seven_day_snapshot_restores_props_with_original_age(store,quote,monkeypatch):
    from tests_helpers import event_payload
    response=event_payload(quote,market='player_points',participant='Test Player',point=25.5,selection='Over')
    store.cache('event-snapshot-NBA-fixture-player_points',response,NOW)
    monkeypatch.setattr('intelligence.pipeline.utcnow',lambda:NOW+timedelta(minutes=6))
    class Provider:
        def odds(self,*a):raise ProviderError('Daily budget exhausted')
    result=run_analysis('fixture',['NBA'],store,Provider(),collect_results=False)
    assert len(result.quotes)==1 and result.quotes[0].source_updated_at==quote.source_updated_at
    assert result.quotes[0].status(NOW+timedelta(minutes=6))=='stale'
    assert not result.opportunities and not result.estimates


def test_narrow_refresh_merges_restored_other_markets_once(store,quote):
    from intelligence.research_refresh import merge_analysis
    total=replace(quote,market='totals',selection='Over',point=220.5)
    from intelligence.domain import parse_time
    old=replace(quote,received_at=(parse_time(quote.received_at)-timedelta(seconds=30)).isoformat())
    with patch('intelligence.research_refresh.evaluate_quotes',side_effect=lambda a,s:a):
        result=merge_analysis(Analysis(quotes=[old,total]),Analysis(quotes=[quote,total]),
            ['NBA'],['totals'],store)
    assert len(result.quotes)==2
    assert next(q for q in result.quotes if q.market=='h2h').received_at==quote.received_at
