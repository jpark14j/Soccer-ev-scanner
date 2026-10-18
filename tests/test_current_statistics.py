"""Synthetic contract checks; these scores are not model-performance evidence."""
from copy import deepcopy
from datetime import timedelta
import csv, io, json
from pathlib import Path
import pytest
from intelligence.domain import utcnow
from intelligence.openliga import parse, save, current, public_dataset
from intelligence.recent_nba import parse as parse_nba, load_report


def season(now):
    mapping=json.loads(Path('config/openliga_teams.json').read_text())['Bundesliga']
    teams=[{'teamId':int(k),'teamName':v['source_name']} for k,v in mapping.items() if k not in ('199','131','98')]
    rows=[]
    for h in teams:
        for a in teams:
            if h==a:continue
            rows.append({'matchID':len(rows)+1,'leagueShortcut':'bl1','leagueId':4937,'leagueSeason':2026,
                'team1':h,'team2':a,'matchDateTimeUTC':'2026-09-15T13:30:00Z',
                'matchIsFinished':True,'matchResults':[{'resultTypeKind':'After90Minutes','pointsTeam1':1,'pointsTeam2':0}]})
    return rows


def test_full_season_normalization_is_exact_and_failures_retain_success(store):
    now=utcnow();rows=season(now);raw=json.dumps(rows).encode()
    meta=save(store,raw,'Bundesliga',now.isoformat(),now)
    assert meta['coverage']['complete_historical_season'] and meta['coverage']['completed']==306
    first=current(store,'Bundesliga',now)
    for change in ('incomplete','score','team','duplicate','scope'):
        broken=deepcopy(rows)
        if change=='incomplete':broken.pop()
        if change=='score':broken[0]['matchResults'][0]['pointsTeam1']=2
        if change=='team':broken[0]['team1']['teamName']='Unreviewed identity'
        if change=='duplicate':broken[-1]['matchID']=broken[0]['matchID']
        if change=='scope':broken[0]['matchResults'][0]['resultTypeKind']='AfterPenalties'
        with pytest.raises(ValueError):save(store,json.dumps(broken).encode(),'Bundesliga',now.isoformat(),now)
        assert current(store,'Bundesliga',now)==first
    assert len(json.loads(public_dataset(store))['source_datasets'])==1
    assert not any(k in public_dataset(store) for k in ('publications','service_role','reader_token'))


def test_expired_observation_missing_fixture_and_future_scores_are_distinct(store):
    now=utcnow();raw=json.dumps(season(now)).encode()
    assert 'No imported' in current(store,'Bundesliga',now)[1]['problem']
    save(store,raw,'Bundesliga',now.isoformat(),now)
    assert 'expired' in current(store,'Bundesliga',now+timedelta(hours=6))[1]['problem']
    with pytest.raises(ValueError):parse(raw,'Bundesliga',(now+timedelta(seconds=1)).isoformat(),now)
    rows=season(now);rows[0]['matchDateTimeUTC']='2027-01-01T00:00:00Z'
    with pytest.raises(ValueError):parse(json.dumps(rows).encode(),'Bundesliga',now.isoformat(),now)


def test_same_day_finals_are_withheld_without_faking_source_timestamp_or_unplayed_status(store):
    from datetime import datetime,timezone
    from intelligence.openliga import model_inputs
    now=datetime(2026,10,18,23,tzinfo=timezone.utc);rows=season(now)
    rows[0]['matchDateTimeUTC']='2026-10-18T13:30:00Z'
    meta=save(store,json.dumps(rows).encode(),'Bundesliga',now.isoformat(),now)
    assert meta['same_day_finals_withheld']==1
    events,_=current(store,'Bundesliga',now)
    held=next(e for e in events if e.source_event_id=='1')
    assert held.status=='unresolved' and held.home_score is held.away_score is held.source_updated_at is None
    assert held.score_scope=='same_day_final_withheld'
    features,_=model_inputs(store,'Bundesliga',now)
    assert len(features)==305 and all(e.event_date<now.date().isoformat() for e in features)
    # Changing the date alone cannot invent the source's missing cached score.
    tomorrow,_=model_inputs(store,'Bundesliga',now+timedelta(hours=2))
    assert any(e.source_event_id=='1' and e.status=='unresolved' for e in tomorrow)


def test_upcoming_source_fixtures_work_without_prices_and_disappear_when_stale(store):
    from intelligence.fixture_research import fixture_games
    now=utcnow();rows=season(now)
    rows[0]['matchDateTimeUTC']=(now+timedelta(days=5)).isoformat();rows[0]['matchIsFinished']=False;rows[0]['matchResults']=[]
    save(store,json.dumps(rows).encode(),'Bundesliga',now.isoformat(),now)
    games=fixture_games(store,now)
    assert len(games)==1 and games[0]['statistics_fixture'] and 'odds' not in games[0]
    assert fixture_games(store,now,hours=48)==[]
    assert fixture_games(store,now+timedelta(hours=6))==[]


