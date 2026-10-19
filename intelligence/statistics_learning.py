"""Reuse the existing locked recalibration policy on real unpriced forecasts.

Separate namespace/ledgers from priced forecasts. Earlier archive evaluations
and already-known pre-lock forecasts can never become a fresh future test.
Training, calibration and one fixed future cohort; no automatic model promotion.
"""
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
import json
from intelligence.domain import utcnow,parse_time,digest
from intelligence.learning import POLICY,partition,train_candidate,transformed
from intelligence.epl_validation import metrics,reliability


def lock(store,now=None):
    now=now or utcnow()
    with store.connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS statistics_learning_protocols(id TEXT PRIMARY KEY,at TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS statistics_challengers(id TEXT PRIMARY KEY,at TEXT NOT NULL,scope TEXT NOT NULL UNIQUE,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS statistics_challenger_forecasts(id TEXT PRIMARY KEY,challenger_id TEXT NOT NULL,forward_id TEXT NOT NULL,at TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS statistics_challenger_evaluations(id TEXT PRIMARY KEY,at TEXT NOT NULL,payload TEXT NOT NULL);
        ''')
        for table in ('statistics_learning_protocols','statistics_challengers','statistics_challenger_forecasts','statistics_challenger_evaluations'):
            for action in ('UPDATE','DELETE'):
                db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'Immutable statistical learning evidence'); END")
        value={'policy':json.loads(POLICY.read_text()),'code_sha256':digest({n:Path(__file__).with_name(n).read_text() for n in ('statistics_learning.py','statistics_forward.py','learning.py')})}
        pid=digest(value)
        db.execute('INSERT OR IGNORE INTO statistics_learning_protocols VALUES(?,?,?)',(pid,now.isoformat(),json.dumps(value)))
        at=db.execute('SELECT at FROM statistics_learning_protocols WHERE id=?',(pid,)).fetchone()[0]
    return pid,parse_time(at),value['policy']


def source_rows(store):
    from intelligence.statistics_forward import ensure
    ensure(store);first={}
    with store.connect() as db:
        records=db.execute('SELECT f.*,o.payload outcome FROM statistics_forecasts f LEFT JOIN statistics_outcomes o ON f.id=o.id ORDER BY f.at,f.id').fetchall()
    for record in records:
        r=json.loads(record['payload'])
        # Logical probability bounds are not point estimates to calibrate.
        if r.get('kind')=='bounded_cross_game':continue
        legs=r.get('legs') or [{k:r[k] for k in ('market','selection','point')}]
        if any(l['market']=='h2h' and l['selection'] not in (r.get('home'),r.get('away'),'Draw') for l in legs):continue
        # A model-favored home selection in different games shares a task, not
        # a team-name-specific training scope. Exact saved fixture IDs remain.
        task=[]
        for leg in legs:
            selection=leg['selection']
            if leg['market']=='h2h':
                selection='home' if selection==r.get('home') else 'away' if selection==r.get('away') else selection
            task.append((leg['market'],selection,leg.get('point')))
        scope={'league':r['league'],'model_version':r['model_version'],'task':task,'kind':'unpriced-statistics'}
        key=(r['fixture_id'],json.dumps(scope,sort_keys=True));outcome=json.loads(record['outcome']) if record['outcome'] else None
        first.setdefault(key,{'id':record['id'],'at':record['at'],'quarantined':False,
            'payload':{'scope':scope,'forecast_at':r['forecast_at'],'quote':{'commence_time':r['kickoff']},
                'estimate':{'probability':r.get('joint_probability',r.get('probability'))}},
            'label':{'outcome':'win' if outcome['all_selections_won'] else 'loss',
                'verified_result':{'observed_at':outcome['source_observed_at']}} if outcome else None})
    return list(first.values())


def update(store,now=None):
    now=now or utcnow();pid,locked,policy=lock(store,now);source=source_rows(store);groups=defaultdict(list)
    for r in source:
        if locked<=parse_time(r['payload']['forecast_at'])<=parse_time(r['at'])<parse_time(r['payload']['quote']['commence_time']):
            groups[json.dumps(r['payload']['scope'],sort_keys=True)].append(r)
    created=captured=evaluated=0
    for scope,rows in groups.items():
        with store.connect() as db:existing=db.execute('SELECT 1 FROM statistics_challengers WHERE scope=?',(scope,)).fetchone()
        if existing:continue
        past=[r for r in rows if parse_time(r['payload']['quote']['commence_time'])+timedelta(hours=3)<now]
        train,cal=partition(past,policy)
        if (len(train)<policy['training_minimum'] or len(cal)<policy['calibration_minimum']
            or len({r['payload']['forecast_at'][:10] for r in cal})<policy['partition_minimum_day_blocks']):continue
        if any(parse_time(r['label']['verified_result']['observed_at'])>now for r in train+cal):continue
        start=(now+timedelta(days=1)).replace(hour=0,minute=0,second=0,microsecond=0)
        artifact=train_candidate(train,cal,policy)|{'scope':json.loads(scope),'protocol':pid,'test_start':start.isoformat(),
            'test_end':(start+timedelta(days=policy['test_days'])).isoformat(),'approved':False}
        with store.connect() as db:created+=db.execute('INSERT OR IGNORE INTO statistics_challengers VALUES(?,?,?,?)',(digest(artifact),now.isoformat(),scope,json.dumps(artifact))).rowcount
    with store.connect() as db:challengers=db.execute('SELECT * FROM statistics_challengers').fetchall()
    for c in challengers:
        a=json.loads(c['payload'])
        if a['protocol']!=pid:continue
        cohort=[r for r in groups.get(c['scope'],[]) if parse_time(a['test_start'])<=parse_time(r['payload']['forecast_at'])<parse_time(a['test_end'])]
        for r in cohort:
            p=r['payload']
            if not parse_time(c['at'])<parse_time(p['forecast_at'])<=parse_time(r['at'])<=now<parse_time(p['quote']['commence_time']):continue
            if r['id'] in a['training_ids']+a['calibration_ids']:raise ValueError('Prospective cohort overlaps fit data')
            value={'probability':transformed(p['estimate']['probability'],a),'champion_probability':p['estimate']['probability']}
            with store.connect() as db:captured+=db.execute('INSERT OR IGNORE INTO statistics_challenger_forecasts VALUES(?,?,?,?,?)',(digest((c['id'],r['id'])),c['id'],r['id'],now.isoformat(),json.dumps(value))).rowcount
        if now<parse_time(a['test_end'])+timedelta(days=3) or any(not r['label'] for r in cohort):continue
        with store.connect() as db:
            if db.execute('SELECT 1 FROM statistics_challenger_evaluations WHERE id=?',(c['id'],)).fetchone():continue
            actual={r['forward_id']:json.loads(r['payload']) for r in db.execute('SELECT * FROM statistics_challenger_forecasts WHERE challenger_id=?',(c['id'],))}
        blockers=[];report=None;days=[r['payload']['forecast_at'][:10] for r in cohort]
        if set(actual)!={r['id'] for r in cohort}:blockers.append('Missing genuine pregame challenger observations; no backfill')
        if len(cohort)<policy['test_minimum'] or len(set(days))<policy['test_minimum_day_blocks']:blockers.append('Insufficient independent future cohort')
        if not blockers:
            p=[actual[r['id']]['probability'] for r in cohort];base=[actual[r['id']]['champion_probability'] for r in cohort];y=[int(r['label']['outcome']=='win') for r in cohort]
            report={'metrics':metrics(p,y,days,policy['bootstrap_resamples'],policy['seed']),
                'paired_minus_champion':metrics(p,y,days,policy['bootstrap_resamples'],policy['seed'],base),'reliability':reliability(p,y)}
        value={'report':report,'blockers':blockers,'approved':False,'automatic_promotion':False,
            'decision':'Retain frozen model; independent reviewed lifecycle gates still required'}
        with store.connect() as db:evaluated+=db.execute('INSERT OR IGNORE INTO statistics_challenger_evaluations VALUES(?,?,?)',(c['id'],now.isoformat(),json.dumps(value))).rowcount
    return {'new_challengers':created,'new_pregame_challenger_forecasts':captured,'new_evaluations':evaluated,
        'automatic_promotion':False,'training_minimum':policy['training_minimum'],'calibration_minimum':policy['calibration_minimum'],
        'fixed_future_test_days':policy['test_days'],'test_minimum':policy['test_minimum'],
        'state':'Collecting protocol-locked, genuinely recorded future results; historical backtests are excluded'}
