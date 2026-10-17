"""Restored snapshots cannot silently restore an earlier provider allowance."""
from intelligence.domain import utcnow
from urllib.parse import urlsplit


def blocked(db):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='recovery_guard_events'").fetchone():return False
    row=db.execute('SELECT action FROM recovery_guard_events ORDER BY id DESC LIMIT 1').fetchone()
    return bool(row and row['action']=='hold')


def hold(db,reference,now=None):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS recovery_guard_events(id INTEGER PRIMARY KEY AUTOINCREMENT,at TEXT NOT NULL,action TEXT NOT NULL,reference TEXT NOT NULL);
    CREATE TRIGGER IF NOT EXISTS recovery_no_update BEFORE UPDATE ON recovery_guard_events BEGIN SELECT RAISE(ABORT,'Immutable recovery audit'); END;
    CREATE TRIGGER IF NOT EXISTS recovery_no_delete BEFORE DELETE ON recovery_guard_events BEGIN SELECT RAISE(ABORT,'Immutable recovery audit'); END;
    ''')
    db.execute('INSERT INTO recovery_guard_events(at,action,reference) VALUES(?,?,?)',((now or utcnow()).isoformat(),'hold',reference))


def reviewed_release(store,odds_used,results_used,reference,now=None):
    """Explicit operator-only budget reconciliation, never callable by chat/UI."""
    now=now or utcnow()
    u=urlsplit(reference)
    if type(odds_used) is not int or not 0<=odds_used<=9 or type(results_used) is not int or not 0<=results_used<=6 or u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment:
        raise ValueError('Explicit reviewed provider-usage counts and secure audit reference required')
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if not blocked(db):raise ValueError('No recovery hold exists')
        row=db.execute('SELECT used FROM budget WHERE day=?',(now.date().isoformat(),)).fetchone()
        db.execute('INSERT OR REPLACE INTO budget VALUES(?,?)',(now.date().isoformat(),max(odds_used,row['used'] if row else 0)))
        db.execute('CREATE TABLE IF NOT EXISTS football_data_requests(at TEXT NOT NULL)')
        existing=db.execute('SELECT count(*) FROM football_data_requests WHERE substr(at,1,10)=?',(now.date().isoformat(),)).fetchone()[0]
        db.executemany('INSERT INTO football_data_requests VALUES(?)',[(now.isoformat(),)]*max(0,results_used-existing))
        db.execute('INSERT INTO recovery_guard_events(at,action,reference) VALUES(?,?,?)',(now.isoformat(),'release',reference))
