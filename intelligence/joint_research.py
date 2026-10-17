"""Compatible 2/3-leg contracts and explicit dependence assumptions.

Optional score grids are scenarios, never approved current predictions. A grid
must come from one coherent game model; marginal calibrators are not spliced.
"""
from itertools import combinations
from math import isfinite
from intelligence.domain import utcnow
from intelligence.parlay_research import quote_problem,contradictory_scores,pair_review
from intelligence.parlay_intelligence import physical_game,normalized_constraint,dependencies
from intelligence.quant_decision import selection_format
from intelligence.score_distribution import joint_outcomes


def bounds(probabilities):
    if not probabilities or any(not isfinite(p) or not 0<=p<=1 for p in probabilities):raise ValueError('Valid component probabilities required')
    return [max(0.,sum(probabilities)-len(probabilities)+1),min(probabilities)]


def analyze(legs,now=None,scenarios=None):
    now=now or utcnow();scenarios=scenarios or {}
    if len(legs) not in (2,3):raise ValueError('Two or three legs required')
    quotes=[l.quote for l in legs]
    if len({q.bookmaker for q in quotes})!=1:raise ValueError('One observed sportsbook required')
    if any(quote_problem(q,now) for q in quotes):raise ValueError('Eligible current observations required')
    normalized=[normalized_constraint(q) for q in quotes]
    if contradictory_scores(normalized) or any(pair_review(a,b)[0] for a,b in combinations(normalized,2)):
        raise ValueError('Contradictory, repeated or nested selections')
    groups={}
    for leg in legs:groups.setdefault(physical_game(leg.quote),[]).append(leg)
    components=[];probabilities=[]
    for game,group in groups.items():
        if game in scenarios:
            joint=joint_outcomes(scenarios[game],[l.quote for l in group])
            components.append({'format':'Coherent game scenario; not current calibrated forecast','evidence':joint})
            probabilities.append(joint['all_full_win'])
        elif len(group)==1 and group[0].estimate and group[0].estimate.valid():
            components.append({'format':'Experimental single marginal','probability':group[0].estimate.probability})
            probabilities.append(group[0].estimate.probability)
        else:
            components.append({'format':'Shared-game joint model unavailable','probability':None})
    all_components=len(probabilities)==len(groups)
    return {'format':selection_format(quotes),'legs':len(legs),'dependencies':dependencies(legs),
        'components':components,'joint_probability':None,'joint_validated':False,
        'logical_all_full_win_bounds':bounds(probabilities) if all_components else None,
        'bounds_scope':'Conditional logical bounds on all-full-win, not calibrated intervals; partial settlements remain distinct',
        'independence_assumed':False,'combined_price':None,'executable':False,'parlay_EV':None,
        'note':'No cross-game probability is multiplied. Same-game probabilities require a coherent supplied scenario; no actual ticket or operator settlement is inferred.'}
