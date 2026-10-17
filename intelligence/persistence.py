"""Check local storage and create consistent private SQLite backups, never keys."""
from pathlib import Path
from contextlib import closing
import os
import sqlite3
from intelligence.domain import utcnow


def storage_status(store):
    with store.connect() as db:
        healthy=db.execute('PRAGMA quick_check').fetchone()[0]=='ok'
        tables={r['name'] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        shadow_n=db.execute('SELECT count(*) FROM shadow_forecasts').fetchone()[0] if 'shadow_forecasts' in tables else 0
        identity=dict(db.execute('SELECT instance,created_at FROM store_identity WHERE id=1').fetchone()) if 'store_identity' in tables else None
        from intelligence.request_guard import blocked
        held=blocked(db)
    return {'database_healthy':healthy,'local_disk_writable':os.access(Path(store.path).parent,os.W_OK),
        'store_identity':identity,'database_file':Path(store.path).name,
        'shadow_forecasts':shadow_n,'redeployment_persistence_verified':False,
        'provider_requests_held_for_recovery_review':held,
        'background_worker':'Disabled: requires a separate scheduler and verified durable shared storage',
        'note':'SQLite survives process restarts on the same disk. Community Cloud redeploy/reboot persistence is not established. A backup on that same disk is not off-host protection.'}


def backup_store(store,target):
    target=Path(target)
    if target.resolve()==Path(store.path).resolve():
        raise ValueError('Backup must use a different private destination')
    target.parent.mkdir(parents=True,exist_ok=True)
    try:
        descriptor=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        os.close(descriptor)
    except FileExistsError:
        raise ValueError('Choose a new backup path; existing backups are never overwritten') from None
    with closing(store.connect()) as source,closing(sqlite3.connect(target)) as destination:
        source.backup(destination)
        destination.commit()
        if destination.execute('PRAGMA quick_check').fetchone()[0]!='ok':
            raise ValueError('Backup consistency check failed')
    target.chmod(0o600)
    return {'created_at':utcnow().isoformat(),'consistent_private_backup':True,
            'off_host_durability_verified':False}


def paper_export(store, limit=10000):
    """Portable inspection copy, without chat, caches, credentials or backtests.

    Downloading this file to another device gives a user an off-host copy. This
    function alone cannot verify that a download occurred or provide restore.
    """
    import json
    from intelligence.processing import ensure_processing
    ensure_processing(store)
    if type(limit) is not int or not 1 <= limit <= 10000:
        raise ValueError('Invalid bounded paper export size')
    with store.connect() as db:
        rows = db.execute('SELECT f.*,o.at AS labeled_at,o.outcome,o.source FROM shadow_forecasts f LEFT JOIN shadow_outcomes o ON f.id=o.id ORDER BY f.at,f.id LIMIT ?', (limit+1,)).fetchall()
    if len(rows) > limit:
        raise ValueError('Paper export exceeds UI limit; use a consistent private SQLite backup')
    return {'format':'sports-intelligence-paper-v1','exported_at':utcnow().isoformat(),
            'origin':'Actually recorded prospective paper research; not backtests or betting returns',
            'off_host_durability_verified':False,
            'records':[{'id':r['id'],'recorded_at':r['at'],'forecast':json.loads(r['payload']),
                        'labeled_at':r['labeled_at'],'outcome':r['outcome'],'outcome_source':r['source']} for r in rows]}
