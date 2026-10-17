"""All provider payloads below are SYNTHETIC contract fixtures, not real results."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import json
from unittest.mock import patch
import pytest
from intelligence.current_results import (ResultsConfig, current, parse, status,
    CODES, cache_key, _reserve)
from intelligence.domain import utcnow, parse_time
from intelligence.data_adapters import aliases, team_identity
from intelligence.competitions import COMPETITIONS
from intelligence.epl_forecasts import load_artifact
from intelligence.expanded_models import load
from intelligence.current_soccer import prepare_epl, prepare_expanded, forecast

CONFIG = ResultsConfig(True, 'synthetic-token-NOT-A-REAL-KEY', True)


def payload(league='Bundesliga', now=None):
    """Reuse reviewed schedule identities; fill gaps with TEST-ONLY scores."""
    now = now or utcnow()
    c = COMPETITIONS[league]
    epl = league == 'Premier League'
    a = load_artifact() if epl else load(league)
    names = {team_identity(c, name)[0]: name for name in aliases()[league]}
    rows = list(a['current_rows'])
    if epl:
        fixtures = [r for r in a['fixtures'] if r['season']=='2026-27']+rows
        fields = lambda f: (f['home'], f['away'], f['date'])
        named = lambda t: next(n for n in aliases()[league] if aliases()[league][n]==t)
    else:
        fixtures = a['fixtures']
        fields = lambda f: (f['home_id'], f['away_id'], f['event_date'])
        named = lambda t: names[t]
    teams = sorted({t for f in fixtures for t in fields(f)[:2]})
    offset = list(CODES).index(league)*10000
    ids = {t: offset+i+1 for i, t in enumerate(teams)}
    known = {(r['home'],r['away'],r['date']): (r['hg'],r['ag']) for r in rows}
    matches = []
    for i, f in enumerate(fixtures):
        h, aw, day = fields(f)
        done = day < now.date().isoformat()
        hg, ag = known.get((h,aw,day), (2,1)) if done else (None,None)
        kickoff=day+'T23:50:00Z'
        if not done and parse_time(kickoff)<=now:
            # Synthetic scheduled fixtures on today's date must remain future
            # even when tests run after 23:50 UTC. Keep their reviewed date;
            # actual past/unresolved behavior is tested explicitly elsewhere.
            midnight=now.replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=1)
            kickoff=(now+(midnight-now)/2).isoformat()
        matches.append({'id': offset+i+1, 'competition': {'code': CODES[league]},
            'season': {'startDate':'2026-08-01'}, 'stage':'REGULAR_SEASON',
            'homeTeam':{'id':ids[h],'name':named(h)}, 'awayTeam':{'id':ids[aw],'name':named(aw)},
            'utcDate':kickoff, 'lastUpdated':now.isoformat(),
            'status':'FINISHED' if done else 'TIMED',
            'score':{'duration':'REGULAR','fullTime':{'home':hg,'away':ag}}})
    return {'competition':{'code':CODES[league],'type':'LEAGUE'},'filters':{'season':'2026'},
            'resultSet':{'count':len(matches),'played':sum(m['status']=='FINISHED' for m in matches)},'matches':matches}


class Response:
    def __init__(self, value=None, status_code=200, raw=None):
        self.raw = json.dumps(value).encode() if raw is None else raw
        self.status_code = status_code
    def iter_content(self, size):
        for i in range(0, len(self.raw), size):
            yield self.raw[i:i+size]
    def close(self):
        pass


class Session:
    def __init__(self, response):
        self.response = response
        self.calls = 0
    def get(self, url, **kwargs):
        self.calls += 1
        assert url.startswith('https://api.football-data.org/v4/competitions/')
        assert kwargs['headers']=={'X-Auth-Token':CONFIG.token}
        assert not kwargs['allow_redirects'] and kwargs['params']=={'season':2026}
        return self.response


def test_synthetic_scheduled_fixture_remains_future_after_2350(store):
    now=utcnow().replace(hour=23,minute=55,second=0,microsecond=0)
    events,meta=current(store,'Bundesliga',now,CONFIG,Session(Response(payload('Bundesliga',now))))
    assert meta['ok'] and meta['coverage']['unresolved_past']==0
    assert all(parse_time(e.kickoff)>now for e in events if e.status=='scheduled')


@pytest.mark.parametrize('config',[ResultsConfig(), ResultsConfig(True), ResultsConfig(True,CONFIG.token), ResultsConfig(True,'bad\nheader',True)])
def test_disabled_missing_token_or_unreviewed_use_never_requests_or_consumes_budget(store,config):
    s=Session(Response())
    events,meta=current(store,'Bundesliga',config=config,session=s)
    assert not events and not meta['ok'] and s.calls==0
    assert CONFIG.token not in repr(config) and CONFIG.token not in str(status(store,config))
    with store.connect() as db:
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='football_data_requests'").fetchall()


@pytest.mark.parametrize('league',['Premier League','Bundesliga','Ligue 1'])
def test_full_season_exact_aliases_provenance_cache_and_no_odds_budget(store,league):
    now=utcnow();s=Session(Response(payload(league,now)))
    events,meta=current(store,league,now,CONFIG,s)
    assert meta['ok'] and meta['coverage']['complete_fixture_schedule'] and events
    assert all(e.source=='football-data.org' and e.kickoff and e.source_updated_at for e in events)
    assert current(store,league,now+timedelta(minutes=1),CONFIG,s)[1]['ok'] and s.calls==1
    with store.connect() as db:
        assert db.execute('SELECT count(*) FROM budget').fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM football_data_requests').fetchone()[0]==1
        assert CONFIG.token not in str([tuple(r) for r in db.execute('SELECT * FROM cache')])


@pytest.mark.parametrize('failure',['truncated','count','filtered','unknown_team','id_alias','duplicate','wrong_competition','future_update','bad_score','extra_time','unfinished_final','completion_time','unknown_status','played'])
def test_incomplete_unverified_or_malformed_results_fail_closed(store,failure):
    now=utcnow();p=payload(now=now);m=p['matches'][0]
    if failure=='truncated':p['matches'].pop();p['resultSet']['count']-=1
    if failure=='count':p['resultSet']['count']-=1
    if failure=='filtered':p['filters']['status']='FINISHED'
    if failure=='unknown_team':m['homeTeam']['name']='Unknown unreviewed team'
    if failure=='id_alias':m['homeTeam']['id']=p['matches'][1]['awayTeam']['id']
    if failure=='duplicate':p['matches'][1]=deepcopy(m)
    if failure=='wrong_competition':m['competition']['code']='FL1'
    if failure=='future_update':m['lastUpdated']=(now+timedelta(days=1)).isoformat()
    if failure=='bad_score':m['score']['fullTime']['home']=True
    if failure=='extra_time':m['score']['duration']='EXTRA_TIME'
    if failure=='unfinished_final':m['score']['fullTime']['away']=None
    if failure=='completion_time':m['lastUpdated']=m['utcDate']
    if failure=='unknown_status':m['status']='NEW_UNKNOWN_STATUS'
    if failure=='played':p['resultSet']['played']+=1
    s=Session(Response(p));events,meta=current(store,'Bundesliga',now,CONFIG,s)
    assert not events and not meta['ok'] and 'failed' in meta['problem']
    assert current(store,'Bundesliga',now,CONFIG,s)[1]==meta and s.calls==1


@pytest.mark.parametrize('code',[301,401,403,429,500])
def test_http_errors_are_private_cached_and_429_is_shared(store,code):
    now=utcnow();s=Session(Response(status_code=code,raw=CONFIG.token.encode()))
    _,meta=current(store,'Bundesliga',now,CONFIG,s)
    assert not meta['ok'] and CONFIG.token not in str(meta)
    assert not current(store,'Bundesliga',now,CONFIG,s)[1]['ok'] and s.calls==1
    if code==429:
        assert not current(store,'Ligue 1',now,CONFIG,s)[1]['ok'] and s.calls==1


def test_size_network_failures_and_reflected_credentials_never_leak(store):
    now=utcnow()
    for league,raw in zip(CODES,[b'x'*2_000_001,CONFIG.token.encode()]):
        s=Session(Response(raw=raw));_,meta=current(store,league,now,CONFIG,s)
        assert not meta['ok'] and CONFIG.token not in str(meta)
    import requests
    s=Session(Response())
    with patch.object(s,'get',side_effect=requests.ConnectionError(CONFIG.token)):
        _,meta=current(store,'Ligue 1',now,CONFIG,s)
    assert not meta['ok'] and CONFIG.token not in str(meta)


def test_request_cap_is_atomic_shared_and_navigation_status_is_read_only(store):
    now=utcnow()
    assert all(_reserve(store,now) for _ in range(6))
    assert not _reserve(store,now)
    assert not current(store,'Bundesliga',now,CONFIG,Session(Response()))[1]['ok']
    assert status(store,CONFIG,now)['maximum_requests_per_UTC_day_per_store']==6
    assert _reserve(store,now+timedelta(days=1))


@pytest.mark.parametrize('change',['score','date','withdraw','team_id','fixture_id'])
def test_cross_snapshot_conflicts_are_not_silently_replaced(store,change):
    # Exercise six-hour expiry within one UTC date at every wall-clock hour.
    # Falling back to `later=now` left the accepted journal fresh after 18 UTC,
    # so no changed provider payload was ever fetched or tested.
    now=utcnow().replace(hour=8,minute=0,second=0,microsecond=0);p=payload(now=now)
    assert current(store,'Bundesliga',now,CONFIG,Session(Response(p)))[1]['ok']
    later=now+timedelta(seconds=21601)
    with store.connect() as db:db.execute('DELETE FROM cache WHERE key=?',(cache_key('Bundesliga','2026-27'),))
    p=payload(now=later);m=p['matches'][0]
    if change=='score':m['score']['fullTime']['home']+=1
    if change=='date':m['utcDate']='2026-08-27T23:50:00Z'
    if change=='withdraw':m['status']='POSTPONED';m['score']['fullTime']={'home':None,'away':None};p['resultSet']['played']-=1
    if change=='team_id':
        old=m['homeTeam']['id']
        for match in p['matches']:
            for side in ('homeTeam','awayTeam'):
                if match[side]['id']==old:match[side]['name']=p['matches'][1]['awayTeam']['name']
    if change=='fixture_id':p['matches'][0]['id'],p['matches'][1]['id']=p['matches'][1]['id'],p['matches'][0]['id']
    events,meta=current(store,'Bundesliga',later,CONFIG,Session(Response(p)))
    assert not events and not meta['ok']
    assert not status(store,CONFIG,later)['leagues']['Bundesliga']['ok']


@pytest.mark.parametrize('league',['Premier League','Bundesliga','Ligue 1'])
def test_optional_bridge_extends_inputs_but_never_approves_model(store,quote,league,monkeypatch):
    now=utcnow();p=payload(league,now);events,meta=current(store,league,now,CONFIG,Session(Response(p)))
    assert meta['ok']
    monkeypatch.setenv('FOOTBALL_DATA_ENABLED','1')
    monkeypatch.setenv('FOOTBALL_DATA_TOKEN',CONFIG.token)
    monkeypatch.setenv('FOOTBALL_DATA_USE_REVIEWED','1')
    frozen=load_artifact() if league=='Premier League' else load(league)
    a=prepare_epl(store,now) if league=='Premier League' else prepare_expanded(league,store,now)
    assert not a.get('problem') and a['state']['n']>frozen['state']['n'] and a['code_sha256']==frozen['code_sha256']
    # Find a genuinely supported synthetic fixture with enough frozen team history.
    selected=None
    for event in events:
        if event.status!='scheduled' or event.event_date<=now.date().isoformat():continue
        q=replace(quote,sport='Soccer',league=league,home=event.home_name,away=event.away_name,
            market='totals' if league=='Ligue 1' else 'btts',selection='Over' if league=='Ligue 1' else 'Yes',
            point=2.5 if league=='Ligue 1' else None,commence_time=event.kickoff,
            source_updated_at=now.isoformat(),received_at=now.isoformat())
        e,d=forecast(q,a,now)
        if e:selected=(q,e,d);break
    assert selected, 'At least one synthetic mature-team fixture should pass unchanged research input gates'
    q,e,d=selected
    assert not e.validated and d['results_provider']=='football-data.org' and d['blockers']
    assert forecast(replace(q,commence_time=(parse_time(q.commence_time)+timedelta(minutes=1)).isoformat()),a,now)[0] is None
    assert forecast(q,a,now+timedelta(hours=6))[0] is None
    from intelligence.pipeline import Analysis
    from intelligence.processing import record_shadow_forecasts,shadow_statistics,label_public_epl
    analysis=Analysis(quotes=[q],estimates={q.id:e},advanced_estimates={q.id:e},advanced_details={q.id:d})
    assert record_shadow_forecasts(analysis,store,now)==1
    assert record_shadow_forecasts(analysis,store,now+timedelta(seconds=1))==0
    assert record_shadow_forecasts(analysis,store,parse_time(q.commence_time))==0
    assert shadow_statistics(store)['private_forecasts']==1
    assert shadow_statistics(store)['betting_roi'] is None and not store.records()
    assert (load_artifact() if league=='Premier League' else load(league))==frozen


from intelligence.domain import parse_time


@pytest.mark.parametrize('status_value',['POSTPONED','CANCELLED','SUSPENDED','AWARDED','TIMED'])
def test_missing_past_results_and_postponed_games_cannot_activate_models(store,monkeypatch,status_value):
    now=utcnow();p=payload(now=now);m=p['matches'][0]
    m['status']=status_value;m['score']['fullTime']={'home':None,'away':None};p['resultSet']['played']-=1
    events,meta=current(store,'Bundesliga',now,CONFIG,Session(Response(p)))
    assert meta['ok'] and meta['provider_statuses'][str(m['id'])]==status_value
    assert meta['coverage']['unresolved_past']>=1
    monkeypatch.setenv('FOOTBALL_DATA_ENABLED','1');monkeypatch.setenv('FOOTBALL_DATA_TOKEN',CONFIG.token);monkeypatch.setenv('FOOTBALL_DATA_USE_REVIEWED','1')
    assert 'unresolved' in prepare_expanded('Bundesliga',store,now)['problem']


def test_free_results_token_is_in_existing_chat_redaction(monkeypatch):
    from intelligence.analyst_config import load_config
    from intelligence.chat_privacy import redact
    monkeypatch.setenv('FOOTBALL_DATA_TOKEN',CONFIG.token)
    c=load_config()
    assert CONFIG.token in c.sensitive_values
    assert CONFIG.token not in redact('Token '+CONFIG.token,c.sensitive_values)
    assert not c.paid_ready


@pytest.mark.parametrize('league',['Premier League','Bundesliga','Ligue 1'])
def test_forward_labels_preserve_original_forecast_and_exact_source_identity(store,quote,league):
    from intelligence.processing import record_shadow_forecasts,label_public_epl
    from intelligence.multi_readiness import process_expanded_paper
    from intelligence.pipeline import Analysis
    from intelligence.persistence import paper_export
    from test_expanded_models import usable_artifact,expanded_quote
    from test_epl_predictions import soccer_quote
    from intelligence.current_soccer import paper_result_matches
    now=utcnow()
    if league=='Premier League':
        q=soccer_quote(quote,now)
        from test_epl_predictions import synthetic_artifact
        a=synthetic_artifact(q,now)
        from intelligence.epl_forecasts import forecast as infer
    else:
        q=expanded_quote(quote,league,now);a=usable_artifact(q,now)
        from intelligence.expanded_forecasts import forecast as infer
    e,d=infer(q,a,now)
    assert e
    analysis=Analysis(quotes=[q],estimates={q.id:e},advanced_estimates={q.id:e},advanced_details={q.id:d})
    assert record_shadow_forecasts(analysis,store,now)==1
    before=paper_export(store)['records'][0]
    h,_=team_identity(COMPETITIONS[league],q.home);aw,_=team_identity(COMPETITIONS[league],q.away)
    end=parse_time(q.commence_time)+timedelta(days=2)
    a.update(results_provider='football-data.org',results_events=[{'home_id':h,'away_id':aw,
        'status':'completed','kickoff':q.commence_time}])
    a['source_check']=end.isoformat()
    if league=='Premier League':
        from intelligence.epl_source import team
        rh,ra=team(q.home),team(q.away)
    else:rh,ra=h,aw
    # A 0–0 final is a miss for Yes/Over. It must remain visible in the export.
    a['current_rows']=[{'date':q.commence_time[:10],'home':rh,'away':ra,'hg':0,'ag':0}]
    assert paper_result_matches(before['forecast']['quote'],a)
    moved=deepcopy(a);moved['results_events'][0]['kickoff']=(parse_time(q.commence_time)+timedelta(minutes=1)).isoformat()
    assert not paper_result_matches(before['forecast']['quote'],moved)
    def label(bundle):
        if league=='Premier League':return label_public_epl(store,bundle,end)
        return process_expanded_paper(store,Analysis(expanded_models={league:bundle}),end)
    assert label(moved)==0 and label(a)==1 and label(a)==0
    after=paper_export(store)['records'][0]
    assert after['forecast']==before['forecast'] and after['recorded_at']==before['recorded_at']
    assert after['outcome']=='miss' and 'football-data.org' in after['outcome_source']
    assert not store.records() and not paper_export(store)['off_host_durability_verified']
    assert CONFIG.token not in json.dumps(paper_export(store))


def test_results_and_export_controls_preserve_four_pages_without_external_calls(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    from ui_navigation import navigate
    monkeypatch.setenv('INTELLIGENCE_DB',str(tmp_path/'ui.sqlite3'))
    monkeypatch.setenv('ODDS_API_KEY','')
    with patch('intelligence.current_results.requests.Session.get',side_effect=AssertionError('No network')):
        app=AppTest.from_file(Path('app.py').resolve(),default_timeout=30).run()
        navigate(app,'Settings')
        assert not app.exception and len(app.sidebar.radio[0].options)==5
        assert next(b for b in app.button if b.label=='Refresh soccer results only').disabled
        next(b for b in app.button if b.label=='Prepare paper research export').click().run()
        assert not app.exception and len(app.get('download_button'))==1


@pytest.mark.parametrize('league',['Premier League','Bundesliga','Ligue 1'])
def test_provider_disagreement_with_frozen_finals_cannot_change_features(store,monkeypatch,league):
    now=utcnow();p=payload(league,now)
    # Alter a frozen completed result before any new source has been imported.
    index=-len(load_artifact()['current_rows']) if league=='Premier League' else 0
    p['matches'][index]['score']['fullTime']['home']+=1
    assert current(store,league,now,CONFIG,Session(Response(p)))[1]['ok']
    monkeypatch.setenv('FOOTBALL_DATA_ENABLED','1');monkeypatch.setenv('FOOTBALL_DATA_TOKEN',CONFIG.token);monkeypatch.setenv('FOOTBALL_DATA_USE_REVIEWED','1')
    a=prepare_epl(store,now) if league=='Premier League' else prepare_expanded(league,store,now)
    assert 'frozen completed fixtures' in a['problem'] and 'state' not in a


def test_enabled_but_missing_credential_cannot_fall_back_to_public_inputs(store,monkeypatch):
    monkeypatch.setenv('FOOTBALL_DATA_ENABLED','1');monkeypatch.setenv('FOOTBALL_DATA_TOKEN','')
    with patch('intelligence.epl_forecasts.prepare',side_effect=AssertionError('No silent fallback')),patch('intelligence.expanded_forecasts.prepare',side_effect=AssertionError('No silent fallback')):
        assert 'FOOTBALL_DATA_TOKEN' in prepare_epl(store)['problem']
        assert 'FOOTBALL_DATA_TOKEN' in prepare_expanded('Bundesliga',store)['problem']
