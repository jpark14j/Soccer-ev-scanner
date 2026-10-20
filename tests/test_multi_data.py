"""Synthetic contracts verify data handling, never claimed as real sport results."""
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
import json
import sqlite3
from unittest.mock import patch
import pytest
from conftest import NOW
from intelligence.competitions import COMPETITIONS,BY_ID,expected_games
from intelligence.event_data import EventObservation,ingest,reconciled,coverage,pregame_features
from intelligence.data_adapters import openfootball,team_identity,provider_results
from intelligence.public_results import get_public,current


def event(**changes):
    e=EventObservation(COMPETITIONS['Bundesliga'].id,'2026-27','synthetic','fixture-one',
        'soccer:club:de:home','soccer:club:de:away','Synthetic Home','Synthetic Away','2026-10-14','completed',2,1,
        NOW.isoformat(),None,'https://example.test/license','source_reported_ft')
    return replace(e,**changes)


META={'sha256':'synthetic-content-hash','license_reference':'https://example.test/license'}


def test_competition_ids_are_stable_and_targets_are_not_implemented_claims():
    assert len(COMPETITIONS)==len(BY_ID)
    assert COMPETITIONS['Bundesliga'].id=='soccer:de:bundesliga'
    assert COMPETITIONS['World Cup'].source_file is None
    assert COMPETITIONS['Conference League'].odds_name is None
    assert expected_games(COMPETITIONS['Ligue 1'],'2022-23')==380
    assert expected_games(COMPETITIONS['Ligue 1'],'2023-24')==306
    assert expected_games(COMPETITIONS['NBA'],'2026') is None


def test_team_reconciliation_is_explicit_scoped_and_not_fuzzy():
    c=COMPETITIONS['Ligue 1']
    assert team_identity(c,'AS Monaco FC')==team_identity(c,'Monaco')
    assert team_identity(c,'RC Strasbourg Alsace')==team_identity(c,'RC Strasbourg')
    assert team_identity(COMPETITIONS['NBA'],'BKN')[0]==team_identity(COMPETITIONS['NBA'],'Brooklyn Nets')[0]
    with pytest.raises(ValueError):team_identity(c,'Monacoo')
    with pytest.raises(ValueError):team_identity(COMPETITIONS['Bundesliga'],'AS Monaco')


def public_raw(score=None,day='2026-10-17'):
    return json.dumps({'matches':[{'team1':'FC Bayern München','team2':'Borussia Dortmund','date':day,'score':score}]}).encode()


def test_missing_score_is_not_zero_and_future_result_is_rejected():
    rows=openfootball(public_raw([]),'Bundesliga','2026-27',NOW.isoformat(),NOW)
    assert rows[0].status=='scheduled' and rows[0].home_score is None
    rows=openfootball(public_raw(None,'2026-10-10'),'Bundesliga','2026-27',NOW.isoformat(),NOW)
    assert rows[0].status=='unresolved'
    with pytest.raises(ValueError):openfootball(public_raw({'ft':[1,0]}),'Bundesliga','2026-27',NOW.isoformat(),NOW)
    with pytest.raises(ValueError):openfootball(public_raw({'ft':[True,0]},'2026-10-10'),'Bundesliga','2026-27',NOW.isoformat(),NOW)


def test_duplicate_snapshot_rejected_atomically_and_receipts_do_not_duplicate(store):
    with pytest.raises(ValueError,match='Duplicate'):ingest(store,[event(),event()],META,NOW)
    assert not reconciled(store,COMPETITIONS['Bundesliga'].id,NOW)
    assert ingest(store,[event()],META,NOW)['added_observations']==1
    assert ingest(store,[event(observed_at=(NOW+timedelta(hours=1)).isoformat())],META,NOW+timedelta(hours=1))['added_observations']==0
    with store.connect() as db:
        with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM event_observations')


def test_conflicts_across_sources_are_preserved_and_cannot_become_team_features(store):
    ingest(store,[event()],META,NOW)
    ingest(store,[event(source='second-source',home_score=3)],META|{'sha256':'second'},NOW)
    records=reconciled(store,COMPETITIONS['Bundesliga'].id,NOW)
    assert len(records)==1 and records[0]['conflicts'] and records[0]['versions']==2
    f=pregame_features(store,COMPETITIONS['Bundesliga'].id,event().home_id,NOW)
    assert f['prior_games']==0 and f['blockers'] and f['recent_goals_or_points_for'] is None


def test_withdrawn_result_and_changed_date_require_review(store):
    ingest(store,[event()],META,NOW)
    ingest(store,[event(status='unresolved',home_score=None,away_score=None,event_date='2026-10-13')],META|{'sha256':'changed'},NOW)
    conflicts=reconciled(store,COMPETITIONS['Bundesliga'].id,NOW)[0]['conflicts']
    assert any('withdrawn' in s for s in conflicts) and any('date changed' in s for s in conflicts)


def test_availability_cutoff_never_backdates_an_archive_observation(store):
    ingest(store,[event()],META,NOW)
    c=COMPETITIONS['Bundesliga']
    assert pregame_features(store,c.id,event().home_id,NOW-timedelta(days=1))['prior_games']==0
    actual=pregame_features(store,c.id,event().home_id,NOW)
    assert actual['prior_games']==1 and actual['result_based_rest_days']==2 and actual['recent_goals_or_points_for']==2
    assert 'Player availability' in actual['unverified_features']


