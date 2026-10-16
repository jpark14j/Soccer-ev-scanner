"""Bounded daily parlay research from current Ontario observations, never picks.

No joint probability, executable price or parlay EV is inferred from singles.
The existing evidence-gated parlay analyzer remains separate and unchanged.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from itertools import combinations, zip_longest
import math
from intelligence.domain import Estimate, Quote, digest, finite, parse_time, utcnow
from intelligence.ev import expected_value
from intelligence.parlays import CATEGORIES, joint_bounds
from intelligence.registry import eligible_book
from intelligence.soccer import canonical

SPORTS = ('NBA','Soccer','MLB')
MARKETS = ('h2h','spreads','totals')


@dataclass(frozen=True)
class ResearchLeg:
    quote: Quote
    implied_probability: float
    estimate: Estimate | None = None
    model_status: str = 'missing'
    model_details: dict = field(default_factory=dict)
    blockers: tuple[str,...] = ()
    estimated_ev: float | None = None


@dataclass(frozen=True)
class ResearchCandidate:
    id: str
    legs: tuple[ResearchLeg,...]
    category: str
    theoretical_odds: float
    probability_bounds: tuple[float,float] | None
    uncertainty_bounds: tuple[float,float] | None
    warnings: tuple[str,...]
    blockers: tuple[str,...]
    rank_key: tuple
    rank_explanation: str
    # The configured feed has no actual combined-price or joint-model adapter.
    status: str = 'research only'
    combined_price_status: str = 'theoretical product; not an available sportsbook offer'
    executable: bool = False
    combined_odds: float | None = None
    joint_probability: float | None = None
    parlay_ev: float | None = None


@dataclass
class ResearchSelection:
    candidates: list[ResearchCandidate] = field(default_factory=list)
    exclusions: dict = field(default_factory=dict)
    eligible_quotes: int = 0
    searched_quotes: int = 0
    examined_combinations: int = 0
    candidate_count: int = 0
    checked_at: str = ''


def event_identity(q):
    """Catch a duplicated physical game even if a feed assigns another event ID.

    Exact scheduled times distinguish MLB doubleheaders; shared teams at different
    times are warned about instead of silently assumed independent.
    """
    return (q.sport,tuple(sorted((canonical(q.home),canonical(q.away)))),parse_time(q.commence_time))


def same_event(a,b):
    return (a.provider,a.event_id)==(b.provider,b.event_id) or event_identity(a)==event_identity(b)


def pair_review(a,b):
    """Return a rejection reason and explicit dependence warnings."""
    warnings=[]
    shared = bool({canonical(a.home),canonical(a.away)} & {canonical(b.home),canonical(b.away)})
    if same_event(a,b):
        warnings.append('Same event: outcomes are dependent; sportsbook same-game restrictions are unknown.')
        if a.market==b.market=='h2h':
            if canonical(a.selection)==canonical(b.selection):
                return 'Duplicate or shared match-winner outcome',warnings
            return 'Contradictory match winners in the same event',warnings
        if a.market==b.market and canonical(a.participant)==canonical(b.participant):
            if canonical(a.selection)==canonical(b.selection):
                return 'Repeated or nested outcome in the same event and market',warnings
            if a.market=='totals':
                over = a if a.selection.lower()=='over' else b
                under = b if over is a else a
                if math.floor(over.point)+1 >= under.point:
                    return 'Contradictory totals: both legs cannot win',warnings
            elif a.market=='spreads' and a.point+b.point<=0:
                return 'Contradictory spreads: both legs cannot win',warnings
        # Winner plus opponent spread cannot both win when the opponent must win.
        if {a.market,b.market}=={'h2h','spreads'}:
            winner = a if a.market=='h2h' else b
            spread = b if winner is a else a
            if winner.selection!='Draw' and canonical(winner.selection)!=canonical(spread.selection) and spread.point<=0:
                return 'Contradictory winner and opponent spread',warnings
    elif a.sport==b.sport and shared:
        warnings.append('Shared team across events: fatigue, lineups and common form may create dependence (including doubleheaders).')
    if a.participant and canonical(a.participant)==canonical(b.participant) and a.sport==b.sport:
        warnings.append('Shared player: selections may depend on the same player availability or performance.')
    return '',warnings


def contradictory_scores(quotes):
    """Check integer-score feasibility, including contradictions across 3 legs.

    Full-game featured markets constrain score difference D and total T. Scores
    are nonnegative integers, so T >= abs(D) and T/D have the same parity. No
    predictive distribution or independence assumption enters this check.
    """
    for anchor in quotes:
        group=[q for q in quotes if same_event(anchor,q)]
        if len(group)<2:
            continue
        low,high,tmin,tmax=-math.inf,math.inf,0,math.inf
        for q in group:
            home=canonical(q.selection)==canonical(anchor.home)
            if q.market=='h2h':
                if q.selection=='Draw':
                    low,high=max(low,0),min(high,0)
                elif home:
                    low=max(low,1)
                else:
                    high=min(high,-1)
            elif q.market=='spreads':
                if home:
                    low=max(low,math.floor(-q.point)+1)
                else:
                    high=min(high,math.ceil(q.point)-1)
            elif q.selection.lower()=='over':
                tmin=max(tmin,math.floor(q.point)+1)
            else:
                tmax=min(tmax,math.ceil(q.point)-1)
        closest=0 if low<=0<=high else low if low>0 else high
        feasible=False
        for difference in (closest,closest-1,closest+1,-2,-1,0,1,2):
            if not low<=difference<=high or (anchor.sport!='Soccer' and difference==0):
                continue
            total=max(tmin,abs(difference))
            total += (total-difference)%2
            if total<=tmax:
                feasible=True
                break
        if not feasible:
            return True
    return False


def quote_problem(q,now):
    if q.sport not in SPORTS:
        return 'Unsupported sport'
    if q.status(now)!='current':
        return q.status(now)
    if q.provider!='the-odds-api' or q.jurisdiction!='CA-ON' or not eligible_book(q.bookmaker,now):
        return 'Ontario provider provenance unavailable or registry expired'
    if q.market not in MARKETS or q.participant:
        return 'Market needs a dedicated settlement and correlation adapter'
    if q.market=='h2h':
        if q.point is not None or q.selection not in ([q.home,'Draw',q.away] if q.sport=='Soccer' else [q.home,q.away]):
            return 'Unsupported match-winner selection'
    elif not finite(q.point):
        return 'Spread/total line is missing or invalid'
    elif q.market=='totals' and (q.selection.lower() not in ('over','under') or q.point<0):
        return 'Unsupported total selection'
    elif q.market=='spreads' and q.selection not in (q.home,q.away):
        return 'Unsupported spread selection'
    return ''


def leg_evidence(q,analysis,now):
    rows=[r for r in analysis.research if r.get('quote_id')==q.id]
    details=rows[0] if len(rows)==1 else {}
    estimate=getattr(analysis,'estimates',{}).get(q.id)
    if estimate is None:
        estimate=next((o.estimate for o in analysis.opportunities if o.quote==q),None)
    usable=False
    if estimate is not None:
        try:
            usable=(estimate.valid() and (estimate.sport,estimate.league,estimate.market)==(q.sport,q.league,q.market)
                    and parse_time(estimate.training_end)<min(now,parse_time(q.commence_time)))
        except (ValueError,TypeError):
            pass
    if not usable:
        estimate=None
    blockers=list(details.get('blockers',[]))
    if estimate is None:
        blockers.append('No source-backed, market-specific model estimate is available for this leg.')
    elif not estimate.validated or not estimate.evidence_id:
        blockers.append('The leg model has not passed publication validation against a timestamped market baseline.')
    if estimate is not None and (now-parse_time(estimate.training_end)).days>90:
        blockers.append('Model history is more than 90 days old; it cannot establish current predictive reliability.')
    status=('validated' if estimate and estimate.validated and estimate.evidence_id and not blockers else
            'research' if estimate else 'missing')
    ev=expected_value(estimate.probability,q.odds) if status=='validated' and q.market=='h2h' else None
    return ResearchLeg(q,1/q.odds,estimate,status,details,tuple(dict.fromkeys(blockers)),ev)


def research_category(quotes,product):
    # Price/leg-count proxies, never empirical or probability-based risk ratings.
    if len(quotes)==2 and max(q.odds for q in quotes)<=1.8:
        return CATEGORIES[0]
    if product<=6:
        return CATEGORIES[1]
    return CATEGORIES[2]


def balanced_pool(legs,limit):
    """Round-robin sports/events before alternate sides; bounded, deterministic."""
    sports=defaultdict(lambda:defaultdict(list))
    for leg in legs:
        sports[leg.quote.sport][event_identity(leg.quote)].append(leg)
    ordered=[]
    queues=[]
    for sport in SPORTS:
        events=sports[sport]
        groups=[]
        for _,group in sorted(events.items(),key=lambda item:item[0][2]):
            groups.append(sorted(group,key=lambda l:(l.model_status!='validated',l.model_status=='missing',
                l.quote.odds,l.quote.selection,l.quote.id)))
        queue=[leg for batch in zip_longest(*groups) for leg in batch if leg is not None]
        queues.append(queue)
    for batch in zip_longest(*queues):
        ordered.extend(leg for leg in batch if leg is not None)
    return ordered[:limit]


def select_candidates(analysis, *, sports=SPORTS, bookmakers=None, leg_counts=(2,3),
                      categories=CATEGORIES, max_results=3, pool_per_book=24, now=None):
    now=now or utcnow()
    if not set(sports)<=set(SPORTS) or not set(leg_counts)<={2,3} or not set(categories)<=set(CATEGORIES):
        raise ValueError('Unsupported parlay research filter')
    if not 0<=max_results<=3 or not 3<=pool_per_book<=30:
        raise ValueError('Research search limits are outside the supported range')
    result=ResearchSelection(checked_at=now.isoformat())
    exclusions=Counter()
    counts=Counter()
    for q in analysis.quotes:
        try:
            counts[q.id]+=1
        except (ValueError,TypeError):
            # Nonfinite/invalid line identities are rejected below, rather than
            # making the whole page fail while forming provenance IDs.
            continue
    by_book=defaultdict(list)
    for q in analysis.quotes:
        if q.sport not in sports or (bookmakers is not None and q.bookmaker not in bookmakers):
            continue
        problem=quote_problem(q,now)
        if not problem and counts[q.id]>1:
            problem='Ambiguous duplicate provider quote'
        if problem:
            exclusions[problem]+=1
            continue
        by_book[(q.provider,q.bookmaker)].append(leg_evidence(q,analysis,now))
        result.eligible_quotes+=1
    candidates=[]
    for (_,book),legs in sorted(by_book.items()):
        pool=balanced_pool(legs,pool_per_book)
        result.searched_quotes+=len(pool)
        for n in sorted(set(leg_counts)):
            for combo in combinations(pool,n):
                result.examined_combinations+=1
                quotes=[leg.quote for leg in combo]
                warnings=[]
                rejected=''
                for a,b in combinations(quotes,2):
                    reason,notes=pair_review(a,b)
                    warnings.extend(notes)
                    if reason:
                        rejected=reason
                        break
                if rejected:
                    exclusions[rejected]+=1
                    continue
                if contradictory_scores(quotes):
                    exclusions['Contradictory score constraints across parlay legs']+=1
                    continue
                product=math.prod(q.odds for q in quotes)
                if not math.isfinite(product):
                    exclusions['Invalid theoretical price product']+=1
                    continue
                category=research_category(quotes,product)
                if category not in categories:
                    continue
                if any(q.market in ('totals','spreads') and q.point%1==0 for q in quotes):
                    warnings.append('Integer line: pushes/voids can change settlement and the payout; the product assumes every leg wins.')
                warnings.append('Dependence is unmeasured, including across different games or sports. No independence assumption or multiplied win probability is used.')
                blockers=[f'Leg {i+1}: {reason}' for i,leg in enumerate(combo) for reason in leg.blockers]
                blockers.extend(['No validated joint probability model covers these exact legs.',
                    'The configured provider supplies no actual combined parlay price for these legs.',
                    'Sportsbook-specific parlay acceptance, combination restrictions and settlement rules are unverified.'])
                estimates=[leg.estimate for leg in combo]
                bounds=joint_bounds([e.probability for e in estimates]) if all(estimates) else None
                interval_bounds=(max(0.,sum(e.lower for e in estimates)-n+1),min(e.upper for e in estimates)) if all(estimates) else None
                validated=sum(leg.model_status=='validated' for leg in combo)
                researched=sum(leg.estimate is not None for leg in combo)
                width=sum((e.upper-e.lower) if e else 1. for e in estimates)/n
                age=max((now-parse_time(q.source_updated_at)).total_seconds() for q in quotes)
                # No odds/payout/EV optimization or sportsbook preference. Leg
                # fractions avoid rewarding three legs just for adding a model.
                rank=(-validated/n,-researched/n,len(set(warnings))-1,width,age,n,
                      tuple(sorted(q.id for q in quotes)))
                explanation=(f'{n}/{n} individual prices are current at the same Ontario sportsbook; '
                    f'{validated}/{n} validated leg models, {researched}/{n} model estimates; '
                    f'mean supplied interval width {width:.3f} (missing models count as 1); '
                    f'oldest source observation {age:.0f} seconds old; '
                    'rank uses model-evidence fractions, explicit dependence flags, interval width, freshness and fewer legs, in that order. '
                    'Price availability is an entry gate; combined prices are unavailable. Ranking is research priority, not estimated profit.')
                candidates.append(ResearchCandidate(digest((book,tuple(sorted(q.id for q in quotes)))),combo,
                    category,product,bounds,interval_bounds,tuple(dict.fromkeys(warnings)),tuple(dict.fromkeys(blockers)),rank,explanation))
    candidates.sort(key=lambda c:c.rank_key)
    result.candidate_count=len(candidates)
    # At most one candidate per physical event set, even across books. This
    # avoids presenting alternate sides/book prices as three distinct ideas.
    seen=set()
    for candidate in candidates:
        identity=tuple(sorted(event_identity(leg.quote) for leg in candidate.legs))
        if identity in seen:
            continue
        seen.add(identity)
        if len(result.candidates)<max_results:
            result.candidates.append(candidate)
        else:
            break
    result.exclusions=dict(exclusions)
    return result
