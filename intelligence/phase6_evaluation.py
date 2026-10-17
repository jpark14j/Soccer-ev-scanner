"""Offline calibration/refit and dependent settlement research. No activation.

All comparisons use predeclared policies and the existing pinned archive. The
candidate-held-out period is reused project research, not independent evidence.
"""
import argparse,json
from pathlib import Path
import numpy as np
from intelligence.domain import digest,utcnow
from intelligence.data_adapters import ROOT,pinned_history
from intelligence.expanded_models import rows_from_events
from intelligence.quant_models import fit_poisson,fit_rho,goal_rates
from intelligence.quant_evaluation import frozen_predictions,ece,score_loss_report
from intelligence.epl_validation import fit_calibrator,calibrated,reliability,metrics
from intelligence.score_distribution import score_distribution,marginals,settlement,state_label

POLICY=ROOT/'config/phase6_research_policy.json'
DESTINATION=ROOT/'research_assets/quantitative/phase6.json'


def beta_probability(p,coefficients):
    p=np.clip(np.asarray(p,dtype=float),1e-8,1-1e-8)
    x=np.column_stack((np.ones(p.size),np.log(p),-np.log1p(-p)))
    return 1/(1+np.exp(-np.clip(x@np.asarray(coefficients),-35,35)))


def fit_beta(p,y,ridge=3.):
    p=np.asarray(p,dtype=float);y=np.asarray(y,dtype=float)
    if p.ndim!=1 or len(p)<100 or p.shape!=y.shape or not np.all(np.isfinite(p)) or not np.all((p>0)&(p<1)) or not np.all((y==0)|(y==1)) or ridge<=0:
        raise ValueError('Adequate binary calibration data required')
    x=np.column_stack((np.ones(p.size),np.log(p),-np.log1p(-p)))
    beta=np.array([0.,1.,1.]);prior=beta.copy();penalty=np.array([1.,ridge,ridge])
    def loss(b):
        z=x@b;return float(np.sum(np.logaddexp(0,z)-y*z)+.5*np.sum(penalty*(b-prior)**2))
    for _ in range(300):
        prob=beta_probability(p,beta);grad=x.T@(prob-y)+penalty*(beta-prior)
        active=np.array([False,*((beta[1:]<=1e-10)&(grad[1:]>0))])
        projected=grad.copy();projected[active]=0
        if np.max(np.abs(projected))<1e-6:return beta.tolist()
        hessian=(x.T*(prob*(1-prob)))@x+np.diag(penalty)
        # Solve only along free coordinates. Clipping an unconstrained Newton
        # step can stall at a boundary because of cross-coordinate curvature.
        free=~active;step=np.zeros(3)
        step[free]=np.linalg.solve(hessian[np.ix_(free,free)],grad[free])
        old=loss(beta);scale=1.
        for _ in range(45):
            candidate=beta-scale*step;candidate[1:]=np.maximum(0.,candidate[1:])
            if loss(candidate)<=old+1e-4*float(grad@(candidate-beta)):break
            scale*=.5
        else:raise ValueError('Monotone beta calibration line search failed')
        beta=candidate
    raise ValueError('Monotone beta calibration did not converge')


def settlement_masks(contracts,limit=40):
    masks={}
    for h in range(limit+1):
        for a in range(limit+1):
            state=tuple(state_label(settlement(m,s,line,'HOME','AWAY',h,a)) for m,s,line in contracts)
            if state not in masks:masks[state]=np.zeros((limit+1,limit+1),dtype=bool)
            masks[state][h,a]=True
    return masks


