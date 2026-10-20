"""Explicit state-only verification. No sports, AI, training or budget release."""
from contextlib import closing
from pathlib import Path
from uuid import uuid4
import os,re,sqlite3,tempfile
from intelligence.domain import digest
from intelligence.shared_state import Client,StateError,configuration,materialize,snapshot


class SavedFile:
    """Backup protocol without Store initialization or local schema mutations."""
    def __init__(self,path):self.path=str(path)
    def connect(self):
        db=sqlite3.connect(Path(self.path).resolve().as_uri()+'?mode=ro',uri=True)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        return db


def inspect(envelope,directory,expected_instance=''):
    path=materialize(envelope,Path(directory)/'verified.sqlite3')
    identity=envelope['snapshot']['manifest']['store_instance']
    if expected_instance and identity!=expected_instance:
        raise StateError('Committed store identity differs from the expected recovery store')
    with closing(SavedFile(path).connect()) as db:
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        counts={t:db.execute('SELECT count(*) FROM '+t).fetchone()[0] if t in tables else 0
            for t in ('publications','settlements','shadow_forecasts','shadow_outcomes',
                'forward_forecasts','forward_labels','research_publications','event_observations')}
    return path,{'generation':envelope['generation'],'store_instance':identity,
        'snapshot_sha256':envelope['snapshot']['manifest']['sha256'],
        'provider_budget_hold':envelope.get('held'),'record_counts':counts}


def expected_store():
    value=os.getenv('RESEARCH_EXPECTED_STORE_INSTANCE','')
    if not re.fullmatch('[a-f0-9]{32}',value):
        raise StateError('Configure the expected recovered store identity before hosted worker verification')
    return value


def verify_shared(*,client=None,expected_instance=''):
    """Two fresh state reads/restores; no local saved replica is used as proof."""
    client=client or Client(configuration(),writer=True)
    with tempfile.TemporaryDirectory(prefix='research-read-check-') as folder:
        _,first=inspect(client.read(),Path(folder)/'first',expected_instance)
        _,second=inspect(client.read(),Path(folder)/'second',first['store_instance'])
    if second['generation']<first['generation']:
        raise StateError('Shared generation regressed during verification')
    if second['generation']==first['generation'] and second['snapshot_sha256']!=first['snapshot_sha256']:
        raise StateError('Committed generation changed its checksum')
    return {'status':'fresh shared-state reads verified',**second,'independent_restores':2,
        'head_changed_during_check':second['generation']!=first['generation'],
        'sports_provider_requests':0,'paid_ai_requests':0,'remote_writes':0,
        'preview_restart_verified':False,'recurring_operation_verified':False}


def storage_check(*,client=None,expected_instance=''):
    """Fenced preservation/readback check; works while the remote hold stays on.

    Publishes an operational checkpoint only. It never invokes the research cycle,
    creates forecasts, hydrates local ledgers, enables providers or releases holds.
    """
    if not expected_instance:expected_instance=expected_store()
    if os.getenv('PAID_ANALYST_APPROVED','0')!='0':
        raise StateError('Storage checks require paid AI disabled')
    client=client or Client(configuration(),writer=True)
    identifier=digest(('explicit-storage-check-1',uuid4().hex))
    envelope=client.acquire(identifier)
    try:
        with tempfile.TemporaryDirectory(prefix='research-storage-check-') as folder:
            path,before=inspect(envelope,Path(folder)/'original',expected_instance)
            from intelligence.background import verify_assets
            verify_assets(SavedFile(path))
            body=snapshot(SavedFile(path))
            # Confirm the prepared checkpoint contains the same genuine records.
            prepared={'generation':envelope['generation']+1,'snapshot':body|{'generation':envelope['generation']+1}}
            _,after=inspect(prepared,Path(folder)/'prepared',expected_instance)
            if before['record_counts']!=after['record_counts']:
                raise StateError('Storage check changed recorded research')
            receipt=client.control('checkpoint',body|{'expected_generation':envelope['generation'],
                'run_id':identifier,'publications':[],'prospective_deadline':None,
                'summary':{'mode':'storage-only verification','provider_requests':0,'new_forecasts':0}})
            result=verify_shared(client=client,expected_instance=expected_instance)
            if result['generation']!=receipt['generation'] or result['snapshot_sha256']!=body['manifest']['sha256']:
                raise StateError('Storage checkpoint readback differs')
            if result['provider_budget_hold']!=envelope.get('held') or result['record_counts']!=before['record_counts']:
                raise StateError('Storage check changed the hold or recorded research')
        return result|{'status':'storage-only checkpoint verified','remote_writes':1,
            'record_counts_preserved':True,'provider_hold_preserved':True}
    except Exception:
        try:client.control('fail')
        except StateError:pass
        raise
