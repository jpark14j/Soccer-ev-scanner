"""Read-only accuracy of immutable, genuinely pregame-recorded predictions.

No backtests, financial returns, automatic approval or result inference.
Repeated source refreshes count the earliest model/selection decision once.
"""
import json,math,re
from intelligence.domain import digest,parse_time,utcnow


def contracts(r):
    legs=r.get('legs') or [r]
    return sorted([{'market':l['market'],'selection':l['selection'],'point':l.get('point'),
        'participant':l.get('participant',''),'fixture_id':l.get('fixture_id',r['fixture_id']),**({'kickoff':l['kickoff']} if l.get('kickoff') else {})} for l in legs],key=digest)


def decision(r):
    return digest((r['fixture_id'],parse_time(r['kickoff']).isoformat(),r['model_version'],contracts(r)))


def rows(store):
    result=[]
    with store.connect() as db:
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if {'statistics_forecasts','statistics_outcomes'}<=tables:
            data=db.execute('SELECT f.*,o.at outcome_at,o.payload outcome FROM statistics_forecasts f LEFT JOIN statistics_outcomes o ON o.id=f.id ORDER BY f.at,f.id').fetchall()
            result=[dict(r)|{'payload':json.loads(r['payload']),'outcome':json.loads(r['outcome']) if r['outcome'] else None} for r in data]
        if {'research_publications','research_publication_labels','shared_publication_receipts','research_publication_issues'}<=tables:
            # A preparation row alone is not a committed pregame publication.
            data=db.execute('SELECT p.id,r.at,l.at outcome_at,p.payload,l.payload outcome FROM research_publications p JOIN shared_publication_receipts r ON r.id=p.id LEFT JOIN research_publication_labels l ON l.id=p.id WHERE NOT EXISTS (SELECT 1 FROM research_publication_issues i WHERE i.publication_id=p.id)').fetchall()
            for row in data:
                try:
                    p=json.loads(row['payload']);legs=[];versions=[];starts=[]
                    for leg in p['legs']:
                        q=leg['quote'];f=leg['source_fixture']
                        fid=digest(tuple(f[k] for k in ('competition_id','season','home_id','away_id')))
                        legs.append({k:q.get(k) for k in ('market','selection','point','participant')}|{'fixture_id':fid})
                        versions.append(leg['estimate']['model_version']);starts.append(q['commence_time'])
                    if not 1<=len(legs)<=3:continue
                    ids=sorted({l['fixture_id'] for l in legs})
                    r={'fixture_id':ids[0] if len(ids)==1 else digest(ids),'model_version':' + '.join(sorted(set(versions))),
                        'legs':legs,'kickoff':min(starts,key=parse_time),'research_eligible':True,'validated':False}
                    o=None
                    if row['outcome']:
                        label=json.loads(row['outcome']);fractions=label['leg_fractions'];proof=label['provenance']
                        if len(fractions)!=len(legs) or len(proof)!=len(legs):continue
                        if any(tuple(f) not in ((1,0,0),(0,0,1)) for f in fractions):continue
                        if any(not x.get('snapshot_sha256') for x in proof):continue
                        receipts=[x['verified_result']['observed_at'] for x in proof]
                        if any(parse_time(s)>=parse_time(t) for s,t in zip(starts,receipts)):continue
                        win=all(tuple(f)==(1,0,0) for f in fractions)
                        if label['outcome']!=('win' if win else 'loss'):continue
                        o={'all_selections_won':win,'source':'Verified committed research labels',
                            'source_sha256':digest(proof),'source_observed_at':max(receipts,key=parse_time)}
                    result.append({'id':row['id'],'at':row['at'],'outcome_at':row['outcome_at'],'payload':r,'outcome':o})
                except (ValueError,KeyError,TypeError):continue
    return sorted(result,key=lambda r:(parse_time(r['at']),r['id']))


def same_value(a,b):
    if isinstance(a,float) and isinstance(b,(int,float)) and not isinstance(b,bool):
        return math.isfinite(a) and math.isfinite(b) and math.isclose(a,b,abs_tol=1e-12,rel_tol=0.)
    if isinstance(a,dict) and isinstance(b,dict):return a.keys()==b.keys() and all(same_value(a[k],b[k]) for k in a)
    if isinstance(a,list) and isinstance(b,list):return len(a)==len(b) and all(same_value(x,y) for x,y in zip(a,b))
    return a==b


