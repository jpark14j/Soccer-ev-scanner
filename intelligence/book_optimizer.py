"""Score the whole observed slate, then shortlist one candidate per sportsbook.

Small pools are exhaustively enumerated. Large pools use a disclosed beam search;
every eligible single is scored/considered, but not every possible combination.
Qualified output additionally needs supplied genuine combined and joint evidence.
"""
from collections import Counter,defaultdict
from itertools import combinations
from intelligence.domain import parse_time,utcnow
from intelligence.ev import qualify
from intelligence.parlay_research import (quote_problem,leg_evidence,build_candidate,event_identity)
from intelligence.parlays import analyze
from intelligence.registry import eligible_book


def scoped_quotes(analysis,now=None):
    now=now or utcnow();window=getattr(analysis,'slate',{})
    end=parse_time(window['window_end']) if window.get('window_end') else None
    return [q for q in analysis.quotes if not end or now<parse_time(q.commence_time)<=end]


def leg_rank(leg,now):
    from intelligence.research_ranking import evidence_key
    opportunity=qualify(leg.quote,leg.estimate,now)[0] if leg.estimate else None
    return (opportunity is None,-opportunity.conservative_ev if opportunity else 0,
        leg.model_status!='validated',*evidence_key(leg,now))


def best_by_game(analysis,bookmakers=None,now=None,limit=2):
    now=now or utcnow();groups=defaultdict(list);seen=Counter(q.id for q in analysis.quotes)
    for q in scoped_quotes(analysis,now):
        if bookmakers is not None and q.bookmaker not in bookmakers:
            continue
        if quote_problem(q,now) or seen[q.id]!=1:
            continue
        groups[(q.league,q.event_id)].append(leg_evidence(q,analysis,now))
    events={(r['league'],r['event_id']):r for r in getattr(analysis,'slate',{}).get('events',[]) if parse_time(r['start'])>now}
    for key,legs in groups.items():
        q=legs[0].quote
        events.setdefault(key,{'league':q.league,'event_id':q.event_id,'sport':q.sport,'event':q.event,'start':q.commence_time})
    result=[]
    for key,event in sorted(events.items(),key=lambda item:(item[1]['start'],item[0])):
        legs=groups.get(key,[]);ordered=sorted(legs,key=lambda leg:leg_rank(leg,now));unique={}
        # Compare equivalent current prices before shortlisting across books.
        for leg in ordered:
            old=unique.get(leg.quote.key)
            if old is None or leg.quote.odds>old.quote.odds:
                unique[leg.quote.key]=leg
        ranked=sorted(unique.values(),key=lambda leg:leg_rank(leg,now));chosen=[];families=set()
        for leg in ranked:
            family=(leg.quote.market,leg.quote.participant)
            if family in families:
                continue
            families.add(family);chosen.append(leg)
            if len(chosen)>=limit:
                break
        qualified=[leg for leg in chosen if leg.estimate and qualify(leg.quote,leg.estimate,now)[0]]
        result.append({'event':event,'selections':chosen,'observations_evaluated':len(legs),
            'market_types':len({l.quote.market for l in legs}),'qualified':len(qualified),
            'reason':'Ranked by qualification, conservative EV when valid, model evidence, interval width and freshness. Equal-evidence ties use stable IDs; price-only choices do not establish statistical superiority.'})
    return result


def optimize_by_book(analysis,bookmakers=None,leg_counts=(2,),now=None,combined_prices=(),joint_estimates=(),beam_width=24):
    now=now or utcnow()
    if not set(leg_counts)<={2,3} or not leg_counts or not 4<=beam_width<=64:
        raise ValueError('Invalid parlay search configuration')
    groups=defaultdict(list);names={};counts=Counter(q.id for q in analysis.quotes)
    for q in scoped_quotes(analysis,now):
        if (bookmakers is not None and q.bookmaker not in bookmakers) or not eligible_book(q.bookmaker,now):
            continue
        names[q.bookmaker]=q.bookmaker_name
        if not quote_problem(q,now) and counts[q.id]==1:
            groups[q.bookmaker].append(leg_evidence(q,analysis,now))
    output=[]
    for book in sorted(names):
        legs=sorted(groups[book],key=lambda l:leg_rank(l,now));best=None;examined=0;rejected=Counter()
        pool={leg.quote.id:leg for leg in legs};qualified=[]
        # Evaluate every genuine quoted ticket even if the research beam misses it.
        for price in combined_prices:
            ids=tuple(sorted(price.leg_ids))
            if price.bookmaker!=book or len(ids) not in leg_counts or not set(ids)<=pool.keys():
                continue
            joint=next((j for j in joint_estimates if tuple(sorted(j.leg_ids))==ids),None)
            opportunities=[qualify(pool[id].quote,pool[id].estimate,now)[0] if pool[id].estimate else None for id in ids]
            if joint and all(opportunities):
                candidate,reason=build_candidate(tuple(pool[id] for id in ids),analysis,now)
                if candidate:
                    evidence=analyze(opportunities,price,joint,now)
                    if evidence['status']=='qualifying':
                        qualified.append((evidence,candidate))
        def review(combo):
            nonlocal examined,best
            examined+=1
            candidate,reason=build_candidate(combo,analysis,now)
            if candidate is None:
                rejected[reason]+=1;return None
            if len(combo) in leg_counts and (best is None or candidate.rank_key<best.rank_key):
                best=candidate
            return candidate
        if len(legs)<=24:
            for n in sorted(leg_counts):
                for combo in combinations(legs,n):
                    review(combo)
            method='exhaustive over eligible observed legs'
        else:
            # Distinct-game seeds prevent one event monopolizing the beam.
            seeds=[];seen=set()
            for leg in legs:
                identity=(event_identity(leg.quote),leg.quote.market,leg.quote.participant)
                if identity not in seen:
                    seeds.append(leg);seen.add(identity)
                if len(seeds)==beam_width:
                    break
            pairs={}
            for a in seeds:
                for b in legs:
                    if a.quote.id>=b.quote.id and b in seeds:
                        continue
                    pair=review((a,b))
                    if pair:
                        pairs[pair.id]=pair
            beam=sorted(pairs.values(),key=lambda c:c.rank_key)[:beam_width]
            if 3 in leg_counts:
                visited=set()
                for pair in beam:
                    ids={leg.quote.id for leg in pair.legs}
                    for leg in legs:
                        if leg.quote.id in ids:
                            continue
                        identity=tuple(sorted((*ids,leg.quote.id)))
                        if identity not in visited:
                            visited.add(identity);review((*pair.legs,leg))
            method=f'beam search width {beam_width}; every eligible single scored, combinations not exhaustive'
        winner=min(qualified,key=lambda item:(-item[0]['conservative_ev'],-item[0]['probability'])) if qualified else None
        output.append({'bookmaker':book,'name':names[book],'qualified':winner,'research':best,
            'eligible_singles_scored':len(legs),'events_considered':len({event_identity(l.quote) for l in legs}),
            'combinations_evaluated':examined,'search_method':method,'rejections':dict(rejected),
            'qualification_status':'Qualified' if winner else 'No Qualifying Parlay'})
    return output
