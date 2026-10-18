"""Independent pregame worker with a fenced, durable single-writer authority.

Explicit activation only. No browser, OpenAI, Telegram or wager execution.
"""
from datetime import timedelta
from pathlib import Path
import argparse,json,os,sqlite3,tempfile
from intelligence.domain import utcnow,parse_time,digest
from intelligence.storage import Store
from intelligence.shared_state import Client,StateError,configuration,materialize,hydrate_budgets,snapshot

MODEL_LEAGUES=('Premier League','Bundesliga','Ligue 1')
LEAGUES=('NBA','Premier League','MLB','Bundesliga','Ligue 1')


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


def collect_supported(store,key,now=None,provider=None,window_hours=48):
    """Multi-date discovery; frozen soccer targets plus NBA/MLB price research."""
    from intelligence.providers import OddsAPI,normalize,ProviderError
    from intelligence.quota import quota_details
    now=now or utcnow();audit=[]
    if type(window_hours) is not int or not 1<=window_hours<=168:raise StateError('Invalid worker lookahead window')
    if not key:return [{'status':'odds credential not configured; saved observations only'}]
    if quota_details(store,9,now)['remaining']==0:return [{'status':'odds allowance unavailable; no discovery or odds calls'}]
    provider=provider or OddsAPI(key,store,daily_limit=9,ttl=1800)
    upcoming={}
    for league in LEAGUES:
        try:
            response=provider.events(league)
            from intelligence.providers import LEAGUES as PROVIDER_LEAGUES
            if not isinstance(response['data'],list):raise ValueError('Invalid event list')
            upcoming[league]=sorted([e for e in response['data'] if
                isinstance(e,dict) and e.get('sport_key')==PROVIDER_LEAGUES[league][1] and isinstance(e.get('id'),str) and e['id']
                and all(isinstance(e.get(k),str) and e[k] for k in ('home_team','away_team'))
                and now+timedelta(minutes=15)<parse_time(e['commence_time'])<=now+timedelta(hours=window_hours)],key=lambda e:e['commence_time'])
            store.cache('background-discovery-'+league,response)
            audit.append({'league':league,'status':'provider event discovery','upcoming_events':len(upcoming[league]),
                'received_at':response['received_at'],'window_hours':window_hours})
        except (ProviderError,ValueError,KeyError,TypeError):
            audit.append({'league':league,'status':'event discovery failed; no fixture invented'})
            upcoming[league]=[]
    tasks=[]
    for league in ('Premier League','Ligue 1'):
        if upcoming[league]:tasks.append((league,None,'totals'))
    for league in ('NBA','MLB'):
        if upcoming[league]:tasks.append((league,None,'h2h'))
    # Round robin across supported leagues/games rather than preferring a book.
    for i in range(min(12,max((len(upcoming[l]) for l in ('Premier League','Bundesliga')),default=0))):
        for league in ('Premier League','Bundesliga'):
            if i<len(upcoming[league]):tasks.append((league,upcoming[league][i]['id'],'btts'))
    # Rotate oldest needed scopes so one busy sport cannot monopolize later runs.
    def task_key(task):return 'background-query-'+digest(task)
    tasks.sort(key=lambda t:(store.cached(task_key(t),604800,now) or {}).get('attempted_at',''))
    for league,event,market in tasks:
        if quota_details(store,9)['remaining']<1:
            audit.append({'status':'daily odds cap reached; remaining market tasks skipped'});break
        try:
            store.cache(task_key((league,event,market)),{'attempted_at':now.isoformat()},now)
            response=provider.odds(league,(market,)) if event is None else provider.event_odds(league,event,(market,))
            normalize(response['data'],league,response['received_at'])  # Validate, preserving exact original bytes/timestamps below.
            cache='last-success-'+league+'-'+market if event is None else 'event-snapshot-'+league+'-'+event+'-'+market
            store.cache(cache,response)
            audit.append({'league':league,'market':market,'event_id':event,'status':'observed provider response','received_at':response['received_at']})
        except (ProviderError,ValueError,KeyError,TypeError):
            audit.append({'league':league,'market':market,'status':'provider failure; previous successful observations retained'})
            break  # No repeated chargeable failures or immediate polling.
    return audit


