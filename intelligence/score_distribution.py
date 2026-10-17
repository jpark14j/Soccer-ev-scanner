"""Coherent regulation soccer score research, not a validated betting forecast.

All joint events use one score matrix. Binary calibration maps cannot be spliced
into it. Ticket acceptance/settlement and combined prices need separate evidence.
"""
from dataclasses import dataclass
from math import exp,isfinite,floor,ceil
import numpy as np


@dataclass(frozen=True)
class ScoreDistribution:
    mass: np.ndarray
    omitted_mass_bound: float
    temperature: float
    rho: float
    validated: bool = False
    scope: str = 'source-reported regulation full-time score; operator rules unverified'


def poisson_weights(rate,limit):
    values=[exp(-rate)]
    for n in range(1,limit+2):values.append(values[-1]*rate/n)
    return np.array(values)


def score_distribution(home_rate,away_rate,rho=0.,temperature=1.,limit=40):
    if (not all(isinstance(v,(float,int)) and not isinstance(v,bool) and isfinite(v) for v in (home_rate,away_rate,rho,temperature))
        or not .05<=home_rate<=8 or not .05<=away_rate<=8 or not .5<=temperature<=2
        or type(limit) is not int or not 20<=limit<=60):
        raise ValueError('Outside reviewed score-research bounds')
    h=poisson_weights(home_rate,limit)**(1/temperature)
    a=poisson_weights(away_rate,limit)**(1/temperature)
    tau=np.array([[1-home_rate*away_rate*rho,1+home_rate*rho],[1+away_rate*rho,1-rho]])
    if np.any(tau<=0):raise ValueError('Invalid Dixon-Coles low-score correction')
    mass=np.outer(h[:-1],a[:-1]);mass[:2,:2]*=tau**(1/temperature)
    total=mass.sum()
    # Geometric upper bound for each tail of the tempered Poisson weights.
    ht=h[-1]/(1-(home_rate/(limit+2))**(1/temperature))
    at=a[-1]/(1-(away_rate/(limit+2))**(1/temperature))
    tail=ht*a[:-1].sum()+at*h[:-1].sum()+ht*at
    omitted=float(tail/(total+tail))
    if omitted>1e-8:raise ValueError('Score-tail bound too wide; no research probability')
    return ScoreDistribution(mass/total,omitted,float(temperature),float(rho))


def marginals(distribution):
    mass=distribution.mass;h,a=np.indices(mass.shape)
    return {'btts':float(mass[(h>0)&(a>0)].sum()),'totals_2.5':float(mass[h+a>2.5].sum()),
        'home_win':float(mass[h>a].sum()),'draw':float(mass[h==a].sum()),'away_win':float(mass[h<a].sum())}


def settlement(market,selection,point,home,away,home_score,away_score):
    """Fractional win/push/loss at the score target, not operator settlement.

    Quarter Asian lines split equally into adjacent integer/half lines. No payout
    or combined ticket treatment is inferred from these fractions.
    """
    if any(type(s) is not int or s<0 for s in (home_score,away_score)):raise ValueError('Invalid score')
    if market=='h2h':
        if selection not in (home,away,'Draw') or point is not None:raise ValueError('Unknown winner contract')
        result=(home_score>away_score if selection==home else away_score>home_score if selection==away else home_score==away_score)
        return (1.,0.,0.) if result else (0.,0.,1.)
    if market=='btts':
        if selection.lower() not in ('yes','no') or point is not None:raise ValueError('Unknown BTTS contract')
        win=((home_score>0 and away_score>0)==(selection.lower()=='yes'))
        return (1.,0.,0.) if win else (0.,0.,1.)
    if (market not in ('totals','spreads') or not isinstance(point,(int,float)) or isinstance(point,bool)
        or not isfinite(point) or abs(point*4-round(point*4))>1e-8):raise ValueError('Unsupported score contract')
    if market=='totals' and (point<0 or selection.lower() not in ('over','under')):raise ValueError('Unknown total')
    if market=='spreads' and selection not in (home,away):raise ValueError('Unknown handicap')
    lines=(floor(point*2)/2,ceil(point*2)/2)
    result=[0.,0.,0.]
    for line in lines:
        difference=((home_score+away_score-line)*(1 if selection.lower()=='over' else -1) if market=='totals' else
            home_score-away_score+line if selection==home else away_score-home_score+line)
        result[0 if difference>0 else 1 if difference==0 else 2]+=.5
    return tuple(result)


def state_label(fractions):
    return {(1.,0.,0.):'win',(0.,1.,0.):'push',(0.,0.,1.):'loss',
        (.5,.5,0.):'half-win',(0.,.5,.5):'half-loss'}[fractions]


def joint_outcomes(distribution,quotes):
    from intelligence.parlay_intelligence import physical_game,team_ids
    if len(quotes) not in (1,2,3) or any(q.sport!='Soccer' for q in quotes):raise ValueError('Soccer score research only')
    if len({physical_game(q) for q in quotes})!=1:raise ValueError('One physical game required; no cross-game independence')
    if len({q.key for q in quotes})!=len(quotes):raise ValueError('Repeated selection')
    anchor=quotes[0];states={};individual=np.zeros(len(quotes))
    for h in range(distribution.mass.shape[0]):
        for a in range(distribution.mass.shape[1]):
            labels=[]
            for i,q in enumerate(quotes):
                # Feed orientation may differ between equivalent physical games.
                same=team_ids(q)[0]==team_ids(anchor)[0]
                fractions=settlement(q.market,q.selection,q.point,q.home,q.away,h if same else a,a if same else h)
                labels.append(state_label(fractions));individual[i]+=distribution.mass[h,a]*fractions[0]
            state=tuple(labels);states[state]=states.get(state,0.)+float(distribution.mass[h,a])
    return {'status':'Experimental coherent score research; not a calibrated/validated joint forecast',
        'joint_validated':False,'all_full_win':states.get(tuple('win' for _ in quotes),0.),
        'states':[{'leg_outcomes':list(k),'probability':v} for k,v in sorted(states.items())],
        'individual_win_fractions':individual.tolist(),'omitted_mass_bound':distribution.omitted_mass_bound,
        'combined_odds':None,'parlay_ev':None,'operator_settlement_verified':False,
        'note':'Outcomes are enumerated from one score matrix, not multiplied marginal estimates. Push/half outcomes are separate; sportsbook ticket treatment and genuine pricing are unavailable.'}
