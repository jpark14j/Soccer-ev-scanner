"""Bounded, attributed public results, reconciled to frozen soccer fixtures.

No account, held-provider endpoint, price, model fitting or approval operation.
Raw responses stay in the private saved store, not a public dataset export.
"""
from dataclasses import asdict, replace
from datetime import date, timedelta
from hashlib import sha256
import json
import re
import requests
from intelligence.domain import utcnow, parse_time, digest
from intelligence.competitions import COMPETITIONS
from intelligence.data_adapters import ROOT, openfootball, team_identity
from intelligence.event_data import EventObservation, coverage, ingest

TERMS='https://sportscore.com/developers/terms/'
NBA_URL='https://sporting-events.org/data/nba.json'
TTL=21600
SCOPES={'Premier League':('english-premier-league','English Premier League'),
        'Ligue 1':('french-ligue-1','French Ligue 1'),
        'NBA':('national-basketball-association','National Basketball Association')}
# Provider-specific reviewed names; the frozen historical identity map is intact.
ALIASES={'Premier League':{'Bournemouth AFC':'Bournemouth','Brighton Hove Albion':'Brighton',
    'Hull City':'Hull','Tottenham Hotspur':'Tottenham','Wolverhampton Wanderers':'Wolves'},
    'Ligue 1':{'Angers SCO':'Angers SCO','Marseille':'Marseille','AS Monaco':'Monaco',
    'Paris Saint Germain':'Paris Saint-Germain','RC Strasbourg Alsace':'Strasbourg',
    'Havre Athletic Club':'Le Havre AC','AJ Auxerre':'AJ Auxerre','Stade Rennais FC':'Rennes',
    'LOSC Lille':'Lille','Stade Brestois 29':'Brest','RC Lens':'Lens','ESTAC Troyes':'Troyes',
    'Lorient':'FC Lorient','OGC Nice':'Nice','Olympique Lyonnais':'Lyon',
    'FC Nantes':'FC Nantes','Toulouse FC':'Toulouse FC','Le Mans FC':'Le Mans FC','Le Mans':'Le Mans FC','Metz':'FC Metz'}}


def identity(league, name):
    from intelligence.data_adapters import aliases
    reviewed=ALIASES.get(league,{}).get(name,name)
    if league!='NBA' and reviewed in aliases()[league].values():
        reviewed=next(k for k,v in aliases()[league].items() if v==reviewed)
    return team_identity(COMPETITIONS[league],reviewed)


def download(url):
    """Only Collector constructs URLs. One attempt, no credentials or redirects."""
    from urllib.parse import urlsplit,parse_qs
    parts=urlsplit(url);query=parse_qs(parts.query)
    pin=json.loads((ROOT/'config/multi_source_snapshot.json').read_text())
    archives={'https://raw.githubusercontent.com/openfootball/football.json/'+pin['revision']+'/'+season+'/'+COMPETITIONS[league].source_file+'.json'
        for league in ('Premier League','Ligue 1') for season in ('2025-26','2026-27')}
    daily=(parts.scheme=='https' and parts.netloc=='sportscore.com' and parts.path=='/api/v1/fixtures/'
        and not parts.fragment and set(query)=={'sport','date','competition','limit'} and query['limit']==['20']
        and len(query['date'])==1 and re.fullmatch(r'202[56]-\d{2}-\d{2}',query['date'][0])
        and any(query['competition']==[slug] and query['sport']==['basketball' if league=='NBA' else 'football']
            for league,(slug,_) in SCOPES.items()))
    if url not in archives and url!=NBA_URL and not daily:raise ValueError('Unreviewed public source URL')
    with requests.Session() as session:
        response=session.get(url,timeout=(5,12),allow_redirects=False,stream=True,
            headers={'Accept':'application/json','User-Agent':'SportsResearch-AttributedPublicResults/1.0'})
        try:
            if response.status_code!=200:raise ValueError('Public results HTTP response unavailable')
            chunks=[];size=0
            for chunk in response.iter_content(65536):
                size+=len(chunk)
                if size>2_000_000:raise ValueError('Public results response exceeds bound')
                chunks.append(chunk)
            return b''.join(chunks),utcnow().isoformat()
        finally:response.close()


