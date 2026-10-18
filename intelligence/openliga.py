"""Reviewed key-free OpenLigaDB full-season snapshots, ODbL 1.0.

Pure import/cache adapter. No provider calls, quota changes or model approval.
Public derivative data is offered separately, never mixed with private ledgers.
"""
from dataclasses import asdict
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import json
from intelligence.domain import utcnow, parse_time, digest
from intelligence.data_adapters import ROOT, team_identity
from intelligence.competitions import COMPETITIONS
from intelligence.event_data import EventObservation, coverage, ingest, reconciled

LICENSE = 'https://opendatacommons.org/licenses/odbl/1-0/'
SCOPES = {'Premier League':('pl',5996), 'Bundesliga':('bl1',4937)}
TTL = 21600


def parse(raw, league, observed_at, now=None, year=2026):
    now = now or utcnow(); observed = parse_time(observed_at)
    lifetime=TTL if year==2026 else 366*86400
    if league not in SCOPES or year not in (2025,2026) or year==2025 and league!='Bundesliga' or len(raw)>2_000_000 or not 0 <= (now-observed).total_seconds() < lifetime:
        raise ValueError('Unreviewed competition or expired results observation')
    shortcut, league_id = SCOPES[league]; c = COMPETITIONS[league]
    if year==2025: league_id=4821
    season=f'{year}-{str(year+1)[-2:]}'
    mapping = json.loads((ROOT/'config/openliga_teams.json').read_text())[league]
    rows = json.loads(raw)
    expected = 380 if league=='Premier League' else 306
    if not isinstance(rows,list) or len(rows)!=expected: raise ValueError('Full season fixture coverage missing')
    events=[];ids=set();pairs=set()
    for r in rows:
        if r['leagueShortcut']!=shortcut or r['leagueId']!=league_id or r['leagueSeason']!=year:
            raise ValueError('OpenLigaDB competition/season mismatch')
        teams=[]
        for name in ('team1','team2'):
            t = r[name]; reviewed = mapping.get(str(t['teamId']))
            if not reviewed or reviewed['source_name'] != t['teamName']: raise ValueError('Unreviewed OpenLigaDB team identity')
            canonical=reviewed['canonical']
            teams.append((*team_identity(c,canonical),canonical))
        (h,_,hn),(a,_,an)=teams; start=parse_time(r['matchDateTimeUTC'])
        if not f'{year}-07-01' <= start.date().isoformat() <= f'{year+1}-06-30' or type(r['matchIsFinished']) is not bool:
            raise ValueError('Invalid OpenLigaDB date or status')
        if r['matchID'] in ids or (h,a) in pairs or h==a: raise ValueError('Duplicate seasonal fixture')
        ids.add(r['matchID']);pairs.add((h,a))
        finals=[s for s in r['matchResults'] if s.get('resultTypeKind')=='After90Minutes']
        completed=r['matchIsFinished'] and start.date()<now.date()
        if r['matchIsFinished'] and (len(finals)!=1 or start>observed): raise ValueError('Missing/ambiguous regulation final score')
        if completed:
            hg,ag=finals[0]['pointsTeam1'],finals[0]['pointsTeam2']
            if any(type(v) is not int or not 0<=v<=30 for v in (hg,ag)): raise ValueError('Invalid regulation score')
        else: hg=ag=None
        # Date-only same-day feature policy stays intact. Overdue/live games
        # remain unresolved and cannot be silently treated as unplayed fixtures.
        status='completed' if completed else 'scheduled' if start>now else 'unresolved'
        scope='same_day_final_withheld' if r['matchIsFinished'] and start.date()==now.date() else 'source_reported_ft'
        events.append(EventObservation(c.id,season,'openligadb',str(r['matchID']),h,a,hn,an,
            start.date().isoformat(),status,hg,ag,observed_at,None,LICENSE,scope,start.isoformat()).validate(now))
    meta=coverage(events,c,season,now)
    if not meta['complete_fixture_schedule']: raise ValueError('Incomplete OpenLigaDB team/pair schedule')
    return events, {'ok':True,'checked_at':observed_at,'coverage':meta,'sha256':sha256(raw).hexdigest(),
        'same_day_finals_withheld':sum(e.score_scope=='same_day_final_withheld' for e in events),
        'provider':'openligadb','source_url':'https://api.openligadb.de/getmatchdata/'+shortcut+'/'+str(year),
        'license_reference':LICENSE,'attribution':'Contains information from OpenLigaDB, available under the Open Database License (ODbL) 1.0.'}


def save(store,raw,league,observed_at,now=None):
    """Validate first; failed refreshes cannot replace a successful snapshot."""
    now=now or utcnow();events,meta=parse(raw,league,observed_at,now)
    previous=reconciled(store,COMPETITIONS[league].id,now)
    by_id={e.fixture_id:e for e in events}
    for row in previous:
        old=row['observation'];new=by_id.get(row['fixture_id'])
        if old['season']!='2026-27' or old['status']!='completed':continue
        if (row['conflicts'] or not new or new.status!='completed' or new.event_date!=old['event_date']
            or (new.home_score,new.away_score)!=(old['home_score'],old['away_score'])):
            raise ValueError('New results conflict with a previously observed completed fixture')
    ingest(store,events,meta|{'source':meta['source_url']},now)
    store.cache('openliga-current-'+league,{'events':[asdict(e) for e in events],'meta':meta},parse_time(observed_at))
    return meta


