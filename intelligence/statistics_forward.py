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
        bounded=r.get('kind')=='bounded_cross_game'
        if bounded:
            from intelligence.fixture_research import forward_combinations
            from intelligence.prediction_accuracy import same_value
            candidates=forward_combinations(r.get('legs',[]),now)
            if not any(same_value(c,r) for c in candidates):
                raise ValueError('Bounded research must preserve exact verified legs and logical bounds')
        if (not r.get('research_eligible') or (not bounded and (not isinstance(p,(int,float)) or isinstance(p,bool) or not math.isfinite(p) or not 0<p<1))
            or r.get('approved') or r.get('validated') or r.get('joint_validated') or r.get('observed_odds') is not None
            or r.get('combined_odds') is not None or r.get('ev') is not None
            or not r.get('evidence_id') or not now+timedelta(minutes=15)<parse_time(r['kickoff'])
            or not 0<=(now-parse_time(r['forecast_at'])).total_seconds()<60
            or not 0<=(now-parse_time(r['source_observed_at'])).total_seconds()<21600):
            raise ValueError('Not eligible as an actually recorded pregame statistical forecast')
        identity={k:v for k,v in r.items() if k!='forecast_at'}
        if bounded:identity['legs']=[{k:v for k,v in leg.items() if k!='forecast_at'} for leg in r['legs']]
        key=digest(identity)
        prepared.append((key,now.isoformat(),r['kickoff'],json.dumps(r,allow_nan=False)))
    with store.connect() as db:
        for row in prepared:
            if db.execute('INSERT OR IGNORE INTO statistics_forecasts VALUES(?,?,?,?)',row).rowcount:created.append(row[0])
    return created


def reconcile(store,now=None):
    """Exact source fixture/kickoff and regulation score; no bookmaker settlement."""
    from intelligence.openliga import current
    from intelligence.score_distribution import settlement
    now=now or utcnow();ensure(store);sources=[current(store,'Bundesliga',now)]
    from intelligence.free_results import current as public_current
    from intelligence.nba_current import current as nba_current
    sources += [public_current(store,league,now) for league in ('Premier League','Ligue 1')]
    sources.append(nba_current(store,now))
    finals={e.fixture_id:(e,meta) for events,meta in sources if meta['ok'] for e in events if e.status=='completed'};added=0
    with store.connect() as db:
        rows=db.execute('SELECT f.* FROM statistics_forecasts f LEFT JOIN statistics_outcomes o ON f.id=o.id WHERE o.id IS NULL').fetchall()
        for row in rows:
            r=json.loads(row['payload'])
            legs=r.get('legs') or [{k:r[k] for k in ('market','selection','point')}]
            states=[];proof=[]
            for leg in legs:
                pair=finals.get(leg.get('fixture_id',r['fixture_id']))
                if not pair:break
                event,meta=pair;start=leg.get('kickoff',r['kickoff'])
                if (not event.kickoff or parse_time(event.kickoff)!=parse_time(start)
                    or not parse_time(row['at'])<parse_time(event.kickoff)<parse_time(event.observed_at)<=now):break
                state=settlement(leg['market'],leg['selection'],leg.get('point'),event.home_name,event.away_name,event.home_score,event.away_score)
                # Pushes, postponed/cancelled games, altered tipoffs and unknown
                # fixtures remain pending, never silently scored as a loss.
                if state not in ((1.,0.,0.),(0.,0.,1.)):break
                states.append(state)
                proof.append({'fixture_id':event.fixture_id,'kickoff':event.kickoff,
                    'home_score':event.home_score,'away_score':event.away_score,
                    'source':meta.get('provider',event.source),'source_observed_at':event.observed_at,
                    'source_sha256':meta['sha256']})
            if len(states)!=len(legs):continue
            value={'all_selections_won':all(s==(1.,0.,0.) for s in states),
                'source':' + '.join(sorted({p['source'] for p in proof})),
                'source_observed_at':max((p['source_observed_at'] for p in proof),key=parse_time),
                'source_sha256':digest(proof),'leg_results':proof,
                'scope':'Unpriced paper forecast outcome; not a settled sportsbook ticket or financial return'}
            if len({p['fixture_id'] for p in proof})==1:
                value.update(home_score=proof[0]['home_score'],away_score=proof[0]['away_score'])
            added+=db.execute('INSERT OR IGNORE INTO statistics_outcomes VALUES(?,?,?)',(row['id'],now.isoformat(),json.dumps(value))).rowcount
    return added


def monitoring(store):
    """First prospectively recorded forecast per game/task, separate from bets.

    Refreshing a source must not increase the number of independent decisions.
    Descriptive calibration only; no promotion, retraining or money returns.
    """
    from collections import defaultdict
    from intelligence.epl_validation import reliability
    ensure(store);first={};groups=defaultdict(list)
    with store.connect() as db:
        records=db.execute('SELECT f.*,o.payload outcome FROM statistics_forecasts f LEFT JOIN statistics_outcomes o ON f.id=o.id ORDER BY f.at,f.id').fetchall()
    for record in records:
        r=json.loads(record['payload']);legs=r.get('legs') or [{k:r[k] for k in ('market','selection','point')}]
        task=digest([{k:l.get(k) for k in ('market','selection','point')} for l in legs])
        key=(r['fixture_id'],r['model_version'],task)
        first.setdefault(key,(r,json.loads(record['outcome']) if record['outcome'] else None))
    for r,outcome in first.values():
        group=(r.get('sport','Soccer'),r['league'],r['model_version'],'single' if not r.get('legs') else str(len(r['legs']))+('-leg cross-game bounds' if r.get('kind')=='bounded_cross_game' else '-leg SGP'))
        groups[group].append((r,outcome))
    output=[]
    for scope,values in sorted(groups.items()):
        labeled=[(r,o) for r,o in values if o is not None]
        points=[(r,o) for r,o in labeled if r.get('kind')!='bounded_cross_game']
        p=[r.get('joint_probability',r.get('probability')) for r,o in points]
        y=[int(o['all_selections_won']) for r,o in points]
        output.append({'sport':scope[0],'league':scope[1],'model_version':scope[2],'format':scope[3],
            'unique_pregame_decisions':len(values),'labeled':len(labeled),'pending':len(values)-len(labeled),'point_probability_labels':len(y),
            'brier':sum((a-b)**2 for a,b in zip(p,y))/len(y) if y else None,
            'log_loss':-sum(b*math.log(max(1e-8,a))+(1-b)*math.log(max(1e-8,1-a)) for a,b in zip(p,y))/len(y) if y else None,
            'reliability':reliability(p,y) if y else [],'approved':False,
            'state':'Descriptive forward monitoring; independent validation and reviewed approval still required',
            'paper_roi':None})
    return {'recorded_snapshots':len(records),'unique_pregame_decisions':len(first),'groups':output,
        'automatic_promotion':False,'note':'First genuinely recorded pregame forecast per fixture/model/selection. SGPs and singles sharing games are dependent; calibration frequency ranges are descriptive. No odds, stakes or financial results are inferred.'}
