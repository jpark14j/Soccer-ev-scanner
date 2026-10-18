"""Offline, chronological NBA/MLB score challengers and joint-task diagnostics.

Uses only permitted final-score archives already in the project. Game-level
score/form/rest features are available; possession pace, injuries, pitchers and
lineups are NOT inferred. Nothing in this module approves or serves forecasts.
"""
from collections import defaultdict,deque
from pathlib import Path
from math import exp,lgamma
import json
import numpy as np
import pandas as pd
from intelligence.domain import digest,utcnow
from intelligence.epl_validation import metrics,reliability

SPEC={'NBA':{'calibration':'2024-07-01','test':'2025-07-01','total':229.5,'upper_total':249.5},
      'MLB':{'calibration':'2024-01-01','test':'2025-01-01','total':8.5,'upper_total':12.5}}
TASKS=('home_win','over_total','home_win_and_over','home_win_and_total_band')
VERSION='chronological-team-score-challengers-1'
# Retrosheet changed the Athletics abbreviation in 2025. Preserve franchise
# history explicitly; this does not claim Oakland/Sacramento parks are equal.
MLB_TEAM_ALIASES={'ATH':'OAK'}


def features(history,sport):
    """Generate all predictions on a date BEFORE adding any date's outcomes."""
    if sport not in SPEC:raise ValueError('NBA or MLB required')
    required={'date','HomeTeam','AwayTeam','FTHG','FTAG','game_id'}
    if not required<=set(history) or history.game_id.duplicated().any():raise ValueError('Unique reviewed score archive required')
    games=history.copy()
    if sport=='MLB':
        for column in ('HomeTeam','AwayTeam'):games[column]=games[column].replace(MLB_TEAM_ALIASES)
    games=games.sort_values(['date','game_id']);teams=defaultdict(lambda:deque(maxlen=30));last={};output=[];league=[]
    for day,batch in games.groupby('date',sort=True):
        day=pd.Timestamp(day).normalize()
        for r in batch.itertuples():
            h,a=teams[r.HomeTeam],teams[r.AwayTeam]
            if min(len(h),len(a))<12 or len(league)<200:continue
            base=float(np.mean(league[-2400:]))
            def mean(rows,i):return (sum(v[i] for v in rows)+15*base)/(len(rows)+15)
            rest=lambda t:min(7,max(0,(day-last[t]).days-1))
            x=[mean(h,0),mean(h,1),mean(a,0),mean(a,1),base,rest(r.HomeTeam),rest(r.AwayTeam)]
            output.append({'date':day.date().isoformat(),'game_id':r.game_id,'x':x,'home':int(r.FTHG),'away':int(r.FTAG)})
        for r in batch.itertuples():
            if any(not np.isfinite(v) or int(v)!=v or v<0 for v in (r.FTHG,r.FTAG)) or r.FTHG==r.FTAG:
                raise ValueError('Completed non-tied integer final scores required')
            teams[r.HomeTeam].append((r.FTHG,r.FTAG));teams[r.AwayTeam].append((r.FTAG,r.FTHG))
            last[r.HomeTeam]=last[r.AwayTeam]=day;league.extend((r.FTHG,r.FTAG))
    return output


def fit(rows):
    x=np.asarray([r['x'] for r in rows],dtype=float);y=np.asarray([[r['home'],r['away']] for r in rows])
    center=x.mean(0);scale=x.std(0);scale[scale<1e-8]=1
    z=np.column_stack((np.ones(len(x)),(x-center)/scale));penalty=np.eye(z.shape[1])*50;penalty[0,0]=0
    beta=np.linalg.solve(z.T@z+penalty,z.T@y)
    return {'center':center,'scale':scale,'beta':beta}


def means(model,rows,sport):
    x=np.asarray([r['x'] for r in rows]);z=np.column_stack((np.ones(len(x)),(x-model['center'])/model['scale']))
    return np.clip(z@model['beta'],.25 if sport=='MLB' else 50,20 if sport=='MLB' else 180)


