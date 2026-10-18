"""Append-only, genuinely recorded unpriced forecasts; never betting returns."""
import json, math
from datetime import timedelta
from intelligence.domain import utcnow, parse_time, digest


def ensure(store):
    with store.connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS statistics_forecasts(id TEXT PRIMARY KEY,at TEXT NOT NULL,kickoff TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS statistics_outcomes(id TEXT PRIMARY KEY REFERENCES statistics_forecasts(id),at TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS statistics_forecasts_no_update BEFORE UPDATE ON statistics_forecasts BEGIN SELECT RAISE(ABORT,'Immutable statistical forecast'); END;
        CREATE TRIGGER IF NOT EXISTS statistics_forecasts_no_delete BEFORE DELETE ON statistics_forecasts BEGIN SELECT RAISE(ABORT,'Immutable statistical forecast'); END;
        CREATE TRIGGER IF NOT EXISTS statistics_outcomes_no_update BEFORE UPDATE ON statistics_outcomes BEGIN SELECT RAISE(ABORT,'Immutable statistical outcome'); END;
        CREATE TRIGGER IF NOT EXISTS statistics_outcomes_no_delete BEFORE DELETE ON statistics_outcomes BEGIN SELECT RAISE(ABORT,'Immutable statistical outcome'); END;
        ''')


def record(store,rows,now=None):
    now=now or utcnow();ensure(store);created=[]
    if len(rows)>100:raise ValueError('Bounded forward records required')
    prepared=[]
    for r in rows:
        p=r.get('joint_probability',r.get('probability'))
        if (not r.get('research_eligible') or not isinstance(p,(int,float)) or not math.isfinite(p) or not 0<p<1
            or r.get('approved') or r.get('validated') or r.get('joint_validated') or r.get('observed_odds') is not None
            or r.get('combined_odds') is not None or r.get('ev') is not None
            or not r.get('evidence_id') or not now+timedelta(minutes=15)<parse_time(r['kickoff'])
            or not 0<=(now-parse_time(r['forecast_at'])).total_seconds()<60
            or not 0<=(now-parse_time(r['source_observed_at'])).total_seconds()<21600):
            raise ValueError('Not eligible as an actually recorded pregame statistical forecast')
        key=digest({k:v for k,v in r.items() if k!='forecast_at'})
        prepared.append((key,now.isoformat(),r['kickoff'],json.dumps(r,allow_nan=False)))
    with store.connect() as db:
        for row in prepared:
            if db.execute('INSERT OR IGNORE INTO statistics_forecasts VALUES(?,?,?,?)',row).rowcount:created.append(row[0])
    return created


def reconcile(store,now=None):
    """Exact source fixture/kickoff and regulation score; no bookmaker settlement."""
    from intelligence.openliga import current
    from intelligence.score_distribution import settlement
    now=now or utcnow();ensure(store);events,meta=current(store,'Bundesliga',now)
    if not meta['ok']:return 0
    finals={e.fixture_id:e for e in events if e.status=='completed'};added=0
    with store.connect() as db:
        rows=db.execute('SELECT f.* FROM statistics_forecasts f LEFT JOIN statistics_outcomes o ON f.id=o.id WHERE o.id IS NULL').fetchall()
        for row in rows:
            r=json.loads(row['payload']);event=finals.get(r['fixture_id'])
            if not event or parse_time(event.kickoff)!=parse_time(r['kickoff']) or parse_time(row['at'])>=parse_time(event.kickoff):continue
            legs=r.get('legs') or [{k:r[k] for k in ('market','selection','point')}]
            states=[settlement(l['market'],l['selection'],l['point'],event.home_name,event.away_name,event.home_score,event.away_score) for l in legs]
            # Current source contracts have no pushes/quarter lines. Do not
            # turn ambiguous partial settlements into binary outcomes.
            if any(s not in ((1.,0.,0.),(0.,0.,1.)) for s in states):continue
            value={'all_selections_won':all(s==(1.,0.,0.) for s in states),
                'home_score':event.home_score,'away_score':event.away_score,'source':event.source,
                'source_observed_at':event.observed_at,'source_sha256':meta['sha256'],
                'scope':'Unpriced paper forecast outcome; not a settled sportsbook ticket or financial return'}
            added+=db.execute('INSERT OR IGNORE INTO statistics_outcomes VALUES(?,?,?)',(row['id'],now.isoformat(),json.dumps(value))).rowcount
    return added
