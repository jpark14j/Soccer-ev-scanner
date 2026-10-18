"""Explicit local-file-only statistics import and fenced preservation checkpoint.

No downloader, sports credential, provider reservation or hold-release operation
exists in this entry point. Source files must be prepared by a reviewed bounded
public-data collection job. Supabase I/O is the only network capability used.
"""
from pathlib import Path
from uuid import uuid4
import argparse,json,os,tempfile
from hashlib import sha256
from intelligence.domain import utcnow,digest,parse_time
from intelligence.storage import Store
from intelligence.shared_state import Client,configuration,StateError,materialize,snapshot
from intelligence.hosted_checks import expected_store


def file_from(root,manifest,name,url):
    entries=[r for r in manifest if r['file']==name]
    if len(entries)!=1:raise ValueError('Source provenance missing')
    m=entries[0];raw=(root/name).read_bytes()
    if m.get('http')!=200 or m.get('url')!=url or sha256(raw).hexdigest()!=m.get('sha256'):
        raise ValueError('Source provenance/hash mismatch')
    return raw,m['observed_at']


def import_files(store,directory,now=None):
    from intelligence.openliga import save,complete_history
    from intelligence.recent_nba import load_bundle,load_report
    from intelligence.data_adapters import team_identity
    from intelligence.competitions import COMPETITIONS
    from intelligence.event_data import EventObservation,ingest
    from intelligence.fixture_research import collect
    from intelligence.current_score_research import candidates
    from intelligence.statistics_forward import record,reconcile
    now=now or utcnow();root=Path(directory);manifest=json.loads((root/'manifest.json').read_text())
    raw,at=file_from(root,manifest,'openliga-bundesliga-2025.json','https://api.openligadb.de/getmatchdata/bl1/2025')
    completion=complete_history(store,raw,(root/'pinned-2025-26-de.1.json').read_bytes(),at,now)
    raw,at=file_from(root,manifest,'openliga-bundesliga.json','https://api.openligadb.de/getmatchdata/bl1/2026')
    coverage=save(store,raw,'Bundesliga',at,now)['coverage']
    history,sources=load_bundle(root,now);report=load_report()
    if not report or report['data_sha256']!=digest(history.to_json(orient='records',date_format='iso')):
        raise ValueError('Imported NBA games differ from tested model data')
    nba=[]
    for r in history.itertuples():
        h,hn=team_identity(COMPETITIONS['NBA'],r.HomeTeam);a,an=team_identity(COMPETITIONS['NBA'],r.AwayTeam)
        nba.append(EventObservation('basketball:nba',r.season,'boxscorelab',r.game_id,h,a,hn,an,
            r.date.date().isoformat(),'completed',int(r.FTHG),int(r.FTAG),now.isoformat(),None,
            report['license_reference'],'archive_full_final'))
    nba_status=ingest(store,nba,{'sha256':report['data_sha256'],'license_reference':report['license_reference'],
        'source':sources,'attribution':report['attribution']},now)
    singles=collect(store,now,168,['Bundesliga'])['forecasts'];sgps=candidates(store,now)
    rows=[r for r in singles+sgps if r['research_eligible']]
    ids=record(store,rows,now);labels=reconcile(store,now)
    summary={'mode':'Explicit prepared statistics import; no sports-provider HTTP',
        'soccer_historical_gaps_recovered':completion['added'],'previous_scores_reconciled':completion['matched'],
        'Bundesliga':coverage,'NBA':{'historical_games_imported':len(nba),'through':report['data_end'],**nba_status},
        'upcoming_single_forecasts':len(singles),'experimental_sgp_2_leg':sum(len(r['legs'])==2 for r in sgps if r['research_eligible']),
        'experimental_sgp_3_leg':sum(len(r['legs'])==3 for r in sgps if r['research_eligible']),
        'new_actual_pregame_records':len(ids),'new_outcome_labels':labels,
        'sports_provider_requests':0,'odds_api_credits':0,'paid_ai_requests':0,
        'approved_models':0,'validated_joint_models':0,'source_expires_after_hours':6,
        'remaining_blockers':{'EPL':'Current source has missing/overdue results and no complete prior season',
            'Ligue 1':'Current permitted full-season results missing',
            'NBA':'Verified near-term fixtures and offseason roster readiness missing',
            'MLB':'Permitted 2026 results require a free authenticated current-results provider'}}
    store.cache('statistics-import-summary',summary,now)
    return summary,rows


