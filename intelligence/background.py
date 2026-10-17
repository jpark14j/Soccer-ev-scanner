"""Independent pregame worker with a fenced, durable single-writer authority.

Explicit activation only. No browser, OpenAI, Telegram or wager execution.
"""
from datetime import timedelta
from pathlib import Path
import argparse,json,os,sqlite3,tempfile
from intelligence.domain import utcnow,parse_time,digest
from intelligence.storage import Store
from intelligence.shared_state import Client,StateError,configuration,materialize,hydrate_budgets,snapshot

LEAGUES=('Premier League','Bundesliga','Ligue 1')


def run_id(now):return digest(('background-pregame-1',now.strftime('%Y-%m-%dT%H')))


def verify_assets(store):
    from intelligence.data_adapters import ROOT
    from hashlib import sha256
    with store.connect() as db:
        rows=db.execute('SELECT path,sha256 FROM backup_model_assets').fetchall()
    if not rows:raise StateError('Frozen model assets missing from committed state')
    for r in rows:
        path=(ROOT/r['path']).resolve()
        if not path.is_relative_to(ROOT.resolve()) or not path.is_file() or sha256(path.read_bytes()).hexdigest()!=r['sha256']:
            raise StateError('Committed model assets differ from this worker checkout; reviewed migration required')


def bootstrap(source,client=None,config=None):
    """Operator-only first head; no provider requests or historical backfill."""
    client=client or Client(config or configuration(),writer=True)
    source=Path(source)
    if not source.is_file():raise StateError('Bootstrap requires an existing inspected SQLite store')
    store=Store(source)
    with store.connect() as db:identity=db.execute('SELECT instance FROM store_identity WHERE id=1').fetchone()[0]
    identifier=digest(('explicit-bootstrap-1',identity));head=client.acquire(identifier)
    try:
        if head['generation']!=0:raise StateError('Shared state already exists; bootstrap never overwrites it')
        # Initial current-day counts are reconciled separately by the operator in
        # Postgres. The default remote hold is NOT released by bootstrap.
        body=snapshot(store)
        response=client.control('checkpoint',body|{'expected_generation':0,'run_id':identifier,
            'summary':{'mode':'explicit bootstrap','provider_requests':0},'publications':[],'prospective_deadline':None})
        observed=client.read()
        if observed['generation']!=response['generation'] or observed['snapshot']['manifest']!=body['manifest']:raise StateError('Bootstrap readback differs')
        return {'status':'bootstrapped','generation':response['generation'],'shared_readback_verified':True,
            'provider_requests':0,'activation':'Worker and request hold are unchanged; operator configuration still required'}
    except Exception:
        try:client.control('fail')
        except StateError:pass
        raise


def collect_supported(store,key,now=None,provider=None):
    """Discovery and supported totals/BTTS only; no speculative prop spending."""
    from intelligence.providers import OddsAPI,normalize,ProviderError
    from intelligence.quota import quota_details
    now=now or utcnow();audit=[]
    if not key:return [{'status':'odds credential not configured; saved observations only'}]
    if quota_details(store,9,now)['remaining']==0:return [{'status':'odds allowance unavailable; no discovery or odds calls'}]
    provider=provider or OddsAPI(key,store,daily_limit=9,ttl=1800)
    upcoming={}
    for league in LEAGUES:
        try:
            response=provider.events(league)
            upcoming[league]=sorted([e for e in response['data'] if
                now+timedelta(minutes=15)<parse_time(e['commence_time'])<=now+timedelta(hours=48)],key=lambda e:e['commence_time'])[:12]
            store.cache('background-discovery-'+league,response)
        except (ProviderError,ValueError,KeyError,TypeError):
            audit.append({'league':league,'status':'event discovery failed; no fixture invented'})
            upcoming[league]=[]
    tasks=[]
    for league in ('Premier League','Ligue 1'):
        if upcoming[league]:tasks.append((league,None,'totals'))
    # Round robin across supported leagues/games rather than preferring a book.
    for i in range(max((len(upcoming[l]) for l in ('Premier League','Bundesliga')),default=0)):
        for league in ('Premier League','Bundesliga'):
            if i<len(upcoming[league]):tasks.append((league,upcoming[league][i]['id'],'btts'))
    for league,event,market in tasks:
        if quota_details(store,9)['remaining']<1:
            audit.append({'status':'daily odds cap reached; remaining market tasks skipped'});break
        try:
            response=provider.odds(league,(market,)) if event is None else provider.event_odds(league,event,(market,))
            normalize(response['data'],league,response['received_at'])  # Validate, preserving exact original bytes/timestamps below.
            cache='last-success-'+league+'-'+market if event is None else 'event-snapshot-'+league+'-'+event+'-'+market
            store.cache(cache,response)
            audit.append({'league':league,'market':market,'event_id':event,'status':'observed provider response','received_at':response['received_at']})
        except (ProviderError,ValueError,KeyError,TypeError):
            audit.append({'league':league,'market':market,'status':'provider failure; previous successful observations retained'})
            break  # No repeated chargeable failures or immediate polling.
    return audit


