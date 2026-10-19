"""Single-writer, key-free OpenLigaDB refresh, independent of held providers.

The existing global hold, held-provider budgets and automatic live-odds flags
remain unchanged. Only the fixed, reviewed public Bundesliga season endpoint is
reachable by this collector; no generic URL, sports key, retry or redirect path.
The private job has the existing writer credentials; Streamlit stays read-only.
"""
from datetime import timedelta
from pathlib import Path
from uuid import uuid4
import argparse,json,os,tempfile
import requests
from intelligence.domain import utcnow,parse_time,digest
from intelligence.storage import Store
from intelligence.shared_state import Client,StateError,configuration,materialize,snapshot
from intelligence.hosted_checks import expected_store
from intelligence.statistics_import import protected_counts

URL='https://api.openligadb.de/getmatchdata/bl1/2026'
MAX_BYTES=2_000_000
MIN_INTERVAL=3*3600


def download(session=None):
    own=session is None;session=session or requests.Session()
    try:
        # One attempt per fenced update. No credential is read or sent.
        response=session.get(URL,timeout=(5,25),allow_redirects=False,stream=True,
            headers={'Accept':'application/json','User-Agent':'SportsResearch-OpenLigaDB-ODbL/1.0'})
        try:
            if response.status_code!=200:raise ValueError('Public results request unavailable')
            chunks=[];size=0
            for chunk in response.iter_content(65536):
                size+=len(chunk)
                if size>MAX_BYTES:raise ValueError('Public results exceed reviewed size')
                chunks.append(chunk)
            return b''.join(chunks),utcnow().isoformat()
        finally:response.close()
    except requests.RequestException:raise ValueError('Public results connection failed') from None
    finally:
        if own:session.close()


def update(store,now=None,fetch=download,extra_fetch=None):
    from intelligence.openliga import save
    from intelligence.fixture_research import collect
    from intelligence.current_score_research import candidates
    from intelligence.statistics_forward import record,reconcile,monitoring
    fixed_now=now;now=now or utcnow()
    cached=store.cached('free-statistics-last-success',MIN_INTERVAL,now)
    cached=bool(cached and parse_time(cached['source_observed_at']).date()==now.date())
    extra_due=extra_fetch is not None and not store.cached('public-results-last-attempt',MIN_INTERVAL,now)
    # Re-evaluate and record newly supported research from verified cached
    # inputs even inside the network cooldown. This never refreshes receipts
    # or reserves provider credits; browsing remains read-only.
    before=protected_counts(store);base_requests=0
    if cached:
        from intelligence.openliga import current
        _,meta=current(store,'Bundesliga',now)
        if not meta['ok']:raise ValueError('Cached Bundesliga verification unavailable')
        at=meta['checked_at']
    else:
        raw,at=fetch();base_requests=1;now=utcnow() if fixed_now is None else fixed_now
        if not 0<=(now-parse_time(at)).total_seconds()<60:raise ValueError('Public source receipt must be current')
        meta=save(store,raw,'Bundesliga',at,now)
    from intelligence.statistics_learning import lock,update as update_learning
    lock(store,now)
    extra={}
    if extra_due:
        from intelligence.free_results import refresh
        extra=refresh(store,None if fixed_now is None else now,extra_fetch)
        if fixed_now is None:now=utcnow()
    result=collect(store,now,168,None if extra_fetch is not None else ['Bundesliga'])
    singles=result['forecasts'];sides={r['fixture_id']:(r['home'],r['away']) for r in singles}
    sgps=candidates(store,now)
    for r in sgps:
        if r['fixture_id'] in sides:r['home'],r['away']=sides[r['fixture_id']]
    rows=singles+sgps
    rows=[r for r in rows if r['research_eligible'] and now+timedelta(minutes=15)<parse_time(r['kickoff'])]
    rows=rows[:94]
    from intelligence.fixture_research import forward_combinations
    cross_game=forward_combinations([r for r in rows if not r.get('legs')],now)
    rows+=cross_game
    created=record(store,rows,now);settled=reconcile(store,now)
    monitor=monitoring(store)
    learning=update_learning(store,now)
    if before!=protected_counts(store):raise StateError('A protected ledger or provider budget changed')
    from intelligence.cross_game_study import summary as cross_game_summary
    from intelligence.dependence_study import load_report as dependence_report
    dependence=dependence_report()
    summary={'state':'Key-free statistics refreshed' if base_requests+extra.get('public_results_requests',0) else 'Verified cached statistics re-evaluated','source':'OpenLigaDB, ODbL 1.0','source_observed_at':at,
        'source_sha256':meta['sha256'],'coverage':meta['coverage'],'public_results_requests':base_requests+extra.get('public_results_requests',0),
        'additional_public_sources':extra.get('sources',{}),
        'prepared_receipts_reused':extra.get('prepared_receipts_reused',0),
        'odds_api_requests':0,'odds_api_credits':0,'paid_ai_requests':0,
        'upcoming_singles':sum(not r.get('legs') for r in rows),
        'experimental_2_leg_sgp':sum(len(r.get('legs',[]))==2 and r.get('kind')!='bounded_cross_game' for r in rows),
        'experimental_3_leg_sgp':sum(len(r.get('legs',[]))==3 and r.get('kind')!='bounded_cross_game' for r in rows),
        'experimental_cross_game_bounds':{str(n):sum(len(r['legs'])==n for r in cross_game) for n in (2,3)},
        'new_pregame_records':len(created),'new_verified_outcomes':settled,
        'unique_pregame_decisions':monitor['unique_pregame_decisions'],
        'challenger_learning':learning,'cross_game_diagnostics':cross_game_summary(),
        'dependence_diagnostics':{'report_verified':dependence is not None,'report_sha256':dependence['sha256'] if dependence else None,'approved_joint_models':0},
        'approved_models':0,'approved_joint_models':0,'automatic_model_promotion':False,
        'forecasts_by_league':{league:sum(r['league']==league and r.get('kind')!='bounded_cross_game' for r in rows) for league in ('Bundesliga','Premier League','Ligue 1','NBA','MLB')},
        'remaining_blockers':result.get('blockers',{})}
    store.cache('free-statistics-last-success',summary,parse_time(at))
    store.cache('statistics-forward-monitoring',monitor,now)
    return summary,rows