def test_recovered_history_identity_survives_later_receipts_and_changed_scores_cannot_replace_it(store,monkeypatch,tmp_path):
    from dataclasses import replace
    from hashlib import sha256
    from intelligence.event_data import EventObservation
    from intelligence.openliga import complete_history,history_completion
    from intelligence.data_adapters import team_identity
    from intelligence.competitions import COMPETITIONS
    now=utcnow();events=[]
    for r in season(now):
        mapping=json.loads(Path('config/openliga_teams.json').read_text())['Bundesliga']
        names=[mapping[str(r[t]['teamId'])]['canonical'] for t in ('team1','team2')]
        (h,hn),(a,an)=[team_identity(COMPETITIONS['Bundesliga'],n) for n in names]
        events.append(EventObservation('soccer:de:bundesliga','2025-26','synthetic-only',str(r['matchID']),h,a,hn,an,
            '2026-05-01','completed',1,0,now.isoformat(),None,'https://example.test/synthetic-license','source_reported_ft'))
    old=[e if i<294 else replace(e,status='unresolved',home_score=None,away_score=None) for i,e in enumerate(events)]
    raw=b'{}';(tmp_path/'config').mkdir()
    (tmp_path/'config/multi_source_snapshot.json').write_text(json.dumps({'files':{'2025-26/de.1.json':sha256(raw).hexdigest()}}))
    monkeypatch.setattr('intelligence.openliga.ROOT',tmp_path)
    monkeypatch.setattr('intelligence.data_adapters.openfootball',lambda *args:old)
    monkeypatch.setattr('intelligence.expanded_models.load',lambda *args:{'artifact_sha256':'synthetic-base'})
    meta={'coverage':{'complete_historical_season':True},'sha256':'synthetic-source'}
    monkeypatch.setattr('intelligence.openliga.parse',lambda *args,**kwargs:(events,meta))
    first=complete_history(store,raw,raw,now.isoformat(),now)
    later=complete_history(store,raw,raw,(now+timedelta(minutes=5)).isoformat(),now+timedelta(minutes=5))
    assert later==first and later['sha256']==first['sha256']
    events[-1]=replace(events[-1],home_score=2)
    with pytest.raises(ValueError,match='Recovered historical results changed'):complete_history(store,raw,raw,now.isoformat(),now)
    assert history_completion(store,now)==first


def nba_file():
    from intelligence.team_codes import NBA
    codes=sorted({v[0] for v in NBA.values()});circle=codes[:];games=[]
    for i in range(82):
        for j in range(15):
            a,b=circle[j],circle[-1-j];day=(__import__('datetime').date(2022,10,18)+timedelta(days=i)).isoformat()
            for team,opponent,home,p,op in ((a,b,True,110,100),(b,a,False,100,110)):
                games.append(dict(season='2022-23',team=team,opponent=opponent,game_date=day,home=str(home),
                    points=p,opponent_points=op,point_diff=p-op,result='W' if p>op else 'L'))
        circle=[circle[0],circle[-1],*circle[1:-1]]
    return games


def csv_bytes(rows):
    f=io.StringIO();w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows);return f.getvalue().encode()


def test_nba_two_rows_become_one_game_no_invented_home_for_neutral_venue():
    rows=nba_file();frame=parse_nba(csv_bytes(rows),'2022-23')
    assert len(frame)==1230 and frame.game_id.is_unique
    rows[0]['home']='False'
    assert len(parse_nba(csv_bytes(rows),'2022-23'))==1229
    rows[0]['points']=111
    with pytest.raises(ValueError):parse_nba(csv_bytes(rows),'2022-23')


@pytest.mark.parametrize('change',['missing','duplicate','future','unknown','opposing_score','both_home'])
def test_nba_unsafe_or_incomplete_sources_never_reach_model(change):
    rows=nba_file()
    if change=='missing':rows.pop()
    if change=='duplicate':rows[-1]=rows[0]
    if change=='future':rows[0]['game_date']='2027-01-01'
    if change=='unknown':rows[0]['team']='INVENTED'
    if change=='opposing_score':rows[1]['opponent_points']=120
    if change=='both_home':rows[1]['home']='True'
    with pytest.raises(ValueError):parse_nba(csv_bytes(rows),'2022-23')


def test_recent_nba_report_contains_real_recent_oos_evidence_and_cannot_approve():
    r=load_report();assert r and r['history_n']==4910 and r['test_n']==1225
    assert r['test_start']>'2025-06-30' and r['data_end']=='2026-04-12'
    assert r['calibration_end']<r['test_start'] and not r['approved'] and not r['replaces_incumbent']
    assert r['minus_baseline']['binary_brier']['interval'][1]<0
    assert not r['current_forecasts_enabled']


def test_recent_mlb_report_uses_full_2025_test_without_claiming_current_2026_predictions():
    from intelligence.recent_mlb import load_report as mlb_report
    r=mlb_report();assert r and r['history_n']==7276 and r['test_n']==2426 and r['paired_test_n']==2414
    assert r['calibration_end']<r['test_start'] and r['test_end']=='2025-09-28'
    assert not r['approved'] and not r['current_forecasts_enabled'] and not r['replaces_incumbent']
    assert r['metrics']['binary_brier']['value']<r['baseline']['binary_brier']['value']
