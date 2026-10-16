"""Dependence-aware analysis without inventing a joint model or book price."""
from dataclasses import dataclass
from intelligence.domain import finite, parse_time, utcnow
from intelligence.ev import expected_value, qualify

NO_PARLAYS = 'No qualifying parlay opportunities identified today.'
CATEGORIES = ('Lower-variance', 'Balanced', 'Higher-variance')


def joint_bounds(probabilities):
    if len(probabilities) < 2 or any(not finite(p) or not 0 <= p <= 1 for p in probabilities):
        raise ValueError('At least two valid leg probabilities required')
    # Frechet bounds remain valid under arbitrary dependence.
    return max(0., sum(probabilities)-len(probabilities)+1), min(probabilities)


@dataclass(frozen=True)
class CombinedPrice:
    bookmaker: str
    leg_ids: tuple[str, ...]
    odds: float
    source_updated_at: str
    restrictions_verified: bool
    evidence_source: str


@dataclass(frozen=True)
class JointEstimate:
    probability: float
    lower: float
    upper: float
    leg_ids: tuple[str, ...]
    evidence_id: str
    validated: bool


def analyze(legs, combined=None, joint=None, now=None):
    if len(legs) < 2 or len(legs) > 6:
        raise ValueError('Select two to six legs')
    now = now or utcnow()
    ids = tuple(sorted(o.quote.id for o in legs))
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate parlay legs')
    for i,a in enumerate(legs):
        for b in legs[i+1:]:
            if (a.quote.provider,a.quote.event_id,a.quote.market)==(b.quote.provider,b.quote.event_id,b.quote.market) and a.quote.market=='h2h' and a.quote.selection!=b.quote.selection:
                raise ValueError('Mutually exclusive match winners cannot form a parlay')
    bounds = joint_bounds([o.estimate.probability for o in legs])
    result = {'status':'theoretical', 'probability_bounds':bounds, 'odds':None, 'ev':None,
              'reason':'No validated joint estimate and sportsbook-specific combined price', 'category':None}
    # Bounds are all that can be asserted without calibrated dependence data.
    if any(qualify(o.quote,o.estimate,now)[0] is None for o in legs):
        result['reason'] = 'Every leg must remain eligible for publication'
        return result
    if joint is None or combined is None:
        return result
    if not joint.validated or not joint.evidence_id or tuple(sorted(joint.leg_ids)) != ids:
        return result
    if not all(finite(x) for x in (joint.lower,joint.probability,joint.upper)) or not 0 <= joint.lower <= joint.probability <= joint.upper <= 1 or not bounds[0] <= joint.probability <= bounds[1]:
        raise ValueError('Incoherent joint probability')
    if tuple(sorted(combined.leg_ids)) != ids or not combined.restrictions_verified or not combined.evidence_source:
        return result
    if any(o.quote.bookmaker != combined.bookmaker or o.quote.status(now) != 'current' for o in legs):
        return result
    age = (now-parse_time(combined.source_updated_at)).total_seconds()
    if not 0 <= age <= 300 or not finite(combined.odds) or combined.odds <= 1:
        return result
    conservative = expected_value(joint.lower,combined.odds)
    if conservative < .02:
        result['reason'] = 'No positive value after joint uncertainty'
        return result
    category = 'Lower-variance' if len(legs)==2 and joint.probability>=.5 else 'Balanced' if len(legs)<=3 and joint.probability>=.25 else 'Higher-variance'
    return result | {'status':'qualifying', 'odds':combined.odds,
        'probability':joint.probability,'ev':expected_value(joint.probability,combined.odds),
        'conservative_ev':conservative,'category':category,'reason':'Validated joint model and actual combined quote passed checks'}
