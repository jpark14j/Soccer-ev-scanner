"""SYNTHETIC price/approval contracts; never real model or live-price evidence."""
from dataclasses import replace
from datetime import timedelta
import pytest
from conftest import NOW
from intelligence.providers import normalize,LEAGUES
from intelligence.pipeline import Analysis
from intelligence.positive_ev import shortlist
from intelligence.parlays import CombinedPrice,JointEstimate


@pytest.mark.parametrize('league',['NBA','MLB','Premier League'])
def test_ingestion_to_conservative_ev_and_two_three_leg_slots(league,store,quote,estimate):
    # Only this isolated test supplies approved fixture evidence. No shipped
    # model is modified, a provider is never constructed, and nothing published.
    payload=[]
    for i in range(3):
        payload.append({'id':f'SYNTHETIC-{i}','sport_key':LEAGUES[league][1],
            'home_team':f'Synthetic Home {i}','away_team':f'Synthetic Away {i}',
            'commence_time':(NOW+timedelta(days=1+i)).isoformat(),
            'bookmakers':[{'key':quote.bookmaker,'title':'Synthetic contract fixture only',
                'markets':[{'key':'h2h','last_update':NOW.isoformat(),'outcomes':[{'name':f'Synthetic Home {i}','price':1.9}]}]}]})
    quotes,rejected=normalize(payload,league,NOW.isoformat(),NOW)
    assert len(quotes)==3 and rejected==0
    e=replace(estimate,sport=LEAGUES[league][0],league=league)
    analysis=Analysis(quotes=quotes,estimates={q.id:e for q in quotes})
    prices=[];joint=[]
    for n,p,lower,odds in [(2,.4,.3,3.6),(3,.28,.2,5.2)]:
        ids=tuple(q.id for q in quotes[:n]);prices.append(CombinedPrice(quote.bookmaker,ids,odds,NOW.isoformat(),True,'SYNTHETIC ticket contract'))
        joint.append(JointEstimate(p,lower,p+.1,ids,'SYNTHETIC joint evidence',True))
    result=shortlist(analysis,store,{quote.bookmaker},[league],NOW,prices,joint)
    assert result['qualified']==3
    for n in (1,2,3):
        w=result['winners'][n]
        assert w['ev']==pytest.approx(w['probability']*w['odds']-1)
        assert w['conservative_ev']==pytest.approx(w['lower']*w['odds']-1)
        assert w['conservative_ev']>=.02
    # Identical prices cannot rescue an unapproved or stale model/quote.
    analysis.estimates={q.id:replace(e,validated=False) for q in quotes}
    assert shortlist(analysis,store,{quote.bookmaker},[league],NOW,prices,joint)['qualified']==0
    analysis.estimates={q.id:e for q in quotes}
    assert shortlist(analysis,store,{quote.bookmaker},[league],NOW+timedelta(minutes=6),prices,joint)['qualified']==0
    assert shortlist(analysis,store,{quote.bookmaker},[league],NOW,prices,[])['winners'][2] is None
    with store.connect() as db:assert db.execute('SELECT count(*) FROM publications').fetchone()[0]==0


def test_offline_verifier_cannot_initialize_missing_store(tmp_path):
    from intelligence.verify_snapshot import inspect
    target=tmp_path/'does-not-exist.sqlite3'
    with pytest.raises(ValueError,match='empty initialization is forbidden'):inspect(target)
    assert not target.exists()
