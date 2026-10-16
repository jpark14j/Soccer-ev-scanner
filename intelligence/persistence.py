"""Check local storage and create consistent private SQLite backups, never keys."""
from pathlib import Path
import os
import sqlite3
from intelligence.domain import utcnow


def storage_status(store):
    with store.connect() as db:
        healthy=db.execute('PRAGMA quick_check').fetchone()[0]=='ok'
        tables={r['name'] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        shadow_n=db.execute('SELECT count(*) FROM shadow_forecasts').fetchone()[0] if 'shadow_forecasts' in tables else 0
    return {'database_healthy':healthy,'local_disk_writable':os.access(Path(store.path).parent,os.W_OK),
        'shadow_forecasts':shadow_n,'redeployment_persistence_verified':False,
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
    with store.connect() as source,sqlite3.connect(target) as destination:
        source.backup(destination)
        if destination.execute('PRAGMA quick_check').fetchone()[0]!='ok':
            raise ValueError('Backup consistency check failed')
    target.chmod(0o600)
    return {'created_at':utcnow().isoformat(),'consistent_private_backup':True,
            'off_host_durability_verified':False}
