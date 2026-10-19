"""Current regular-season fixtures/results for the unchanged NBA Elo study.

Experimental only. Opening-season team ratings omit offseason roster changes;
after games begin every earlier scheduled game requires a verified final.
"""
from dataclasses import asdict
from datetime import date, timedelta
from math import log
import json
from intelligence.domain import utcnow, parse_time, digest
from intelligence.event_data import EventObservation, ingest
from intelligence.competitions import COMPETITIONS
from intelligence.data_adapters import team_identity

START=date(2026,10,20)
END=date(2027,4,12)
LICENSE='https://sporting-events.org/data/'


def fixtures(value,now):
    data=json.loads(value['raw'])
    if (data.get('competition')!='NBA' or data.get('source')!='https://sporting-events.org/data/nba/'
        or data.get('event_count')!=len(data.get('events',[])) or not 1000<=data['event_count']<=1400
        or not 0<=(parse_time(value['checked_at'])-parse_time(data['generated'])).total_seconds()<86400):
        raise ValueError('NBA current-season fixture coverage or source timestamp invalid')
    result=[];seen=set()
    for r in data['events']:
        # Tournament/context headings are not games. Never invent opponents/time.
        if not r['home_team'] and not r['away_team'] and not r['time_utc']:continue
        h,hn=team_identity(COMPETITIONS['NBA'],r['home_team']);a,an=team_identity(COMPETITIONS['NBA'],r['away_team'])
        if ':archive:' in h+a or r['fixture']!=r['away_team']+' at '+r['home_team']:
            raise ValueError('NBA fixture identity or home designation is unreviewed')
        start=parse_time(r['date_utc']+'T'+r['time_utc']+':00+00:00')
        if not START<=start.date()<=END or r['status'] not in ('scheduled','completed','postponed','cancelled'):
            raise ValueError('NBA source is not a reviewed regular-season fixture')
        key=digest((r['date_utc'],h,a))
        if key in seen:raise ValueError('Duplicate NBA game')
        seen.add(key)
        result.append(EventObservation(COMPETITIONS['NBA'].id,'2026-27','sporting-events+sportscore',key,h,a,hn,an,
            start.date().isoformat(),'scheduled' if r['status']=='scheduled' and start>now else 'unresolved',
            None,None,value['checked_at'],None,LICENSE,
            'source_'+r['status'] if r['status'] in ('postponed','cancelled') else 'fixture_only_no_score',start.isoformat()).validate(now))
    if len({e.home_id for e in result}|{e.away_id for e in result})!=30:
        raise ValueError('NBA schedule does not contain all 30 reviewed teams')
    return result


def missing_final(event,now):
    if event.status=='completed' or event.score_scope in ('source_postponed','source_cancelled'):return False
    if event.score_scope=='same_day_final_withheld' and event.event_date==now.date().isoformat():return False
    return parse_time(event.kickoff)<=now


