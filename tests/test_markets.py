from dataclasses import replace
from datetime import timedelta
import pytest
import requests
from conftest import NOW
from intelligence.providers import OddsAPI, ProviderError, normalize
from intelligence.registry import eligible_book, load_registry
from intelligence.ev import expected_value, remove_margin, market_baselines, qualify, best_prices


def event():
    return {'id':'fixture','sport_key':'basketball_nba','home_team':'Home','away_team':'Away',
            'commence_time':'2026-10-17T01:00:00Z','bookmakers':[
                {'key':'betmgm_ca_on','title':'Test Ontario book','last_update':'2026-10-16T01:59:00Z',
                 'markets':[{'key':'h2h','outcomes':[{'name':'Home','price':1.9},{'name':'Away','price':2.1}]}]}]}


def test_ev_and_pushes():
    assert expected_value(.6,1.9)==pytest.approx(.14)
    assert expected_value(.5,2.,.1)==pytest.approx(.1)
    assert expected_value(0.,2.)==-1
    assert expected_value(1.,2.)==1
    assert sum(remove_margin([1.9,1.9]))==pytest.approx(1)


@pytest.mark.parametrize('p,o,push',[(float('nan'),2,0),(.5,float('inf'),0),(True,2,0),(-.1,2,0),(.9,2,.2),(.5,1,0)])
def test_invalid_ev(p,o,push):
    with pytest.raises(ValueError): expected_value(p,o,push)


def test_ontario_mapping_never_substitutes_us():
    assert eligible_book('betmgm_ca_on',NOW)
    assert eligible_book('pointsbetca',NOW)
    assert not eligible_book('draftkings',NOW)
    assert not eligible_book('playnow_ca',NOW)
    assert not eligible_book('pinnacle',NOW)
    assert not eligible_book('betmgm_ca_on',NOW+timedelta(days=60))


def test_normalize_source_timestamp_and_missing_timestamp():
    e = event()
    q,rejected = normalize([e],'NBA','2026-10-16T01:59:01Z',NOW)
    assert len(q)==2 and rejected==0
    assert q[0].source_updated_at=='2026-10-16T01:59:00Z'
    assert q[0].jurisdiction=='CA-ON'
    del e['bookmakers'][0]['last_update']
    q,rejected = normalize([e],'NBA','2026-10-16T01:59:01Z',NOW)
    assert not q and rejected==2


@pytest.mark.parametrize('price',[float('nan'),float('inf'),True,1,-2,'2.0'])
def test_bad_provider_price(price):
    e = event()
    e['bookmakers'][0]['markets'][0]['outcomes'][0]['price']=price
    q,rejected=normalize([e],'NBA','2026-10-16T01:59:01Z',NOW)
    assert len(q)==1 and rejected==1


def test_duplicate_quote_and_sport_mismatch_rejected():
    e = event()
    e['bookmakers'] += e['bookmakers']
    q,n = normalize([e],'NBA','2026-10-16T01:59:01Z',NOW)
    assert q==[] and n==4
    assert normalize([e],'MLB','2026-10-16T01:59:01Z',NOW)[0]==[]


def test_price_comparison_only_equivalent_selections(quote,estimate):
    a=qualify(quote,estimate,NOW)[0]
    b=qualify(replace(quote,bookmaker='betrivers_ca_on',odds=2.),estimate,NOW)[0]
    c=qualify(replace(quote,selection='Away',odds=2.2),estimate,NOW)[0]
    best=best_prices([a,b,c])
    assert len(best)==2
    assert next(o for o in best if o.quote.selection=='Home').quote.odds==2.
    assert replace(quote,point=2.5).key != replace(quote,point=3.5).key
    assert replace(quote,participant='Player A').key != replace(quote,participant='Player B').key


def test_stale_live_suspended_future_never_qualify(quote,estimate):
    for changed in [replace(quote,source_updated_at='2026-10-16T01:00:00Z'),
                    replace(quote,commence_time='2026-10-16T01:59:00Z'),
                    replace(quote,suspended=True),replace(quote,received_at='2026-10-17T00:00:00Z')]:
        assert qualify(changed,estimate,NOW)[0] is None
    assert qualify(quote,replace(estimate,validated=False),NOW)[0] is None
    assert qualify(quote,replace(estimate,lower=.4),NOW)[0] is None
    assert qualify(quote,replace(estimate,sport='MLB'),NOW)[0] is None


def test_complete_market_consensus_excludes_target(quote):
    other=replace(quote,selection='Away',odds=2.1)
    peers=[replace(quote,bookmaker='betrivers_ca_on',odds=2.0),replace(other,bookmaker='betrivers_ca_on',odds=2.0)]
    consensus=market_baselines([quote,other,*peers],NOW)
    assert consensus[quote.id]['probability']==pytest.approx(.5)
    assert market_baselines([quote,*peers[:1]],NOW)=={}


class Response:
    status_code=200
    headers={'x-requests-remaining':'100','x-requests-last':'1'}
    def json(self): return []


class Session:
    def __init__(self,response=None,error=None): self.calls=0; self.response=response or Response(); self.error=error
    def get(self,*args,**kwargs):
        self.calls+=1
        if self.error: raise self.error
        return self.response


def test_provider_cache_budget_and_redacted_errors(store):
    session=Session()
    api=OddsAPI('TEST_SECRET',store,daily_limit=1,session=session)
    api.odds('NBA'); api.odds('NBA')
    assert session.calls==1
    with pytest.raises(ProviderError,match='budget'): api.odds('MLB')
    bad=OddsAPI('TEST_SECRET',store,daily_limit=10,session=Session(error=requests.RequestException('https://example/?apiKey=TEST_SECRET')))
    with pytest.raises(ProviderError) as e: bad.odds('MLB')
    assert 'TEST_SECRET' not in str(e.value)


def test_http_error_never_contains_url_or_body(store):
    response=Response(); response.status_code=401
    api=OddsAPI('TEST_SECRET',store,session=Session(response))
    with pytest.raises(ProviderError,match='HTTP 401') as e: api.odds('NBA')
    assert 'TEST_SECRET' not in str(e.value)


@pytest.mark.parametrize('field,value',[('bookmakers',None),('bookmakers',['bad'])])
def test_malformed_nested_events_fail_closed(field,value):
    e=event(); e[field]=value
    q,n=normalize([e],'NBA','2026-10-16T01:59:01Z',NOW)
    assert q==[] and n>0


def test_event_props_preserve_player_line_and_period(store):
    class PropSession(Session):
        def get(self,url,params,timeout):
            self.calls+=1
            assert '/events/fixture/odds' in url
            assert params['regions']=='ca' and params['markets']=='player_points'
            e=event()
            e['bookmakers'][0]['markets']=[{'key':'player_points','outcomes':[
                {'name':'Over','description':'Test Player','point':20.5,'price':1.9},
                {'name':'Under','description':'Test Player','point':20.5,'price':1.9}]}]
            class PropResponse(Response):
                def json(self): return e
            return PropResponse()
    r=OddsAPI('test',store,session=PropSession()).event_odds('NBA','fixture',('player_points',))
    q,n=normalize(r['data'],'NBA',r['received_at'],NOW)
    assert n==0 and len(q)==2
    assert q[0].participant=='Test Player' and q[0].point==20.5
