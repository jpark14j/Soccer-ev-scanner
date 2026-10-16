"""Synthetic transport fixtures verify spend/coverage, never model profitability."""
from dataclasses import replace
from datetime import timedelta
from unittest.mock import patch
import pytest
from conftest import NOW
from intelligence.pipeline import Analysis,run_analysis
from intelligence.slate import run_slate
from intelligence.quota import quota_details
from intelligence.providers import LEAGUES,ProviderError


class Provider:
    ttl=1800
    def __init__(self,store,quote,cap=9):
        self.store,self.quote,self.daily_limit=store,quote,cap
        self.calls=[]
    def events(self,league):
        q=self.quote
        return {'data':[{'id':league+'-event','sport_key':LEAGUES[league][1],
            'home_team':q.home,'away_team':q.away,'commence_time':q.commence_time}],
            'received_at':NOW.isoformat()}
    def odds(self,league,markets):
        assert self.store.reserve(len(markets),self.daily_limit,NOW)
        self.calls.append((league,markets))
        return {'data':[],'received_at':NOW.isoformat()}
    def event_odds(self,league,event,markets):
        return self.odds(league,markets)


@pytest.fixture
def fixed_clock(monkeypatch):
    for name in ('intelligence.slate','intelligence.pipeline','intelligence.processing','intelligence.results'):
        monkeypatch.setattr(name+'.utcnow',lambda:NOW)


def test_auto_scan_discovers_all_configured_events_and_stops_at_cap(store,quote,fixed_clock):
    provider=Provider(store,quote,3)
    result=run_slate('synthetic',['NBA','Premier League','MLB'],store,provider)
    assert len(result.slate['events'])==3
    assert len(provider.calls)==3 and quota_details(store,3,NOW)['used']==3
    assert {league for league,_ in provider.calls}=={'NBA','MLB','Premier League'}
    assert any('credit cap' in q['status'] for q in result.slate['queries'])
    assert not result.opportunities


def test_empty_queries_reused_then_unscanned_markets_rotate_first(store,quote,fixed_clock):
    provider=Provider(store,quote,2)
    run_slate('synthetic',['NBA'],store,provider)
    first=list(provider.calls)
    run_slate('synthetic',['NBA'],store,provider)
    assert provider.calls==first
    later=NOW+timedelta(minutes=10)
    with patch('intelligence.slate.utcnow',return_value=later),patch('intelligence.quota.utcnow',return_value=later):
        # Inspect the scheduling order without authorizing additional spend.
        provider.daily_limit=0
        result=run_slate('synthetic',['NBA'],store,provider)
    assert result.slate['queries'][0]['market'] not in {markets[0] for _,markets in first}


def test_exhausted_budget_still_discovers_without_odds_calls(store,quote,fixed_clock):
    store.reserve(9,9,NOW);provider=Provider(store,quote)
    result=run_slate('synthetic',['NBA'],store,provider)
    assert len(result.slate['events'])==1 and provider.calls==[]
    assert quota_details(store,9,NOW)['used']==9
    assert all('not requested' in row['status'] for row in result.slate['queries'])


def test_provider_failure_does_not_sweep_all_remaining_queries(store,quote,fixed_clock):
    provider=Provider(store,quote)
    def fail(*a):
        provider.calls.append('failure');raise ProviderError('synthetic safe failure')
    provider.odds=fail
    result=run_slate('synthetic',['NBA'],store,provider)
    assert provider.calls==['failure'] and result.errors
    assert any('earlier provider failure' in row['status'] for row in result.slate['queries'])
    run_slate('synthetic',['NBA'],store,provider)
    assert provider.calls==['failure']  # Shared five-minute outage backoff.


def test_pipeline_explicit_autonomous_dispatch_preserves_existing_default(store,quote,fixed_clock):
    provider=Provider(store,quote)
    with patch('intelligence.slate.run_slate',return_value=Analysis()) as automatic:
        run_analysis('synthetic',['NBA'],store,provider,autonomous=True)
        automatic.assert_called_once()


def test_event_window_omits_outside_games_and_labels_discovery_failure(store,quote,fixed_clock):
    provider=Provider(store,replace(quote,commence_time=(NOW+timedelta(days=4)).isoformat()),0)
    result=run_slate('synthetic',['NBA'],store,provider,window_hours=48)
    assert result.slate['events']==[]
    def fail(*a):raise ProviderError('unavailable')
    provider.events=fail
    result=run_slate('synthetic',['MLB'],store,provider)
    assert result.slate['discovery'][0]['status']=='unverified saved fallback'
    assert result.warnings


def test_forecast_recording_uses_post_fetch_time_not_scan_start(store,quote,fixed_clock):
    provider=Provider(store,quote,0)
    finished=NOW+timedelta(seconds=8)
    with patch('intelligence.slate.utcnow',side_effect=[NOW,finished]), \
         patch('intelligence.processing.record_shadow_forecasts',return_value=0) as record:
        run_slate('synthetic',['NBA'],store,provider)
    assert record.call_args.args[2]==finished


def test_pending_public_results_refresh_without_any_new_market_quote(store,quote,fixed_clock):
    provider=Provider(store,quote,0)
    with patch('intelligence.processing.process_cycle',return_value={'pending_public_epl_forecasts':1}), \
         patch('intelligence.epl_forecasts.prepare',return_value={'problem':'synthetic offline gap'}) as prepare, \
         patch('intelligence.processing.label_public_epl',return_value=0) as label:
        result=run_slate('synthetic',['NBA'],store,provider)
    prepare.assert_called_once()
    assert label.call_args.args[1]=={'problem':'synthetic offline gap'}
    assert result.processing['public_epl_target_labels']==0 and provider.calls==[]
