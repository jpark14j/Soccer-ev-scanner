"""Competition-local venue goal strengths, with separate prior-date features."""
from math import exp,log
from datetime import date
from copy import deepcopy


def fit(rows,day,policy):
    prior=[r for r in rows if r['date']<day]
    state={'n':len(prior),'w':0.,'hg':0.,'ag':0.,'latest':None,'teams':{},'as_of':day}
    for row in prior:
        w=exp(-log(2)*(date.fromisoformat(day)-date.fromisoformat(row['date'])).days/policy['half_life_days'])
        state['w']+=w;state['hg']+=w*row['hg'];state['ag']+=w*row['ag']
        state['latest']=max(state['latest'] or row['date'],row['date'])
        for name,venue,gf,ga in ((row['home'],'home',row['hg'],row['ag']),(row['away'],'away',row['ag'],row['hg'])):
            team=state['teams'].setdefault(name,{'n':0,'w':0.,'w2':0.,'last':row['date'],'recent':[],
                'home':{'w':0.,'gf':0.,'ga':0.},'away':{'w':0.,'gf':0.,'ga':0.}})
            team['n']+=1;team['w']+=w;team['w2']+=w*w;team['last']=max(team['last'],row['date'])
            team['recent'].append([row['date'],gf,ga]);team['recent']=sorted(team['recent'])[-5:]
            v=team[venue];v['w']+=w;v['gf']+=w*gf;v['ga']+=w*ga
    return state


def predict(state,home,away,day,policy):
    if day<state['as_of']:
        return None,'Cannot use future-fitted state for an earlier event'
    if state['n']<policy['minimum_league_games'] or state['w']<=0:
        return None,'Insufficient competition history'
    for name in (home,away):
        t=state['teams'].get(name)
        if not t or t['n']<policy['minimum_team_games']:
            return None,f'{name}: fewer than {policy["minimum_team_games"]} earlier team games'
        if t['w']**2/t['w2']<policy['minimum_effective_team_games']:
            return None,f'{name}: insufficient effective weighted team sample'
    lh,la=state['hg']/state['w'],state['ag']/state['w']
    if min(lh,la)<=0:return None,'Degenerate league scoring distribution'
    # Moving state to the future decays observations and their prior weight;
    # fitted league rates stay ratios. Team venue rates shrink back to the league.
    decay=exp(-log(2)*(date.fromisoformat(day)-date.fromisoformat(state['as_of'])).days/policy['half_life_days'])
    prior=policy['prior_venue_games'];h=state['teams'][home]['home'];a=state['teams'][away]['away']
    def rate(v,key,mean):return (decay*v[key]+prior*mean)/(decay*v['w']+prior)
    home_rate=rate(h,'gf',lh)*rate(a,'ga',lh)/lh
    away_rate=rate(a,'gf',la)*rate(h,'ga',la)/la
    total=home_rate+away_rate
    return {'btts':(1-exp(-home_rate))*(1-exp(-away_rate)),
        'totals_2.5':1-exp(-total)*(1+total+total**2/2),
        'home_rate':home_rate,'away_rate':away_rate},''


def extend(state,rows,day,policy):
    """Append only genuinely new prior-date results, preserving frozen calibration."""
    if day<state['as_of'] or any(r['date']>=day for r in rows):raise ValueError('Future incremental feature data')
    result=deepcopy(state)
    factor=exp(-log(2)*(date.fromisoformat(day)-date.fromisoformat(state['as_of'])).days/policy['half_life_days'])
    for key in ('w','hg','ag'):result[key]*=factor
    for team in result['teams'].values():
        team['w']*=factor;team['w2']*=factor**2
        for venue in ('home','away'):
            for key in ('w','gf','ga'):team[venue][key]*=factor
    extra=fit(rows,day,policy)
    for key in ('n','w','hg','ag'):result[key]+=extra[key]
    if extra['latest']:result['latest']=max(result['latest'],extra['latest'])
    for name,t in extra['teams'].items():
        if name not in result['teams']:result['teams'][name]=t;continue
        existing=result['teams'][name]
        for key in ('n','w','w2'):existing[key]+=t[key]
        existing['last']=max(existing['last'],t['last'])
        existing['recent']=sorted(existing['recent']+t['recent'])[-5:]
        for venue in ('home','away'):
            for key in ('w','gf','ga'):existing[venue][key]+=t[venue][key]
    result['as_of']=day
    return result
