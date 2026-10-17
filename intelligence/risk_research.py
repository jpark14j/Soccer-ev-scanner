"""Defined research ranking, not validated EV, a Sharpe ratio or approval.

The supplied ranges are historical calibration envelopes. They are not
event-specific posterior intervals or guaranteed probability bounds.
"""
from intelligence.research_ranking import evidence_key,comparison,count

VERSION='risk-research-1'
MOST_LIKELY='MOST LIKELY TO WIN'
RISK_ADJUSTED='BEST RISK-ADJUSTED RESEARCH OPPORTUNITY'
PARLAY='BEST SUPPORTED RESEARCH PARLAY'


def sensitivity(leg):
    e=leg.estimate;gap=comparison(leg);width=e.upper-e.lower
    ratio=gap['difference_envelope'][0]/width if width>0 else None
    return {'version':VERSION,'break_even':gap['sportsbook_break_even'],
        'model_difference':gap['difference'],'difference_envelope':gap['difference_envelope'],
        'range_width':width,'lower_margin_per_range':ratio,
        'model_loss_probability':1-e.probability,
        'price_support_across_supplied_range':gap['difference_envelope'][0]>0 and width>0,
        'current_model_disagreement':None,
        'disagreement_limitation':'No independently supported event-level challenger comparison is available',
        'estimated_EV':None,'approved':False,
        'interpretation':'Lower model-minus-break-even margin divided by supplied calibration-range width; research sensitivity only, not validated value or a confidence bound'}


def rank(legs,now):
    # Caller has already applied existing consistency, source and display gates.
    likely=sorted(legs,key=lambda l:(-l.estimate.probability,*evidence_key(l,now)))
    supported=[l for l in legs if sensitivity(l)['price_support_across_supplied_range']]
    supported.sort(key=lambda l:(-sensitivity(l)['lower_margin_per_range'],
        l.estimate.upper-l.estimate.lower,-count(l.model_details,'calibration_bin_n'),
        -count(l.model_details,'test_n'),1-l.estimate.probability,*evidence_key(l,now)))
    best=supported[0] if supported else None
    return {'version':VERSION,'most_likely':likely,'risk_adjusted':supported,
        'best_risk_adjusted':best,'default':best or (likely[0] if likely else None),
        'default_mode':'Range-supported price research' if best else 'Probability-based fallback; risk-adjusted value not established',
        'method':'Existing gates first. Require a nonzero calibration range wholly above observed break-even for the price-research ranking. Rank (lower minus break-even) / range width, then width, calibration/test support, loss probability and existing evidence. No EV, payout or approval objective.',
        'limitations':['Historical bucket uncertainty is not current-event uncertainty',
            'An unfavorable price can accompany the most likely outcome',
            'Historical performance and model disagreement remain in evidence; absent event-level sensitivity is not assumed zero',
            'Singles and parlays are not compared by invented joint risk-adjusted returns']}
