"""Reproducible offline chronological challenger comparison. No activation/I/O APIs.

CLI: python -m intelligence.quant_evaluation --source work/phase2/source
2024-25 is candidate-held-out but previously inspected in this project. It cannot
establish independent confirmation or replace a frozen current-inference model.
"""
import argparse,json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from hashlib import sha256
from datetime import date,timedelta
import numpy as np
from intelligence.domain import utcnow,digest
from intelligence.data_adapters import ROOT,pinned_history
from intelligence.expanded_models import rows_from_events,load as load_expanded
from intelligence.epl_forecasts import load_artifact
from intelligence.epl_validation import fit_calibrator,calibrated,reliability,metrics
from intelligence.quant_models import fit_poisson,fit_rho,goal_rates
from intelligence.score_distribution import score_distribution,marginals

POLICY=ROOT/'config/quant_research_policy.json'
DESTINATION=ROOT/'research_assets/quantitative/evaluation.json'


def ece(prob,y):
    bins=reliability(prob,y)
    return sum(b['n']*abs(b['mean_probability']-b['observed_frequency']) for b in bins if b['n'])/len(y)


def binary_report(prob,y,days,p,baseline):
    return {'metrics':metrics(prob,y,days,p['bootstrap_resamples'],p['seed']),
        'minus_frozen':metrics(prob,y,days,p['bootstrap_resamples'],p['seed'],baseline),
        'ece':ece(prob,y),'calibration_bins':reliability(prob,y)}


def score_loss_report(values,days,p):
    values=np.array(values);days=np.array(days)
    blocks=[values[days==d] for d in sorted(set(days))]
    sums=np.array([b.sum(axis=0) for b in blocks]);counts=np.array([len(b) for b in blocks])
    samples=np.random.default_rng(p['seed']).integers(0,len(blocks),size=(p['bootstrap_resamples'],len(blocks)))
    boot=sums[samples].sum(axis=1)/counts[samples].sum(axis=1)[:,None]
    return {key:{'value':float(values[:,i].mean()),'interval':np.quantile(boot[:,i],[.025,.975]).tolist()}
        for i,key in enumerate(('scoreline_log_loss','scoreline_multiclass_brier'))}


def frozen_predictions(league,rows,p):
    """Replay the unchanged model functions with strictly preceding dates."""
    from intelligence.venue_goals import fit as venue_fit,extend,predict
    from intelligence.epl_goal_model import fit as epl_fit,advance,add_result,rates,probabilities
    from intelligence.epl_source import team
    epl=league=='Premier League';artifact=load_artifact() if epl else load_expanded(league)
    if not artifact:return {},None
    model_policy=artifact['policy'];start=p['calibration_start']
    data=[dict(r,home=team(r['home_name']),away=team(r['away_name'])) if epl else r for r in rows]
    state=(epl_fit if epl else venue_fit)(data,start,model_policy);by_day={}
    for r in data:
        if start<=r['date']<=p['test_end']:by_day.setdefault(r['date'],[]).append(r)
    output={};pending=[]
    for day,batch in sorted(by_day.items()):
        if epl:
            advance(state,day,model_policy)
            for r in pending:add_result(state,r,model_policy)
        else:state=extend(state,pending,day,model_policy)
        for row in batch:
            if epl:
                value,_=rates(state,row['home'],row['away'],day,model_policy)
                value=probabilities(*value) if value else None
            else:value,_=predict(state,row['home'],row['away'],day,model_policy)
            if value:
                targets=artifact['tasks'] if epl else {artifact['target']:artifact}
                output[row['fixture_id']]={target:float(calibrated(value[target],task['coefficients'])) for target,task in targets.items()}
        pending=batch
    return output,artifact