class Collector:
    def __init__(self,store,now,fetch=download):
        self.store,self.now,self.fetch=store,now,fetch;self.requests=0;self.network_requests=0
        self.real_time=fetch is download

    def get(self,key,url,age=10800):
        value=self.store.cached('public-source-'+key,age,self.now)
        if value:
            if sha256(value['raw'].encode()).hexdigest()!=value['sha256']:raise ValueError('Cached public source checksum differs')
            return value
        if self.store.cached('public-attempt-'+key,10800,self.now):
            raise ValueError('Public source retry interval has not elapsed')
        if self.requests>=200:raise ValueError('Public-data per-run request bound reached; continue next scheduled update')
        self.requests+=1
        if not getattr(self.fetch,'prepared_receipts',False):self.network_requests+=1
        # Reserve the attempt before transport, including failures. Never retry.
        self.store.cache('public-attempt-'+key,{'attempted_at':self.now.isoformat()},self.now)
        raw,at=self.fetch(url)
        if self.real_time:self.now=utcnow()
        if len(raw)>2_000_000 or not 0<=(self.now-parse_time(at)).total_seconds()<TTL:
            raise ValueError('Invalid public source receipt')
        json.loads(raw)
        value={'raw':raw.decode('utf-8'),'checked_at':at,'sha256':sha256(raw).hexdigest(),'source_url':url}
        self.store.cache('public-source-'+key,value,parse_time(at))
        return value

    def archive(self,league,season):
        pin=json.loads((ROOT/'config/multi_source_snapshot.json').read_text())
        path=season+'/'+COMPETITIONS[league].source_file+'.json'
        value=self.get('archive-'+path,'https://raw.githubusercontent.com/openfootball/football.json/'+pin['revision']+'/'+path,10*366*86400)
        if value['sha256']!=pin['files'][path]:raise ValueError('Frozen archive checksum differs')
        return value

    def day(self,league,day):
        parsed=date.fromisoformat(day)
        if league not in SCOPES or not date(2025,7,1)<=parsed<=self.now.date()+timedelta(days=7):
            raise ValueError('Unreviewed public results date or competition')
        sport='basketball' if league=='NBA' else 'football';slug=SCOPES[league][0]
        url='https://sportscore.com/api/v1/fixtures/?sport='+sport+'&date='+day+'&competition='+slug+'&limit=20'
        age=10800 if parsed>=self.now.date()-timedelta(days=3) else 366*86400
        value=self.get(slug+'-'+day,url,age)
        return parse_day(value,league,day,self.now),value


def parse_day(value,league,day,now):
    data=json.loads(value['raw']);sport='basketball' if league=='NBA' else 'football'
    if (data.get('sport')!=sport or data.get('date')!=day or type(data.get('count')) is not int
        or not isinstance(data.get('matches'),list) or data['count']!=len(data['matches']) or not 0<=data['count']<20):
        raise ValueError('Incomplete or mismatched public daily response')
    events=[];seen=set()
    for r in data['matches']:
        if r['competition']!=SCOPES[league][1]:raise ValueError('Public result competition mismatch')
        h,hn=identity(league,r['home']);a,an=identity(league,r['away']);start=parse_time(r['time'])
        if start.date().isoformat()!=day or not r['url'].startswith('/'+sport+'/match/'):
            raise ValueError('Public fixture date or source identifier mismatch')
        finished=r['status']=='finished'
        if r['status'] not in ('finished','upcoming','live','postponed','cancelled','suspended'):
            raise ValueError('Unreviewed public fixture status')
        if finished:
            scores=[r['home_score'],r['away_score']]
            if any(not isinstance(s,(str,int)) or isinstance(s,bool) or not str(s).isdigit() for s in scores):
                raise ValueError('Missing final score')
            hg,ag=map(int,scores)
            if any(not 0<=v<=(250 if league=='NBA' else 30) for v in (hg,ag)) or start>parse_time(value['checked_at']):
                raise ValueError('Invalid or future final score')
            if league=='NBA' and (min(hg,ag)<40 or hg==ag):raise ValueError('Invalid NBA full-game final')
        completed=finished and start.date()<now.date()
        season='2025-26' if start.date()<date(2026,7,1) else '2026-27'
        event=EventObservation(COMPETITIONS[league].id,season,'sportscore',r['url'],h,a,hn,an,day,
            'completed' if completed else 'scheduled' if r['status']=='upcoming' and start>now else 'unresolved',
            hg if completed else None,ag if completed else None,value['checked_at'],None,TERMS,
            'same_day_final_withheld' if finished and start.date()==now.date() else
            'source_'+r['status'] if r['status'] in ('postponed','cancelled','suspended') else 'source_reported_ft',start.isoformat()).validate(now)
        if event.fixture_id in seen:raise ValueError('Duplicate daily fixture')
        seen.add(event.fixture_id);events.append(event)
    return events


