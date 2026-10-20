"""Published experimental choices, distinct from forecasts and accepted wagers.

Only the background writer prepares publications. In shared mode a Postgres
receipt establishes actual committed pregame publication. No ticket price exists.
"""
from dataclasses import asdict
from datetime import timedelta
import json,math
from intelligence.domain import utcnow,parse_time,digest,Quote
from intelligence.forward_testing import records as forecasts,hypothetical_return
from intelligence.parlay_intelligence import binary_market
from intelligence.parlay_research import quote_problem
from intelligence.score_distribution import settlement,state_label

VERSION='published-research-1'


def ensure(store):
    with store.connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS research_publications(id TEXT PRIMARY KEY,at TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS research_publication_labels(id TEXT PRIMARY KEY REFERENCES research_publications(id),at TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS research_publication_issues(id TEXT PRIMARY KEY,publication_id TEXT NOT NULL REFERENCES research_publications(id),at TEXT NOT NULL,code TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS shared_publication_receipts(id TEXT PRIMARY KEY,at TEXT NOT NULL,generation INTEGER NOT NULL);
        ''')
        for table in ('research_publications','research_publication_labels','research_publication_issues','shared_publication_receipts'):
            for action in ('UPDATE','DELETE'):
                db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'Immutable published research'); END")


def overall(top):
    single=top.get('recommended') or top.get('pick');parlay=top.get('parlay')
    if parlay is None:
        linked=[p for values in top.get('format_candidates',{}).values() for p in values]
        if linked:parlay=min(linked,key=lambda p:p.evidence_rank)
    if single and parlay:return {'winner':None,'single':single,'parlay':parlay,
        'reason':'A single has a supported marginal estimate. The parlay lacks a validated joint estimate and an observed combined ticket price, so an overall probability/value comparison is not defensible.'}
    if single:return {'winner':'single','single':single,'parlay':None,
        'reason':'Strongest eligible single under the stated research ranking; no comparable model-backed parlay is available. Experimental, not an approved bet.'}
    return {'winner':None,'single':None,'parlay':parlay,'reason':'No defensible overall research pick is available from current supported evidence.'}


def prepare(analysis,store,top=None,now=None):
    if getattr(store,'read_replica',False):return []
    from intelligence.research_top import select_top
    now=now or utcnow();ensure(store);top=top or select_top(analysis,store,now=now)
    forward=forecasts(store);by_contract={}
    for row in forward:
        p=row['payload'];q=Quote(**p['quote']);e=p['estimate']
        if not row['quarantined']:
            by_contract[(binary_market(q)[0],e['model_version'],e['evidence_id'])]=row
    choices=[]
    single=top.get('recommended') or top.get('pick')
    if single:choices.append(('single',[single],top.get('risk_rankings',{}).get('default_mode',top['method'])))
    # Include a compatible 2- and 3-leg candidate where the existing gates allow;
    # no forced pick, no assumed optimal payout or validated joint probability.
    pool=[p for items in top.get('format_candidates',{}).values() for p in items]
    if top.get('parlay'):pool.append(top['parlay'])
    for size in (2,3):
        matches=[p for p in pool if len(p.research.legs)==size]
        if matches:
            p=min(matches,key=lambda p:p.evidence_rank)
            choices.append((str(size)+'-leg parlay',p.research.legs,top['parlay_method']))
    created=[]
    for kind,legs,reason in choices:
        items=[]
        for leg in legs:
            q,e=leg.quote,leg.estimate
            row=by_contract.get((binary_market(q)[0],e.model_version,e.evidence_id))
            if not row or quote_problem(q,now) or parse_time(q.commence_time)<=now+timedelta(minutes=10):break
            items.append({'forward_id':row['id'],'quote':asdict(q),'estimate':asdict(e),
                'model_details':leg.model_details,'blockers':list(leg.blockers),
                'forecast_at':row['payload']['forecast_at'],'source_fixture':row['payload']['source_fixture']})
        if len(items)!=len(legs):continue
        keys=sorted((digest((binary_market(l.quote)[0],l.estimate.model_version,l.estimate.evidence_id)) for l in legs))
        identifier=digest((VERSION,kind,keys))
        payload={'id':identifier,'kind':kind,'prepared_at':now.isoformat(),'legs':items,
            'ranking_version':VERSION,'rationale':reason,'status':'Experimental / unapproved',
            'combined_odds':None,'combined_quote_verified':False,'joint_probability':None,'parlay_ev':None,
            'theoretical_individual_odds_product':math.prod(l.quote.odds for l in legs) if len(legs)>1 else None,
            'overall_comparison':overall(top)['reason'],'stake_policy':'One hypothetical unit for a current observed single-leg score contract only. No parlay money-return calculation without a genuine applicable combined quote and reviewed rules.',
            'commit_generation':getattr(store,'commit_generation',None)}
        with store.connect() as db:
            inserted=db.execute('INSERT OR IGNORE INTO research_publications VALUES(?,?,?)',(identifier,now.isoformat(),json.dumps(payload,allow_nan=False))).rowcount
        if inserted:created.append({'id':identifier,'prepared_at':now.isoformat(),
            'kickoff':min((l.quote.commence_time for l in legs),key=parse_time)})
    return created


def combined_outcome(fractions):
    """Logical settled score state, never an operator payout or probability."""
    if not 1<=len(fractions)<=3:raise ValueError('One to three settled legs required')
    for f in fractions:
        if len(f)!=3 or any(not isinstance(v,(float,int)) or isinstance(v,bool) or not math.isfinite(v) or v<0 for v in f) or not math.isclose(sum(f),1):raise ValueError('Invalid settlement fractions')
    if any(tuple(f)==(0,0,1) for f in fractions):return 'loss'
    if all(tuple(f)==(1,0,0) for f in fractions):return 'win'
    if all(tuple(f)==(0,1,0) for f in fractions):return 'push'
    return 'partial'


def reconcile(store,now=None):
    if getattr(store,'read_replica',False):return {'labeled':0,'mode':'Read-only shared replica'}
    now=now or utcnow();ensure(store);source={r['id']:r for r in forecasts(store)};n=0
    with store.connect() as db:rows=db.execute('SELECT * FROM research_publications').fetchall()
    for row in rows:
        p=json.loads(row['payload']);values=[];provenance=[];quarantine=False
        for leg in p['legs']:
            r=source.get(leg['forward_id']);q=Quote(**leg['quote'])
            if r and r['quarantined']:quarantine=True;break
            if not r or not r['label']:break
            label=r['label'];event=label['verified_result']
            if leg['source_fixture']!=r['payload']['source_fixture']:quarantine=True;break
            f=settlement(q.market,q.selection,q.point,q.home,q.away,event['home_score'],event['away_score'])
            values.append(f);provenance.append({'forward_id':r['id'],'verified_result':event,'snapshot_sha256':label['snapshot_sha256']})
        if quarantine:
            with store.connect() as db:db.execute('INSERT OR IGNORE INTO research_publication_issues VALUES(?,?,?,?)',
                (digest((row['id'],'result_conflict')),row['id'],now.isoformat(),'result_conflict'))
            continue
        if len(values)!=len(p['legs']):continue
        label={'outcome':state_label(tuple(values[0])) if len(values)==1 else combined_outcome(values),
            'leg_fractions':values,'provenance':provenance,
            'paper_net_units':hypothetical_return(values[0],p['legs'][0]['quote']['odds']) if len(values)==1 else None,
            'parlay_return':None,'scope':'Verified source-score target; not operator ticket settlement',
            'voids':'No void inferred from a final score; operator adjudication is unavailable'}
        with store.connect() as db:
            old=db.execute('SELECT payload FROM research_publication_labels WHERE id=?',(row['id'],)).fetchone()
            if old and json.loads(old['payload'])['leg_fractions']!=[list(f) for f in values]:
                db.execute('INSERT OR IGNORE INTO research_publication_issues VALUES(?,?,?,?)',(digest((row['id'],'changed_label')),row['id'],now.isoformat(),'changed_label'))
            elif not old:n+=db.execute('INSERT OR IGNORE INTO research_publication_labels VALUES(?,?,?)',(row['id'],now.isoformat(),json.dumps(label,allow_nan=False))).rowcount
    return {'labeled':n,'provider_requests':0}


def records(store):
    ensure(store)
    with store.connect() as db:
        rows=db.execute('SELECT p.*,l.payload AS label,r.at AS committed_at FROM research_publications p LEFT JOIN research_publication_labels l ON l.id=p.id LEFT JOIN shared_publication_receipts r ON r.id=p.id ORDER BY p.at,p.id LIMIT 10001').fetchall()
        issues={r[0] for r in db.execute('SELECT DISTINCT publication_id FROM research_publication_issues')}
    if len(rows)>10000:raise ValueError('Published research exceeds bounded report; use a complete private batch export')
    return [dict(r)|{'payload':json.loads(r['payload']),'label':json.loads(r['label']) if r['label'] else None,'quarantined':r['id'] in issues} for r in rows]


def performance(store):
    rows=records(store);committed=[r for r in rows if r['committed_at'] and parse_time(r['committed_at'])<min(parse_time(l['quote']['commence_time']) for l in r['payload']['legs'])]
    eligible=[r for r in committed if not r['quarantined']];settled=[r for r in eligible if r['label']]
    money=[r for r in settled if r['payload']['kind']=='single' and r['label']['paper_net_units'] is not None]
    from intelligence.evaluation import wilson
    from collections import defaultdict
    import numpy as np
    wins=sum(r['label']['outcome']=='win' for r in settled);losses=sum(r['label']['outcome']=='loss' for r in settled)
    equity=peak=drawdown=0.
    for r in sorted(money,key=lambda r:(max(x['verified_result']['source_updated_at'] for x in r['label']['provenance']),r['id'])):
        equity+=r['label']['paper_net_units'];peak=max(peak,equity);drawdown=max(drawdown,peak-equity)
    blocks=defaultdict(list)
    for r in money:blocks[r['committed_at'][:10]].append(r['label']['paper_net_units'])
    roi_interval=None
    if len(blocks)>=30:
        sums=np.array([sum(v) for _,v in sorted(blocks.items())]);counts=np.array([len(v) for _,v in sorted(blocks.items())])
        draws=np.random.default_rng(82913).integers(0,len(blocks),(1000,len(blocks)))
        roi_interval=np.quantile(sums[draws].sum(axis=1)/counts[draws].sum(axis=1),[.025,.975]).tolist()
    breakdown={}
    for r in settled:
        p=r['payload'];group=(p['kind'],' + '.join(sorted({l['quote']['league'] for l in p['legs']})),
            ' + '.join(sorted({l['quote']['market'] for l in p['legs']})),
            ' + '.join(sorted({l['estimate']['model_version'] for l in p['legs']})))
        key=' | '.join(group);b=breakdown.setdefault(key,{'settled':0,'wins':0,'losses':0,'paper_priced_n':0,'paper_net_units':None})
        b['settled']+=1;b['wins']+=r['label']['outcome']=='win';b['losses']+=r['label']['outcome']=='loss'
        value=r['label']['paper_net_units']
        if value is not None:b['paper_priced_n']+=1;b['paper_net_units']=(b['paper_net_units'] or 0)+value
    return {'prepared':len(rows),'published_committed_pregame':len(committed),'quarantined':sum(r['quarantined'] for r in committed),
        'settled':len(settled),'pending':sum(not r['label'] for r in eligible),'wins':wins,'losses':losses,
        'pushes':sum(r['label']['outcome']=='push' for r in settled),'partial':sum(r['label']['outcome'] in ('partial','half-win','half-loss') for r in settled),
        'win_rate':wins/(wins+losses) if wins+losses else None,
        'descriptive_IID_win_rate_interval':wilson(wins,wins+losses) if wins+losses else None,
        'paper_priced_single_n':len(money),'paper_net_units':equity if money else None,'paper_roi':equity/len(money) if money else None,
        'paper_max_drawdown_units':drawdown if money else None,'breakdown':breakdown,'actual_betting_profit':None,
        'paper_roi_uncertainty':{'interval':roi_interval,'UTC_day_blocks':len(blocks),
            'method':'Descriptive publication-day cluster bootstrap; suppressed below 30 days. Between-day dependence, selection, operator acceptance and execution remain unresolved; not proof of profitability.'},
        'note':'Fixed one-unit hypothetical single score contracts at observed publication prices; final-source settlement, not accepted bets. Parlays have no monetary returns. Win-rate interval assumes IID and is descriptive; shared legs/games are dependent. No profitability or independent edge is established.'}