def publish(client=None,fetch=download,readback_output=None,extra_fetch=None):
    from intelligence.background import verify_assets
    from intelligence.persistence import backup_store
    if (os.getenv('PAID_ANALYST_APPROVED','0')!='0' or os.getenv('RESEARCH_WORKER_ENABLED','0')!='0'
        or os.getenv('RESEARCH_SCHEDULE_ENABLED','0')!='0'):
        raise StateError('Paid AI and live-provider automatic workers must stay disabled')
    identity=expected_store();client=client or Client(configuration(),writer=True)
    run_id=digest(('key-free-statistics-1',uuid4().hex));envelope=client.acquire(run_id)
    try:
        if (envelope.get('held') is not True or not envelope.get('snapshot')
            or envelope['snapshot']['manifest']['store_instance']!=identity):
            raise StateError('Expected recovered store with an active provider hold is required')
        with tempfile.TemporaryDirectory(prefix='key-free-statistics-') as folder:
            store=Store(materialize(envelope,Path(folder)/'writer.sqlite3'))
            verify_assets(store);before=protected_counts(store)
            from intelligence.free_results import download as public_download
            summary,rows=update(store,fetch=fetch,extra_fetch=extra_fetch or public_download)
            if protected_counts(store)!=before:raise StateError('Protected history or budgets changed')
            body=snapshot(store)
            receipt=client.control('checkpoint',body|{'run_id':run_id,'expected_generation':envelope['generation'],
                'publications':[],'prospective_deadline':min((r['kickoff'] for r in rows),default=None),'summary':summary})
            after=client.read()
            if (after.get('held') is not True or after['generation']!=receipt['generation']
                or after['snapshot']['manifest']!=body['manifest'] or after.get('budgets')!=envelope.get('budgets')):
                raise StateError('Hosted state, hold or budget readback mismatch')
            restored=Store(materialize(after,Path(folder)/'readback.sqlite3'))
            if protected_counts(restored)!=before:raise StateError('Restored protected history mismatch')
            if readback_output:backup_store(restored,readback_output)
            return summary|{'generation':receipt['generation'],'store_instance':identity,'shared_readback_verified':True,
                'provider_hold_preserved':True,'provider_budgets_preserved':True}
    except Exception:
        try:client.control('fail')
        except StateError:pass
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--private-readback-output',type=Path)
    p.add_argument('--prepared-public-data',type=Path);a=p.parse_args()
    try:
        from intelligence.free_results import prepared_fetch
        print(json.dumps(publish(readback_output=a.private_readback_output,
            extra_fetch=prepared_fetch(a.prepared_public_data) if a.prepared_public_data else None),allow_nan=False))
    except Exception:
        print(json.dumps({'status':'failed','error_code':'key_free_statistics_validation_or_storage',
            'provider_hold_released':False,'odds_api_requests':0}));raise SystemExit(1) from None


if __name__=='__main__':main()