def test_completeness_does_not_assume_missing_fixtures_or_scores_are_played():
    c=COMPETITIONS['Bundesliga'];r=coverage([event()],c,'2026-27',NOW)
    assert r['expected_season_games']==306 and r['completed']==1 and not r['complete_historical_season']
    # 306 rows from an incorrect 19-club population is not a full Bundesliga season.
    from itertools import islice
    pairs=islice(((h,a) for h in range(19) for a in range(19) if h!=a),306)
    bad=[event(source_event_id=f'{h}-{a}',home_id=str(h),away_id=str(a)) for h,a in pairs]
    report=coverage(bad,c,'2026-27',NOW)
    assert report['completed']==306 and not report['complete_fixture_schedule'] and not report['complete_historical_season']


class PublicSession:
    def __init__(self,raw=b'public-data'):
        self.calls=[];self.raw=raw
    def get(self,url,**kwargs):
        self.calls.append(url)
        assert url.startswith('https://raw.githubusercontent.com/openfootball/football.json/master/')
        assert 'headers' not in kwargs and 'params' not in kwargs
        raw=self.raw
        class Response:
            status_code=200
            def iter_content(self,n):yield raw
            def close(self):pass
        return Response()


def test_public_budget_cache_and_endpoint_allowlist_never_change_odds_budget(store):
    store.reserve(9,9,NOW);session=PublicSession()
    paths=['LICENSE.md',*[f'2026-27/{c.source_file}.json' for c in COMPETITIONS.values() if c.source_file]]
    for path in paths:assert get_public(store,path,NOW,session)['ok']
    assert len(session.calls)==6
    assert get_public(store,paths[0],NOW,session)['ok'] and len(session.calls)==6
    with store.connect() as db:db.execute("DELETE FROM cache WHERE key LIKE 'public-results-v1-%'")
    assert not get_public(store,paths[0],NOW,session)['ok'] and len(session.calls)==6
    with store.connect() as db:
        assert db.execute('SELECT used FROM budget').fetchone()[0]==9
        assert db.execute('SELECT used FROM public_result_budget').fetchone()[0]==6
    with pytest.raises(ValueError):get_public(store,'../../private',NOW,session)


def test_license_change_blocks_before_fetching_scores(store):
    session=PublicSession(b'not the reviewed license')
    rows,meta=current(store,'Bundesliga',NOW,session)
    assert not rows and not meta['ok'] and 'license changed' in meta['problem']
    assert len(session.calls)==1


def test_unimplemented_competition_does_not_make_a_speculative_request(store):
    session=PublicSession()
    rows,meta=current(store,'World Cup',NOW,session)
    assert not rows and not meta['ok'] and 'discovery target' in meta['problem']
    assert not session.calls


def test_public_failure_is_cached_and_raw_exception_is_not_logged_or_returned(store):
    import requests
    class BadSession:
        calls=0
        def get(self,*a,**k):
            self.calls+=1;raise requests.ConnectionError('secret-synthetic-do-not-display')
    session=BadSession();first=get_public(store,'LICENSE.md',NOW,session)
    assert not first['ok'] and 'secret-synthetic' not in str(first)
    assert get_public(store,'LICENSE.md',NOW,session)==first and session.calls==1


def test_existing_provider_bridge_uses_local_results_only_and_preserves_conflicts(store):
    from intelligence.results import ensure_table,history_from_results
    from intelligence.domain import digest
    ensure_table(store)
    row={'provider':'the-odds-api','league':'NBA','event_id':'synthetic-result','home':'Toronto Raptors','away':'Boston Celtics',
         'home_score':100,'away_score':99,'commence_time':'2026-10-14T00:00:00Z','observed_at':'2026-10-14T03:00:00Z','received_at':'2026-10-14T04:00:00Z'}
    with store.connect() as db:
        for value in (row,row|{'home_score':101,'observed_at':'2026-10-14T03:30:00Z'}):
            db.execute('INSERT INTO observed_results VALUES(?,?,?)',(digest(value),'NBA',json.dumps(value)))
    result=provider_results(store,NOW)
    assert result['normalized']==2
    assert reconciled(store,COMPETITIONS['NBA'].id,NOW)[0]['conflicts']
    assert history_from_results('NBA',store).empty
    with store.connect() as db:assert db.execute('SELECT count(*) FROM budget').fetchone()[0]==0


@pytest.mark.parametrize('entrypoint',['provider','non_autonomous_pipeline'])
def test_legacy_entrypoints_cannot_default_above_nine_credits(store,monkeypatch,entrypoint):
    from intelligence.domain import utcnow
    from intelligence.providers import OddsAPI,ProviderError
    from intelligence.pipeline import run_analysis
    from intelligence.research_refresh import credit_status
    monkeypatch.delenv('ODDS_DAILY_CREDITS',raising=False)
    now=utcnow();store.reserve(9,9,now)
    if entrypoint=='provider':
        with pytest.raises(ProviderError,match='budget exhausted'):
            OddsAPI('synthetic-key-only',store).odds('NBA')
    else:
        result=run_analysis('synthetic-key-only',['NBA'],store=store,collect_results=False)
        assert result.errors and 'budget exhausted' in result.errors[0]
    assert credit_status(store)==(9,9)