def saved_for_display(store,current,now=None):
    """Show original stored values only, while current input gates still pass.

    A freshly computed timestamp is not a durable publication. The numerical
    forecast, source receipt, model evidence and exact contract must match an
    actual pregame record. A new receipt/probability awaits the worker checkpoint.
    """
    now=now or utcnow();indexed={}
    for row in rows(store):
        r=row['payload']
        try:
            if not parse_time(row['at'])<parse_time(r['kickoff']) or parse_time(row['at'])>now:continue
            indexed.setdefault(decision(r),[]).append(row)
        except (ValueError,KeyError,TypeError):continue
    found=[]
    fields=('kickoff','source_observed_at','evidence_id','probability','joint_probability','lower','upper','legs','kind','logical_probability_bounds','marginal_envelope_bounds','fair_odds_range')
    for computed in current:
        if not computed.get('research_eligible') or not now<parse_time(computed['kickoff']):continue
        for row in reversed(indexed.get(decision(computed),[])):
            saved=row['payload']
            def value(payload,key):
                if key=='legs' and payload.get('kind')=='bounded_cross_game':
                    return [{k:v for k,v in leg.items() if k not in ('forecast_at','record_id','recorded_at')} for leg in payload[key]]
                return payload.get(key)
            if all(same_value(value(saved,k),value(computed,k)) for k in fields):
                found.append(saved|{'recorded_at':row['at'],'record_id':row['id']});break
    return found


def summary(store,now=None):
    now=now or utcnow();first={};ignored=0
    for row in rows(store):
        r=row['payload']
        try:
            if (r.get('origin')=='backtest' or not r.get('research_eligible')
                or not parse_time(row['at'])<parse_time(r['kickoff'])
                or parse_time(row['at'])>now or len(contracts(r)) not in (1,2,3)):
                ignored+=1;continue
            first.setdefault(decision(r),row)
        except (ValueError,KeyError,TypeError):ignored+=1
    report={n:{'correct':0,'settled':0,'pending':0,'excluded':0,
        'Experimental':{'correct':0,'settled':0},'Validated':{'correct':0,'settled':0}} for n in (1,2,3)}
    for row in first.values():
        r=row['payload'];item=report[len(contracts(r))];o=row['outcome']
        if not o:item['pending']+=1;continue
        try:
            verified=(type(o.get('all_selections_won')) is bool and o.get('source') and re.fullmatch('[a-f0-9]{64}',str(o.get('source_sha256','')))
                and o.get('settlement_status') not in ('void','push','partial','unresolved')
                and parse_time(r['kickoff'])<parse_time(o['source_observed_at'])<=parse_time(row['outcome_at'])<=now)
        except (ValueError,KeyError,TypeError):verified=False
        if not verified:item['excluded']+=1;continue
        classification='Validated' if r.get('validated') is True and (not r.get('legs') or r.get('joint_validated') is True) else 'Experimental'
        item['settled']+=1;item['correct']+=int(o['all_selections_won'])
        item[classification]['settled']+=1;item[classification]['correct']+=int(o['all_selections_won'])
    for item in report.values():
        for bucket in (item,item['Experimental'],item['Validated']):
            bucket['accuracy']=100*bucket['correct']/bucket['settled'] if bucket['settled'] else None
    return {'formats':report,'unique_predictions':len(first),'ignored':ignored,
        'scope':'First genuine pregame statistics forecast per fixture, model and exact selection; backtests excluded. Pending, void and unverified outcomes are excluded from accuracy.'}


def home_choices(store,leagues,now=None):
    from intelligence.fixture_research import collect,forward_combinations
    from intelligence.current_score_research import candidates
    now=now or utcnow()
    current=collect(store,now,168,leagues)['forecasts']
    if 'Bundesliga' in leagues:current+=candidates(store,now)
    bounded=saved_for_display(store,forward_combinations([r for r in current if not r.get('legs')],now),now)
    current=saved_for_display(store,current,now)
    result={}
    for n in (1,2,3):
        eligible=[r for r in current if len(contracts(r))==n]
        result[n]=min(eligible,key=lambda r:(r['upper']-r['lower'],-r['calibration_bin_n'],
            -r.get('joint_probability',r.get('probability',0)),r['kickoff'])) if eligible else None
        if result[n] is None and n>1:
            alternatives=[r for r in bounded if len(r['legs'])==n]
            result[n]=min(alternatives,key=lambda r:(sum(l['upper']-l['lower'] for l in r['legs']),
                -min(l['probability'] for l in r['legs']),r['kickoff'])) if alternatives else None
    return result
