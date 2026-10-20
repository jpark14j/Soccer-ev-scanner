"""Private append-only accepted results, separate from disposable attempt cache.

Same-disk recovery only: this is not an external backup or a provider recheck.
Original source receipt and status remain unchanged. No token/raw HTTP is stored.
"""
import json
from intelligence.domain import digest, parse_time


def exists(db, table):
    return bool(db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone())


def latest(store, league, season):
    with store.connect() as db:
        if not exists(db,'accepted_soccer_snapshots'):return None
        row=db.execute('SELECT payload,checksum FROM accepted_soccer_snapshots WHERE league=? AND season=? ORDER BY at DESC,id DESC LIMIT 1',(league,season)).fetchone()
    if not row:return None
    data=json.loads(row['payload'])
    if digest(data)!=row['checksum']:raise ValueError('Accepted results journal integrity failed')
    return data


def accept(store, league, season, payload):
    if not (payload['ok'] and payload['events'] and payload['sha256']):
        raise ValueError('Only accepted results enter the journal')
    # Allowlist avoids carrying any request/credential/debug fields into history.
    fields=('ok','problem','provider','checked_at','events','coverage','sha256','source_url',
        'license_reference','provider_statuses','team_bindings')
    data=json.loads(json.dumps({k:payload[k] for k in fields if k in payload},allow_nan=False))
    checksum=digest(data)
    parse_time(data['checked_at'])
    with store.connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS accepted_soccer_snapshots(id TEXT PRIMARY KEY,league TEXT NOT NULL,season TEXT NOT NULL,at TEXT NOT NULL,checksum TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS soccer_snapshot_scope ON accepted_soccer_snapshots(league,season,at);
        CREATE TRIGGER IF NOT EXISTS soccer_snapshot_no_update BEFORE UPDATE ON accepted_soccer_snapshots BEGIN SELECT RAISE(ABORT,'Immutable accepted results'); END;
        CREATE TRIGGER IF NOT EXISTS soccer_snapshot_no_delete BEFORE DELETE ON accepted_soccer_snapshots BEGIN SELECT RAISE(ABORT,'Immutable accepted results'); END;
        ''')
        db.execute('INSERT OR IGNORE INTO accepted_soccer_snapshots VALUES(?,?,?,?,?,?)',
            (checksum,league,season,data['checked_at'],checksum,json.dumps(data,allow_nan=False)))


def retained_observations(store, competition):
    """Inspection facts only; do not reconstruct an authoritative full snapshot."""
    with store.connect() as db:
        if not exists(db,'event_observations'):return {'observations':0,'completed_observations':0}
        rows=db.execute('SELECT payload FROM event_observations WHERE competition_id=?',(competition,)).fetchall()
    rows=[json.loads(r['payload']) for r in rows]
    rows=[r for r in rows if r['source']=='football-data.org']
    return {'observations':len(rows),'completed_observations':sum(r['status']=='completed' for r in rows),
        'note':'Versions, not unique games. Retained observations alone cannot prove a complete fresh source snapshot.'}
