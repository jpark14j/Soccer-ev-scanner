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


def update(store,now=None,fetch=download):
    from intelligence.openliga import save
    from intelligence.fixture_research import collect
    from intelligence.current_score_research import candidates
    from intelligence.statistics_forward import record,reconcile,monitoring
    fixed_now=now;now=now or utcnow()
    cached=store.cached('free-statistics-last-success',MIN_INTERVAL,now)
    if cached and parse_time(cached['source_observed_at']).date()==now.date():
        return {'state':'Cached public update retained; refresh interval not reached','public_results_requests':0},[]
    before=protected_counts(store);raw,at=fetch();now=utcnow() if fixed_now is None else fixed_now
    if not 0<=(now-parse_time(at)).total_seconds()<60:raise ValueError('Public source receipt must be current')
    from intelligence.statistics_learning import lock,update as update_learning
    lock(store,now)
    meta=save(store,raw,'Bundesliga',at,now)
    singles=collect(store,now,168,['Bundesliga'])['forecasts'];sides={r['fixture_id']:(r['home'],r['away']) for r in singles}
    sgps=candidates(store,now)
    for r in sgps:
        if r['fixture_id'] in sides:r['home'],r['away']=sides[r['fixture_id']]
    rows=singles+sgps
    rows=[r for r in rows if r['research_eligible'] and now+timedelta(minutes=15)<parse_time(r['kickoff'])]
    created=record(store,rows,now);settled=reconcile(store,now)
    monitor=monitoring(store)
    learning=update_learning(store,now)
    if before!=protected_counts(store):raise StateError('A protected ledger or provider budget changed')
    summary={'state':'Key-free statistics refreshed','source':'OpenLigaDB, ODbL 1.0','source_observed_at':at,
        'source_sha256':meta['sha256'],'coverage':meta['coverage'],'public_results_requests':1,
        'odds_api_requests':0,'odds_api_credits':0,'paid_ai_requests':0,
        'upcoming_singles':sum(not r.get('legs') for r in rows),
        'experimental_2_leg_sgp':sum(len(r.get('legs',[]))==2 for r in rows),
        'experimental_3_leg_sgp':sum(len(r.get('legs',[]))==3 for r in rows),
        'new_pregame_records':len(created),'new_verified_outcomes':settled,
        'unique_pregame_decisions':monitor['unique_pregame_decisions'],
        'challenger_learning':learning,
        'approved_models':0,'approved_joint_models':0,'automatic_model_promotion':False,
        'remaining_blockers':{'NBA':'No reviewed key-free current fixture source or offseason readiness',
            'MLB':'No permitted key-free 2026 final results/fixture source',
            'other_soccer':'Incomplete current/previous-season reconciliation; unchanged model gates'}}
    store.cache('free-statistics-last-success',summary,now)
    store.cache('statistics-forward-monitoring',monitor,now)
    return summary,rows


def publish(client=None,fetch=download,readback_output=None):
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
            summary,rows=update(store,fetch=fetch)
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
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--private-readback-output',type=Path);a=p.parse_args()
    try:print(json.dumps(publish(readback_output=a.private_readback_output),allow_nan=False))
    except Exception:
        print(json.dumps({'status':'failed','error_code':'key_free_statistics_validation_or_storage',
            'provider_hold_released':False,'odds_api_requests':0}));raise SystemExit(1) from None


if __name__=='__main__':main()