def evaluate(league,directory,base,p):
    events,sources=pinned_history(directory,league)
    result={'league':league,'approved':False,'source_coverage':sources}
    if any(not next(s['complete_historical_season'] for s in sources if s['season']==season) for season in ('2020-21','2021-22','2022-23','2023-24','2024-25')):
        return result|{'blocked':'Incomplete training/calibration/test season; no fit'}
    names={e.fixture_id:(e.home_name,e.away_name) for e in events}
    rows=[r|{'home_name':names[r['fixture_id']][0],'away_name':names[r['fixture_id']][1]} for r in rows_from_events(events)]
    model=fit_poisson(rows,base);rho=fit_rho(model,rows,base)
    refit_policy=base|{'training_end':p['annual_refit_training_end'],'calibration_start':p['annual_refit_anchor']}
    refit=fit_poisson(rows,refit_policy);refit_rho=fit_rho(refit,rows,refit_policy)
    frozen,artifact=frozen_predictions(league,rows,base)
    if not artifact:return result|{'blocked':'Frozen comparator unavailable'}
    targets=list(artifact['tasks']) if league=='Premier League' else [artifact['target']]
    cal=[];test=[];excluded=0
    for row in rows:
        if not base['calibration_start']<=row['date']<=base['test_end']:continue
        rates=goal_rates(model,row,base['minimum_training_team_games'])
        is_test=row['date']>=base['test_start']
        new_rates=goal_rates(refit,row,base['minimum_training_team_games']) if is_test else None
        if rates is None or row['fixture_id'] not in frozen or is_test and new_rates is None:excluded+=1;continue
        try:
            raw=marginals(score_distribution(*rates,rho))
            new=marginals(score_distribution(*new_rates,refit_rho)) if is_test else None
        except ValueError:excluded+=1;continue
        value={'row':row,'rates':rates,'raw':raw,'refit':new,'frozen':frozen[row['fixture_id']]}
        (test if is_test else cal).append(value)
    if len(cal)<100 or len(test)<100:return result|{'blocked':'Insufficient matched chronological sample'}
    temperature_scores=[]
    for t in base['score_temperature_grid']:
        loss=sum(-float(np.log(max(score_distribution(*r['rates'],rho,t).mass[r['row']['hg'],r['row']['ag']],1e-15))) for r in cal)
        temperature_scores.append((loss,abs(t-1),t))
    temperature=min(temperature_scores)[2]
    days=[r['row']['date'] for r in test];settings=base|{'seed':p['bootstrap_seed'],'bootstrap_seed':p['bootstrap_seed'],'bootstrap_resamples':p['bootstrap_resamples']}
    summary={}
    for target in targets:
        truth=lambda r:int(r['hg']>0 and r['ag']>0) if target=='btts' else int(r['hg']+r['ag']>2.5)
        cy=[truth(r['row']) for r in cal];y=[truth(r['row']) for r in test]
        cp=[r['raw'][target] for r in cal];tp=[r['raw'][target] for r in test]
        platt=fit_calibrator(cp,cy);beta=fit_beta(cp,cy,p['beta_calibration_ridge'])
        predictions={'frozen':[r['frozen'][target] for r in test],
            'static_dc_platt':calibrated(tp,platt).tolist(),
            'static_dc_beta':beta_probability(tp,beta).tolist(),
            'annual_refit_dc_platt':calibrated([r['refit'][target] for r in test],platt).tolist(),
            'constant':[float(np.mean(cy))]*len(test)}
        methods={}
        for method,prob in predictions.items():
            methods[method]={'metrics':metrics(prob,y,days,settings['bootstrap_resamples'],settings['bootstrap_seed']),
                'minus_frozen':metrics(prob,y,days,settings['bootstrap_resamples'],settings['bootstrap_seed'],predictions['frozen']),
                'minus_static_dc_platt':metrics(prob,y,days,settings['bootstrap_resamples'],settings['bootstrap_seed'],predictions['static_dc_platt']),
                'ece':ece(prob,y),'calibration_bins':reliability(prob,y)}
        summary[target]={'calibration_n':len(cal),'test_n':len(test),'beta_coefficients':beta,'platt_coefficients':platt,'methods':methods}
    masks={name:settlement_masks(contracts,base['score_limit']) for name,contracts in p['settlement_tasks'].items()}
    joint={name:{'prob':[],'truth':[],'scores':[],'cal_prob':[],'cal_y':[]} for name in masks}
    for is_test,period in ((False,cal),(True,test)):
        for r in period:
            grid=score_distribution(*r['rates'],rho,temperature).mass
            h,a=r['row']['hg'],r['row']['ag']
            for name,states in masks.items():
                probabilities={state:float(grid[mask].sum()) for state,mask in states.items()}
                actual=next(state for state,mask in states.items() if mask[h,a])
                all_win=tuple('win' for _ in p['settlement_tasks'][name]);prob=probabilities.get(all_win,0.)
                record=joint[name]
                if is_test:
                    record['prob'].append(prob);record['truth'].append(int(actual==all_win))
                    true_prob=probabilities[actual]
                    record['scores'].append([-float(np.log(max(true_prob,1e-15))),sum(v*v for v in probabilities.values())-2*true_prob+1])
                else:record['cal_prob'].append(prob);record['cal_y'].append(int(actual==all_win))
    joint_report={}
    for name,v in joint.items():
        proper=score_loss_report(v['scores'],days,settings)
        joint_report[name]={'contracts':p['settlement_tasks'][name],'n':len(test),'possible_joint_states':len(masks[name]),
            'settlement_state_proper_scores':{k.replace('scoreline','settlement_state'):value for k,value in proper.items()},
            'all_full_win':{'metrics':metrics(v['prob'],v['truth'],days,settings['bootstrap_resamples'],settings['bootstrap_seed']),
                'ece':ece(v['prob'],v['truth']),'calibration_bins':reliability(v['prob'],v['truth']),
                'prior_calibration_bins':reliability(v['cal_prob'],v['cal_y'])},
            'joint_approved':False,'actual_combined_price':None,'EV':None,
            'scope':'Hypothetical regulation-score contracts; operator settlement, accepted combination and pricing unverified'}
    return result|{'common_test_n':len(test),'calibration_n':len(cal),'matched_test_ids_sha256':digest([r['row']['fixture_id'] for r in test]),
        'excluded':excluded,'markets':summary,'rho':rho,'refit_rho':refit_rho,'coherent_temperature':temperature,
        'joint_settlement_research':joint_report,'fit_training_end':model['training_end'],'refit_training_end':refit['training_end'],
        'independent_confirmation':False,'live_dispatch':False}