def save(collector):
    from intelligence.free_results import NBA_URL, TERMS
    now=collector.now;store=collector.store
    source=collector.get('nba-fixtures',NBA_URL)
    now=collector.now
    events=fixtures(source,now);by_key={(e.event_date,e.home_id,e.away_id):e for e in events}
    previous=store.cached('nba-current',10*366*86400,now)
    removed=[]
    if previous:
        for row in previous['events']:
            old=EventObservation(**row);key=(old.event_date,old.home_id,old.away_id)
            if key not in by_key:
                # Repeated NBA pairings cannot be rebound by team names alone.
                # Preserve the original for final reconciliation, but never
                # show a removed scheduled game as a fresh upcoming pick.
                if old.status!='completed':
                    from dataclasses import replace
                    removed.append(old.fixture_id)
                    old=replace(old,status='unresolved',score_scope='fixture_removed_pending_reconciliation')
                by_key[key]=old
    receipts=[source]
    day=START
    while day<=now.date():
        finals,receipt=collector.day('NBA',day.isoformat());receipts.append(receipt)
        for e in finals:
            key=(e.event_date,e.home_id,e.away_id);old=by_key.get(key)
            if old is None or parse_time(old.kickoff)!=parse_time(e.kickoff):
                raise ValueError('NBA final does not reconcile to exact scheduled teams and tipoff')
            if old.status=='completed' and (e.status!='completed' or (old.home_score,old.away_score)!=(e.home_score,e.away_score)):
                raise ValueError('NBA final conflicts with a previously verified result')
            # Keep the schedule's stable fixture identity for original records.
            from dataclasses import replace
            by_key[key]=replace(e,source_event_id=old.source_event_id,source=old.source)
        day+=timedelta(days=1)
    now=collector.now;events=list(by_key.values())
    if previous:
        by_id={e.fixture_id:e for e in events}
        for row in previous['events']:
            old=EventObservation(**row)
            if old.status!='completed':continue
            new=by_id.get(old.fixture_id)
            if (not new or new.status!='completed' or new.kickoff!=old.kickoff
                or (new.home_score,new.away_score)!=(old.home_score,old.away_score)):
                raise ValueError('NBA refresh withdrew or revised a previously verified final')
    recent=[source['checked_at']]+[r['checked_at'] for r in receipts[1:]
        if date.fromisoformat(json.loads(r['raw'])['date'])>=now.date()-timedelta(days=3)]
    checked=min(recent,key=parse_time)
    if not 0<=(now-parse_time(checked)).total_seconds()<21600:
        raise ValueError('NBA recent result verification expired')
    meta={'ok':True,'provider':'sporting-events + sportscore','checked_at':checked,
        'sha256':digest([r['sha256'] for r in receipts]),'license_reference':LICENSE,'results_license_reference':TERMS,
        'source_url':NBA_URL,'source_receipts':[{k:r[k] for k in ('source_url','sha256','checked_at')} for r in receipts],
        'removed_unreconciled_fixtures':removed,
        'coverage':{'fixtures':len(events),'completed':sum(e.status=='completed' for e in events),
            'unresolved_past':sum(missing_final(e,now) for e in events)},
        'attribution':'Sporting Events fixture data; Powered by SportScore for verified final scores'}
    ingest(store,events,meta,now)
    store.cache('nba-current',{'events':[asdict(e) for e in events],'meta':meta},parse_time(checked))
    return meta


def current(store,now=None):
    from dataclasses import replace
    now=now or utcnow();value=store.cached('nba-current',21600,now)
    if not value:return [],{'ok':False,'problem':'No fresh reviewed NBA fixture/result snapshot'}
    events=[EventObservation(**e).validate(now) for e in value['events']]
    events=[replace(e,status='unresolved') if e.status=='scheduled' and parse_time(e.kickoff)<=now else e for e in events]
    meta=dict(value['meta']);meta['coverage']=dict(meta['coverage'],
        unresolved_past=sum(missing_final(e,now) for e in events))
    return events,meta