def labels(home,away,spec):
    win=home>away;over=home+away>spec['total'];under=home+away<spec['upper_total']
    return np.column_stack((win,over,win&over,win&over&under)).astype(float)


def count_mass(mean,dispersion,limit=80):
    if dispersion<1e-8:
        values=[exp(-mean)]
        for k in range(1,limit+1):values.append(values[-1]*mean/k)
    else:
        shape=1/dispersion;prob=shape/(shape+mean)
        values=[exp(lgamma(k+shape)-lgamma(shape)-lgamma(k+1)+shape*np.log(prob)+k*np.log1p(-prob)) for k in range(limit+1)]
    values=np.asarray(values)
    if 1-values.sum()>1e-6:raise ValueError('Run-score tail exceeds research tolerance')
    return values


def probabilities(predictions,residuals,sport,spec,variant,scale=1.):
    output=[]
    if variant=='paired_residual':
        # Pairing preserves empirical within-game residual dependence. It is not
        # an estimated correlation between arbitrary different-game selections.
        residuals=residuals-residuals.mean(0)
        for mu in predictions:
            scores=np.maximum(1,np.rint(mu+scale*residuals));keep=scores[:,0]!=scores[:,1]
            if keep.sum()<100:raise ValueError('Too few non-tie residual scenarios')
            output.append(labels(scores[keep,0],scores[keep,1],spec).mean(0))
    else:
        # Conditional independent run counts are a disclosed research assumption.
        # NB dispersion comes only from earlier disjoint residual-period errors.
        # Dispersion is supplied from the earlier residual fit, never from
        # evaluated outcomes or the evaluated period's predicted means.
        dispersion=scale if variant=='negative_binomial' else 0.
        h,a=np.indices((81,81));mask=h!=a;outcomes=labels(h.ravel(),a.ravel(),spec).reshape(81,81,4)
        for mu in predictions:
            mass=np.outer(count_mass(mu[0],dispersion),count_mass(mu[1],dispersion));mass*=mask;mass/=mass.sum()
            output.append(np.sum(mass[:,:,None]*outcomes,axis=(0,1)))
    return np.asarray(output)


