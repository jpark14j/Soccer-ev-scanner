"""Hypothetical loss/exposure arithmetic; never wager execution or profit advice."""
from intelligence.domain import finite


def analyze(bankroll,*,odds=None,probability=None,lower=None,upper=None,validated=False,
            price_verified=False,kelly_fraction=.25,per_bet_cap=.005,portfolio_cap=.02):
    if not finite(bankroll) or not 0<bankroll<=1e9 or not 0<kelly_fraction<=.25 or not 0<per_bet_cap<=.02 or not per_bet_cap<=portfolio_cap<=.05:
        raise ValueError('Invalid hypothetical bankroll or conservative exposure settings')
    rows=[{'stake_fraction':f,'stake':bankroll*f,'maximum_loss':bankroll*f,
           'three_equal_stakes_maximum_loss':3*bankroll*f,
           'exceeds_per_bet_cap':f>per_bet_cap,'exceeds_portfolio_cap_for_three':3*f>portfolio_cap}
          for f in (.0025,.005,.01,.02)]
    result={'bankroll':bankroll,'scenarios':rows,'per_bet_limit':bankroll*per_bet_cap,
        'portfolio_limit':bankroll*portfolio_cap,'kelly_amount':None,'kelly_fraction_of_bankroll':None,
        'sensitivity':[],'reason':'Kelly unavailable: validated probability, uncertainty and a verified actual price are required'}
    valid=(validated and price_verified and finite(odds) and odds>1 and
           all(finite(x) for x in (lower,probability,upper)) and 0<lower<=probability<=upper<1)
    if not valid:
        return result
    if upper-lower>.15+1e-12:
        result['reason']='Avoid sizing from this model: the supplied probability interval is too wide'
        return result
    def fractional(p):
        return min(per_bet_cap,max(0.,(odds*p-1)/(odds-1))*kelly_fraction)
    fraction=fractional(lower)
    result.update(kelly_amount=bankroll*fraction,kelly_fraction_of_bankroll=fraction,
        reason='Conservative lower-probability fractional Kelly, capped per bet; it is not an exact profitable stake')
    if fraction==0:
        result['reason']='Avoid the wager under the lower probability: no positive uncertainty-adjusted edge'
    result['sensitivity']=[{'assumed_probability':p,'estimated_ev':p*odds-1,
        'capped_fraction':fractional(p),'hypothetical_amount':bankroll*fractional(p)} for p in (lower,probability,upper)]
    return result