def reconcile_archive(base,observations):
    """No revised completed score/date is accepted; unknown slots can be filled."""
    merged={e.fixture_id:e for e in base}
    for e in observations:
        old=merged.get(e.fixture_id)
        if old is None:raise ValueError('Daily fixture not present in reviewed full-season schedule')
        if old.status=='completed' and (e.status!='completed' or old.event_date!=e.event_date
            or (old.home_score,old.away_score)!=(e.home_score,e.away_score)):
            raise ValueError('Daily result conflicts with an already completed fixture')
        merged[e.fixture_id]=e
    return list(merged.values())


def save_soccer(collector,league):
    """Recover only missing history, then reconcile an entire current season."""
    from intelligence.epl_forecasts import load_artifact
    from intelligence.expanded_models import load
    now=collector.now;store=collector.store;c=COMPETITIONS[league]
    artifact=load_artifact() if league=='Premier League' else load(league)
    if not artifact:raise ValueError('Frozen model unavailable')
    completion=store.cached('public-history-completion-'+league,10*366*86400,now)
    if not completion:
        source=collector.archive(league,'2025-26')
        base=openfootball(source['raw'].encode(),league,'2025-26',source['checked_at'],now)
        missing=[e for e in base if e.status!='completed'];observations=[];receipts=[]
        for day in sorted({e.event_date for e in missing}):
            events,receipt=collector.day(league,day);observations+=events;receipts.append(receipt['sha256'])
        # On historical dates the endpoint may also contain other rounds; only
        # this reviewed season's exact identities can enter reconciliation.
        recovered=reconcile_archive(base,observations)
        meta=coverage(recovered,c,'2025-26',now)
        if not meta['complete_historical_season']:
            raise ValueError('Prior-season result gaps remain: '+str(meta['unresolved_past']))
        ids={e.fixture_id for e in missing};rows=[]
        from intelligence.epl_source import team
        for e in recovered:
            if e.fixture_id not in ids:continue
            row={'season':e.season,'date':e.event_date,'home':team(e.home_name) if league=='Premier League' else e.home_id,
                'away':team(e.away_name) if league=='Premier League' else e.away_id,'hg':e.home_score,'ag':e.away_score}
            if league!='Premier League':row['fixture_id']=e.fixture_id
            rows.append(row)
        completion={'kind':'verified-missing-prior-results-1','league':league,'base_artifact_sha256':artifact['artifact_sha256'],
            'pinned_source_sha256':source['sha256'],'matched':len(base)-len(missing),'added':len(rows),
            'rows':sorted(rows,key=lambda r:(r['date'],r['home'],r['away'])),'source_receipts':receipts}
        completion['sha256']=digest(completion)
        store.cache('public-history-completion-'+league,completion,now)
    elif completion['base_artifact_sha256']!=artifact['artifact_sha256']:
        raise ValueError('Historical completion model identity changed')
    source=collector.archive(league,'2026-27')
    base=openfootball(source['raw'].encode(),league,'2026-27',source['checked_at'],now)
    observations=[];receipts=[];failed_dates=[]
    day=date(2026,8,21)
    while day<=now.date()+timedelta(days=7):
        try:
            events,receipt=collector.day(league,day.isoformat());observations+=events;receipts.append(receipt)
        except (ValueError,requests.RequestException):
            failed_dates.append(day.isoformat())
        day+=timedelta(days=1)
    now=collector.now
    events=reconcile_archive(base,observations)
    previous=store.cached('public-results-current-'+league,10*366*86400,now)
    if previous:
        old=[EventObservation(**e) for e in previous['events'] if e['status']=='completed']
        latest={e.fixture_id:e for e in events}
        for e in old:
            new=latest.get(e.fixture_id)
            if (not new or new.status!='completed' or new.event_date!=e.event_date
                or (new.home_score,new.away_score)!=(e.home_score,e.away_score)):
                raise ValueError('Public refresh withdrew or revised a previously completed result')
    recent=[r['checked_at'] for r in receipts if date.fromisoformat(json.loads(r['raw'])['date'])>=now.date()-timedelta(days=3)]
    if not recent:raise ValueError('No recent public source observation')
    checked=min(recent,key=parse_time)
    if not 0<=(now-parse_time(checked)).total_seconds()<TTL:raise ValueError('Recent public results verification expired')
    meta={'ok':True,'provider':'sportscore','checked_at':checked,'coverage':coverage(events,c,'2026-27',now),
        'source_url':'https://sportscore.com/developers/api/','license_reference':TERMS,
        'sha256':digest([source['sha256']]+[r['sha256'] for r in receipts]),
        'source_receipts':[{k:r[k] for k in ('source_url','sha256','checked_at')} for r in receipts],
        'unavailable_query_dates':failed_dates,
        'attribution':'Powered by SportScore; OpenFootball CC0 fixture reconciliation'}
    ingest(store,events,meta,now)
    store.cache('public-results-current-'+league,{'events':[asdict(e) for e in events],'meta':meta},parse_time(checked))
    return meta


