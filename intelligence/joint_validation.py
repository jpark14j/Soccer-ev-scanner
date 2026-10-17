"""Replay frozen offline score research against a simpler coherent baseline.

No new model fitting, test-based tuning, current prediction or provider request.
The project has already examined these dates; this is not independent evidence.
"""
import argparse,json
from pathlib import Path
from datetime import date
import numpy as np
from intelligence.data_adapters import ROOT,pinned_history
from intelligence.domain import digest,utcnow
from intelligence.expanded_models import rows_from_events
from intelligence.quant_evaluation import frozen_predictions,score_loss_report,ece
from intelligence.quant_models import goal_rates
from intelligence.score_distribution import score_distribution
from intelligence.phase6_evaluation import settlement_masks
from intelligence.epl_validation import metrics,reliability

DESTINATION=ROOT/'research_assets/quantitative/joint_validation.json'


def load_previous(name):
    r=json.loads((ROOT/'research_assets/quantitative'/name).read_text())
    checksum=r.pop('sha256')
    if digest(r)!=checksum:raise ValueError('Previous research checksum mismatch')
    return r


def probability_vector(grid,states):
    return np.array([float(grid[mask].sum()) for mask in states.values()])


def proper(prob,index):
    return [-float(np.log(max(prob[index],1e-15))),float(prob@prob-2*prob[index]+1)]