def build(directory,destination=DESTINATION):
    p=json.loads(POLICY.read_text());base=json.loads((ROOT/p['base_policy']).read_text())
    result={'version':p['version'],'generated_at':utcnow().isoformat(),'policy':p,'base_policy_sha256':digest(base),'policy_sha256':digest(p),
        'code_sha256':digest({name:(ROOT/'intelligence'/name).read_text() for name in ('phase6_evaluation.py','quant_models.py','score_distribution.py','quant_evaluation.py')}),
        'independent_confirmation':False,'models_approved':0,'joint_probabilities_approved':0,'actual_market_benchmark':None,
        'limitations':['Reused 2024-25 project test period, not fresh independent confirmation','All 2025-26 archives remain incomplete',
            'Common-sample exclusions can bias results; no test-based tuning/activation','Beta calibration adds a parameter; small calibration samples and binning uncertainty remain',
            'Annual refit uses only prior results but can change calibration transfer; no independent test of stability',
            'UTC-day block intervals do not capture model-search/cross-day dependence','No verified historical odds, operator rules, accepted tickets or profitability'],
        'leagues':{league:evaluate(league,directory,base,p) for league in ('Premier League','Bundesliga','Ligue 1','La Liga','Serie A')}}
    result['sha256']=digest(result);destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',required=True);parser.add_argument('--output',default=str(DESTINATION));args=parser.parse_args()
    report=build(args.source,args.output)
    print(json.dumps({league:{'n':r.get('common_test_n'),'blocked':r.get('blocked')} for league,r in report['leagues'].items()}))