def cycle(store,key='',now=None,provider=None):
    """Reusable integration seam. Tests supply fixtures; production uses adapters."""
    from intelligence.current_results import current
    from intelligence.pipeline import run_analysis
    from intelligence.forward_testing import reconcile
    from intelligence.publication_journal import prepare,reconcile as settle,performance
    from intelligence.learning import lock_protocol,update
    now=now or utcnow();lock_protocol(store,now)
    results={}
    for league in LEAGUES:
        _,meta=current(store,league)
        results[league]={k:meta.get(k) for k in ('ok','failure_code','checked_at','problem')}
    audit=collect_supported(store,key,now,provider)
    analysis=run_analysis('',LEAGUES,store=store,cached_only=True,window_hours=48)
    labels=reconcile(store)
    created=prepare(analysis,store)
    settlement=settle(store)
    learning=update(store)
    summary={'mode':'independent pregame research','observed_quotes':len(analysis.quotes),
        'coverage_status':'partial: inputs or market evidence unavailable' if not analysis.estimates or not all(r.get('ok') for r in results.values()) else 'experimental supported inputs; no betting approval',
        'model_estimates':len(analysis.estimates),'new_publications':len(created),'new_forward_labels':labels['labeled'],
        'new_published_labels':settlement['labeled'],'results':results,'odds_tasks':audit,
        'learning':learning,'paid_ai_requests':0,'approved_opportunities':len(analysis.opportunities),
        'performance':performance(store),'backfill':'Missed runs reconcile saved pending events. Missed pregame picks are never reconstructed.'}
    store.cache('background-latest-summary',summary)
    return summary,created


def run_background(*,client=None,config=None,now=None,cycle_fn=None):
    # These flags authorize a configured integration; they do not prove hosted
    # operation. The remote hold, fence and budget remain authoritative.
    if os.getenv('RESEARCH_WORKER_ENABLED','0')!='1':return {'status':'disabled','provider_requests':0}
    if os.getenv('PAID_ANALYST_APPROVED','0')!='0':raise StateError('Background worker requires paid AI disabled')
    if os.getenv('RESEARCH_DATA_RIGHTS_VERIFIED','0')!='1':raise StateError('Review permitted provider research use before worker activation')
    if os.getenv('RESEARCH_BUDGET_SCOPE_REVIEWED','0')!='1':raise StateError('Review other users of the same provider credentials; production is outside this development ledger')
    client=client or Client(config or configuration(),writer=True);now=now or utcnow();identifier=run_id(now)
    envelope=client.acquire(identifier)
    try:
        with tempfile.TemporaryDirectory(prefix='research-writer-') as folder:
            path=materialize(envelope,Path(folder)/'working.sqlite3')
            from intelligence.shared_state import MAX_RAW
            if path.stat().st_size>MAX_RAW-16*1024*1024 or len(envelope['snapshot']['compressed'])>4800000:
                raise StateError('Shared state is approaching its bounded capacity; reviewed storage migration required before new provider requests')
            store=Store(path,request_authority=client);store.commit_generation=client.generation+1
            hydrate_budgets(store,envelope);verify_assets(store)
            from intelligence.forward_testing import records
            old_ids={r['id'] for r in records(store)}
            summary,created=(cycle_fn or cycle)(store,os.getenv('ODDS_API_KEY',''),now)
            new=[r for r in records(store) if r['id'] not in old_ids]
            starts=[r['payload']['quote']['commence_time'] for r in new]+[r['kickoff'] for r in created]
            body=snapshot(store)
            receipt=client.control('checkpoint',body|{'expected_generation':client.generation,'run_id':identifier,
                'prospective_deadline':min(starts,key=parse_time) if starts else None,'publications':created,
                'summary':{'new_publications':len(created),'new_forward_forecasts':len(new),
                    'new_labels':summary.get('new_forward_labels',0),'paid_ai_requests':0,
                    'coverage_status':summary.get('coverage_status','integration replay')}})
            observed=client.read()
            verified=observed.get('generation')==receipt['generation'] and observed.get('snapshot',{}).get('manifest')==body['manifest']
            return {'status':'committed','generation':receipt['generation'],'committed_at':receipt['committed_at'],
                'shared_readback_verified':verified,'summary':summary,
                'note':'One independent invocation; this does not verify a recurring scheduler, redeployment or model improvement.'}
    except Exception:
        try:client.control('fail')
        except StateError:pass
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',action='store_true',help='Explicit enabled independent cycle; otherwise no external requests')
    p.add_argument('--bootstrap',type=Path,help='Explicit existing-store first upload; never enables provider calls')
    p.add_argument('--pull',type=Path,help='Explicit read-only committed-state sync directory')
    args=p.parse_args()
    if sum(bool(v) for v in (args.run,args.bootstrap,args.pull))>1:p.error('Choose one explicit operation')
    try:
        if args.bootstrap:result=bootstrap(args.bootstrap)
        elif args.pull:
            from intelligence.shared_state import pull_replica
            r=pull_replica(args.pull);result={'status':'replica saved','generation':r['envelope']['generation'],'sports_requests':0}
        elif args.run:result=run_background()
        else:result={'status':'disabled dry status; no network requests','activation_required':True}
        print(json.dumps(result,allow_nan=False,default=str))
    except (StateError,OSError,sqlite3.Error,ValueError,KeyError,TypeError):
        print(json.dumps({'status':'blocked or failed','error_code':'configuration_storage_or_provider',
            'action':'Inspect private configuration and saved heartbeat. No credentials or raw exception text are logged.'}));raise SystemExit(1) from None


if __name__=='__main__':main()