def evaluate(league,directory,p):
    events,sources=pinned_history(directory,league)
    result={'league':league,'source_coverage':sources,'approved':False,'live_dispatch':False}
    required=('2020-21','2021-22','2022-23','2023-24','2024-25')
    if any(not next(s['complete_historical_season'] for s in sources if s['season']==season) for season in required):
        result['blocked']='Incomplete training/calibration/test seasons; no challenger fit or approval'
        return result
    rows=rows_from_events(events);names={e.fixture_id:(e.home_name,e.away_name) for e in events}
    rows=[dict(r,home_name=names[r['fixture_id']][0],away_name=names[r['fixture_id']][1]) for r in rows]
    model=fit_poisson(rows,p);rho=fit_rho(model,rows,p)
    frozen,artifact=frozen_predictions(league,rows,p)
    if not artifact:result['blocked']='No verified frozen comparator';return result
    targets=list(artifact['tasks']) if league=='Premier League' else [artifact['target']]
    cal=[];test=[];excluded=Counter()
    for r in rows:
        if not p['calibration_start']<=r['date']<=p['test_end']:continue
        rates=goal_rates(model,r,p['minimum_training_team_games'])
        if not rates or r['fixture_id'] not in frozen:excluded['unknown/low training-team support or frozen exclusion']+=1;continue
        try:
            pois=score_distribution(*rates);dc=score_distribution(*rates,rho)
        except ValueError:excluded['out-of-range distribution']+=1;continue
        record={'row':r,'rates':rates,'poisson':marginals(pois),'dixon_coles':marginals(dc),'frozen':frozen[r['fixture_id']]}
        (cal if r['date']<=p['calibration_end'] else test).append(record)
    if len(cal)<100 or len(test)<100:result['blocked']='Insufficient common chronological sample';return result
    temperatures=[]
    for temperature in p['score_temperature_grid']:
        loss=0.
        for r in cal:
            grid=score_distribution(*r['rates'],rho,temperature,p['score_limit']).mass
            row=r['row'];loss-=float(np.log(max(grid[row['hg'],row['ag']],1e-15)))
        temperatures.append((loss,abs(temperature-1),temperature))
    temperature=min(temperatures)[2]
    for record in cal+test:
        record['coherent_temperature']=marginals(score_distribution(*record['rates'],rho,temperature,p['score_limit']))
    reports={}
    for target in targets:
        outcome=lambda r:int(r['hg']>0 and r['ag']>0) if target=='btts' else int(r['hg']+r['ag']>2.5)
        cy=[outcome(r['row']) for r in cal];y=[outcome(r['row']) for r in test];days=[r['row']['date'] for r in test]
        baseline=[r['frozen'][target] for r in test];methods={}
        methods['frozen']=binary_report(baseline,y,days,p,baseline)
        methods['constant']=binary_report([float(np.mean(cy))]*len(test),y,days,p,baseline)
        for method in ('poisson','dixon_coles','coherent_temperature'):
            cp=[r[method][target] for r in cal];tp=[r[method][target] for r in test]
            coefficients=fit_calibrator(cp,cy) if method!='coherent_temperature' else None
            prob=calibrated(tp,coefficients).tolist() if coefficients else tp
            methods[method]=binary_report(prob,y,days,p,baseline)|{'binary_calibration_coefficients':coefficients}
        reports[target]={'calibration_n':len(cal),'test_n':len(test),'test_start':min(days),'test_end':max(days),'methods':methods}
    joint_scores=[];sgp={'btts_and_over_2.5':[],'home_and_over_2.5':[]};sgp_y={k:[] for k in sgp}
    h,a=np.indices((p['score_limit']+1,p['score_limit']+1))
    masks={'btts_and_over_2.5':(h>0)&(a>0)&(h+a>2.5),'home_and_over_2.5':(h>a)&(h+a>2.5)}
    training=[r for r in rows if p['training_start']<=r['date']<=p['training_end']]
    league_grid=score_distribution(float(np.mean([r['hg'] for r in training])),float(np.mean([r['ag'] for r in training]))).mass
    sgp_baselines={k:float(league_grid[mask].sum()) for k,mask in masks.items()}
    days=[r['row']['date'] for r in test]
    for r in test:
        grid=score_distribution(*r['rates'],rho,temperature,p['score_limit']).mass;row=r['row'];true=grid[row['hg'],row['ag']]
        joint_scores.append([float(-np.log(max(true,1e-15))),float((grid*grid).sum()-2*true+1)])
        for k,mask in masks.items():
            sgp[k].append(float(grid[mask].sum()));sgp_y[k].append(int(mask[row['hg'],row['ag']]))
    result.update(training_model=model,rho_training_only=rho,score_temperature_calibration_only=temperature,
        calibration_n=len(cal),common_test_n=len(test),common_test_ids_sha256=digest([r['row']['fixture_id'] for r in test]),
        excluded=dict(excluded),markets=reports,joint_score_diagnostics={'n':len(test),
            'proper_scores':score_loss_report(joint_scores,days,p),
            'joint_validated':False,'scope':'Proper score over the coherent full score grid; no specific SGP validation or market-price baseline'},
        joint_event_research={k:{'n':len(test),'metrics':metrics(prob,sgp_y[k],days,p['bootstrap_resamples'],p['seed']),
            'minus_training_league_poisson':metrics(prob,sgp_y[k],days,p['bootstrap_resamples'],p['seed'],[sgp_baselines[k]]*len(test)),
            'ece':ece(prob,sgp_y[k]),'calibration_bins':reliability(prob,sgp_y[k]),'validated':False,
            'note':'Retrospective predeclared event within the same coherent score matrix; no operator acceptance, genuine ticket price or prospective confirmation'} for k,prob in sgp.items()},
        frozen_comparator_artifact=artifact['artifact_sha256'])
    return result


def build(directory,destination=DESTINATION):
    p=json.loads(POLICY.read_text())
    result={'version':p['version'],'generated_at':utcnow().isoformat(),'policy':p,
        'policy_sha256':digest(p),'candidate_code_sha256':digest({n:(ROOT/'intelligence'/n).read_text() for n in ('quant_models.py','quant_evaluation.py','score_distribution.py')}),
        'status':'Offline research only; no replacement/approval/current inference',
        'independent_confirmation':False,'historical_market_benchmark':None,'profitability':None,
        'limitations':['Candidate fitting/calibration never uses test outcomes; test dates were previously examined in this project, not a fresh independent confirmation',
            'All 2025-26 archives are incomplete, so no later complete independent period is claimed',
            'Common-sample comparisons exclude unseen/promoted or low-training-history teams; selection can bias evaluation',
            'Candidate parameters are fixed before calibration; the existing comparator updates earlier-result strengths each day',
            'No historical availability/revision timestamps, xG, lineups/injuries or tradable Ontario price benchmark',
            'UTC-day bootstrap assumes exchangeable day blocks; cross-day and model-search uncertainty are unmeasured'],
        'leagues':{league:evaluate(league,directory,p) for league in ('Premier League','Bundesliga','Ligue 1','La Liga','Serie A')}}
    result['sha256']=digest(result);destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',required=True);parser.add_argument('--output',default=str(DESTINATION));args=parser.parse_args()
    report=build(args.source,args.output)
    print(json.dumps({'status':report['status'],'leagues':{k:{'n':v.get('common_test_n'),'blocked':v.get('blocked')} for k,v in report['leagues'].items()}}))
