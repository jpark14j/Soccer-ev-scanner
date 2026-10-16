"""Fixed, shrunk, time-decayed Poisson goal-strength research model.

Only earlier UTC dates enter features. Full-time source results are not accepted
ticket settlement, xG, injuries, lineups or verified historical publication times.
"""
from datetime import date
from math import exp, log
from copy import deepcopy


def empty_state(day):
    return {'anchor':day,'n':0,'w':0.,'hg':0.,'ag':0.,'latest':None,'teams':{}}


def advance(state,day,policy):
    delta=(date.fromisoformat(day)-date.fromisoformat(state['anchor'])).days
    if delta<0:
        raise ValueError('Cannot backdate model features')
    factor=exp(-log(2)*delta/policy['half_life_days'])
    for key in ('w','hg','ag'):
        state[key]*=factor
    for values in state['teams'].values():
        for key in ('w','gf','ga'):
            values[key]*=factor
        values['w2']*=factor**2
    state['anchor']=day


def add_result(state,row,policy):
    if row['date']>=state['anchor']:
        raise ValueError('Same-day or future outcome cannot enter pregame features')
    age=(date.fromisoformat(state['anchor'])-date.fromisoformat(row['date'])).days
    weight=exp(-log(2)*age/policy['half_life_days'])
    state['n']+=1;state['w']+=weight
    state['hg']+=weight*row['hg'];state['ag']+=weight*row['ag']
    state['latest']=max(state['latest'] or row['date'],row['date'])
    for name,gf,ga in ((row['home'],row['hg'],row['ag']),(row['away'],row['ag'],row['hg'])):
        v=state['teams'].setdefault(name,{'n':0,'w':0.,'w2':0.,'gf':0.,'ga':0.,'latest':row['date']})
        v['n']+=1;v['w']+=weight;v['w2']+=weight**2
        v['gf']+=weight*gf;v['ga']+=weight*ga;v['latest']=max(v['latest'],row['date'])


def fit(rows,day,policy):
    state=empty_state(day)
    for row in rows:
        if row['date']<day:
            add_result(state,row,policy)
    return state


def rates(state,home,away,day,policy):
    state=deepcopy(state);advance(state,day,policy)
    if state['n']<policy['minimum_league_games'] or state['w']<=0:
        return None,'Fewer than required prior league results'
    values=[state['teams'].get(home),state['teams'].get(away)]
    for name,v in zip((home,away),values):
        if not v or v['n']<policy['minimum_team_games']:
            return None,f'{name}: fewer than {policy["minimum_team_games"]} prior team results'
        effective=v['w']**2/v['w2'] if v['w2'] else 0
        if effective<policy['minimum_effective_team_games']:
            return None,f'{name}: insufficient effective weighted sample'
    lh,la=state['hg']/state['w'],state['ag']/state['w']
    mean=(lh+la)/2
    if min(lh,la,mean)<=0:
        return None,'Degenerate historical scoring distribution'
    prior=policy['prior_team_games']
    attack=[(v['gf']+prior*mean)/(v['w']+prior)/mean for v in values]
    defence=[(v['ga']+prior*mean)/(v['w']+prior)/mean for v in values]
    return (lh*attack[0]*defence[1],la*attack[1]*defence[0]),''


def probabilities(home_rate,away_rate):
    total=home_rate+away_rate
    return {'btts':(1-exp(-home_rate))*(1-exp(-away_rate)),
            'totals_2.5':1-exp(-total)*(1+total+total*total/2)}
