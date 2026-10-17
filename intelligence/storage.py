"""Small transactional SQLite store; publication and settlement records are immutable.

Use a persistent disk for production. GitHub runners/Streamlit ephemeral disks are
not a permanent ledger. An external SQLite backup or database is a rollout gate.
"""
import json
from pathlib import Path
import sqlite3
from uuid import uuid4
from datetime import timedelta
from intelligence.domain import digest, parse_time, utcnow


class Store:
    def __init__(self, path='data/intelligence.sqlite3'):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, at TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS budget(day TEXT PRIMARY KEY, used INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS publications(
                id TEXT PRIMARY KEY, at TEXT NOT NULL, origin TEXT NOT NULL,
                payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS settlements(
                publication_id TEXT PRIMARY KEY REFERENCES publications(id),
                at TEXT NOT NULL, outcome TEXT NOT NULL, result TEXT NOT NULL,
                source TEXT NOT NULL, closing_odds REAL, closing_source TEXT, closing_observed_at TEXT);
            CREATE TABLE IF NOT EXISTS deliveries(
                day TEXT PRIMARY KEY, status TEXT NOT NULL, at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS fetch_leases(
                key TEXT PRIMARY KEY, owner TEXT NOT NULL, expires_at TEXT NOT NULL);
            CREATE TRIGGER IF NOT EXISTS publication_no_update BEFORE UPDATE ON publications
                BEGIN SELECT RAISE(ABORT, 'Published predictions are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS publication_no_delete BEFORE DELETE ON publications
                BEGIN SELECT RAISE(ABORT, 'Published predictions are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS settlement_no_update BEFORE UPDATE ON settlements
                BEGIN SELECT RAISE(ABORT, 'Settlements are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS settlement_no_delete BEFORE DELETE ON settlements
                BEGIN SELECT RAISE(ABORT, 'Settlements are immutable'); END;
            ''')
            columns = {row['name'] for row in db.execute('PRAGMA table_info(settlements)')}
            for column in ('closing_source','closing_observed_at'):
                if column not in columns:
                    db.execute('ALTER TABLE settlements ADD COLUMN ' + column + ' TEXT')
            db.execute('CREATE TABLE IF NOT EXISTS store_identity(id INTEGER PRIMARY KEY CHECK(id=1),instance TEXT NOT NULL,created_at TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO store_identity VALUES(1,?,?)',(uuid4().hex,utcnow().isoformat()))

    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

    def cached(self, key, ttl, now=None):
        now = now or utcnow()
        with self.connect() as db:
            row = db.execute('SELECT * FROM cache WHERE key=?', (key,)).fetchone()
        if row and timedelta(0) <= now - parse_time(row['at']) < timedelta(seconds=ttl):
            return json.loads(row['payload'])
        return None

    def cache(self, key, payload, now=None):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)',
                       (key, (now or utcnow()).isoformat(), json.dumps(payload, allow_nan=False)))

    def reserve(self, cost, daily_limit=12, now=None):
        if cost <= 0 or daily_limit < 0:
            raise ValueError('Invalid quota budget')
        day = (now or utcnow()).date().isoformat()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            from intelligence.request_guard import blocked
            if blocked(db):return False
            row = db.execute('SELECT used FROM budget WHERE day=?', (day,)).fetchone()
            used = row['used'] if row else 0
            if used + cost > daily_limit:
                return False
            db.execute('INSERT OR REPLACE INTO budget VALUES(?,?)', (day, used + cost))
        return True

    def claim_fetch(self,key,owner,now=None):
        now=now or utcnow()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM fetch_leases WHERE expires_at<=?',(now.isoformat(),))
            return db.execute('INSERT OR IGNORE INTO fetch_leases VALUES(?,?,?)',
                (key,owner,(now+timedelta(seconds=90)).isoformat())).rowcount==1

    def release_fetch(self,key,owner):
        with self.connect() as db:
            db.execute('DELETE FROM fetch_leases WHERE key=? AND owner=?',(key,owner))

    def publish(self, opportunity, origin='forward', now=None):
        if origin not in ('forward', 'backtest'):
            raise ValueError('Unknown prediction origin')
        if origin=='forward':
            from intelligence.ev import qualify
            if qualify(opportunity.quote,opportunity.estimate,now)[0] is None:
                raise ValueError('Only current qualifying forward predictions may be published')
        payload = opportunity.to_dict()
        # Repeated renders of the same verified quote/model do not duplicate records.
        identifier = digest((payload, origin))
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO publications VALUES(?,?,?,?)',
                       (identifier, (now or utcnow()).isoformat(), origin, json.dumps(payload, allow_nan=False)))
        return identifier

    def settle(self, identifier, outcome, result, source, closing_odds=None, now=None, closing_source=None, closing_observed_at=None):
        from intelligence.domain import finite
        if outcome not in ('win', 'loss', 'push', 'void') or not result or not source:
            raise ValueError('Settlement requires outcome, final result and evidence source')
        if closing_odds is not None and (not finite(closing_odds) or closing_odds <= 1):
            raise ValueError('Invalid closing odds')
        with self.connect() as db:
            row=db.execute('SELECT payload,at FROM publications WHERE id=?',(identifier,)).fetchone()
            if row is None:
                raise ValueError('Unknown published prediction')
            if outcome!='void' and parse_time(json.loads(row['payload'])['quote']['commence_time']) >= (now or utcnow()):
                raise ValueError('Cannot settle a result before the event begins')
            if closing_odds is not None:
                if not closing_source or not closing_observed_at:
                    raise ValueError('Closing quote requires its source and observed timestamp')
                row=db.execute('SELECT payload,at FROM publications WHERE id=?',(identifier,)).fetchone()
                if row is None:
                    raise ValueError('Unknown published prediction')
                event_start=parse_time(json.loads(row['payload'])['quote']['commence_time'])
                observed=parse_time(closing_observed_at)
                if not parse_time(row['at']) <= observed < event_start or observed > (now or utcnow()):
                    raise ValueError('Closing quote must be observed after publication and before event')
            db.execute('INSERT INTO settlements VALUES(?,?,?,?,?,?,?,?)',
                       (identifier, (now or utcnow()).isoformat(), outcome, str(result), source, closing_odds, closing_source, closing_observed_at))

    def records(self, origin='forward'):
        with self.connect() as db:
            rows = db.execute('''SELECT p.*, s.outcome, s.result, s.source, s.closing_odds,
                s.at AS settled_at, s.closing_source, s.closing_observed_at FROM publications p LEFT JOIN settlements s
                ON p.id=s.publication_id WHERE p.origin=? ORDER BY p.at,p.id''', (origin,)).fetchall()
        return [dict(row) | {'payload': json.loads(row['payload'])} for row in rows]

    def claim_delivery(self, day, now=None):
        with self.connect() as db:
            result = db.execute('INSERT OR IGNORE INTO deliveries VALUES(?,?,?)',
                                (day, 'pending', (now or utcnow()).isoformat()))
            return result.rowcount == 1

    def delivery_sent(self, day):
        with self.connect() as db:
            db.execute("UPDATE deliveries SET status='sent' WHERE day=?", (day,))
