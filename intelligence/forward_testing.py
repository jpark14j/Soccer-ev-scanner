"""Immutable, deduplicated prospective evaluation alongside the legacy paper log.

No backfill from historical forecasts, provider calls, betting publication or
automatic approval. One first pregame forecast per contract/model/protocol.
"""
from collections import Counter,defaultdict
from dataclasses import asdict
from pathlib import Path
from datetime import timedelta
import json,math,sqlite3
from intelligence.domain import Quote,Estimate,digest,utcnow,parse_time
from intelligence.data_adapters import ROOT,team_identity
from intelligence.competitions import COMPETITIONS
from intelligence.parlay_intelligence import binary_market,physical_game
from intelligence.parlay_research import leg_evidence,quote_problem
from intelligence.research_ranking import evidence_problem
from intelligence.research_top import SourceChecks
from intelligence.risk_research import VERSION
from intelligence.results_journal import latest
from intelligence.score_distribution import settlement,state_label

POLICY=ROOT/'config/forward_research_policy.json'


def ensure(store):
    with store.connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS forward_protocols(id TEXT PRIMARY KEY,at TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS forward_forecasts(id TEXT PRIMARY KEY,at TEXT NOT NULL,protocol_id TEXT NOT NULL REFERENCES forward_protocols(id),payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS forward_labels(id TEXT PRIMARY KEY REFERENCES forward_forecasts(id),at TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS forward_issues(id TEXT PRIMARY KEY,forecast_id TEXT NOT NULL REFERENCES forward_forecasts(id),at TEXT NOT NULL,code TEXT NOT NULL);
        ''')
        for table in ('forward_protocols','forward_forecasts','forward_labels','forward_issues'):
            for action in ('UPDATE','DELETE'):
                db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'Immutable forward evidence'); END")


def lock_protocol(store,now=None):
    now=now or utcnow();ensure(store)
    policy=json.loads(POLICY.read_text())
    payload={'policy':policy,'ranking_version':VERSION,'forward_code_sha256':digest(Path(__file__).read_text()),
        'reliability_code_sha256':digest(Path(__file__).with_name('model_reliability.py').read_text()),
        'ranking_code_sha256':digest(Path(__file__).with_name('risk_research.py').read_text())}
    identifier=digest(payload)
    with store.connect() as db:
        db.execute('INSERT OR IGNORE INTO forward_protocols VALUES(?,?,?)',(identifier,now.isoformat(),json.dumps(payload,allow_nan=False)))
        row=db.execute('SELECT * FROM forward_protocols WHERE id=?',(identifier,)).fetchone()
        if digest(json.loads(row['payload']))!=identifier or parse_time(row['at'])>now:raise ValueError('Invalid protocol lock')
    return identifier


def source_fixture(store,q,now):
    from intelligence.current_results import season_at
    snapshot=latest(store,q.league,season_at(now))
    if not snapshot or not snapshot.get('ok'):raise ValueError('Accepted full source snapshot unavailable')
    c=COMPETITIONS[q.league];h,_=team_identity(c,q.home);a,_=team_identity(c,q.away)
    found=[e for e in snapshot['events'] if (e['home_id'],e['away_id'])==(h,a) and parse_time(e['kickoff'])==parse_time(q.commence_time)]
    if len(found)!=1:raise ValueError('Exact source fixture unavailable')
    return found[0],snapshot


def baseline(leg):
    from intelligence.epl_forecasts import load_artifact
    from intelligence.expanded_models import load
    q,e=leg.quote,leg.estimate
    a=load_artifact() if q.league=='Premier League' else load(q.league)
    if not a or e.evidence_id!=a['artifact_sha256']:raise ValueError('Matching frozen baseline unavailable')
    task=a['tasks']['btts' if q.market=='btts' else 'totals_2.5'] if 'tasks' in a else a
    p=task.get('constant_baseline_probability')
    if p is None:
        bins=task['calibration_bins'];n=sum(b['n'] for b in bins)
        p=sum(b['n']*b['observed_frequency'] for b in bins if b['n'])/n
    return float(p if q.selection.lower() in ('yes','over') else 1-p)


def capture(analysis,store,now=None):
    now=now or utcnow();identifier=lock_protocol(store,now);checks=SourceChecks(store,now)
    with store.connect() as db:protocol=dict(db.execute('SELECT * FROM forward_protocols WHERE id=?',(identifier,)).fetchone())
    groups=defaultdict(list);excluded=Counter();recorded=0
    for q in analysis.quotes:
        try:
            leg=leg_evidence(q,analysis,now);e=leg.estimate;d=leg.model_details
            if not e:continue
            if q.sport!='Soccer' or d.get('results_provider')!='football-data.org':
                excluded['Current supported frozen source proof unavailable']+=1;continue
            key,side=binary_market(q)
            if key is None:excluded['Binary model contract required; no fabricated partial-settlement probability']+=1;continue
            prediction=parse_time(d['prediction_at']);kickoff=parse_time(q.commence_time)
            if not parse_time(e.training_end)<prediction<=now<kickoff:raise ValueError('Nonprospective prediction')
            if parse_time(q.received_at)>prediction or parse_time(d['source_checked_at'])>prediction:raise ValueError('Future input')
            if quote_problem(q,prediction):raise ValueError('No eligible price/contract at actual forecast time')
            problem=evidence_problem(leg,now) or checks.check(leg,model_only=True)
            if problem:excluded[problem]+=1;continue
            groups[(key,e.model_version,e.evidence_id)].append(leg)
        except (KeyError,ValueError,TypeError):excluded['Incomplete or nonprospective forecast evidence']+=1
    for key,legs in groups.items():
        canonical=lambda l:tuple(getattr(l.estimate,k) for k in ('probability','lower','upper')) if l.quote.selection.lower() in ('yes','over') else (1-l.estimate.probability,1-l.estimate.upper,1-l.estimate.lower)
        if any(any(not math.isclose(x,y,abs_tol=1e-8) for x,y in zip(canonical(l),canonical(legs[0]))) for l in legs):
            excluded['Conflicting equivalent/opposing forecast evidence']+=1;continue
        # Record the canonical side if observed, then best current observed price.
        # No probability threshold, top-pick filter or eventual result selection.
        leg=min(legs,key=lambda l:(l.quote.selection.lower() not in ('yes','over'),-l.quote.odds,l.quote.bookmaker,l.quote.id))
        q,e,d=leg.quote,leg.estimate,leg.model_details
        try:event,snapshot=source_fixture(store,q,now);base=baseline(leg)
        except (KeyError,ValueError,TypeError):excluded['Exact prospective fixture/baseline proof unavailable']+=1;continue
        pred=parse_time(d['prediction_at']);current=not quote_problem(q,now)
        fid=digest((key,identifier))
        payload={'quote':asdict(q),'estimate':asdict(e),'model_evidence':d,
            'forecast_at':pred.isoformat(),'recorded_at':now.isoformat(),'ranking_version':VERSION,
            'scope':{'sport':q.sport,'league':q.league,'market':q.market,'point':q.point,'participant':q.participant,
                'model_version':e.model_version,'evidence_id':e.evidence_id,'protocol_id':identifier},
            'source_fixture':{k:event[k] for k in ('competition_id','season','source_event_id','home_id','away_id','kickoff')},
            'source_snapshot_sha256':snapshot['sha256'],'source_checked_at':snapshot['checked_at'],
            'baseline':{'probability':base,'kind':'Frozen calibration-period constant; recorded before outcome'},
            'observed_price_at_recording':{'decimal':q.odds,'bookmaker':q.bookmaker,'source_updated_at':q.source_updated_at,'received_at':q.received_at} if current else None,
            'status':'Experimental','model_validated':e.validated,'betting_approved':False,
            'protocol_locked_before_forecast':parse_time(protocol['at'])<=pred,
            'deduplication':'First contract/model/protocol forecast across books, sides and input refreshes; no hindsight replacement'}
        with store.connect() as db:
            recorded+=db.execute('INSERT OR IGNORE INTO forward_forecasts VALUES(?,?,?,?)',(fid,now.isoformat(),identifier,json.dumps(payload,allow_nan=False))).rowcount
    return {'recorded':recorded,'excluded':dict(excluded),'protocol_id':identifier,'provider_requests':0}


def hypothetical_return(fractions,odds):
    if not isinstance(odds,(int,float)) or isinstance(odds,bool) or not math.isfinite(odds) or odds<=1:raise ValueError('Observed decimal odds required')
    if len(fractions)!=3 or any(not math.isfinite(v) or v<0 for v in fractions) or not math.isclose(sum(fractions),1):raise ValueError('Valid win/push/loss fractions required')
    return fractions[0]*(odds-1)-fractions[2]


def reconcile(store,now=None):
    from intelligence.event_data import EventObservation,reconciled
    now=now or utcnow();ensure(store);labeled=0;blocked=Counter();sources={}
    with store.connect() as db:rows=db.execute('SELECT f.*,l.payload AS label FROM forward_forecasts f LEFT JOIN forward_labels l ON f.id=l.id').fetchall()
    for row in rows:
        p=json.loads(row['payload']);q=Quote(**p['quote']);identity=p['source_fixture']
        if parse_time(q.commence_time)>=now:continue
        group=(q.league,identity['season'])
        if group not in sources:
            snapshot=latest(store,*group)
            versions=reconciled(store,identity['competition_id'],now)
            sources[group]=(snapshot,{v['fixture_id'] for v in versions if v['conflicts']})
        snapshot,conflicts=sources[group]
        if not snapshot or not snapshot.get('ok'):blocked['Verified result snapshot unavailable']+=1;continue
        try:
            found=[r for r in snapshot['events'] if all(r[k]==v for k,v in identity.items())]
            if len(found)!=1:blocked['Exact fixture identity or kickoff changed']+=1;continue
            event=EventObservation(**found[0]).validate(now)
            if event.fixture_id in conflicts:raise ValueError('Conflicting source results')
            if event.status!='completed':blocked['Game unfinished or postponed; no result inferred']+=1;continue
            if event.source!='football-data.org' or event.score_scope!='source_reported_ft':raise ValueError('Unverified result scope')
            if parse_time(event.source_updated_at)<parse_time(event.kickoff)+timedelta(minutes=90):raise ValueError('Unverified completion time')
            if not parse_time(p['forecast_at'])<=parse_time(row['at'])<parse_time(event.kickoff)<parse_time(event.source_updated_at)<=parse_time(event.observed_at)<=now:
                raise ValueError('Invalid outcome chronology')
            fractions=settlement(q.market,q.selection,q.point,q.home,q.away,event.home_score,event.away_score)
            label={'fractions':fractions,'outcome':state_label(fractions),'verified_result':asdict(event),
                'snapshot_sha256':snapshot['sha256'],'scope':'Source-score contract, not operator ticket settlement',
                'hypothetical_score_contract_return':hypothetical_return(fractions,p['observed_price_at_recording']['decimal']) if p['observed_price_at_recording'] else None,
                'accepted_ticket_return':None}
            if row['label']:
                old=json.loads(row['label'])['verified_result']
                if (old['home_score'],old['away_score'])!=(event.home_score,event.away_score):raise ValueError('Result changed after labeling')
                continue
            with store.connect() as db:labeled+=db.execute('INSERT OR IGNORE INTO forward_labels VALUES(?,?,?)',(row['id'],now.isoformat(),json.dumps(label,allow_nan=False))).rowcount
        except (KeyError,ValueError,TypeError):
            blocked['Conflicting or invalid result proof; forecast quarantined']+=1
            with store.connect() as db:db.execute('INSERT OR IGNORE INTO forward_issues VALUES(?,?,?,?)',(digest((row['id'],'result_proof')),row['id'],now.isoformat(),'result_proof'))
    return {'labeled':labeled,'blocked':dict(blocked),'provider_requests':0}


def update(analysis,store,now=None):
    try:return {'capture':capture(analysis,store,now),'reconciliation':reconcile(store,now)}
    except (sqlite3.Error,OSError,ValueError):return {'failure_code':'storage_or_integrity','message':'Forward evidence could not be recorded or verified; inspect storage/protocol integrity. No approval inferred.'}


def records(store,limit=10000):
    ensure(store)
    with store.connect() as db:
        rows=db.execute('SELECT f.*,l.payload AS label FROM forward_forecasts f LEFT JOIN forward_labels l ON f.id=l.id ORDER BY f.at,f.id LIMIT ?',(limit+1,)).fetchall()
        issues={r[0] for r in db.execute('SELECT DISTINCT forecast_id FROM forward_issues')}
    if len(rows)>limit:raise ValueError('Forward report exceeds bounded UI limit; use a private batch export, not a partial scorecard')
    return [dict(r)|{'payload':json.loads(r['payload']),'label':json.loads(r['label']) if r['label'] else None,'quarantined':r['id'] in issues} for r in rows]