def evaluate(history,sport,source,resamples=500):
    """Locked simple specifications, warm fit / residual / calibration / test.

    The archive's test seasons were examined by earlier project studies. This
    new comparison is a retrospective diagnostic, NOT independent confirmation.
    Model choice uses calibration only; final outcomes never fit coefficients,
    residuals, dispersion, scale or baseline probabilities.
    """
    spec=SPEC[sport];allrows=features(history,sport)
    warm=[r for r in allrows if r['date']<spec['calibration']]
    cal=[r for r in allrows if spec['calibration']<=r['date']<spec['test']]
    test=[r for r in allrows if r['date']>=spec['test']]
    days=sorted({r['date'] for r in warm});cut=days[int(len(days)*.75)]
    training=[r for r in warm if r['date']<cut];residual_rows=[r for r in warm if r['date']>=cut]
    if min(len(training),len(residual_rows),len(cal),len(test))<200:raise ValueError('Insufficient chronological partitions')
    model=fit(training);mu=means(model,residual_rows,sport)
    residuals=np.asarray([[r['home'],r['away']] for r in residual_rows])-mu
    dispersion=max(0.,float(np.mean(residuals**2)-np.mean(mu)))/float(np.mean(mu)**2)
    cy=labels(np.asarray([r['home'] for r in cal]),np.asarray([r['away'] for r in cal]),spec)
    ty=labels(np.asarray([r['home'] for r in test]),np.asarray([r['away'] for r in test]),spec)
    base=np.mean(labels(np.asarray([r['home'] for r in training]),np.asarray([r['away'] for r in training]),spec),0)
    cm,tm=means(model,cal,sport),means(model,test,sport)
    configurations=[('paired_residual',s) for s in (.85,1.,1.15)] if sport=='NBA' else [('poisson',0.),('negative_binomial',dispersion)]
    scored=[]
    for variant,scale in configurations:
        cp=probabilities(cm,residuals,sport,spec,variant,scale)
        # Select with the two single tasks; do not optimize the requested parlays.
        score=float(np.mean((cp[:,:2]-cy[:,:2])**2));scored.append((score,variant,scale,cp))
    _,variant,scale,cp=min(scored,key=lambda x:(x[0],x[1],x[2]))
    tp=probabilities(tm,residuals,sport,spec,variant,scale);td=[r['date'] for r in test]
    tasks={}
    for i,task in enumerate(TASKS):
        p=tp[:,i].tolist();y=ty[:,i].tolist();b=[float(base[i])]*len(y);bins=reliability(p,y)
        tasks[task]={'test_n':len(y),'metrics':metrics(p,y,td,resamples,51492),
            'training_constant_baseline':metrics(b,y,td,resamples,51492),
            'paired_minus_baseline':metrics(p,y,td,resamples,51492,b),
            'calibration_bins':reliability(cp[:,i],cy[:,i]),'test_reliability':bins,
            'ece':sum(z['n']*abs(z['mean_probability']-z['observed_frequency']) for z in bins if z['n'])/len(y)}
    r={'schema':1,'model_version':VERSION,'sport':sport,'source':source,'generated_at':utcnow().isoformat(),
        'data_end':history.date.max().date().isoformat(),'data_sha256':digest(history.to_json(orient='records',date_format='iso')),
        'code_sha256':digest(Path(__file__).read_text()),'specification':spec,
        'method':'Ridge score means with paired earlier residual scenarios' if sport=='NBA' else 'Ridge run means with conditional independent non-tie count distributions',
        'selected_variant':variant,'selected_scale_or_dispersion':scale,
        'calibration_comparison':[{'variant':v,'scale_or_dispersion':s,'single_task_mean_brier':x} for x,v,s,_ in scored],
        'partitions':{name:{'n':len(rows),'start':rows[0]['date'],'end':rows[-1]['date']} for name,rows in [('fit',training),('residual',residual_rows),('calibration',cal),('test',test)]},
        'tasks':tasks,'approved':False,'replaces_incumbent':False,'current_forecasts_enabled':False,
        'limitations':['Retrospective comparison on previously inspected archives; a new independent prospective period is required',
            'Fixed half-point total lines are research targets, not observed historical sportsbook markets',
            'No possessions, player availability, pitcher, bullpen, ballpark or lineup inputs',
            'Athletics ATH/OAK franchise identity is reconciled, but relocation/park effects remain unmodeled',
            'Conditioning non-tied final scores does not model overtime/extra-inning rules mechanistically',
            'No individual or joint model approval, sportsbook prices, betting returns or cross-game independence',
            'Day-block intervals do not account for all serial/team dependence or model-selection uncertainty']}
    r['evidence_id']=digest(r);return r


def load_report():
    try:
        value=json.loads((Path(__file__).resolve().parents[1]/'research_assets/team_score_study.json').read_text())
        checksum=value.pop('sha256')
        if digest(value)!=checksum:return None
        if any(r['code_sha256']!=digest(Path(__file__).read_text()) or r['approved'] or r['current_forecasts_enabled'] for r in value['reports'].values()):return None
        return value
    except (OSError,ValueError,KeyError,TypeError):return None


def main():
    import argparse
    from intelligence.recent_nba import load_bundle
    from intelligence.history import load_licensed
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--nba-bundle',type=Path,required=True);p.add_argument('--history-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    nba,sources=load_bundle(a.nba_bundle);mlb=load_licensed('MLB',a.history_dir)
    value={'reports':{'NBA':evaluate(nba,'NBA',sources),'MLB':evaluate(mlb,'MLB',json.loads((a.history_dir/'mlb.source.json').read_text()))}}
    value['sha256']=digest(value);a.output.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    print(json.dumps({s:{'method':r['selected_variant'],'test_n':r['partitions']['test']['n'],'tasks':{k:t['metrics']['binary_brier']['value'] for k,t in r['tasks'].items()}} for s,r in value['reports'].items()}))


if __name__=='__main__':main()
