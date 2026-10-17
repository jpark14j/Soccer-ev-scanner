"""Model-first parlay research from trusted application estimates, with no I/O.

No probabilities are inferred from prices. Separate games are not declared
independent; no joint point estimate, executable ticket price or EV is invented.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from itertools import combinations
from math import isclose
from intelligence.domain import utcnow, parse_time, digest
from intelligence.markets import CATALOG, is_half_line
from intelligence.parlay_research import (quote_problem, leg_evidence, build_candidate,
    same_event, contradictory_scores)
from intelligence.research_ranking import evidence_problem, evidence_key, comparison, count
from intelligence.soccer import canonical


def team_ids(q):
    from intelligence.competitions import COMPETITIONS
    from intelligence.data_adapters import team_identity
    try:
        c=COMPETITIONS[q.league]
        return team_identity(c,q.home)[0],team_identity(c,q.away)[0]
    except (ValueError,KeyError):
        return canonical(q.home),canonical(q.away)


def physical_game(q):
    return q.sport,q.league,tuple(sorted(team_ids(q))),parse_time(q.commence_time).isoformat()


def binary_market(q):
    """Return common market identity and side; integer/quarter lines can push."""
    h,a=team_ids(q)
    line=q.point
    if q.market=='btts':
        side=q.selection.lower()
    elif q.market=='h2h' and q.sport in ('NBA','MLB'):
        side=h if q.selection==q.home else a
    elif q.market=='spreads' and is_half_line(line):
        side=h if q.selection==q.home else a
        # Store the handicap on the lexically first team, independent of feed
        # orientation. Home -3.5 and Away +3.5 are opposing sides of one line.
        line=q.point if side==min(h,a) else -q.point
    elif CATALOG[q.market].kind in ('total','player','corners') and is_half_line(line):
        side=q.selection.lower()
    else:
        return None,None
    return (physical_game(q),q.market,line,canonical(q.participant)),side


@dataclass
class SelectionGroup:
    id: str
    market_key: tuple
    offers: tuple
    preferred: object = None
    preferred_side: str = ''
    problem: str = ''
    model_favored: bool = False
    research_eligible: bool = False


def coherent_envelopes(by_side):
    a,b=(legs[0].estimate for legs in by_side.values())
    return isclose(a.lower,1-b.upper,abs_tol=1e-8,rel_tol=0) and isclose(a.upper,1-b.lower,abs_tol=1e-8,rel_tol=0)


def selection_groups(analysis, bookmakers=None, now=None):
    now=now or utcnow()
    counts=Counter()
    for q in analysis.quotes:
        try:counts[q.id]+=1
        except (ValueError,TypeError):continue
    groups=defaultdict(list)
    excluded=Counter()
    window=getattr(analysis,'slate',{}).get('window_end')
    try:end=parse_time(window) if window else None
    except (ValueError,TypeError):return [],{'Invalid scan window; research withheld':len(analysis.quotes)}
    for q in analysis.quotes:
        if bookmakers is not None and q.bookmaker not in bookmakers:continue
        problem=quote_problem(q,now)
        if problem:
            excluded[problem]+=1;continue
        if end and parse_time(q.commence_time)>end:continue
        if counts[q.id]!=1:
            excluded[problem or 'Ambiguous duplicate quote']+=1;continue
        key,side=binary_market(q)
        if key is None:
            excluded['Push, quarter-line or multi-outcome market needs an explicit outcome contract']+=1;continue
        groups[key].append((side,leg_evidence(q,analysis,now)))
    result=[]
    for key,items in sorted(groups.items(),key=lambda item:digest(item[0])):
        group=SelectionGroup(digest(key),key,tuple(leg for _,leg in items))
        modeled=[(side,leg) for side,leg in items if leg.estimate]
        if not modeled:
            group.problem='No functioning market-specific model estimate; prices are inspection only'
        else:
            signatures={(l.estimate.model_version,l.estimate.training_end,l.estimate.evidence_id,
                         l.estimate.validated,l.model_details.get('data_sha256','')) for _,l in modeled}
            by_side=defaultdict(list)
            for side,leg in modeled:by_side[side].append(leg)
            if len(signatures)!=1:
                group.problem='Conflicting model versions or input snapshots for equivalent outcomes'
            elif any(not all(isclose(getattr(l.estimate,k),getattr(legs[0].estimate,k),abs_tol=1e-8,rel_tol=0)
                             for k in ('probability','lower','upper')) for legs in by_side.values() for l in legs):
                group.problem='Equivalent outcomes have inconsistent model probabilities or envelopes'
            elif len(by_side)>2 or len(by_side)==2 and not isclose(sum(legs[0].estimate.probability for legs in by_side.values()),1.,abs_tol=1e-8,rel_tol=0):
                group.problem='Opposing binary probabilities do not reconcile to one distribution'
            elif len(by_side)==2 and not coherent_envelopes(by_side):
                group.problem='Opposing binary probability envelopes do not reconcile'
            else:
                favorites=[(side,leg) for side,leg in modeled if leg.estimate.probability>.5+1e-8]
                if not favorites:
                    group.problem=('Model is tied at 50%; no favored outcome' if any(isclose(l.estimate.probability,.5,abs_tol=1e-8) for _,l in modeled)
                        else 'The model-favored opposing outcome has no current observed price; no selection is invented')
                else:
                    side=favorites[0][0]
                    # Prefer adequate evidence, then a better price only for the
                    # same modeled outcome. Price never determines the favorite.
                    eligible=[l for s,l in favorites if s==side and evidence_problem(l,now) is None]
                    pool=eligible or [l for s,l in favorites if s==side]
                    chosen=min(pool,key=lambda l:(-l.quote.odds,evidence_key(l,now)))
                    group.preferred,group.preferred_side=chosen,side
                    group.model_favored=True
                    group.research_eligible=bool(eligible)
                    group.problem=evidence_problem(chosen,now) or ''
        if group.problem:excluded[group.problem]+=1
        result.append(group)
    return result,dict(excluded)


def preferred_offers(group, now):
    by_book={}
    for leg in group.offers:
        if not (leg.estimate and leg.estimate.probability>.5+1e-8
                and binary_market(leg.quote)[1]==group.preferred_side and evidence_problem(leg,now) is None):continue
        book=leg.quote.bookmaker
        old=by_book.get(book)
        if old is None or (-leg.quote.odds,evidence_key(leg,now))<(-old.quote.odds,evidence_key(old,now)):
            by_book[book]=leg
    return tuple(by_book.values())


def dependencies(legs):
    links=[];shared_game=shared_team=shared_player=0
    for a,b in combinations(legs,2):
        x,y=a.quote,b.quote
        game=same_event(x,y) or physical_game(x)==physical_game(y)
        teams=x.sport==y.sport and bool(set(team_ids(x)) & set(team_ids(y)))
        player=bool(x.participant and y.participant and x.sport==y.sport and canonical(x.participant)==canonical(y.participant))
        if game:
            shared_game+=1;links.append('Shared game: outcomes and sportsbook same-game restrictions may be linked')
        elif teams:
            shared_team+=1;links.append('Shared team across games: availability, form and rest may be linked')
        if player:
            shared_player+=1;links.append('Shared player: selections depend on the same participation/performance')
        if x.league==y.league:
            links.append('Same competition: common scoring environment and model errors may be shared')
        if a.estimate.model_version==b.estimate.model_version:
            links.append('Shared fitted model/calibration: prediction errors may be linked')
    return {'shared_game_pairs':shared_game,'shared_team_pairs':shared_team,'shared_player_pairs':shared_player,
        'known_links':tuple(dict.fromkeys(links)),
        'note':'Distinct games do not prove independence. Cross-game and cross-sport dependence is unmeasured.'}


def normalized_constraint(q):
    h,a=team_ids(q)
    selection=h if q.selection==q.home else a if q.selection==q.away else q.selection
    return replace(q,provider='constraint-only',event_id=digest(physical_game(q)),home=h,away=a,selection=selection)


@dataclass
class IntelligentCandidate:
    research: object
    group_ids: tuple
    dependence: dict
    evidence_rank: tuple
    probability_rank: tuple
    qualification: str = 'Experimental parlay research; not approved'


@dataclass
class Intelligence:
    groups: list = field(default_factory=list)
    favored: list = field(default_factory=list)
    potential_value: list = field(default_factory=list)
    two_leg: list = field(default_factory=list)
    three_leg: list = field(default_factory=list)
    alternatives: list = field(default_factory=list)
    exclusions: dict = field(default_factory=dict)
    examined_combinations: int = 0
    eligible_model_groups: int = 0
    searched_model_groups: int = 0
    checked_at: str = ''
    by_format: dict = field(default_factory=dict)
    method: str = 'Bounded per-book search, maximum 24 favored markets per sportsbook; no global optimum or joint probability claimed'


def generate(analysis,bookmakers=None,now=None,include_linked=False,max_per_size=2,pool_limit=24):
    now=now or utcnow()
    if not 1<=max_per_size<=3 or not 3<=pool_limit<=24:
        raise ValueError('Invalid bounded parlay search limits')
    groups,exclusions=selection_groups(analysis,bookmakers,now)
    favored=[g for g in groups if g.model_favored and g.research_eligible and not g.problem]
    favored.sort(key=lambda g:(-g.preferred.estimate.probability,*evidence_key(g.preferred,now)))
    values=[g for g in favored if comparison(g.preferred)['difference']>0]
    values.sort(key=lambda g:(-comparison(g.preferred)['difference'],*evidence_key(g.preferred,now)))
    result=Intelligence(groups=groups,favored=favored,potential_value=values,
        exclusions=exclusions,eligible_model_groups=len(favored),checked_at=now.isoformat())
    by_book=defaultdict(list)
    for group in favored:
        for leg in preferred_offers(group,now):by_book[leg.quote.bookmaker].append((group,leg))
    candidates={};searched=set();rejected=Counter(exclusions)
    for book,pairs in sorted(by_book.items()):
        pairs.sort(key=lambda item:evidence_key(item[1],now))
        # Round-robin distinct physical games before alternate markets on a game.
        buckets=defaultdict(list)
        for pair in pairs:buckets[physical_game(pair[1].quote)].append(pair)
        pool=[]
        while buckets and len(pool)<pool_limit:
            for key in list(buckets):
                pool.append(buckets[key].pop(0))
                if not buckets[key]:del buckets[key]
                if len(pool)==pool_limit:break
        searched.update(g.id for g,_ in pool)
        for n in (2,3):
            for combo in combinations(pool,n):
                result.examined_combinations+=1
                ids=tuple(sorted(g.id for g,_ in combo))
                if len(set(ids))!=n:continue
                legs=tuple(l for _,l in combo)
                dep=dependencies(legs)
                linked=dep['shared_game_pairs']+dep['shared_team_pairs']+dep['shared_player_pairs']
                if contradictory_scores([normalized_constraint(l.quote) for l in legs]):
                    rejected['Contradictory or duplicate physical outcome constraints']+=1;continue
                if linked and not include_linked:
                    rejected['Known shared-game/team/player link excluded from default candidates']+=1;continue
                candidate,problem=build_candidate(legs,analysis,now)
                if not candidate:
                    rejected[problem]+=1;continue
                lower=min(l.estimate.lower for l in legs)
                probability=min(l.estimate.probability for l in legs)
                width=max(l.estimate.upper-l.estimate.lower for l in legs)
                support=min(count(l.model_details,'calibration_bin_n') for l in legs)
                age=max((now-parse_time(l.quote.source_updated_at)).total_seconds() for l in legs)
                # Marginal support and uncertainty, never a joint win score or
                # theoretical payout objective. Sizes are shortlisted separately.
                erank=(linked,width,-support,-lower,-probability,age,ids,book)
                prank=(linked,-lower,-probability,width,-support,age,ids,book)
                item=IntelligentCandidate(candidate,ids,dep,erank,prank)
                old=candidates.get(ids)
                if old is None or erank<old.evidence_rank:candidates[ids]=item
    ordered=sorted(candidates.values(),key=lambda c:c.probability_rank)
    unlinked=lambda c:not any(c.dependence[k] for k in ('shared_game_pairs','shared_team_pairs','shared_player_pairs'))
    result.two_leg=[c for c in ordered if len(c.group_ids)==2 and unlinked(c)][:max_per_size]
    result.three_leg=[c for c in ordered if len(c.group_ids)==3 and unlinked(c)][:max_per_size]
    shown={c.group_ids for c in result.two_leg+result.three_leg}
    result.alternatives=sorted((c for c in candidates.values() if c.group_ids not in shown),key=lambda c:c.evidence_rank)[:3]
    result.searched_model_groups=len(searched);result.exclusions=dict(rejected)
    from intelligence.quant_decision import selection_format
    result.by_format={kind:sorted((c for c in candidates.values() if selection_format([l.quote for l in c.research.legs])==kind),
        key=lambda c:c.evidence_rank)[:3] for kind in ('Same-game parlay','Multi-game parlay','Mixed parlay')}
    return result


def explain_leg(leg):
    e=leg.estimate;d=leg.model_details
    direction='higher' if e.probability>.5 else 'lower'
    explanation=[f'The model assigns this binary outcome a {direction} chance than its opposite: {e.probability:.1%}.',
        f'The supplied historical calibration envelope is {e.lower:.1%}–{e.upper:.1%}; it is not a guarantee or an event-specific confidence interval.']
    if e.lower<=.5:explanation.append('The envelope includes 50%; uncertainty could reverse the model’s preference.')
    if e.model_version=='epl-goal-strength-1':
        explanation.append('It uses earlier goals scored/conceded, weights older games less and shrinks team strengths toward the league.')
    elif e.model_version.startswith('venue-goals-1-'):
        explanation.append('It uses earlier home/away scoring and conceding history fitted for this competition, with frozen probability calibration.')
    explanation.append(f"Calibration bucket: {count(d,'calibration_bin_n')} past outcomes; held-out evaluation: {count(d,'test_n')} outcomes.")
    if d.get('method'):explanation.append('Method: '+d['method'])
    explanation.append('The model remains experimental; no validated betting advantage or profitability is established.')
    return explanation