def forecasts(store,now=None,hours=168):
    from intelligence.recent_nba import load_report
    from intelligence.team_rating import probability,SETTINGS
    from intelligence.epl_validation import calibrated
    from intelligence.research_ranking import MIN_CALIBRATION_BIN,MIN_CALIBRATION,MIN_TEST,MAX_ENVELOPE_WIDTH
    now=now or utcnow();events,meta=current(store,now);report=load_report()
    if not meta['ok']:return [],meta['problem']
    if not report:return [],'Verified NBA historical model evidence missing or changed'
    if report['opening_14_days']['n']<MIN_TEST:return [],'Insufficient opening-season held-out evidence'
    if report['test_n']<MIN_TEST:return [],'Insufficient regular-season held-out evidence'
    if meta.get('removed_unreconciled_fixtures'):
        return [],'NBA schedule removed an uncompleted fixture; exact cross-date source binding is required before research resumes'
    if meta['coverage']['unresolved_past']:
        return [],'An earlier NBA game lacks a verified final, is suspended or is still in progress; same-day results are withheld'
    completed=sorted([e for e in events if e.status=='completed'],key=lambda e:(e.event_date,e.fixture_id))
    ratings=dict(report['ratings']);p=SETTINGS['NBA'];changes={};last=None
    for e in completed:
        if e.event_date>=now.date().isoformat():return [],'Same-day NBA features withheld'
        if last and e.event_date!=last:
            for t,d in changes.items():ratings[t]+=d
            changes={}
        h=e.home_id.split(':')[-1];a=e.away_id.split(':')[-1]
        if h not in ratings or a not in ratings:return [],'NBA team lacks historical ratings'
        raw=probability(ratings,h,a,'NBA')
        delta=p['k']*min(2.,max(.5,log(1+abs(e.home_score-e.away_score))))*(int(e.home_score>e.away_score)-raw)
        changes[h]=changes.get(h,0.)+delta;changes[a]=changes.get(a,0.)-delta;last=e.event_date
    for t,d in changes.items():ratings[t]+=d
    latest={}
    for e in completed:
        for team in (e.home_id,e.away_id):latest[team]=max(latest.get(team,e.event_date),e.event_date)
    rows=[];missing_recent=False
    for e in events:
        start=parse_time(e.kickoff)
        if e.status!='scheduled' or not now+timedelta(minutes=15)<start<=now+timedelta(hours=hours):continue
        # The frozen report also evaluates an entire unseen regular season.
        # Beyond opening fortnight, both teams need actual current-season
        # results and recent inputs. No transfer to playoffs/preseason.
        if not START<=start.date()<=END:continue
        opening=start.date()<START+timedelta(days=14)
        if not opening and any(t not in latest or not 0<(start.date()-date.fromisoformat(latest[t])).days<=21
            for t in (e.home_id,e.away_id)):
            missing_recent=True;continue
        h=e.home_id.split(':')[-1];a=e.away_id.split(':')[-1]
        if h not in ratings or a not in ratings:continue
        estimate=float(calibrated(probability(ratings,h,a,'NBA'),report['coefficients']))
        bucket=report['calibration_bins'][min(9,int(estimate*10))];lo,hi=bucket['frequency_interval']
        lo,hi=min(lo,estimate),max(hi,estimate);home=estimate>=.5
        if not home:estimate,lo,hi=1-estimate,1-hi,1-lo
        eligible=(bucket['n']>=MIN_CALIBRATION_BIN and report['calibration_n']>=MIN_CALIBRATION
            and report['test_n']>=MIN_TEST and hi-lo<=MAX_ENVELOPE_WIDTH)
        rows.append({'sport':'NBA','league':'NBA','event':e.home_name+' vs '+e.away_name,
            'home':e.home_name,'away':e.away_name,'home_id':e.home_id,'away_id':e.away_id,
            'fixture_id':e.fixture_id,'kickoff':e.kickoff,'market':'h2h','point':None,
            'selection':e.home_name if home else e.away_name,'probability':estimate,'lower':lo,'upper':hi,'fair_odds':1/estimate,
            'model_version':report['model_version'],'evidence_id':report['evidence_id'],
            'data_sha256':digest((report['data_sha256'],meta['sha256'])),'history_n':report['history_n']+len(completed),
            'training_end':last or report['data_end'],'calibration_n':report['calibration_n'],
            'calibration_bin_n':bucket['n'],'test_n':report['test_n'],'source_observed_at':meta['checked_at'],
            'source':meta['provider'],'forecast_at':now.isoformat(),'validated':False,'research_eligible':eligible,
            'sportsbook':None,'observed_odds':None,'ev':None,'status':'Experimental '+('opening-season' if opening else 'regular-season')+' forecast; not a betting pick',
            'limitations':['Prior-season team Elo with frozen calibration; offseason roster changes, injuries and lineups are unmodeled',
                ('Opening 14-day retrospective test: 102 games; Brier 0.2241, log loss 0.6422. Not prospective confirmation' if opening else
                 f"Frozen 2025–26 regular-season test: {report['test_n']} games; Brier {report['metrics']['binary_brier']['value']:.4f}, log loss {report['metrics']['log_loss']['value']:.4f}. Not prospective confirmation"),
                'Historical calibration frequency range, not an event-specific confidence guarantee',
                'Regular season and game winner including overtime only; no props, spread, total or playoff estimate',
                'No model approval, current sportsbook price, betting EV or demonstrated advantage',report['attribution'],
                'Fixture attribution: https://sporting-events.org/data/nba/']})
    return rows,'' if rows else ('Current-season NBA results missing or older than 21 days for an upcoming team' if missing_recent else 'No supported regular-season NBA fixture in this window')
