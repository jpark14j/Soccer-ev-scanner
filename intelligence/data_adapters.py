"""Authorized public snapshots and existing locally licensed/provider results."""
from dataclasses import asdict
from datetime import date
from hashlib import sha256
from pathlib import Path
import json
from functools import lru_cache
from intelligence.domain import digest,utcnow,parse_time
from intelligence.competitions import COMPETITIONS
from intelligence.event_data import EventObservation,ingest,coverage

ROOT=Path(__file__).resolve().parents[1]
SOURCE_ROOT='https://raw.githubusercontent.com/openfootball/football.json/'
SOURCE_LICENSE='https://github.com/openfootball/football.json/blob/master/LICENSE.md'
SEASONS=tuple(f'{y}-{str(y+1)[-2:]}' for y in range(2020,2027))


def download_snapshot(directory,session=None):
    """Explicit one-off pinned archive import: at most 36 sequential public GETs.

    This is never called by page rendering or automatic analysis. Existing files
    are verified/reused; corrupt files are not silently overwritten. No retries.
    """
    import requests
    import time
    manifest=json.loads((ROOT/'config/multi_source_snapshot.json').read_text())
    files={'LICENSE.md':manifest['license_sha256'],**manifest['files']}
    allowed={'LICENSE.md',*(s+'/'+c.source_file+'.json' for s in SEASONS for c in COMPETITIONS.values() if c.source_file)}
    if set(files)!=allowed or len(files)>36:raise ValueError('Unreviewed archive request list')
    target=Path(directory);target.mkdir(parents=True,exist_ok=True);owned=session is None;session=session or requests.Session();calls=0
    try:
        for name,checksum in files.items():
            path=target/name.replace('/','_')
            if path.exists():raw=path.read_bytes()
            else:
                response=session.get(SOURCE_ROOT+manifest['revision']+'/'+name,timeout=(5,15),allow_redirects=False)
                calls+=1
                try:
                    if response.status_code!=200 or len(response.content)>2_000_000:raise ValueError('Pinned public archive unavailable')
                    raw=response.content
                finally:response.close()
                if sha256(raw).hexdigest()==checksum:path.write_bytes(raw)
                time.sleep(.25)
            if sha256(raw).hexdigest()!=checksum:raise ValueError('Pinned archive hash mismatch; no content substituted')
    except requests.RequestException:raise ValueError('Public archive connection unavailable') from None
    finally:
        if owned:session.close()
    return {'public_archive_requests':calls,'verified_files':len(files),'odds_requests':0}


@lru_cache(maxsize=1)
def aliases():
    return json.loads((ROOT/'config/team_aliases.json').read_text())


def team_identity(competition,name):
    if competition.sport=='Soccer':
        canonical=aliases().get(competition.name,{}).get(name)
        if canonical is None:raise ValueError('Unreviewed team alias: '+str(name))
        return 'soccer:club:'+competition.id.split(':')[1]+':'+digest(canonical)[:20],canonical
    from intelligence.team_codes import NBA,MLB
    mapping=NBA if competition.sport=='NBA' else MLB
    for current,codes in mapping.items():
        if name==current or name in codes:return competition.sport.lower()+':team:'+codes[0],current
    # Archive-only identity: intentionally not linked to a current franchise.
    if isinstance(name,str) and name.isalnum() and len(name)<=4:
        return competition.sport.lower()+':archive:'+name,name
    raise ValueError('Unreviewed current team identity')


def openfootball(raw,league,season,observed_at,now=None):
    now=now or utcnow();c=COMPETITIONS[league]
    if not c.source_file or season not in SEASONS or len(raw)>2_000_000:
        raise ValueError('Unsupported source scope or oversized response')
    data=json.loads(raw);matches=data.get('matches') if isinstance(data,dict) else None
    if not isinstance(matches,list) or not 1<=len(matches)<=500:
        raise ValueError('Unexpected public-results schema')
    result=[];seen=set();a=aliases()[league]
    for m in matches:
        if not isinstance(m,dict):raise ValueError('Invalid fixture record')
        h,aw=m.get('team1'),m.get('team2')
        if h not in a or aw not in a:raise ValueError('Unreviewed public-source team name')
        home_id,home=team_identity(c,h);away_id,away=team_identity(c,aw)
        day=date.fromisoformat(m['date']).isoformat();year=int(season[:4])
        if not f'{year}-07-01'<=day<=f'{year+1}-06-30':raise ValueError('Fixture outside the declared season')
        score=m.get('score');ft=score.get('ft') if isinstance(score,dict) else None
        if ft is not None and (not isinstance(ft,list) or len(ft)!=2 or any(type(v) is not int or not 0<=v<=30 for v in ft)):
            raise ValueError('Invalid public full-time score')
        status='completed' if ft is not None else 'unresolved' if day<now.date().isoformat() else 'scheduled'
        e=EventObservation(c.id,season,'openfootball',season+':'+home_id+':'+away_id,
            home_id,away_id,home,away,day,status,ft[0] if ft else None,ft[1] if ft else None,
            observed_at,None,SOURCE_LICENSE,'source_reported_ft').validate(now)
        if e.fixture_id in seen:raise ValueError('Duplicate seasonal home/away fixture')
        seen.add(e.fixture_id);result.append(e)
    return result


