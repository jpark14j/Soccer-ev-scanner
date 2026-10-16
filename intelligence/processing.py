"""Private shadow forecasts and guarded, append-only result processing.

Research forecasts never become published betting performance. Provider scores
alone do not establish operator settlement scope, player results or void rules.
"""
from dataclasses import asdict
from collections import Counter
from pathlib import Path
import json
import sqlite3
from intelligence.domain import digest,parse_time,utcnow
from intelligence.quota import quota_details
from intelligence.results import collect,ensure_table


def ensure_processing(store):
    ensure_table(store)
    with store.connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS shadow_forecasts(id TEXT PRIMARY KEY,at TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS shadow_outcomes(id TEXT PRIMARY KEY REFERENCES shadow_forecasts(id),at TEXT NOT NULL,outcome TEXT NOT NULL,source TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS shadow_no_update BEFORE UPDATE ON shadow_forecasts BEGIN SELECT RAISE(ABORT,'Immutable research forecast'); END;
        CREATE TRIGGER IF NOT EXISTS shadow_no_delete BEFORE DELETE ON shadow_forecasts BEGIN SELECT RAISE(ABORT,'Immutable research forecast'); END;
        CREATE TRIGGER IF NOT EXISTS shadow_result_no_update BEFORE UPDATE ON shadow_outcomes BEGIN SELECT RAISE(ABORT,'Immutable research result'); END;
        CREATE TRIGGER IF NOT EXISTS shadow_result_no_delete BEFORE DELETE ON shadow_outcomes BEGIN SELECT RAISE(ABORT,'Immutable research result'); END;
        ''')


def record_shadow_forecasts(analysis,store,now=None):
    now=now or utcnow();ensure_processing(store);n=0
    from intelligence.market_validation import code_hash
    from intelligence.evaluation import model_code_hash
    from intelligence.advanced_models import VERSIONS
    from intelligence.epl_validation import policy as epl_policy,code_hash as epl_hash
    advanced_hash,team_hash=code_hash(),model_code_hash()
    focused_version,focused_hash=epl_policy()['model_version'],epl_hash()
    research={row['quote_id']:row for row in analysis.research}
    for q in analysis.quotes:
        estimate=analysis.advanced_estimates.get(q.id) or analysis.estimates.get(q.id)
        if estimate is None or q.status(now)!='current' or q.jurisdiction!='CA-ON':
            continue
        if parse_time(estimate.training_end)>=now:
            continue
        detail=analysis.advanced_details.get(q.id) or research.get(q.id,{})
        focused=estimate.model_version==focused_version
        expanded=estimate.model_version.startswith('venue-goals-1-')
        code=detail.get('model_code_sha256') if expanded else focused_hash if focused else advanced_hash if estimate.model_version in VERSIONS.values() else team_hash
        data=detail.get('data_sha256','unavailable')
        identifier=digest((q.id,estimate.model_version,q.commence_time,code,data))
        payload={'quote':asdict(q),'estimate':asdict(estimate),'origin':'shadow research',
                 'model_code_sha256':code,'history_data_sha256':data,
                 'target_scope':'source_reported_ft' if focused else 'expanded_source_ft' if expanded else 'full_event_final_including_extras' if q.sport in ('NBA','MLB') else 'regulation_90_unverified',
                 'model_evidence':detail if focused or expanded else {},
                 'scope':'Unverified model score target; not accepted sportsbook settlement',
                 'publication_status':'Not a betting recommendation; never included in forward betting ROI'}
        with store.connect() as db:
            n+=db.execute('INSERT OR IGNORE INTO shadow_forecasts VALUES(?,?,?)',
                (identifier,now.isoformat(),json.dumps(payload,allow_nan=False))).rowcount
    return n


def load_rules(path='config/settlement_rules.json',now=None):
    now=now or utcnow()
    try:
        rules=json.loads(Path(path).read_text()).get('rules',[])
        return [r for r in rules if isinstance(r,dict) and r.get('verified') is True and r.get('source','').startswith('https://')
            and r.get('provider_scope_source','').startswith('https://') and
            parse_time(r['reviewed_at'])<=now<=parse_time(r['expires_at'])]
    except (OSError,ValueError,KeyError,TypeError):
        return []


def outcome_for(quote,result,rule):
    if not rule:
        return None,'Operator settlement and provider score scope are unverified'
    if any(result.get(k)!=quote.get(v) for k,v in [('provider','provider'),('event_id','event_id'),('league','league'),('home','home'),('away','away')]) or parse_time(result['commence_time'])!=parse_time(quote['commence_time']):
        return None,'Result does not exactly match the published event'
    if rule.get('score_scope') not in ('full_event_final_including_extras','regulation_90'):
        return None,'Unsupported settlement scope'
    if quote['sport']=='Soccer' and result.get('score_scope')!=rule['score_scope']:
        return None,'Soccer regulation/extra-time result scope is unverified'
    if quote['sport'] in ('NBA','MLB') and rule['score_scope']!='full_event_final_including_extras':
        return None,'Final score does not support this operator period'
    h,a=result['home_score'],result['away_score']; market=quote['market']; selection=quote['selection']
    if market=='h2h':
        if selection not in (quote['home'],quote['away'],*(['Draw'] if quote['sport']=='Soccer' else [])):
            return None,'Unknown match-winner selection'
        if h==a and quote['sport']!='Soccer':
            return None,'Tied final score needs operator review'
        won=(h==a) if selection=='Draw' else h>a if selection==quote['home'] else a>h
        return ('win' if won else 'loss'),''
    if market=='btts' and quote['sport']=='Soccer':
        return ('win' if ((h>0 and a>0)==(selection.lower()=='yes')) else 'loss'),''
    if market in ('spreads','totals'):
        point=quote['point']
        if point is None or point%0.5:
            return None,'Quarter-line partial settlement is not supported'
        value=(h+point-a if selection==quote['home'] else a+point-h) if market=='spreads' else (h+a-point)*(1 if selection.lower()=='over' else -1)
        return ('push' if value==0 else 'win' if value>0 else 'loss'),''
    return None,'Player/period/void outcomes require a dedicated verified results adapter'


def process_cycle(store,provider,leagues,cap,*,collect_results=False,now=None,rules_path='config/settlement_rules.json'):
    now=now or utcnow();ensure_processing(store)
    records=[r for r in store.records() if not r['outcome'] and parse_time(r['payload']['quote']['commence_time'])<now]
    with store.connect() as db:
        shadows=[dict(r) for r in db.execute('SELECT f.* FROM shadow_forecasts f LEFT JOIN shadow_outcomes o ON f.id=o.id WHERE o.id IS NULL')]
    pending=[r['payload']['quote']['league'] for r in records]
    pending.extend(json.loads(r['payload'])['quote']['league'] for r in shadows
        if json.loads(r['payload']).get('target_scope') not in ('source_reported_ft','expanded_source_ft')
        and parse_time(json.loads(r['payload'])['quote']['commence_time'])<now)
    if collect_results:
        pending.extend(l for l in leagues if l in ('NBA','MLB'))
    summary={'collection':{},'settled':0,'pending_completed_publications':len(records),'blocked':{},'shadow_forecasts_recorded':0}
    summary['pending_public_epl_forecasts']=sum(json.loads(r['payload']).get('target_scope')=='source_reported_ft' for r in shadows)
    summary['pending_expanded_leagues']=sorted({json.loads(r['payload'])['quote']['league'] for r in shadows if json.loads(r['payload']).get('target_scope')=='expanded_source_ft'})
    for league in sorted(set(pending)&set(leagues)):
        if store.cached('daily-completed-v1-'+league,86400,now) is None and quota_details(store,cap,now)['remaining']<2:
            summary['collection'][league]='not requested: existing local credit cap'
            continue
        try:
            summary['collection'][league]=collect(provider,store,[league])[league]
        except Exception:
            summary['collection'][league]='provider results unavailable; no outcome inferred'
    with store.connect() as db:
        rows=[json.loads(r['payload']) for r in db.execute('SELECT payload FROM observed_results')]
    results={};conflicts=set()
    for row in rows:
        k=(row['provider'],row['league'],row['event_id'])
        if k in results and (row['home_score'],row['away_score'])!=(results[k]['home_score'],results[k]['away_score']):
            conflicts.add(k)
        results[k]=row
    rules=load_rules(rules_path,now);blocked=Counter()
    for record in records:
        q=record['payload']['quote'];k=(q['provider'],q['league'],q['event_id']); row=results.get(k)
        if not row or k in conflicts:
            blocked['Missing or conflicting final-score observations']+=1;continue
        rule=next((r for r in rules if (r.get('bookmaker'),r.get('sport'),r.get('market'))==(q['bookmaker'],q['sport'],q['market'])),None)
        outcome,reason=outcome_for(q,row,rule)
        if not outcome:
            blocked[reason]+=1;continue
        source='the-odds-api completed result '+row['event_id']+' observed '+row['observed_at']+'; rules '+rule['source']
        try:
            store.settle(record['id'],outcome,f"Final {row['home_score']}–{row['away_score']}",source,now=now)
            summary['settled']+=1
        except sqlite3.IntegrityError:
            pass  # Another worker settled the immutable record first.
    summary['blocked']=dict(blocked)
    summary['shadow_labels_recorded']=0
    for record in shadows:
        payload=json.loads(record['payload']);q=payload['quote']
        k=(q['provider'],q['league'],q['event_id']);row=results.get(k)
        if not row or k in conflicts or payload.get('target_scope')!='full_event_final_including_extras':
            continue
        if not parse_time(record['at'])<parse_time(q['commence_time'])<now:
            continue
        # NBA/MLB completed scores label the explicit full-final forecast target.
        # This does NOT establish operator rules, accepted odds, profit or voids.
        outcome,_=outcome_for(q,row,{'score_scope':payload['target_scope']})
        if outcome:
            with store.connect() as db:
                summary['shadow_labels_recorded']+=db.execute('INSERT OR IGNORE INTO shadow_outcomes VALUES(?,?,?,?)',
                    (record['id'],now.isoformat(),{'win':'hit','loss':'miss','push':'push'}[outcome],
                     'Provider-declared completed final '+row['event_id']+' observed '+row['observed_at']+'; forecast target only, not ticket settlement')).rowcount
    summary['shadow_note']='Private pregame forecasts are stored separately; result labels require verified model-target scope and do not imply betting ROI'
    return summary


def shadow_statistics(store):
    import math
    ensure_processing(store)
    with store.connect() as db:
        rows=db.execute('SELECT f.payload,o.outcome FROM shadow_forecasts f LEFT JOIN shadow_outcomes o ON f.id=o.id').fetchall()
    settled=[r for r in rows if r['outcome'] in ('hit','miss')]
    brier=logloss=None
    if settled:
        pairs=[(json.loads(r['payload'])['estimate']['probability'],int(r['outcome']=='hit')) for r in settled]
        brier=sum((p-y)**2 for p,y in pairs)/len(pairs)
        logloss=-sum(math.log(max(1e-12,min(1-1e-12,p if y else 1-p))) for p,y in pairs)/len(pairs)
    groups={}
    for row in rows:
        payload=json.loads(row['payload']);q=payload['quote'];e=payload['estimate']
        key=' / '.join((q['sport'],q['market'],e['model_version']))
        groups.setdefault(key,[]).append((e['probability'],row['outcome']))
    grouped={}
    for key,group in groups.items():
        pairs=[(p,int(outcome=='hit')) for p,outcome in group if outcome in ('hit','miss')]
        n=len(pairs);hits=sum(y for _,y in pairs)
        bins=[]
        for index in range(10):
            bucket=[(p,y) for p,y in pairs if min(9,int(p*10))==index]
            if bucket:
                bins.append({'range':[index/10,(index+1)/10],'n':len(bucket),
                    'mean_probability':sum(p for p,_ in bucket)/len(bucket),
                    'observed_frequency':sum(y for _,y in bucket)/len(bucket)})
        grouped[key]={'recorded':len(group),'labeled':n,'hits':hits,'misses':n-hits,
            'selection_hit_rate':hits/n if n else None,
            'binary_brier':sum((p-y)**2 for p,y in pairs)/n if n else None,
            'log_loss':-sum(math.log(max(1e-12,min(1-1e-12,p if y else 1-p))) for p,y in pairs)/n if n else None,
            'calibration_bins':bins,'betting_roi':None,
            'note':'Dependent source-target labels, not sportsbook settlement or independently verified forecasting skill'}
    return {'private_forecasts':len(rows),'scored_forecast_labels':len(settled),
        'binary_brier':brier,'log_loss':logloss,'betting_roi':None,
        'by_sport_market_model':grouped,
        'note':'Unvalidated first pregame forecasts; shared games/lines/books are dependent. These are model-target labels, not operator wins/losses or a tradable advantage.'}


def label_public_epl(store,artifact,now=None):
    """Append source-target labels only, never ticket settlement or hypothetical ROI."""
    from intelligence.epl_source import team
    now=now or utcnow();ensure_processing(store)
    if not artifact or artifact.get('problem'):
        return 0
    # Current-season rows only. Archived forecasts are never reconstructed/backdated.
    results={(r['home'],r['away'],r['date']):r for r in artifact['current_rows']}
    n=0
    with store.connect() as db:
        records=db.execute('SELECT f.* FROM shadow_forecasts f LEFT JOIN shadow_outcomes o ON f.id=o.id WHERE o.id IS NULL').fetchall()
        for record in records:
            payload=json.loads(record['payload']);q=payload['quote']
            if payload.get('target_scope')!='source_reported_ft':
                continue
            start=parse_time(q['commence_time'])
            if not parse_time(record['at'])<start<now:
                continue
            row=results.get((team(q['home']),team(q['away']),start.date().isoformat()))
            if not row or row['date']>=now.date().isoformat():
                continue
            positive=row['hg']>0 and row['ag']>0 if q['market']=='btts' else row['hg']+row['ag']>2.5
            hit=positive==(q['selection'].lower() in ('yes','over'))
            n+=db.execute('INSERT OR IGNORE INTO shadow_outcomes VALUES(?,?,?,?)',
                (record['id'],now.isoformat(),'hit' if hit else 'miss',
                 'openfootball public source-reported full-time target; checked '+artifact['source_check']+
                 '; data '+artifact['data_sha256']+'; not operator settlement')).rowcount
    return n