def protected_counts(store):
    """Existing ledgers and local budgets must remain byte-for-byte unchanged."""
    tables=('publications','settlements','shadow_forecasts','shadow_outcomes','forward_forecasts','forward_labels','budget','football_data_requests','recovery_guard_events','backup_model_assets')
    with store.connect() as db:
        existing={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return {t:digest(sorted([tuple(row) for row in db.execute('SELECT * FROM '+t)],key=str)) for t in tables if t in existing}


def publish(directory,client=None,readback_output=None):
    if os.getenv('PAID_ANALYST_APPROVED','0')!='0':raise StateError('Paid AI must remain disabled')
    client=client or Client(configuration(),writer=True);identity=expected_store()
    identifier=digest(('prepared-statistics-import-1',uuid4().hex));envelope=client.acquire(identifier)
    try:
        if envelope.get('held') is not True:raise StateError('This import requires the existing provider hold to stay active')
        if not envelope.get('snapshot'):raise StateError('An already bootstrapped recovered store is required')
        if envelope['snapshot']['manifest']['store_instance']!=identity:raise StateError('Unexpected recovered store identity')
        with tempfile.TemporaryDirectory(prefix='statistics-writer-') as folder:
            path=materialize(envelope,Path(folder)/'working.sqlite3');store=Store(path)
            from intelligence.background import verify_assets
            verify_assets(store);before=protected_counts(store)
            summary,rows=import_files(store,directory)
            if before!=protected_counts(store):raise StateError('Statistics import changed a protected ledger or budget')
            body=snapshot(store)
            # The remote server checks the deadline before committing the head.
            deadline=min((r['kickoff'] for r in rows),default=None)
            receipt=client.control('checkpoint',body|{'expected_generation':envelope['generation'],'run_id':identifier,
                'publications':[],'prospective_deadline':deadline,'summary':summary})
            after=client.read()
            if (after.get('held') is not True or after['generation']!=receipt['generation']
                or after['snapshot']['manifest']!=body['manifest'] or after.get('budgets')!=envelope.get('budgets')):
                raise StateError('Shared readback, hold or provider budget differs')
            restored=materialize(after,Path(folder)/'readback.sqlite3')
            if protected_counts(Store(restored))!=before:raise StateError('Protected records differ after fresh hosted readback')
            if readback_output:
                from intelligence.persistence import backup_store
                backup_store(Store(restored),readback_output)
            return summary|{'generation':receipt['generation'],'store_instance':identity,'shared_readback_verified':True,
                'provider_hold_preserved':True,'provider_budgets_preserved':True}
    except Exception:
        try:client.control('fail')
        except StateError:pass
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',required=True,type=Path)
    p.add_argument('--store',type=Path);p.add_argument('--publish-prepared',action='store_true')
    p.add_argument('--private-readback-output',type=Path);a=p.parse_args()
    try:
        if a.publish_prepared:
            if a.store:p.error('Remote import uses the verified committed store')
            result=publish(a.bundle,readback_output=a.private_readback_output)
        elif a.store:result,_=import_files(Store(a.store),a.bundle)
        else:p.error('Choose an inspected local store or explicit protected publication')
        print(json.dumps(result,allow_nan=False))
    except Exception:
        # No arbitrary exceptions, remote bodies, paths or credentials in logs.
        print(json.dumps({'status':'failed','error_code':'statistics_import_validation_or_storage_failure',
            'provider_hold_released':False,'sports_provider_requests':0}))
        raise SystemExit(1) from None


if __name__=='__main__':main()
