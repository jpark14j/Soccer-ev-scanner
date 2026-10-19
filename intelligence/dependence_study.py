"""Explicit cross-game dependence challenger; offline research, no approval.

A one-parameter Farlie-Gumbel-Morgenstern (FGM) joint Bernoulli distribution
preserves each earlier-calibrated marginal. Unlike a recalibration of an all-win
product, it defines every joint outcome coherently. Its restrictive common
pair-dependence and zero higher-order term are assumptions, not discovered truth.
"""
from pathlib import Path
from itertools import combinations,product
import json
import numpy as np
from intelligence.domain import digest,utcnow
from intelligence.cross_game_study import FOLDS,groups,assessment
from intelligence.team_rating import replay
from intelligence.epl_validation import fit_calibrator,calibrated

DESTINATION=Path(__file__).resolve().parents[1]/'research_assets/dependence_study.json'
VERSION='fgm-cross-game-research-1'
RIDGE=25.  # Fixed shrinkage toward no dependence; never selected on test scores.


def state_probability(ps,ys,theta):
    if len(ps) not in (2,3) or len(ys)!=len(ps):raise ValueError('Two or three matched binary contracts required')
    lower=-1 if len(ps)==2 else -1/3
    if not np.isfinite(theta) or not lower<=theta<=1:raise ValueError('Dependence outside coherent FGM range')
    if any(not np.isfinite(p) or not 0<=p<=1 for p in ps) or any(y not in (0,1) for y in ys):raise ValueError('Invalid binary marginal/outcome')
    mass=np.prod([p if y else 1-p for p,y in zip(ps,ys)])
    # Integrate (1-2u) on the winning/losing intervals of each uniform marginal.
    centered=[1-p if y else -p for p,y in zip(ps,ys)]
    return float(mass*(1+theta*sum(centered[i]*centered[j] for i,j in combinations(range(len(ps)),2))))


def attach(rows,legs):
    grouped,excluded=groups(rows,legs)
    lookup={(r['date'],r['home'],r['away']):r for r in rows}
    for g in grouped:
        components=[lookup[(g['date'],h,a)] for h,a in g['ids']]
        g['ps']=[max(r['p'],1-r['p']) for r in components]
        g['ys']=[int(r['y']==int(r['p']>=.5)) for r in components]
    return grouped,excluded


def fit(records,legs):
    """Convex one-dimensional penalized likelihood over ALL observed states."""
    lower=-1 if legs==2 else -1/3
    factors=np.array([sum((1-p if y else -p)*(1-q if z else -q)
        for (p,y),(q,z) in combinations(zip(r['ps'],r['ys']),2)) for r in records])
    def derivative(theta):return -float(np.sum(factors/(1+theta*factors)))+RIDGE*theta
    lo,hi=lower+1e-8,1-1e-8
    if derivative(lo)>=0:return lo
    if derivative(hi)<=0:return hi
    for _ in range(80):
        mid=(lo+hi)/2
        if derivative(mid)>0:hi=mid
        else:lo=mid
    return (lo+hi)/2


def all_win(records,theta):
    return [state_probability(r['ps'],[1]*len(r['ps']),theta) for r in records]