def current(store,league,now=None,allow_fetch=False):
    """Cache only; network refresh belongs to an explicit bounded import job."""
    now=now or utcnow();value=store.cached('openliga-current-'+league,TTL,now)
    if value:
        meta=value['meta'];events=[EventObservation(**e).validate(now) for e in value['events']]
        if meta.get('provider')!='openligadb' or not meta.get('sha256'): raise ValueError('Saved result provenance missing')
        return events,meta
    with store.connect() as db:exists=db.execute('SELECT 1 FROM cache WHERE key=?',('openliga-current-'+league,)).fetchone()
    return [],{'ok':False,'provider':'openligadb','problem':'Saved OpenLigaDB observation expired' if exists else 'No imported OpenLigaDB full-season observation'}


def model_inputs(store,league,now=None,allow_fetch=False):
    """Withhold today's reported finals entirely; do not fake update timezones.

    Full-source coverage was checked before filtering. No same-day score enters
    the model. Actual unfinished/overdue games remain unresolved and blocking.
    Once the date changes a fresh source observation is required to recover the
    withheld scores; cached unknown scores cannot become completed implicitly.
    """
    now=now or utcnow();events,meta=current(store,league,now)
    return [e for e in events if not (e.event_date==now.date().isoformat() and e.score_scope=='same_day_final_withheld')],meta


def complete_history(store, raw, pinned_raw, observed_at, now=None):
    """Reconcile all 294 previously scored matches; append only the 12 gaps.

    Full source files remain private. The source-specific ODbL subset can be
    exported independently of predictions and unrelated historical records.
    """
    from intelligence.data_adapters import openfootball
    from intelligence.expanded_models import load
    now=now or utcnow();league='Bundesliga';artifact=load(league)
    pin=json.loads((ROOT/'config/multi_source_snapshot.json').read_text())['files']['2025-26/de.1.json']
    if not artifact or sha256(pinned_raw).hexdigest()!=pin: raise ValueError('Frozen history source mismatch')
    old=openfootball(pinned_raw,league,'2025-26',observed_at,now)
    events,meta=parse(raw,league,observed_at,now,year=2025)
    if not meta['coverage']['complete_historical_season']: raise ValueError('Previous season still incomplete')
    previous={e.fixture_id:e for e in old};extra=[];matched=0
    for e in events:
        p=previous.get(e.fixture_id)
        if not p or p.event_date!=e.event_date: raise ValueError('Historical fixture/date mismatch')
        if p.status=='completed':
            if (p.home_score,p.away_score)!=(e.home_score,e.away_score): raise ValueError('Historical final score conflict')
            matched+=1
        else: extra.append({'fixture_id':e.fixture_id,'season':e.season,'date':e.event_date,
            'home':e.home_id,'away':e.away_id,'hg':e.home_score,'ag':e.away_score})
    if len(previous)!=306 or matched!=294 or len(extra)!=12: raise ValueError('Unexpected historical recovery cohort')
    successful=history_completion(store,now)
    if successful:
        if (successful.get('base_artifact_sha256')!=artifact['artifact_sha256']
            or successful.get('pinned_source_sha256')!=pin or successful.get('rows')!=extra):
            raise ValueError('Recovered historical results changed; explicit reconciliation required')
        # Keep the first verified completed-season evidence identity when only
        # a later receipt timestamp changed. Do not invalidate all sessions or
        # silently replace any of the twelve genuinely recovered scores.
        return successful
    value={'base_artifact_sha256':artifact['artifact_sha256'],'pinned_source_sha256':pin,
        'matched':matched,'added':len(extra),'rows':extra,'source':meta,'source_events':[asdict(e) for e in events]}
    value['sha256']=digest(value)
    store.cache('openliga-history-completion-Bundesliga',value,now)
    return value


def history_completion(store,now=None):
    value=store.cached('openliga-history-completion-Bundesliga',10*366*86400,now)
    if not value or digest({k:v for k,v in value.items() if k!='sha256'})!=value.get('sha256'):
        return None
    return value


def public_dataset(store):
    """ODbL source subset only: never export private predictions or other data."""
    with store.connect() as db:
        rows=db.execute("SELECT payload FROM cache WHERE key IN ('openliga-current-Premier League','openliga-current-Bundesliga')").fetchall()
    data=[json.loads(r['payload']) for r in rows]
    completion=history_completion(store)
    if completion:data.append({'events':completion['source_events'],'meta':completion['source']})
    return json.dumps({'license':LICENSE,'attribution':'OpenLigaDB; normalized identities and prior-date final-score handling modified by this application.',
        'source_datasets':data},indent=2,allow_nan=False)