def cycle(store,key='',now=None,provider=None,manual=False):
    """Reusable integration seam. Tests supply fixtures; production uses adapters."""
    from intelligence.current_results import current
    from intelligence.pipeline import run_analysis
    from intelligence.forward_testing import reconcile
    from intelligence.publication_journal import prepare,reconcile as settle,performance
    from intelligence.learning import lock_protocol,update
    now=now or utcnow();lock_protocol(store,now)
    results={}
    for league in MODEL_LEAGUES:
        _,meta=current(store,league)
        results[league]={k:meta.get(k) for k in ('ok','failure_code','checked_at','problem')}
    from intelligence.data_settings import load_settings
    settings=load_settings()
    if settings.errors:raise StateError('Worker data settings invalid; no odds requests authorized')
    if manual and provider is None:
        from intelligence.providers import OddsAPI
        provider=OddsAPI(key,store,daily_limit=9,ttl=60)
    audit=collect_supported(store,key,now,provider,settings.window_hours)
    analysis=run_analysis('',LEAGUES,store=store,cached_only=True,window_hours=settings.window_hours)
    labels=reconcile(store)
    created=prepare(analysis,store)
    settlement=settle(store)
    learning=update(store)
    summary={'mode':'independent pregame research','observed_quotes':len(analysis.quotes),
        'window_hours':settings.window_hours,'sports':['NBA','Soccer','MLB'],
        'sport_limitations':{'NBA':'Observed prices only unless existing sport-specific model gates pass',
            'MLB':'Observed prices only unless existing sport-specific model gates pass'},
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
    return _run(client=client,config=config,now=now,cycle_fn=cycle_fn)


def run_manual(request_id,*,client=None,config=None,now=None,cycle_fn=None):
    """One explicitly authenticated workflow invocation, never a scheduler."""
    import re
    if not isinstance(request_id,str) or not re.fullmatch('[a-f0-9]{32}',request_id):raise StateError('Invalid manual request identity')
    if os.getenv('RESEARCH_MANUAL_ENABLED','0')!='1':raise StateError('Manual research is disabled pending owner review')
    if os.getenv('RESEARCH_SCHEDULE_ENABLED','0')!='0' or os.getenv('RESEARCH_WORKER_ENABLED','0')!='0':
        raise StateError('Manual mode requires automatic worker and schedule flags to remain disabled')
    if not os.getenv('ODDS_API_KEY'):raise StateError('Configure the permitted odds credential only in private worker Secrets')
    from intelligence.hosted_checks import expected_store
    expected_store()  # Required in manual mode, before any remote operation.
    return _run(client=client,config=config,now=now,cycle_fn=cycle_fn,manual_request_id=request_id)


def _run(*,client=None,config=None,now=None,cycle_fn=None,manual_request_id=None):
    if os.getenv('PAID_ANALYST_APPROVED','0')!='0':raise StateError('Background worker requires paid AI disabled')
    if os.getenv('RESEARCH_DATA_RIGHTS_VERIFIED','0')!='1':raise StateError('Review permitted provider research use before worker activation')
    if os.getenv('RESEARCH_BUDGET_SCOPE_REVIEWED','0')!='1':raise StateError('Review other users of the same provider credentials; production is outside this development ledger')
    client=client or Client(config or configuration(),writer=True);now=now or utcnow()
    identifier=digest(('manual-pregame-1',manual_request_id)) if manual_request_id else run_id(now)
    envelope=client.acquire(identifier)
    try:
        if manual_request_id and envelope.get('held') is not False:
            raise StateError('Manual research blocked by remote provider hold; no provider request authorized')
        if os.getenv('RESEARCH_EXPECTED_STORE_INSTANCE'):
            from intelligence.hosted_checks import expected_store
            if (envelope.get('snapshot') or {}).get('manifest',{}).get('store_instance')!=expected_store():
                raise StateError('Research worker is connected to an unexpected store; no provider request authorized')
        with tempfile.TemporaryDirectory(prefix='research-writer-') as folder:
            path=materialize(envelope,Path(folder)/'working.sqlite3')
            from intelligence.shared_state import MAX_RAW
            if path.stat().st_size>MAX_RAW-16*1024*1024 or len(envelope['snapshot']['compressed'])>4800000:
                raise StateError('Shared state is approaching its bounded capacity; reviewed storage migration required before new provider requests')
            store=Store(path,request_authority=client);store.commit_generation=client.generation+1
            hydrate_budgets(store,envelope);verify_assets(store)
            if manual_request_id:
                from intelligence.quota import quota_details
                if quota_details(store,9,now)['remaining']<1:raise StateError('Manual research allowance unavailable; no provider requests authorized')
            from intelligence.forward_testing import records
            old_ids={r['id'] for r in records(store)}
            if manual_request_id and cycle_fn is None:
                summary,created=cycle(store,os.getenv('ODDS_API_KEY',''),now,manual=True)
            else:summary,created=(cycle_fn or cycle)(store,os.getenv('ODDS_API_KEY',''),now)
            new=[r for r in records(store) if r['id'] not in old_ids]
            starts=[r['payload']['quote']['commence_time'] for r in new]+[r['kickoff'] for r in created]
            body=snapshot(store)
            receipt=client.control('checkpoint',body|{'expected_generation':client.generation,'run_id':identifier,
                'prospective_deadline':min(starts,key=parse_time) if starts else None,'publications':created,
                'summary':{'new_publications':len(created),'new_forward_forecasts':len(new),
                    'new_labels':summary.get('new_forward_labels',0),'paid_ai_requests':0,
                    'coverage_status':summary.get('coverage_status','integration replay'),
                    **({'manual_request_id':manual_request_id,'mode':'owner-requested research'} if manual_request_id else {})}})
            observed=client.read()
            verified=observed.get('generation')==receipt['generation'] and observed.get('snapshot',{}).get('manifest')==body['manifest']
            if not verified:raise StateError('Committed research readback was not verified; do not claim new research is visible')
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
    p.add_argument('--manual',metavar='REQUEST_ID',help='One owner-requested private workflow cycle; automatic flags must remain zero')
    p.add_argument('--bootstrap',type=Path,help='Explicit existing-store first upload; never enables provider calls')
    p.add_argument('--pull',type=Path,help='Explicit read-only committed-state sync directory')
    p.add_argument('--verify-shared',action='store_true',help='Two independent state-only reads/restores; no provider requests or writes')
    p.add_argument('--storage-check',action='store_true',help='Fenced preservation checkpoint and fresh readback; no research/provider requests')
    p.add_argument('--review-hold',action='store_true',help='Read-only hold, ledger and configuration review; never release or collect data')
    args=p.parse_args()
    if sum(bool(v) for v in (args.run,args.manual,args.bootstrap,args.pull,args.verify_shared,args.storage_check,args.review_hold))>1:p.error('Choose one explicit operation')
    try:
        if args.review_hold:
            from intelligence.provider_hold import review
            result=review()
        elif args.verify_shared or args.storage_check:
            from intelligence.hosted_checks import verify_shared,storage_check,expected_store
            expected=expected_store()
            result=storage_check(expected_instance=expected) if args.storage_check else verify_shared(expected_instance=expected)
        elif args.bootstrap:result=bootstrap(args.bootstrap)
        elif args.pull:
            from intelligence.shared_state import pull_replica
            r=pull_replica(args.pull);result={'status':'replica saved','generation':r['envelope']['generation'],'sports_requests':0}
        elif args.manual:result=run_manual(args.manual)
        elif args.run:result=run_background()
        else:result={'status':'disabled dry status; no network requests','activation_required':True}
        print(json.dumps(result,allow_nan=False,default=str))
    except Exception as error:
        # CLI jobs must fail visibly without emitting an unknown exception's
        # text/traceback (which can contain credentials from a transport).
        # The integration seam still raises normally for deterministic tests.
        from intelligence.shared_state import public_failure
        print(json.dumps({'status':'blocked or failed',**public_failure(error)}));raise SystemExit(1) from None


if __name__=='__main__':main()
