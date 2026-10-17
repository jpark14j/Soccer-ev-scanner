"""Evidence-triggered calibration challengers; fixed prospective tests, no promotion.

Historical frozen models remain intact. No downloads, odds calls, code editing,
page-load fitting, or training on the candidate's prospective test outcomes.
"""
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
import json,math
from intelligence.domain import utcnow,parse_time,digest
from intelligence.data_adapters import ROOT
from intelligence.forward_testing import records
from intelligence.epl_validation import fit_calibrator,calibrated,metrics,reliability

POLICY=ROOT/'config/continuous_learning_policy.json'


def ensure(store):
    with store.connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS learning_protocols(id TEXT PRIMARY KEY,at TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS learning_challengers(id TEXT PRIMARY KEY,at TEXT NOT NULL,scope TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS learning_forecasts(id TEXT PRIMARY KEY,challenger_id TEXT NOT NULL REFERENCES learning_challengers(id),forward_id TEXT NOT NULL,at TEXT NOT NULL,payload TEXT NOT NULL,UNIQUE(challenger_id,forward_id));
        CREATE TABLE IF NOT EXISTS learning_evaluations(id TEXT PRIMARY KEY REFERENCES learning_challengers(id),at TEXT NOT NULL,payload TEXT NOT NULL);
        ''')
        for table in ('learning_protocols','learning_challengers','learning_forecasts','learning_evaluations'):
            for action in ('UPDATE','DELETE'):
                db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'Immutable learning evidence'); END")


def lock_protocol(store,now=None):
    now=now or utcnow();ensure(store)
    payload={'policy':json.loads(POLICY.read_text()),'code_sha256':digest(Path(__file__).read_text())};identifier=digest(payload)
    with store.connect() as db:
        db.execute('INSERT OR IGNORE INTO learning_protocols VALUES(?,?,?)',(identifier,now.isoformat(),json.dumps(payload,allow_nan=False)))
        row=db.execute('SELECT at FROM learning_protocols WHERE id=?',(identifier,)).fetchone()
    if parse_time(row['at'])>now:raise ValueError('Future learning protocol')
    return identifier,parse_time(row['at']),payload


def partition(rows,policy):
    """Whole UTC dates, all outcomes required; never split a game's date."""
    ordered=sorted(rows,key=lambda r:(r['payload']['forecast_at'],r['id']));groups=defaultdict(list)
    for r in ordered:groups[r['payload']['forecast_at'][:10]].append(r)
    training=[];calibration=[]
    for day,batch in sorted(groups.items()):
        if any(not r['label'] or r['quarantined'] or r['label']['outcome'] not in ('win','loss') for r in batch):
            # Do not select only the settled/hit subset of an earlier date.
            break
        if len(training)<policy['training_minimum'] or len({r['payload']['forecast_at'][:10] for r in training})<policy['partition_minimum_day_blocks']:
            training.extend(batch)
        else:calibration.extend(batch)
        if len(calibration)>=policy['calibration_minimum'] and len({r['payload']['forecast_at'][:10] for r in calibration})>=policy['partition_minimum_day_blocks']:break
    return training,calibration


def transformed(p,artifact):
    mapped=float(calibrated([p],artifact['coefficients'])[0]);weight=artifact['blend']
    return min(1-1e-8,max(1e-8,(1-weight)*p+weight*mapped))


def train_candidate(training,calibration,policy):
    if not training or not calibration or max(r['payload']['forecast_at'][:10] for r in training)>=min(r['payload']['forecast_at'][:10] for r in calibration):raise ValueError('Chronological training/calibration separation required')
    p=[r['payload']['estimate']['probability'] for r in training];y=[int(r['label']['outcome']=='win') for r in training]
    coefficients=fit_calibrator(p,y)
    cp=[r['payload']['estimate']['probability'] for r in calibration];cy=[int(r['label']['outcome']=='win') for r in calibration]
    mapped=calibrated(cp,coefficients)
    choices=[(sum(((1-w)*a+w*float(b)-v)**2 for a,b,v in zip(cp,mapped,cy))/len(cy),w) for w in policy['blend_grid']]
    loss,weight=min(choices)  # Identity wins ties; the future test never tunes it.
    return {'coefficients':coefficients,'blend':weight,'calibration_brier':loss,
        'training_ids':[r['id'] for r in training],'calibration_ids':[r['id'] for r in calibration],
        'data_sha256':digest([(r['id'],r['payload'],r['label']) for r in training+calibration]),
        'training_n':len(training),'calibration_n':len(calibration),
        'training_end':max(r['payload']['forecast_at'] for r in training),
        'calibration_end':max(r['payload']['forecast_at'] for r in calibration),
        'method':'Monotone Platt recalibration fitted on earlier frozen-model forward forecasts; blend selected only on subsequent calibration dates'}


def update(store,now=None):
    if getattr(store,'read_replica',False):return {'state':'Read-only replica; learning runs in the worker'}
    now=now or utcnow();pid,locked,protocol=lock_protocol(store,now);policy=protocol['policy'];groups=defaultdict(list)
    source=records(store)
    # Require a genuine protocol lock before any eligible observation, retaining
    # earlier historical/forward knowledge without passing it off as new evidence.
    for r in source:
        if r['payload']['protocol_locked_before_forecast'] and locked<=parse_time(r['payload']['forecast_at'])<=parse_time(r['at'])<parse_time(r['payload']['quote']['commence_time']):
            groups[json.dumps(r['payload']['scope'],sort_keys=True)].append(r)
    created=0
    for scope,rows in groups.items():
        with store.connect() as db:existing=db.execute('SELECT 1 FROM learning_challengers WHERE scope=?',(scope,)).fetchone()
        if existing:continue  # No repeated fishing against the same cohort.
        train,cal=partition([r for r in rows if parse_time(r['payload']['quote']['commence_time'])+timedelta(hours=3)<now],policy)
        if len(train)<policy['training_minimum'] or len(cal)<policy['calibration_minimum'] or len({r['payload']['forecast_at'][:10] for r in cal})<policy['partition_minimum_day_blocks']:continue
        if any(parse_time(r['label']['verified_result']['observed_at'])>now for r in train+cal):continue
        artifact=train_candidate(train,cal,policy)
        payload=artifact|{'learning_protocol':pid,'scope':json.loads(scope),'created_at':now.isoformat(),
            'test_start':(now+timedelta(days=1)).replace(hour=0,minute=0,second=0,microsecond=0).isoformat(),
            'test_end':((now+timedelta(days=1)).replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=policy['test_days'])).isoformat(),
            'status':'Challenger only; frozen champion unchanged','approved':False,'automatic_promotion':False}
        identifier=digest(payload)
        with store.connect() as db:created+=db.execute('INSERT OR IGNORE INTO learning_challengers VALUES(?,?,?,?)',(identifier,now.isoformat(),scope,json.dumps(payload,allow_nan=False))).rowcount
    captured=0
    with store.connect() as db:challengers=db.execute('SELECT * FROM learning_challengers').fetchall()
    for c in challengers:
        a=json.loads(c['payload'])
        if a['learning_protocol']!=pid:continue
        for r in source:
            p=r['payload'];at=parse_time(p['forecast_at']);kick=parse_time(p['quote']['commence_time'])
            if p['scope']!=a['scope'] or r['quarantined'] or not parse_time(a['test_start'])<=at<parse_time(a['test_end']):continue
            if not parse_time(c['at'])<at<=parse_time(r['at'])<=now<kick:continue
            if r['id'] in set(a['training_ids']+a['calibration_ids']):raise ValueError('Challenger test overlaps fit data')
            cp=transformed(p['estimate']['probability'],a)
            value={'probability':cp,'champion_probability':p['estimate']['probability'],
                'forward_id':r['id'],'challenger_id':c['id'],'forecast_at':at.isoformat(),'kickoff':kick.isoformat(),
                'baseline':p['baseline'],'status':'Unapproved prospective challenger; no source outcome used'}
            with store.connect() as db:captured+=db.execute('INSERT OR IGNORE INTO learning_forecasts VALUES(?,?,?,?,?)',(digest((c['id'],r['id'])),c['id'],r['id'],now.isoformat(),json.dumps(value,allow_nan=False))).rowcount
    evaluated=evaluate(store,source,now,pid,policy)
    return {'state':'Collecting independent forward evidence' if not challengers and not created else 'Challengers locked; future evaluation pending or completed',
        'new_challengers':created,'new_test_forecasts':captured,'new_evaluations':evaluated,
        'eligible_scope_count':len(groups),'automatic_promotion':False,'provider_requests':0,
        'requirements':{'training':policy['training_minimum'],'calibration':policy['calibration_minimum'],'prospective_test':policy['test_minimum'],'fixed_test_days':policy['test_days']}}


def evaluate(store,source,now,pid,policy):
    source={r['id']:r for r in source};n=0
    with store.connect() as db:
        candidates=db.execute('SELECT c.* FROM learning_challengers c LEFT JOIN learning_evaluations e ON e.id=c.id WHERE e.id IS NULL').fetchall()
    for c in candidates:
        a=json.loads(c['payload'])
        if a['learning_protocol']!=pid or now<parse_time(a['test_end'])+timedelta(days=3):continue
        with store.connect() as db:raw=db.execute('SELECT * FROM learning_forecasts WHERE challenger_id=? ORDER BY at,id',(c['id'],)).fetchall()
        rows=[(r,json.loads(r['payload']),source.get(r['forward_id'])) for r in raw]
        # All eligible independent source forecasts in the fixed period must
        # have a pregame challenger record, including losses and missed runs.
        expected={r['id'] for r in source.values() if r['payload']['scope']==a['scope'] and parse_time(a['test_start'])<=parse_time(r['payload']['forecast_at'])<parse_time(a['test_end'])}
        complete={r['forward_id'] for r,_,_ in rows}==expected and bool(expected)
        valid=all(r and not r['quarantined'] and r['label'] and r['label']['outcome'] in ('win','loss') for _,_,r in rows)
        if any(r and not r['quarantined'] and not r['label'] for _,_,r in rows):continue
        days=[p['forecast_at'][:10] for _,p,_ in rows]
        blockers=[]
        if not complete:blockers.append('Some eligible test forecasts lack an actually recorded pregame challenger; no hindsight backfill')
        if not valid:blockers.append('Pending, quarantined or invalid test results; no settled-only selection')
        if len(rows)<policy['test_minimum'] or len(set(days))<policy['test_minimum_day_blocks']:blockers.append('Fixed future cohort has insufficient observations or independent day blocks')
        report=None
        if not blockers:
            prob=[p['probability'] for _,p,_ in rows];base=[p['champion_probability'] for _,p,_ in rows];y=[int(r['label']['outcome']=='win') for _,_,r in rows]
            scores=metrics(prob,y,days,policy['bootstrap_resamples'],policy['seed'])
            difference=metrics(prob,y,days,policy['bootstrap_resamples'],policy['seed'],base)
            interval=difference['binary_brier']['interval']
            report={'metrics':scores,'paired_minus_champion':difference,'calibration_bins':reliability(prob,y),
                'improvement_supported':bool(interval and interval[1]<0)}
            if not report['improvement_supported']:blockers.append('Paired Brier improvement is inconclusive; champion retained')
        payload={'challenger_id':c['id'],'test_n':len(rows),'UTC_day_blocks':len(set(days)),
            'test_start':a['test_start'],'test_end':a['test_end'],'report':report,'blockers':blockers,
            'decision':'Review preparation only; champion retained','automatic_promotion':False,
            'approved':False,'repeated_looks':'One report after the predeclared cohort closes; no retuning on these outcomes',
            'external_verification':'Self-recorded evidence; external verification and existing reviewed lifecycle gates remain required'}
        with store.connect() as db:n+=db.execute('INSERT OR IGNORE INTO learning_evaluations VALUES(?,?,?)',(c['id'],now.isoformat(),json.dumps(payload,allow_nan=False))).rowcount
    return n


def status(store):
    ensure(store)
    with store.connect() as db:
        challengers=[dict(r)|{'payload':json.loads(r['payload'])} for r in db.execute('SELECT * FROM learning_challengers ORDER BY at,id')]
        reports=[dict(r)|{'payload':json.loads(r['payload'])} for r in db.execute('SELECT * FROM learning_evaluations ORDER BY at,id')]
        n=db.execute('SELECT count(*) FROM learning_forecasts').fetchone()[0]
    return {'frozen_champions':'Existing EPL, Bundesliga and Ligue 1 experimental models; no replacement',
        'challengers':challengers,'test_forecasts':n,'evaluations':reports,'last_evaluation':reports[-1]['at'] if reports else None,
        'improvement_verified':False,'automatic_promotion':False,
        'state':'Collecting evidence; improvement not established' if not reports else 'Candidate report available; reviewed activation remains required',
        'policy':json.loads(POLICY.read_text()),'note':'No model is trained on page load. Existing historical models remain the research foundation. No automatic improvement or betting approval is promised.'}
