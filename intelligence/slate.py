"""Automatic slate discovery and fair, bounded research within the existing cap.

All configured events are discovered/considered. Market retrieval is partial when
quota is insufficient. Queue age rotates scarce credits instead of favoring a book.
No background thread, paid AI, price substitution or budget reset is involved.
"""
from collections import Counter
from datetime import timedelta
from itertools import zip_longest
import logging
from intelligence.domain import digest,parse_time,utcnow
from intelligence.providers import LEAGUES,ProviderError,normalize
from intelligence.markets import CATALOG,FEATURED
from intelligence.quota import quota_details

LOG=logging.getLogger(__name__)


def in_window(q,start,end):
    return start<parse_time(q.commence_time)<=end


def run_slate(key,leagues,store,provider,*,window_hours=48,collect_results=False):
    from intelligence.pipeline import Analysis,restore_market_snapshots,evaluate_quotes
    from intelligence.processing import process_cycle
    if not 1<=window_hours<=168 or any(l not in LEAGUES for l in leagues):
        raise ValueError('Invalid slate window or competition')
    now=utcnow(); end=now+timedelta(hours=window_hours)
    cap=provider.daily_limit
    result=restore_market_snapshots(Analysis(checked_at=now.isoformat()),store,leagues)
    discovered={}; discovery=[]; queries=[]; tasks=[]; cached_rows={}
    failure_key='auto-provider-backoff-'+digest(key)
    # Completed pending predictions get first claim on the SAME capped database.
    result.processing=process_cycle(store,provider,leagues,cap,collect_results=collect_results,now=now)
    for league in leagues:
        scope='auto-events-'+digest((digest(key),league))
        verified=True
        try:
            response=provider.events(league)
            if not isinstance(response['data'],list):
                raise ValueError()
            store.cache(scope,response)
        except Exception:
            response=store.cached(scope,604800)
            verified=False
            result.warnings.append(league+': event discovery unavailable; saved events are incomplete fallback, not a live slate')
        rows=[]
        for event in (response or {}).get('data',[]):
            try:
                if event['sport_key']!=LEAGUES[league][1] or not isinstance(event['id'],str) or not event['id'] or not all(isinstance(event[k],str) and event[k] for k in ('home_team','away_team')):
                    continue
                if now<parse_time(event['commence_time'])<=end:
                    row={'league':league,'sport':LEAGUES[league][0],'event_id':event['id'],
                        'home':event['home_team'],'away':event['away_team'],
                        'event':event['home_team']+' vs '+event['away_team'],'start':event['commence_time'],
                        'discovered_at':response['received_at'],'live_discovery':verified}
                    discovered[(league,event['id'])]=row;rows.append(row)
            except (ValueError,TypeError,KeyError):
                continue
        discovery.append({'league':league,'events':len(rows),'status':'provider event list' if verified else 'unverified saved fallback',
            'received_at':(response or {}).get('received_at')})
        # Three featured tasks cover every returned event for their competition.
        has_saved_games=any(q.league==league and in_window(q,now,end) for q in result.quotes)
        for market in FEATURED:
            if rows or has_saved_games or not verified:
                tasks.append((league,None,market))
            else:
                queries.append({'league':league,'event_id':None,'market':market,
                    'status':'not requested: no games discovered in the scan window','received_at':None})
        for row in sorted(rows,key=lambda r:(r['start'],r['event_id'])):
            for market in CATALOG.values():
                if market.key not in FEATURED and market.documented and row['sport'] in market.sports:
                    tasks.append((league,row['event_id'],market.key))
    # Saved prices still explain which games were observed if listing is unavailable.
    for q in result.quotes:
        if q.league in leagues and in_window(q,now,end):
            discovered.setdefault((q.league,q.event_id),{'league':q.league,'sport':q.sport,'event_id':q.event_id,
                'home':q.home,'away':q.away,'event':q.event,'start':q.commence_time,
                'discovered_at':q.received_at,'live_discovery':False})
    def task_key(task):
        return 'auto-query-'+digest((digest(key),task))
    for task in tasks:
        cached_rows[task]=store.cached(task_key(task),604800)
    # Never-scanned tasks first, then oldest; featured tasks interleave competitions.
    task_order={task:i for i,task in enumerate((l,None,m) for m in FEATURED for l in leagues)}
    market_order={m:i for i,m in enumerate(CATALOG)}
    event_queues=[sorted([t for t in tasks if t[0]==league and t[1] is not None],
        key=lambda t:(market_order[t[2]],discovered[(league,t[1])]['start'],t[1])) for league in leagues]
    interleaved=[t for group in zip_longest(*event_queues) for t in group if t is not None]
    task_order.update({task:len(task_order)+i for i,task in enumerate(interleaved)})
    initial_order={task:i for i,task in enumerate(tasks)}
    def age_order(task):
        return ((cached_rows[task] or {}).get('attempted_at',''),task_order.get(task,len(task_order)),initial_order[task])
    featured=sorted([t for t in tasks if t[1] is None],key=age_order)
    event_tasks=sorted([t for t in tasks if t[1] is not None],key=age_order)
    # One oldest-needed featured task per competition preserves breadth. Then
    # alternate event/featured work so player markets cannot starve team markets.
    head=[];represented=set()
    for task in featured:
        if task[0] not in represented:
            head.append(task);represented.add(task[0])
    tail=[t for t in featured if t not in head]
    tasks=head+[t for pair in zip_longest(event_tasks,tail) for t in pair if t is not None]
    transport_failed=store.cached(failure_key,300,now) is not None
    for league,event,market in tasks:
        task=(league,event,market); prior=cached_rows[task]
        age=(now-parse_time(prior['attempted_at'])).total_seconds() if prior else None
        current=[q for q in result.quotes if q.league==league and q.market==market and
            (event is None or q.event_id==event) and q.status(now)=='current' and q.jurisdiction=='CA-ON']
        status=''; received=None
        if prior and age is not None and 0<=age<max(60,provider.ttl):
            status='cached query: '+prior['status'];received=prior.get('received_at')
        elif current:
            status='current observations reused; full task coverage not established'
        elif transport_failed:
            status='not requested: earlier provider failure'
        elif quota_details(store,cap,now)['remaining']<1:
            status='not requested: local credit cap'
        else:
            try:
                response=provider.odds(league,(market,)) if event is None else provider.event_odds(league,event,(market,))
                quotes,rejected=normalize(response['data'],league,response['received_at'],utcnow())
                received=response['received_at']
                status='returned Ontario observations' if any(q.jurisdiction=='CA-ON' for q in quotes) else 'queried; no Ontario observations returned'
                by_id={q.id:q for q in result.quotes}
                by_id.update({q.id:q for q in quotes}); result.quotes=list(by_id.values())
                result.quote_origins.update({q.id:{'origin':'provider snapshot','received_at':q.received_at} for q in quotes})
                cache=('last-success-'+league+'-'+market if event is None else 'event-snapshot-'+league+'-'+event+'-'+market)
                store.cache(cache,response)
                if rejected:
                    result.warnings.append(f'{league}: malformed market records were excluded')
            except Exception:
                status='query failed; no substitute data'; transport_failed=True
                result.errors.append(league+': automatic market retrieval unavailable; later chargeable tasks skipped')
                store.cache(failure_key,{'failed_at':now.isoformat()},now)
            store.cache(task_key(task),{'attempted_at':now.isoformat(),'received_at':received,'status':status})
        queries.append({'league':league,'event_id':event,'market':market,'status':status,'received_at':received})
    outside=[q for q in result.quotes if not in_window(q,now,end)]
    result.quotes=[q for q in result.quotes if in_window(q,now,end)]
    result=evaluate_quotes(result,store)
    result.quotes.extend(outside)  # Inspection only; selectors apply the window.
    result.slate={'window_start':now.isoformat(),'window_end':end.isoformat(),'window_hours':window_hours,
        'events':list(discovered.values()),'discovery':discovery,'queries':queries,
        'last_successful_update':max((q.received_at for q in result.quotes),default=None),
        'coverage':'partial: per-event availability, quota, freshness and unvalidated models limit coverage',
        'gaps':['Player logs, injuries and confirmed lineups are not connected',
                'Corners and operator settlement rules are not verified',
                'No validated joint model or actual combined parlay-price feed',
                'Configured competitions and time window are not the entire sports calendar']}
    # Shadow forecasts are private diagnostics, separate from published bets/ROI.
    from intelligence.processing import record_shadow_forecasts
    recorded_at=utcnow()  # Responses arrived after scan start; never backdate receipt/publication checks.
    result.processing['shadow_forecasts_recorded']=record_shadow_forecasts(result,store,recorded_at)
    from intelligence.processing import label_public_epl
    if not result.focused_model and result.processing.get('pending_public_epl_forecasts'):
        from intelligence.current_soccer import prepare_epl as prepare
        result.focused_model=prepare(store,recorded_at)
    result.processing['public_epl_target_labels']=label_public_epl(store,result.focused_model,recorded_at)
    from intelligence.multi_readiness import process_expanded_paper
    result.processing['expanded_paper_labels']=process_expanded_paper(store,result,recorded_at)
    from intelligence.data_adapters import provider_results
    result.processing['normalized_existing_results']=provider_results(store,recorded_at)
    result.processing['published_predictions']=len(__import__('intelligence.pipeline',fromlist=['publish_current']).publish_current(result,store,recorded_at))
    LOG.info('slate_scan_complete',extra={'discovered_events':len(discovered),'query_statuses':dict(Counter(q['status'] for q in queries))})
    return result
