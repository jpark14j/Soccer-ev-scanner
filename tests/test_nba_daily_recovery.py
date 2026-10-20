"""SYNTHETIC provider contracts, not genuine current NBA forecasts."""
from datetime import datetime,timedelta,timezone
from urllib.parse import urlsplit,parse_qs
import json
import pytest
from intelligence.free_results import Collector,PublicSourceUnavailable,NBA_URL,SCOPES
from intelligence.nba_current import save,current,fixtures
from test_free_results import schedule,receipt
from unittest.mock import patch,MagicMock

NOW=datetime(2026,10,20,12,tzinfo=timezone.utc)
OLD=NOW-timedelta(hours=18)


def registry(store):
    data=schedule();data['generated']=OLD.isoformat()
    for i,r in enumerate(data['events']):r['date_utc']=(NOW+timedelta(days=i//6)).date().isoformat()
    value=receipt(data,OLD)
    fixtures(value,NOW)  # A valid reviewed-format full-season registry.
    store.cache('public-source-nba-fixtures',value,OLD)
    return value,data


def daily(data,day):
    return {'sport':'basketball','date':day,'count':sum(r['date_utc']==day for r in data['events']),
        'matches':[{'competition':SCOPES['NBA'][1],'home':r['home_team'],'away':r['away_team'],
            'status':'upcoming','time':day+'T23:00:00+00:00','home_score':None,'away_score':None,
            'url':'/basketball/match/synthetic-'+str(i)} for i,r in enumerate(data['events']) if r['date_utc']==day]}


def test_daily_fallback_verifies_whole_window_without_redating_archived_registry(store):
    original,data=registry(store);calls=[]
    def fetch(url):
        calls.append(url)
        if url==NBA_URL:raise PublicSourceUnavailable('Synthetic HTTP 503')
        day=parse_qs(urlsplit(url).query)['date'][0]
        return json.dumps(daily(data,day)).encode(),NOW.isoformat()
    meta=save(Collector(store,NOW,fetch))
    assert len(calls)==9 and meta['checked_at']==NOW.isoformat()
    assert 'Daily verified window' in meta['fixture_verification']
    assert meta['source_receipts'][0]['checked_at']==OLD.isoformat()
    assert store.cached('public-source-nba-fixtures',86400,NOW)==original
    events,_=current(store,NOW)
    assert len(events)==48 and all(e.observed_at==NOW.isoformat() for e in events)
    assert not current(store,NOW+timedelta(hours=6))[1]['ok']


def test_incomplete_daily_feed_cannot_activate_a_fresh_nba_snapshot(store):
    registry(store)
    def fetch(url):
        if url==NBA_URL:raise PublicSourceUnavailable('Synthetic temporary failure')
        day=parse_qs(urlsplit(url).query)['date'][0]
        return json.dumps({'sport':'basketball','date':day,'count':0,'matches':[]}).encode(),NOW.isoformat()
    with pytest.raises(ValueError,match='incomplete'):save(Collector(store,NOW,fetch))
    assert not current(store,NOW)[1]['ok']


def test_malformed_primary_calendar_does_not_replace_verified_raw_registry_or_trigger_fallback(store):
    original,_=registry(store);calls=[]
    def malformed(url):calls.append(url);return b'{}',NOW.isoformat()
    with pytest.raises(ValueError):save(Collector(store,NOW,malformed))
    assert calls==[NBA_URL]
    assert store.cached('public-source-nba-fixtures',86400,NOW)==original


def test_unverified_future_game_does_not_block_other_independently_verified_future_games(store):
    _,data=registry(store)
    def fetch(url):
        if url==NBA_URL:raise PublicSourceUnavailable('Synthetic HTTP 503')
        day=parse_qs(urlsplit(url).query)['date'][0];body=daily(data,day)
        if day=='2026-10-22':body.update(count=0,matches=[])
        return json.dumps(body).encode(),NOW.isoformat()
    meta=save(Collector(store,NOW,fetch));events,_=current(store,NOW)
    assert len(events)==42 and len(meta['unverified_future_fixtures'])==6
    assert all(e.event_date!='2026-10-22' for e in events)


def test_utc_midnight_overlap_is_filtered_without_relabeling_a_game():
    from intelligence.free_results import parse_day
    from test_free_results import day_response
    body=day_response('NBA','2026-10-20');body['matches'][0].update(status='upcoming',time='2026-10-21T00:00:00+00:00')
    assert parse_day(receipt(body,NOW),'NBA','2026-10-20',NOW)==[]
    body['date']='2026-10-21'
    events=parse_day(receipt(body,NOW),'NBA','2026-10-21',NOW)
    assert len(events)==1 and events[0].kickoff=='2026-10-21T00:00:00+00:00'
    body['date']='2026-10-20';body['matches'][0]['time']='2026-10-21T01:00:00+00:00'
    with pytest.raises(ValueError):parse_day(receipt(body,NOW),'NBA','2026-10-20',NOW)


def test_daily_source_allowlist_supports_the_2027_part_of_the_reviewed_season():
    from intelligence.free_results import download
    session=MagicMock();response=session.__enter__.return_value.get.return_value
    response.status_code=200;response.iter_content.return_value=[b'{}']
    with patch('intelligence.free_results.requests.Session',return_value=session):
        raw,_=download('https://sportscore.com/api/v1/fixtures/?sport=basketball&date=2027-01-14&competition=national-basketball-association&limit=20')
    assert raw==b'{}'
    response.close.assert_called_once()
