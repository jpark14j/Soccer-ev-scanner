import pytest
from conftest import NOW
from intelligence.results import normalize_results,collect,history_from_results


def completed():
    return {'id':'test-result','sport_key':'basketball_nba','commence_time':'2026-10-14T00:00:00Z',
            'completed':True,'home_team':'Home','away_team':'Away','last_update':'2026-10-14T03:00:00Z',
            'scores':[{'name':'Home','score':'100'},{'name':'Away','score':'90'}]}


def test_completed_results_require_final_matching_teams_and_real_timestamps():
    e=completed()
    assert len(normalize_results([e],'NBA','2026-10-14T04:00:00Z',NOW))==1
    e['completed']=False
    assert normalize_results([e],'NBA','2026-10-14T04:00:00Z',NOW)==[]
    e['completed']=True; e['scores'][0]['score']='unknown'
    assert normalize_results([e],'NBA','2026-10-14T04:00:00Z',NOW)==[]


def test_results_collection_is_cached_and_keeps_source_identity(store,monkeypatch):
    monkeypatch.setattr('intelligence.results.utcnow',lambda:NOW)
    class Provider:
        calls=0
        def scores(self,league,days_from):
            self.calls+=1
            return {'data':[completed()],'received_at':'2026-10-14T04:00:00Z'}
    p=Provider()
    collect(p,store,['NBA']); collect(p,store,['NBA'])
    assert p.calls==1
    history=history_from_results('NBA',store)
    assert len(history)==1 and history.iloc[0].FTHG==100
    assert history.iloc[0].game_id=='test-result'


def test_incomplete_result_does_not_settle_or_create_history(store,monkeypatch):
    monkeypatch.setattr('intelligence.results.utcnow',lambda:NOW)
    class Provider:
        def scores(self,*a,**k): return {'data':[{'completed':False}],'received_at':NOW.isoformat()}
    collect(Provider(),store,['NBA'])
    assert history_from_results('NBA',store).empty
    assert store.records()==[]
