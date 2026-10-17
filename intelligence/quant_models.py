"""Offline regularized goal models; no live dispatch or model promotion."""
from collections import Counter
from datetime import date
from math import log,exp
import numpy as np
from intelligence.score_distribution import score_distribution


def design(rows,teams,targets=True):
    index={team:i for i,team in enumerate(teams)};x=np.zeros((len(rows)*2,2+2*len(teams)));y=[]
    for i,r in enumerate(rows):
        for j,(team,opponent,goals) in enumerate(((r['home'],r['away'],r['hg'] if targets else 0),(r['away'],r['home'],r['ag'] if targets else 0))):
            k=2*i+j;x[k,0]=1;x[k,1]=1-j;x[k,2+index[team]]=1;x[k,2+len(teams)+index[opponent]]=1;y.append(goals)
    return x,np.array(y,dtype=float)


def fit_poisson(rows,policy):
    train=[r for r in rows if policy['training_start']<=r['date']<=policy['training_end']]
    if len(train)<300:raise ValueError('Insufficient training matches')
    counts=Counter(t for r in train for t in (r['home'],r['away']))
    teams=sorted(counts);x,y=design(train,teams)
    weights=np.repeat([exp(-log(2)*(date.fromisoformat(policy['calibration_start'])-date.fromisoformat(r['date'])).days/policy['half_life_days']) for r in train],2)
    penalty=np.full(x.shape[1],policy['ridge']);penalty[:2]=[0.,1.]
    beta=np.zeros(x.shape[1]);beta[0]=log(max(.1,float(np.mean(y))))
    def objective(b):
        z=x@b
        if np.max(z)>20:return float('inf')
        return float(np.sum(weights*(np.exp(z)-y*z))+.5*np.sum(penalty*b*b))
    for iteration in range(80):
        mu=np.exp(x@beta);gradient=x.T@(weights*(mu-y))+penalty*beta
        if np.max(np.abs(gradient))<1e-6:break
        hessian=(x.T*(weights*mu))@x+np.diag(penalty)
        step=np.linalg.solve(hessian,gradient);scale=1.;old=objective(beta)
        while scale>1e-7 and objective(beta-scale*step)>old:scale*=.5
        beta-=scale*step
    else:raise ValueError('Poisson fit did not converge')
    return {'teams':teams,'coefficients':beta.tolist(),'team_training_games':dict(counts),
        'training_n':len(train),'training_end':policy['training_end'],'iterations':iteration,
        'method':'Time-weighted ridge Poisson attack/defence with home effect; parameters fixed before calibration'}


def goal_rates(model,row,minimum=16):
    if row['date']<=model['training_end']:raise ValueError('Training outcome cannot receive held-out prediction')
    if any(model['team_training_games'].get(t,0)<minimum for t in (row['home'],row['away'])):
        return None
    x,_=design([row],model['teams'],targets=False);rates=np.exp(x@np.array(model['coefficients']))
    return tuple(float(r) for r in rates) if np.all((rates>=.05)&(rates<=8)) else None


def fit_rho(model,rows,policy):
    # Training likelihood only, no calibration/test outcomes. The model's
    # coefficients are already fitted; bypass held-out API for training rates.
    training=[r for r in rows if policy['training_start']<=r['date']<=policy['training_end']]
    x,_=design(training,model['teams']);rates=np.exp(x@np.array(model['coefficients'])).reshape(-1,2)
    losses=[]
    for rho in policy['rho_grid']:
        score=0.;valid=True
        for r,(h,a) in zip(training,rates):
            tau=(1-h*a*rho,1+h*rho,1+a*rho,1-rho)
            if min(tau)<=0:valid=False;break
            if r['hg']<=1 and r['ag']<=1:score-=log(tau[2*r['hg']+r['ag']])
        if valid:losses.append((score,abs(rho),rho))
    if not losses:raise ValueError('No valid training-only Dixon-Coles correction')
    return min(losses)[2]