def pinned_history(directory,league,now=None):
    now=now or utcnow();c=COMPETITIONS[league]
    manifest=json.loads((ROOT/'config/multi_source_snapshot.json').read_text())
    license_raw=(Path(directory)/'LICENSE.md').read_bytes()
    if sha256(license_raw).hexdigest()!=manifest['license_sha256']:
        raise ValueError('Pinned license differs from reviewed source')
    events=[];sources=[]
    for season in SEASONS:
        path=season+'/'+c.source_file+'.json';raw=(Path(directory)/path.replace('/','_')).read_bytes()
        if sha256(raw).hexdigest()!=manifest['files'][path]:raise ValueError('Pinned content hash mismatch')
        parsed=openfootball(raw,league,season,now.isoformat(),now);events.extend(parsed)
        sources.append(coverage(parsed,c,season,now)|{'url':SOURCE_ROOT+manifest['revision']+'/'+path,
            'sha256':sha256(raw).hexdigest(),'license_reference':SOURCE_LICENSE})
    return events,sources


def import_history(store,directory,leagues=None,now=None):
    now=now or utcnow();summary={}
    leagues=leagues or [c.name for c in COMPETITIONS.values() if c.source_file]
    for league in leagues:
        events,sources=pinned_history(directory,league,now)
        for source in sources:
            ingest(store,[e for e in events if e.season==source['season']],source,now)
        summary[league]={'coverage':sources,'normalized_events':len(events)}
    return summary


def provider_results(store,now=None):
    """Bridge already-collected finals. No new odds/result request or quota use."""
    now=now or utcnow()
    from intelligence.results import ensure_table
    ensure_table(store);summary={'normalized':0,'rejected':0}
    with store.connect() as db:rows=[json.loads(r['payload']) for r in db.execute('SELECT payload FROM observed_results')]
    for row in rows:
        try:
            c=COMPETITIONS[row['league']]
            home_id,home=team_identity(c,row['home']);away_id,away=team_identity(c,row['away'])
            day=parse_time(row['commence_time']).date().isoformat()
            event=EventObservation(c.id,day[:4],'the-odds-api',row['event_id'],home_id,away_id,home,away,day,
                'completed',row['home_score'],row['away_score'],row['received_at'],row['observed_at'],
                'https://the-odds-api.com/terms-of-use.html',
                'full_event_final_including_extras' if c.sport in ('NBA','MLB') else 'unverified_soccer_period',row['commence_time'],True)
            value=ingest(store,[event],{'source':'existing private provider observation','sha256':digest(row),
                'license_reference':event.license_reference,'rights':'Existing account only; redistribution unverified'},now)
            summary['normalized']+=value['added_observations']
        except (ValueError,KeyError,TypeError):summary['rejected']+=1
    return summary


def licensed_archive(store,league,directory,now=None):
    """Import existing validated local history/manifest, never a guessed current feed."""
    from intelligence.history import load_licensed
    now=now or utcnow();c=COMPETITIONS[league]
    frame=load_licensed(league,directory)
    manifest=json.loads((Path(directory)/(league.lower()+'.source.json')).read_text())
    events=[]
    for row in frame.itertuples():
        h,hn=team_identity(c,row.HomeTeam);a,an=team_identity(c,row.AwayTeam)
        events.append(EventObservation(c.id,str(row.date.year),'licensed-archive',str(row.game_id),h,a,hn,an,
            row.date.date().isoformat(),'completed',int(row.FTHG),int(row.FTAG),now.isoformat(),None,
            manifest['license_reference'],'archive_full_final').validate(now))
    return ingest(store,events,{'source':manifest['source'],'license_reference':manifest['license_reference'],
        'sha256':manifest['normalized_sha256'],'snapshot_only':True},now)
