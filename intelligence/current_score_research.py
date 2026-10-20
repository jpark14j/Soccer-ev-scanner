"""Coherent, unpriced Bundesliga SGP research with recent held-out diagnostics.

Same-game probabilities are sums of score cells, not products of calibrated
binary probabilities. Existing publication/approval rules are unchanged.
"""
from pathlib import Path
import json
import numpy as np
from intelligence.domain import digest, utcnow, parse_time
from intelligence.data_adapters import ROOT
from intelligence.epl_validation import metrics, reliability
from intelligence.score_distribution import score_distribution
from intelligence.venue_goals import fit, extend, predict

PATH=ROOT/'research_assets/current_score_research.json'
TASKS={
    'home_over_2.5': [('h2h','Home',None),('totals','Over',2.5)],
    'away_over_2.5': [('h2h','Away',None),('totals','Over',2.5)],
    'home_btts_under_4.5': [('h2h','Home',None),('btts','Yes',None),('totals','Under',4.5)],
    'away_btts_under_4.5': [('h2h','Away',None),('btts','Yes',None),('totals','Under',4.5)]}


def masks():
    h,a=np.indices((41,41))
    leg={('h2h','Home',None):h>a,('h2h','Away',None):a>h,
        ('btts','Yes',None):(h>0)&(a>0),('totals','Over',2.5):h+a>2.5,('totals','Under',4.5):h+a<4.5}
    return leg,{name:np.logical_and.reduce([leg[tuple(c)] for c in contracts]) for name,contracts in TASKS.items()}


def code_hash():
    return digest({n:Path(__file__).with_name(n).read_text() for n in ('current_score_research.py','venue_goals.py','score_distribution.py')})


def build(source_directory, completion_store, output=PATH):
    from intelligence.data_adapters import pinned_history
    from intelligence.expanded_models import load, rows_from_events
    from intelligence.openliga import history_completion
    from intelligence.event_data import EventObservation
    artifact=load('Bundesliga');completion=history_completion(completion_store)
    if not artifact or not completion or completion['base_artifact_sha256']!=artifact['artifact_sha256']:
        raise ValueError('Verified historical completion required')
    events,sources=pinned_history(source_directory,'Bundesliga')
    events=[e for e in events if e.season<='2024-25']+[EventObservation(**e) for e in completion['source_events']]
    rows=rows_from_events(events);policy=artifact['policy']
    state=fit(rows,'2023-07-01',policy);pending=[];samples=[]
    days=sorted({r['date'] for r in rows if r['date']>='2023-07-01'})
    for day in days:
        state=extend(state,pending,day,policy)
        pending=[r for r in rows if r['date']==day]
        for r in pending:
            p,problem=predict(state,r['home'],r['away'],day,policy)
            if p:samples.append({'row':r,'h':p['home_rate'],'a':p['away_rate']})
    cal=[s for s in samples if s['row']['date']<'2024-07-01']
    test=[s for s in samples if s['row']['date']>='2025-07-01']
    if min(len(cal),len(test))<200: raise ValueError('Insufficient chronological joint evidence')
    temperatures=[]
    for t in (.85,1.,1.15):
        loss=sum(-np.log(max(1e-15,score_distribution(s['h'],s['a'],temperature=t).mass[s['row']['hg'],s['row']['ag']])) for s in cal)
        temperatures.append((float(loss),abs(t-1),t))
    temperature=min(temperatures)[2];leg_masks,joint_masks=masks()
    training=[r for r in rows if r['date']<'2023-07-01']
    baseline=score_distribution(float(np.mean([r['hg'] for r in training])),float(np.mean([r['ag'] for r in training]))).mass
    reports={}
    all_tasks={**{str(k):v for k,v in leg_masks.items()},**joint_masks}
    for name,mask in all_tasks.items():
        sets={}
        for label,records in [('cal',cal),('test',test)]:
            ps=[float(score_distribution(s['h'],s['a'],temperature=temperature).mass[mask].sum()) for s in records]
            y=[int(mask[s['row']['hg'],s['row']['ag']]) for s in records];d=[s['row']['date'] for s in records]
            sets[label]=(ps,y,d)
        p,y,d=sets['test'];cp,cy,_=sets['cal'];b=[float(baseline[mask].sum())]*len(y)
        reports[name]={'calibration_n':len(cal),'test_n':len(test),
            'calibration_bins':reliability(cp,cy),'test_reliability':reliability(p,y),
            'metrics':metrics(p,y,d,1000,51789),'baseline':metrics(b,y,d,1000,51789),
            'minus_baseline':metrics(p,y,d,1000,51789,b)}
    report={'schema':1,'league':'Bundesliga','model_version':'bundesliga-coherent-score-research-1',
        'generated_at':utcnow().isoformat(),'base_artifact_sha256':artifact['artifact_sha256'],
        'completion_sha256':completion['sha256'],'code_sha256':code_hash(),
        'data_sha256':digest(rows),'source_coverage':sources[:-2]+[completion['source']],
        'temperature':temperature,'temperature_selection':'Full score likelihood on 2023–24 only; fixed .85/1/1.15 grid',
        'calibration_start':'2023-07-01','calibration_end':'2024-06-30','test_start':'2025-07-01','test_end':max(s['row']['date'] for s in test),
        'reports':reports,'contracts':TASKS,'excluded_test_games':306-len(test),
        'approved':False,'joint_validated':False,'replaces_incumbent':False,
        'limitations':['Recent season is held out from parameter/calibration fitting; parts were previously inspected in this project',
            'This is retrospective rolling research, not independently confirmed prospective evidence',
            'Home and away score counts use an independent Poisson assumption within one coherent game model',
            'Score temperature preserves coherent dependencies; it does not establish parlay calibration',
            'Promoted teams without sufficient prior samples are excluded',
            'No sportsbook ticket, operator settlement rules, prices, positive EV or profitability claim']}
    report['sha256']=digest(report);Path(output).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');return report