def block_difference(p,q,records,block_days=14,resamples=500):
    """Longer calendar-block sensitivity, not a cure for all team dependence."""
    from datetime import date
    days=[r['date'] for r in records];anchor=date.fromisoformat(min(days))
    grouped=[str((date.fromisoformat(d)-anchor).days//block_days).zfill(5) for d in days]
    from intelligence.epl_validation import metrics
    return metrics(p,[r['y'] for r in records],grouped,resamples,17184,q)


def evaluate(history,sport,source,resamples=500):
    games=history.copy()
    if sport=='MLB':
        for c in ('HomeTeam','AwayTeam'):games[c]=games[c].replace({'ATH':'OAK'})
    rows,_=replay(games,sport);folds=[]
    for cal_start,test_start,test_end in FOLDS[sport]:
        cal=[r for r in rows if cal_start<=r['date']<test_start]
        test=[r for r in rows if test_start<=r['date']<test_end]
        days=sorted({r['date'] for r in cal});cut=days[len(days)//2]
        first=[r for r in cal if r['date']<cut];second=[r for r in cal if r['date']>=cut]
        coefficients=fit_calibrator([r['p'] for r in first],[r['y'] for r in first])
        def apply(records):return [r|{'p':float(p)} for r,p in zip(records,calibrated([r['p'] for r in records],coefficients))]
        jcal,jtest=apply(second),apply(test);tasks={}
        for legs in (2,3):
            training,ec=attach(jcal,legs);testing,et=attach(jtest,legs)
            if min(len(training),len(testing))<40:raise ValueError('Insufficient disjoint historical groups')
            theta=fit(training,legs);ps=all_win(testing,theta);base=all_win(testing,0.)
            # All-state likelihood tests the dependence model independently of
            # whether the requested all-win ticket happened to win.
            ll=[-np.log(max(1e-15,state_probability(r['ps'],r['ys'],theta))) for r in testing]
            bl=[-np.log(max(1e-15,state_probability(r['ps'],r['ys'],0.))) for r in testing]
            tasks[str(legs)]={'fit_n':len(training),'test_n':len(testing),'theta':theta,
                'excluded_repeated_team_games':{'calibration':ec,'test':et},
                'test_groups_sha256':digest([{'day':r['date'],'ids':r['ids']} for r in testing]),
                'fgm_all_win':assessment(ps,testing,resamples),
                'hypothetical_independence':assessment(base,testing,resamples),
                'fgm_minus_product':assessment(ps,testing,resamples,base),
                'fourteen_day_block_difference':block_difference(ps,base,testing,resamples=resamples),
                'all_state_log_loss':float(np.mean(ll)),'independence_all_state_log_loss':float(np.mean(bl)),
                'probability_shift_quantiles':np.quantile(np.array(ps)-base,[0,.5,.95,1]).tolist(),
                'approved':False,'joint_forecast_enabled':False,'actual_combined_odds':None,'EV':None}
        folds.append({'calibration_start':cal_start,'marginal_fit_end':first[-1]['date'],
            'dependence_fit_start':second[0]['date'],'test_start':test_start,'test_end_exclusive':test_end,
            'marginal_coefficients':coefficients,'tasks':tasks})
    return {'sport':sport,'source':source,'data_sha256':digest(games.to_json(orient='records',date_format='iso')),'folds':folds}


def code_hash():
    return digest({n:Path(__file__).with_name(n).read_text() for n in
        ('dependence_study.py','cross_game_study.py','team_rating.py','epl_validation.py')})


def build(nba,mlb,nba_source,mlb_source,resamples=500):
    result={'schema':1,'version':VERSION,'generated_at':utcnow().isoformat(),'code_sha256':code_hash(),
        'ridge':RIDGE,'reports':{'NBA':evaluate(nba,'NBA',nba_source,resamples),'MLB':evaluate(mlb,'MLB',mlb_source,resamples)},
        'approved_models':0,'approved_joint_models':0,'current_forecasts_enabled':False,
        'limitations':['Previously inspected archives, not independent prospective confirmation',
            'FGM preserves individual marginals but assumes one common pair interaction and zero higher-order interaction',
            'FGM cannot represent all strong/extreme dependence structures; shrinkage is fixed, not evidence that dependence is absent',
            'Favorite groups are deterministic/disjoint on each day; the study cannot validate arbitrary or mixed-sport combinations',
            '14-day blocks provide sensitivity to temporal clustering; season/team/source-revision uncertainty remains',
            'Current fixtures, offseason/roster/pitcher context, actual tickets and historical market baselines remain missing',
            'No automatic approval, positive-EV claim or backdated forward record']}
    result['sha256']=digest(result);return result


def load_report(path=DESTINATION):
    try:
        r=json.loads(Path(path).read_text());sha=r.pop('sha256')
        if digest(r)!=sha or r['code_sha256']!=code_hash() or r['approved_models'] or r['approved_joint_models'] or r['current_forecasts_enabled']:return None
        return r|{'sha256':sha}
    except (OSError,ValueError,KeyError,TypeError):return None


def main():
    import argparse
    from intelligence.recent_nba import load_bundle
    from intelligence.history import load_licensed
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--nba-bundle',type=Path,required=True);p.add_argument('--history-dir',type=Path,required=True);a=p.parse_args()
    nba,ns=load_bundle(a.nba_bundle);mlb=load_licensed('MLB',a.history_dir)
    r=build(nba,mlb,ns,json.loads((a.history_dir/'mlb.source.json').read_text()))
    DESTINATION.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n')
    print(json.dumps({s:[{'start':f['test_start'],'tasks':{k:{'theta':v['theta'],'n':v['test_n'],
        'Brier_difference':v['fgm_minus_product']['metrics']['binary_brier'],
        'fourteen_day':v['fourteen_day_block_difference']['binary_brier']} for k,v in f['tasks'].items()}} for f in x['folds']] for s,x in r['reports'].items()}))


if __name__=='__main__':main()
