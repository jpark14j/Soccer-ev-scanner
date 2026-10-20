"""Synthetic source contracts only; not evidence of actual game predictions."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from dataclasses import replace
from hashlib import sha256
import json
from unittest.mock import patch
import pytest
from intelligence.domain import digest
from intelligence.free_results import Collector,parse_day,reconcile_archive,identity,refresh,download,SCOPES,TERMS
from intelligence.nba_current import fixtures,current,forecasts
from intelligence.event_data import EventObservation
from intelligence.statistics_forward import record,reconcile
from intelligence.prediction_accuracy import saved_for_display,summary
from intelligence.fixture_research import collect,combinations_for,fixture_games

NOW=datetime(2026,10,19,18,tzinfo=timezone.utc)


def receipt(data,now=NOW):
    raw=json.dumps(data).encode()
    return {'raw':raw.decode(),'checked_at':now.isoformat(),'sha256':sha256(raw).hexdigest(),
        'source_url':'https://sporting-events.org/data/nba.json'}


def schedule():
    from intelligence.team_codes import NBA
    names=list(dict.fromkeys(NBA))
    names.remove('Los Angeles Clippers')
    events=[]
    for i in range(1020):
        h=names[i%30];a=names[(i+1)%30];day=datetime(2026,10,20,23,tzinfo=timezone.utc)+timedelta(days=i//30)
        events.append({'date_utc':day.date().isoformat(),'time_utc':'23:00','home_team':h,'away_team':a,
            'fixture':a+' at '+h,'status':'scheduled'})
    return {'competition':'NBA','generated':NOW.isoformat(),'source':'https://sporting-events.org/data/nba/',
        'event_count':len(events),'events':events}


def save_fixture_cache(store):
    source=receipt(schedule());es=fixtures(source,NOW)
    from dataclasses import asdict
    meta={'ok':True,'provider':'sporting-events + sportscore','checked_at':NOW.isoformat(),
        'sha256':source['sha256'],'coverage':{'fixtures':len(es),'completed':0,'unresolved_past':0}}
    store.cache('nba-current',{'events':[asdict(e) for e in es],'meta':meta},NOW)
    return es,meta


def day_response(league='Premier League',day='2026-10-18'):
    nba=league=='NBA'
    return {'sport':'basketball' if nba else 'football','date':day,'count':1,'matches':[
        {'competition':SCOPES[league][1],'home':'Boston Celtics' if nba else 'Arsenal',
         'away':'New York Knicks' if nba else 'Chelsea','home_score':'110' if nba else '2',
         'away_score':'105' if nba else '0','status':'finished','time':day+'T15:00:00+00:00',
         'url':'/basketball/match/synthetic' if nba else '/football/match/synthetic'}]}


@pytest.mark.parametrize('mutation',['count','competition','date','alias','score','duplicate','future','status','nba_tie'])
def test_daily_results_fail_closed(mutation):
    league='NBA' if mutation=='nba_tie' else 'Premier League';data=day_response(league)
    r=data['matches'][0]
    if mutation=='count':data['count']=20
    if mutation=='competition':r['competition']='Different competition'
    if mutation=='date':data['date']='2026-10-17'
    if mutation=='alias':r['home']='Unreviewed club'
    if mutation=='score':r['home_score']=True
    if mutation=='duplicate':data['matches']*=2;data['count']=2
    if mutation=='future':r['time']='2026-10-20T15:00:00+00:00'
    if mutation=='status':r['status']='guessed'
    if mutation=='nba_tie':r['away_score']=r['home_score']
    with pytest.raises(ValueError):parse_day(receipt(data),league,'2026-10-18',NOW)


def test_finals_identity_and_same_day_withholding():
    r=parse_day(receipt(day_response()),'Premier League','2026-10-18',NOW)[0]
    assert r.status=='completed' and r.home_score==2 and r.license_reference==TERMS
    data=day_response(day='2026-10-19')
    held=parse_day(receipt(data),'Premier League','2026-10-19',NOW)[0]
    assert held.status=='unresolved' and held.home_score is None and held.score_scope=='same_day_final_withheld'
    assert identity('Ligue 1','Le Mans')==identity('Ligue 1','Le Mans FC')
    assert identity('Ligue 1','Havre Athletic Club')==identity('Ligue 1','Le Havre AC')


def test_newly_fetched_live_score_is_not_a_final_or_an_application_cache_problem():
    data=day_response();data['matches'][0]['status']='live'
    event=parse_day(receipt(data),'Premier League','2026-10-18',NOW)[0]
    assert event.status=='unresolved' and event.score_scope=='source_live'
    assert event.home_score is None and event.away_score is None
    from intelligence.current_soccer import _prepare
    meta={'ok':True,'provider':'sportscore','checked_at':NOW.isoformat(),
        'coverage':{'unresolved_past':1}}
    result=_prepare('Premier League',None,NOW,False,lambda *a,**k:([event],meta))
    assert 'Arsenal vs Chelsea' in result['problem'] and 'source_live' in result['problem']
    assert event.kickoff in result['problem'] and 'unresolved' in result['problem']


def test_public_http_failure_reports_safe_source_and_status_without_response_content():
    from unittest.mock import MagicMock
    session=MagicMock();response=session.__enter__.return_value.get.return_value
    response.status_code=503
    response.content=b'synthetic-private-response-must-not-be-reported'
    with patch('intelligence.free_results.requests.Session',return_value=session):
        with pytest.raises(ValueError,match=r'Sporting Events NBA fixtures; HTTP 503') as error:
            download('https://sporting-events.org/data/nba.json')
    assert 'synthetic-private-response' not in str(error.value)
    response.close.assert_called_once()


def test_nba_results_use_reviewed_competition_slug_not_empty_nba_alias(store):
    calls=[]
    def fetch(url):
        calls.append(url)
        return json.dumps(day_response('NBA')).encode(),NOW.isoformat()
    c=Collector(store,NOW,fetch);events,_=c.day('NBA','2026-10-18')
    assert 'competition=national-basketball-association&' in calls[0]
    assert 'competition=nba&' not in calls[0]
    assert len(events)==1 and events[0].home_score==110


def test_completed_result_conflicts_and_unknown_pairs_rejected():
    event=parse_day(receipt(day_response()),'Premier League','2026-10-18',NOW)[0]
    assert reconcile_archive([replace(event,status='unresolved',home_score=None,away_score=None)],[event])==[event]
    for wrong in (replace(event,home_score=3),replace(event,event_date='2026-10-17'),replace(event,away_id='unknown')):
        with pytest.raises(ValueError):reconcile_archive([event],[wrong])


def test_public_request_cache_attempt_limits_and_no_sports_budget(store):
    from intelligence.statistics_import import protected_counts
    before=protected_counts(store);calls=[]
    def fetch(url):calls.append(url);return b'{}',NOW.isoformat()
    c=Collector(store,NOW,fetch)
    c.get('test','https://sporting-events.org/data/nba.json')
    c.get('test','https://sporting-events.org/data/nba.json')
    assert len(calls)==1 and protected_counts(store)==before
    c.requests=200
    with pytest.raises(ValueError,match='bound'):c.get('new','https://sporting-events.org/data/nba.json')
    def fail(url):raise ValueError('Synthetic transport failure')
    c=Collector(store,NOW,fail)
    with pytest.raises(ValueError):c.get('failed','https://sporting-events.org/data/nba.json')
    with pytest.raises(ValueError,match='interval'):c.get('failed','https://sporting-events.org/data/nba.json')
    assert c.requests==1


@pytest.mark.parametrize('url',['https://api.the-odds-api.com/v4/sports','http://sportscore.com/api/v1/fixtures/',
    'https://localhost/','https://sportscore.com.evil.example/api/v1/fixtures/',
    'https://sporting-events.org/data/nba.json?key=synthetic'])
def test_only_reviewed_public_urls_reachable(url):
    with pytest.raises(ValueError,match='Unreviewed'):download(url)


@pytest.mark.parametrize('mutation',['time','team','venue','scope','duplicate','future_receipt'])
def test_nba_fixture_contract(mutation):
    data=schedule();r=data['events'][0]
    if mutation=='time':r['time_utc']=''
    if mutation=='team':r['home_team']='Unknown NBA team'
    if mutation=='venue':r['fixture']='invented home team'
    if mutation=='scope':r['date_utc']='2026-10-01'
    if mutation=='duplicate':data['events'][-1]=r
    if mutation=='future_receipt':data['generated']=(NOW+timedelta(seconds=1)).isoformat()
    with pytest.raises((ValueError,KeyError)):fixtures(receipt(data),NOW)


def test_nba_real_model_evidence_is_experimental_and_cached_only(store):
    save_fixture_cache(store)
    rows,reason=forecasts(store,NOW)
    assert rows and not reason and all(r['sport']=='NBA' for r in rows)
    assert all(not r['validated'] and r['ev'] is None and r['observed_odds'] is None for r in rows)
    assert all(0<=r['lower']<=r['probability']<=r['upper']<=1 and r['fair_odds']==1/r['probability'] for r in rows)
    assert saved_for_display(store,rows,NOW)==[]  # Inference is not publication.
    record(store,[r for r in rows if r['research_eligible']][:100],NOW)
    assert saved_for_display(store,rows,NOW)
    assert forecasts(store,NOW+timedelta(hours=6))[0]==[]
    assert fixture_games(store,NOW) and all(r['sport']=='NBA' for r in fixture_games(store,NOW))
    with patch('intelligence.recent_nba.load_report',return_value=None):assert forecasts(store,NOW)[0]==[]


def test_nba_unresolved_game_blocks_every_forecast_and_joint_point_not_invented(store):
    save_fixture_cache(store)
    rows,_=forecasts(store,NOW)
    for size in (2,3):
        cs=combinations_for(rows,size,now=NOW)
        assert cs
        assert all(c['joint_probability'] is None and not c['joint_validated'] and c['ev'] is None for c in cs)
    # Moving clock past a kickoff ages cached fixtures even before source expiry.
    early=NOW.replace(day=20,hour=22)
    value=store.cached('nba-current',10*86400,early)
    store.cache('nba-current',value,early)
    assert forecasts(store,early+timedelta(hours=2))[0]==[]


def test_nba_result_enters_existing_accuracy_tracker_only_after_verified_final(store):
    from dataclasses import asdict
    es,meta=save_fixture_cache(store);rows,_=forecasts(store,NOW)
    r=next(r for r in rows if r['research_eligible']);record(store,[r],NOW)
    assert summary(store,NOW)['formats'][1]['pending']==1
    later=datetime(2026,10,22,12,tzinfo=timezone.utc)
    e=next(e for e in es if e.fixture_id==r['fixture_id'])
    e=replace(e,status='completed',home_score=110,away_score=105,observed_at=later.isoformat(),score_scope='sportscore_final')
    meta=meta|{'checked_at':later.isoformat()}
    store.cache('nba-current',{'events':[asdict(e)],'meta':meta},later)
    assert reconcile(store,later)==1 and reconcile(store,later)==0
    result=summary(store,later)['formats'][1]
    assert result['settled']==1 and result['pending']==0


def test_sources_fail_independently_and_never_replace_existing_success(store):
    save_fixture_cache(store);before=current(store,NOW)
    def fail(url):raise ValueError('Synthetic unavailable source')
    result=refresh(store,NOW,fail)
    assert all(not s['ok'] for s in result['sources'].values())
    assert current(store,NOW)==before
    assert collect(store,NOW,168,['NBA'])['forecasts']


def test_sport_result_aliases_do_not_modify_frozen_models():
    from intelligence.epl_forecasts import load_artifact
    from intelligence.expanded_models import load
    from intelligence.recent_nba import load_report
    assert load_artifact() and load('Bundesliga') and load('Ligue 1') and load_report()


def test_prepared_public_receipts_preserve_timestamps_and_require_hashes(tmp_path):
    from intelligence.free_results import prepared_fetch
    raw=b'{}';at=(NOW-timedelta(hours=1)).isoformat();url='https://sporting-events.org/data/nba.json'
    m={'file':'nba.json','url':url,'http':200,'observed_at':at,'sha256':sha256(raw).hexdigest()}
    (tmp_path/'nba.json').write_bytes(raw);(tmp_path/'manifest.json').write_text(json.dumps([m]))
    assert prepared_fetch(tmp_path)(url)==(raw,at)
    (tmp_path/'nba.json').write_bytes(b'{"modified":true}')
    with pytest.raises(ValueError,match='checksum'):prepared_fetch(tmp_path)(url)
    m['file']='../outside.json';(tmp_path/'manifest.json').write_text(json.dumps([m]))
    with pytest.raises(ValueError):prepared_fetch(tmp_path)


def test_new_public_data_does_not_reset_existing_bundesliga_refresh_clock(store):
    from intelligence.free_statistics_worker import update
    from test_current_statistics import season
    raw=json.dumps(season(NOW)).encode()
    with patch('intelligence.fixture_research.collect',return_value={'forecasts':[]}),patch('intelligence.current_score_research.candidates',return_value=[]):
        update(store,NOW,lambda:(raw,NOW.isoformat()))
        later=NOW+timedelta(hours=1)
        def no_redundant_bundesliga_get():raise AssertionError('Existing fresh receipt must be reused')
        with patch('intelligence.free_results.refresh',return_value={'sources':{},'public_results_requests':0}):
            result,_=update(store,later,no_redundant_bundesliga_get,extra_fetch=lambda url:None)
        assert result['public_results_requests']==0 and result['source_observed_at']==NOW.isoformat()
        # Three hours are measured from the real source receipt, not the
        # additional-source import, so the next ordinary refresh is still due.
        later=NOW+timedelta(hours=3,minutes=1)
        result,_=update(store,later,lambda:(raw,later.isoformat()))
        assert result['public_results_requests']==1