def load_report():
    try:
        r=json.loads(PATH.read_text());checksum=r.pop('sha256')
        if digest(r)!=checksum or r['code_sha256']!=code_hash() or r['approved'] or r['joint_validated']:return None
        return r|{'sha256':checksum}
    except (OSError,ValueError,KeyError,TypeError):return None


def envelope(p,task):
    b=task['calibration_bins'][min(9,int(p*10))];lo,hi=b['frequency_interval'] if b['n']>=50 else (0.,1.)
    return min(lo,p),max(hi,p),b['n']


def candidates(store,now=None,hours=168):
    from intelligence.current_soccer import prepare_openliga
    from intelligence.fixture_research import soccer_forecasts
    from intelligence.lifecycle import research_hold
    from types import SimpleNamespace
    now=now or utcnow();report=load_report()
    if not report:return []
    artifact=prepare_openliga('Bundesliga',store,now)
    if artifact.get('problem') or artifact.get('historical_completion_sha256')!=report['completion_sha256']:return []
    # This score model inherits the frozen venue strengths. A hold on that
    # underlying model is not escaped by using a different SGP version/name.
    base_contract=SimpleNamespace(sport='Soccer',league='Bundesliga',market='btts',point=None)
    base_model=SimpleNamespace(model_version=artifact['model_version'],evidence_id=artifact['artifact_sha256'])
    if research_hold(store,base_contract,base_model):return []
    events,_=soccer_forecasts('Bundesliga',artifact,now,hours)
    leg_masks,joint_masks=masks();out=[]
    for event in events:
        raw,_=predict(artifact['state'],event['home_id'],event['away_id'],parse_time(event['kickoff']).date().isoformat(),artifact['policy'])
        if not raw:continue
        mass=score_distribution(raw['home_rate'],raw['away_rate'],temperature=report['temperature']).mass
        side='Home' if mass[leg_masks[('h2h','Home',None)]].sum()>=mass[leg_masks[('h2h','Away',None)]].sum() else 'Away'
        for name,contracts in TASKS.items():
            if contracts[0][1]!=side:continue
            task=report['reports'][name];p=float(mass[joint_masks[name]].sum());lo,hi,n=envelope(p,task)
            model=SimpleNamespace(model_version=report['model_version'],evidence_id=report['sha256'])
            if any(research_hold(store,SimpleNamespace(sport='Soccer',league='Bundesliga',market=m,point=point),model)
                for m,selection,point in contracts):continue
            legs=[]
            for market,selection,point in contracts:
                lp=float(mass[leg_masks[(market,selection,point)]].sum());ll,lu,ln=envelope(lp,report['reports'][str((market,selection,point))])
                legs.append({'market':market,'selection':event['home'] if selection=='Home' else event['away'] if selection=='Away' else selection,
                    'point':point,'probability':lp,'lower':ll,'upper':lu,'calibration_bin_n':ln})
            out.append({'event':event['event'],'league':'Bundesliga','kickoff':event['kickoff'],'fixture_id':event['fixture_id'],
                'source_observed_at':event['source_observed_at'],'forecast_at':now.isoformat(),
                'legs':legs,'joint_probability':p,'lower':lo,'upper':hi,'fair_odds':1/p,
                'calibration_bin_n':n,'calibration_n':task['calibration_n'],'test_n':task['test_n'],
                'test_metrics':task['metrics'],'test_baseline':task['baseline'],
                'model_version':report['model_version'],'evidence_id':report['sha256'],
                'research_eligible':n>=50 and hi-lo<=.5 and task['test_n']>=100 and task['calibration_n']>=100,
                'joint_validated':False,'approved':False,'executable':False,'combined_odds':None,'ev':None,
                'probability_method':'Sum of matching outcomes in one coherent score distribution; no multiplied leg probabilities',
                'limitations':report['limitations']})
    out.sort(key=lambda c:(not c['research_eligible'],c['upper']-c['lower'],-c['joint_probability'],c['kickoff']))
    # At most one per leg count and physical game in the concise research view.
    return out