def current(store,league,now=None,allow_fetch=False):
    """Cache only. Overdue fixtures become unresolved without inventing results."""
    now=now or utcnow();value=store.cached('public-results-current-'+league,TTL,now)
    if not value:
        attempt=store.cached('public-results-status-'+league,86400,now)
        return [],{'ok':False,'provider':'sportscore','problem':(attempt or {}).get('problem','No fresh reconciled public results snapshot')}
    events=[EventObservation(**e).validate(now) for e in value['events']]
    events=[replace(e,status='unresolved') if e.status=='scheduled' and
        (parse_time(e.kickoff)<=now if e.kickoff else e.event_date<now.date().isoformat()) else e for e in events]
    meta=dict(value['meta']);meta['coverage']=coverage(events,COMPETITIONS[league],'2026-27',now)
    return events,meta


def model_inputs(store,league,now=None,allow_fetch=False):
    now=now or utcnow();events,meta=current(store,league,now)
    # Explicitly unplayed fixtures are not missing final scores. They stay in
    # the source/immutable ledger but cannot become model features or picks.
    # Suspensions and unknown/live states still block the existing gates.
    excluded={'source_postponed','source_cancelled'}
    active=[e for e in events if e.score_scope not in excluded and
        not(e.event_date==now.date().isoformat() and e.score_scope=='same_day_final_withheld')]
    if meta.get('ok'):
        meta=dict(meta,coverage=dict(meta['coverage'],
            unresolved_past=sum(e.status!='completed' and e.event_date<now.date().isoformat() for e in active)),
            explicitly_unplayed=sum(e.score_scope in excluded for e in events))
    return active,meta


def prepare(league,store,now=None):
    from intelligence.current_soccer import _prepare
    now=now or utcnow();completion=store.cached('public-history-completion-'+league,10*366*86400,now)
    if not completion:return {'problem':current(store,league,now)[1].get('problem','Prior-season reconciliation unavailable')}
    if digest({k:v for k,v in completion.items() if k!='sha256'})!=completion.get('sha256'):
        return {'problem':'Historical completion checksum differs'}
    return _prepare(league,store,now,False,model_inputs,completion)


def refresh(store,now=None,fetch=download):
    """Independent source failures do not discard another league's good data."""
    now=now or utcnow();collector=Collector(store,now,fetch);status={}
    store.cache('public-results-last-attempt',{'at':now.isoformat()},now)
    from intelligence.nba_current import save as save_nba,NBAReconciliationError
    for league,operation in [('NBA',lambda:save_nba(collector)),
        *[(league,lambda league=league:save_soccer(collector,league)) for league in ('Premier League','Ligue 1')]]:
        try:
            meta=operation();status[league]={'ok':True,'coverage':meta['coverage']}
        except (ValueError,KeyError,TypeError,requests.RequestException):
            # A safe specific failure is produced by the parser, never a URL,
            # credential, response dump, traceback or provider exception text.
            import sys
            error=sys.exception()
            reason=str(error) if isinstance(error,ValueError) and not isinstance(error,requests.RequestException) else 'Public results transport or schema validation failed'
            status[league]={'ok':False,'problem':reason[:220],
                'blocks_cached_inference':isinstance(error,NBAReconciliationError)}
        store.cache('public-results-status-'+league,status[league]|{'checked_at':now.isoformat()},now)
    return {'sources':status,'public_results_requests':collector.network_requests,
        'prepared_receipts_reused':collector.requests-collector.network_requests,'odds_api_requests':0}


def prepared_fetch(directory):
    """Reuse private audit receipts without pretending they were observed now.

    Requested URLs are still constructed only by Collector. No network fallback,
    public raw-data publication, arbitrary file traversal or credential handling.
    """
    from pathlib import Path
    root=Path(directory);entries=json.loads((root/'manifest.json').read_text())
    if not isinstance(entries,list) or len(entries)>250:raise ValueError('Prepared source bound exceeded')
    by_url={}
    for m in entries:
        name=m['file']
        if Path(name).name!=name or name in ('.','..'):raise ValueError('Invalid prepared source filename')
        if m.get('http')!=200:continue
        if m['url'] in by_url:raise ValueError('Duplicate prepared source URL')
        by_url[m['url']]=m
    def fetch(url):
        m=by_url.get(url)
        if m is None:raise ValueError('Prepared public source receipt unavailable; no network fallback')
        raw=(root/m['file']).read_bytes()
        if len(raw)>2_000_000 or sha256(raw).hexdigest()!=m['sha256']:raise ValueError('Prepared source checksum differs')
        return raw,m['observed_at']
    fetch.prepared_receipts=True
    return fetch