def evaluate(league,directory,old,phase6):
    events,sources=pinned_history(directory,league);previous=old['leagues'][league];policy=old['policy']
    names={e.fixture_id:(e.home_name,e.away_name) for e in events}
    rows=[r|{'home_name':names[r['fixture_id']][0],'away_name':names[r['fixture_id']][1]} for r in rows_from_events(events)]
    frozen,_=frozen_predictions(league,rows,policy)
    model=previous['training_model'];rho=previous['rho_training_only'];temperature=previous['score_temperature_calibration_only']
    training=[r for r in rows if policy['training_start']<=r['date']<=policy['training_end']]
    baseline=score_distribution(float(np.mean([r['hg'] for r in training])),float(np.mean([r['ag'] for r in training]))).mass
    samples=[]
    for r in rows:
        if not policy['calibration_start']<=r['date']<=policy['test_end'] or r['fixture_id'] not in frozen:continue
        rates=goal_rates(model,r,policy['minimum_training_team_games'])
        if rates is not None:samples.append((r,rates))
    test=[s for s in samples if s[0]['date']>=policy['test_start']]
    if digest([r['fixture_id'] for r,_ in test])!=phase6['leagues'][league]['matched_test_ids_sha256']:
        raise ValueError('Matched historical test cases differ; do not select an easier sample')
    tasks=phase6['policy']['settlement_tasks'];records={}
    for name,contracts in tasks.items():
        masks=settlement_masks(contracts,policy['score_limit']);states=list(masks)
        all_win=tuple('win' for _ in contracts);index=states.index(all_win)
        records[name]={'states':states,'masks':masks,'base':probability_vector(baseline,masks),
            'win_index':index,'scores':[],'baseline_scores':[],'p':[],'y':[],'cp':[],'cy':[],
            'baseline_p':[],'days':[],'sensitivity_widths':[]}
    for r,(h,a) in samples:
        grid=score_distribution(h,a,rho,temperature).mass
        is_test=r['date']>=policy['test_start']
        scenarios=[]
        if is_test:
            # Predefined perturbations, not confidence levels or optimized fits.
            settings=[(h*.9,a*.9,rho,temperature),(h*1.1,a*1.1,rho,temperature),
                (h*.9,a*1.1,rho,temperature),(h*1.1,a*.9,rho,temperature),
                (h,a,0.,temperature),(h,a,rho,1.)]
            for values in settings:
                try:scenarios.append(score_distribution(*values).mass)
                except ValueError:raise ValueError('Sensitivity scenario outside reviewed model bounds') from None
        for name,v in records.items():
            prob=probability_vector(grid,v['masks']);actual=next(i for i,mask in enumerate(v['masks'].values()) if mask[r['hg'],r['ag']])
            p=float(prob[v['win_index']]);y=int(actual==v['win_index'])
            if is_test:
                v['scores'].append(proper(prob,actual));v['baseline_scores'].append(proper(v['base'],actual))
                v['p'].append(p);v['y'].append(y);v['days'].append(r['date']);v['baseline_p'].append(float(v['base'][v['win_index']]))
                changes=[p,*[float(probability_vector(s,v['masks'])[v['win_index']]) for s in scenarios]]
                v['sensitivity_widths'].append(max(changes)-min(changes))
            else:v['cp'].append(p);v['cy'].append(y)
    report={}
    for name,v in records.items():
        differences=np.asarray(v['scores'])-np.asarray(v['baseline_scores'])
        quarters={}
        for quarter in sorted({d[:4]+'-Q'+str((date.fromisoformat(d).month-1)//3+1) for d in v['days']}):
            ix=[i for i,d in enumerate(v['days']) if d[:4]+'-Q'+str((date.fromisoformat(d).month-1)//3+1)==quarter]
            quarters[quarter]={'n':len(ix),'binary_brier':float(np.mean([(v['p'][i]-v['y'][i])**2 for i in ix])),
                'mean_Brier_minus_baseline':float(np.mean([(v['p'][i]-v['y'][i])**2-(v['baseline_p'][i]-v['y'][i])**2 for i in ix]))}
        report[name]={'contracts':tasks[name],'n':len(v['p']),'states':[list(s) for s in v['states']],
            'coherent_state_scores':score_loss_report(v['scores'],v['days'],policy),
            'training_league_state_baseline':score_loss_report(v['baseline_scores'],v['days'],policy),
            'state_score_difference':score_loss_report(differences,v['days'],policy),
            'all_full_win':{'model':metrics(v['p'],v['y'],v['days'],1000,policy['seed']),
                'minus_training_league_baseline':metrics(v['p'],v['y'],v['days'],1000,policy['seed'],v['baseline_p']),
                'ece':ece(v['p'],v['y']),'calibration_bins':reliability(v['p'],v['y']),
                'prior_calibration_bins':reliability(v['cp'],v['cy'])},
            'sensitivity_range_width_quantiles':np.quantile(v['sensitivity_widths'],[0,.5,.95,1]).tolist(),
            'stability_by_quarter':quarters,'joint_approved':False,'executable_combined_price':None,'EV':None}
    return {'n':len(test),'training_end':model['training_end'],'sources':sources,
        'baseline':'Coherent independent home/away Poisson using training-only league mean goals; selections inside the same game remain jointly enumerated',
        'tasks':report}


def build(directory,output=DESTINATION):
    old=load_previous('evaluation.json');previous=load_previous('phase6.json')
    result={'version':'joint-research-2','generated_at':utcnow().isoformat(),
        'code_sha256':digest(Path(__file__).read_text()),'previous_reports_sha256':digest((old,previous)),
        'method':'Replay existing frozen offline score parameters; no new fits or threshold optimization',
        'test_previously_inspected':True,'independent_confirmation':False,'approved_joint_models':0,
        'sensitivity':'Home/away goal rates ±10% together and oppositely, zero-rho and temperature-one; deterministic scenarios, not probability/confidence intervals',
        'limitations':['Historical score-grid diagnostics, not current automatic SGP forecasts',
            'Quarter partitions and sensitivity are descriptive; no repeated-test promotion',
            'Day-block intervals omit model-search and cross-day dependence',
            'Operator periods, voids, accepted combinations and combined prices remain unverified'],
        'leagues':{league:evaluate(league,directory,old,previous) for league in ('Premier League','Bundesliga','Ligue 1')}}
    result['sha256']=digest(result);Path(output).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',required=True);parser.add_argument('--output',default=str(DESTINATION));args=parser.parse_args()
    result=build(args.source,args.output)
    print(json.dumps({'matched_n':{l:v['n'] for l,v in result['leagues'].items()},'approved_joint_models':0}))
