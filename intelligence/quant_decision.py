"""Format-neutral publication gate. No new models, requests or wagering."""
from collections import Counter
from itertools import combinations
from intelligence.domain import utcnow
from intelligence.ev import qualify
from intelligence.parlay_research import quote_problem,leg_evidence,build_candidate,contradictory_scores,pair_review
from intelligence.parlay_intelligence import physical_game,normalized_constraint
from intelligence.parlays import analyze

FORMATS=('Single','Same-game parlay','Multi-game parlay','Mixed parlay')


def selection_format(quotes):
    games=[physical_game(q) for q in quotes]
    return 'Single' if len(quotes)==1 else 'Same-game parlay' if len(set(games))==1 else 'Multi-game parlay' if len(set(games))==len(games) else 'Mixed parlay'


def decide(analysis,books=None,now=None,combined_prices=(),joint_estimates=()):
    now=now or utcnow();counts=Counter(q.id for q in analysis.quotes);pool={};options=[];blocked=Counter()
    for q in analysis.quotes:
        if books is not None and q.bookmaker not in books:continue
        if counts[q.id]!=1 or quote_problem(q,now):blocked['Missing/expired/ambiguous eligible Ontario price']+=1;continue
        leg=leg_evidence(q,analysis,now);opportunity,problem=qualify(q,leg.estimate,now)
        if not opportunity:blocked[problem]+=1;continue
        pool[q.id]=(leg,opportunity)
        options.append({'format':'Single','quotes':(q,),'odds':q.odds,'probability':opportunity.estimate.probability,
            'lower':opportunity.estimate.lower,'upper':opportunity.estimate.upper,'ev':opportunity.ev,
            'conservative_ev':opportunity.conservative_ev,'source_updated_at':q.source_updated_at,
            'evidence':opportunity.estimate.evidence_id,'why':'Existing validated model and uncertainty-adjusted value gates pass at this observed individual price.'})
    if len(combined_prices)>100 or len(joint_estimates)>100:raise ValueError('Bounded quoted-ticket evidence required')
    for price in combined_prices:
        ids=tuple(sorted(price.leg_ids))
        if not 2<=len(ids)<=3 or len(set(ids))!=len(ids) or not set(ids)<=pool.keys():continue
        matches=[j for j in joint_estimates if tuple(sorted(j.leg_ids))==ids]
        if len(matches)!=1:blocked['Missing or ambiguous validated joint evidence']+=1;continue
        legs=tuple(pool[i][0] for i in ids);quotes=tuple(l.quote for l in legs)
        normalized=[normalized_constraint(q) for q in quotes]
        if contradictory_scores(normalized) or any(pair_review(a,b)[0] for a,b in combinations(normalized,2)):continue
        candidate,_=build_candidate(legs,analysis,now)
        if not candidate:continue
        try:result=analyze([pool[i][1] for i in ids],price,matches[0],now)
        except (ValueError,TypeError):blocked['Incoherent joint/ticket evidence']+=1;continue
        if result['status']!='qualifying':blocked[result['reason']]+=1;continue
        joint=matches[0]
        options.append({'format':selection_format(quotes),'quotes':quotes,'odds':result['odds'],
            'probability':joint.probability,'lower':joint.lower,'upper':joint.upper,'ev':result['ev'],
            'conservative_ev':result['conservative_ev'],'source_updated_at':price.source_updated_at,
            'evidence':joint.evidence_id,'why':'Existing leg gates, validated joint evidence, actual combined pricing and operator restriction checks pass.'})
    # Same rule for every format; no single/parlay preference or payout objective.
    options.sort(key=lambda o:(-o['conservative_ev']*(1-(o['upper']-o['lower'])),o['upper']-o['lower'],
        -o['probability'],tuple(sorted(q.id for q in o['quotes']))))
    return {'status':'QUALIFYING EVIDENCE AVAILABLE' if options else 'NO QUALIFYING BET',
        'best':options[0] if options else None,'options':options,'qualified_by_format':{kind:sum(o['format']==kind for o in options) for kind in FORMATS},
        'blockers':dict(blocked),'missing_joint_or_combined_price_adapter':not combined_prices,
        'method':'Existing eligibility gates first; conservative EV × (1 − probability-envelope width), narrower envelope, then estimated probability. Same rule for each format; heuristic, not validated portfolio optimality.'}
