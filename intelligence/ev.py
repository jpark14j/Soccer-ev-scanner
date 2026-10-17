"""Transparent EV and margin comparison; consensus alone is never a model."""
from collections import defaultdict
from intelligence.domain import Opportunity, finite, parse_time, utcnow
from intelligence.registry import eligible_book


def expected_value(probability, decimal_odds, push_probability=0.):
    if not all(finite(x) for x in (probability, decimal_odds, push_probability)) or not 0 <= probability <= 1 or decimal_odds <= 1 or not 0 <= push_probability <= 1-probability:
        raise ValueError('Invalid probability, odds or push mass')
    # At zero push mass this is p*odds - 1. Push returns the stake.
    return probability * decimal_odds + push_probability - 1


def remove_margin(odds):
    if len(odds) < 2 or any(not finite(o) or o <= 1 for o in odds):
        raise ValueError('A complete mutually exclusive market is required')
    inverse = [1/o for o in odds]
    return [p/sum(inverse) for p in inverse]


def market_baselines(quotes, now=None):
    """Only complete, current h2h markets; exclude target book from its consensus."""
    now = now or utcnow()
    groups = defaultdict(list)
    for q in quotes:
        if q.market == 'h2h' and q.status(now) == 'current' and eligible_book(q.bookmaker, now):
            groups[(q.provider,q.event_id,q.bookmaker)].append(q)
    complete = {}
    for key, group in groups.items():
        names = [group[0].home,'Draw',group[0].away] if group[0].sport == 'Soccer' else [group[0].home,group[0].away]
        by_name = {q.selection:q for q in group}
        if set(by_name) != set(names) or len(group) != len(names):
            continue
        probs = remove_margin([by_name[n].odds for n in names])
        complete[key] = dict(zip(names, probs))
    output = {}
    for q in quotes:
        peers = [p[q.selection] for (provider,event,book),p in complete.items()
                 if provider==q.provider and event==q.event_id and book!=q.bookmaker and q.selection in p]
        if peers:
            output[q.id] = {'probability':sum(peers)/len(peers), 'peers':len(peers)}
    return output


def qualify(quote, estimate, now=None, min_ev=.02):
    now = now or utcnow()
    if quote.status(now) != 'current' or not eligible_book(quote.bookmaker, now):
        return None, 'Current Ontario quote required'
    if estimate is None or not estimate.valid() or not estimate.validated or not estimate.evidence_id:
        return None, 'Validated model and uncertainty evidence required'
    if (estimate.sport, estimate.league, estimate.market) != (quote.sport, quote.league, quote.market):
        return None, 'Model evidence does not cover this market'
    try:
        if parse_time(estimate.training_end) >= min(parse_time(quote.commence_time),now):
            return None, 'Training data must precede event and analysis'
    except (TypeError,ValueError):
        return None, 'Invalid model training timestamp'
    if quote.market != 'h2h' or quote.point is not None or quote.participant:
        return None, 'Push/prop/handicap model not yet validated for publication'
    ev = expected_value(estimate.probability, quote.odds)
    conservative = expected_value(estimate.lower, quote.odds)
    if conservative < min_ev:
        return None, 'Uncertainty-adjusted expected value below threshold'
    # Rank by worst plausible EV, penalized by interval width. All terms visible.
    score = conservative * (1 - (estimate.upper-estimate.lower))
    return Opportunity(quote,estimate,ev,conservative,1/quote.odds,score), ''


def best_prices(opportunities):
    selected = {}
    for o in opportunities:
        previous = selected.get(o.quote.key)
        if previous is None or (o.quote.odds,o.quote.bookmaker) > (previous.quote.odds,previous.quote.bookmaker):
            selected[o.quote.key] = o
    return sorted(selected.values(), key=lambda o:o.score, reverse=True)
