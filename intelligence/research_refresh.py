"""Explicit market-scoped refresh; existing caps are never raised or reset."""
from dataclasses import replace
import os
from intelligence.domain import utcnow,parse_time
from intelligence.pipeline import run_analysis,evaluate_quotes
from intelligence.providers import OddsAPI,LEAGUES,ProviderError,normalize
from intelligence.markets import CATALOG,FEATURED
from intelligence.quota import quota_details


def credit_status(store,now=None,limit=None):
    try:
        limit=int(os.getenv('ODDS_DAILY_CREDITS','16')) if limit is None else int(limit)
        if not 0<=limit<=10000:
            raise ValueError()
    except (ValueError,TypeError):
        raise ProviderError('The local odds credit cap is invalid; configure a non-negative integer. Refresh is disabled.') from None
    info=quota_details(store,limit,now)
    return info['used'],limit


def featured_plan(current,leagues,markets,now=None):
    now=now or utcnow()
    plan=[]
    for league in dict.fromkeys(leagues):
        needed=tuple(m for m in sorted(set(markets)) if not any(q.league==league and q.market==m and
            q.jurisdiction=='CA-ON' and q.status(now)=='current' for q in current.quotes))
        if needed:
            plan.append((league,needed))
    return plan


def merge_analysis(current,fresh,leagues,markets,store,event_id=None):
    def selected(q):
        return q.league in leagues and q.market in markets and (event_id is None or q.event_id==event_id)
    retained=[q for q in current.quotes if not selected(q)]
    # run_analysis may restore other cached markets as well as the requested ones.
    # Merge by exact quote identity, preserving the latest original observation.
    merged={}
    for quote in retained+fresh.quotes:
        old=merged.get(quote.id)
        if old is None or (parse_time(quote.source_updated_at),parse_time(quote.received_at))>(parse_time(old.source_updated_at),parse_time(old.received_at)):
            merged[quote.id]=quote
    result=replace(current,quotes=list(merged.values()),checked_at=fresh.checked_at,
        warnings=list(dict.fromkeys(current.warnings+fresh.warnings)),exclusions={},
        errors=[e for e in current.errors if not any(e.startswith(l+':') for l in leagues)]+fresh.errors)
    return evaluate_quotes(result,store)


def refresh_research(current,key,leagues,store,markets=('h2h',),limit=None):
    leagues=list(dict.fromkeys(leagues)); markets=tuple(sorted(set(markets)))
    if not key or not leagues or not set(leagues)<=set(LEAGUES) or not markets or not set(markets)<=set(FEATURED):
        raise ProviderError('Configure the odds key and select supported competitions/featured markets before refreshing')
    plan=featured_plan(current,leagues,markets)
    used,limit=credit_status(store,limit=limit)
    cost=sum(len(m) for _,m in plan)
    if cost>limit-used:
        raise ProviderError('Not enough local daily credits for this search. Select fewer competitions/markets or wait for the next UTC reset; no budget was reset.')
    if not plan:
        return replace(current,warnings=list(dict.fromkeys(current.warnings+['Selected market observations are still current; no provider request was needed'])))
    provider=OddsAPI(key,store,daily_limit=limit,ttl=0)
    result=current
    for league,needed in plan:
        fresh=run_analysis(key,[league],store,provider,markets=needed,collect_results=False)
        result=merge_analysis(result,fresh,[league],needed,store)
    return result


def refresh_event(current,key,league,event_id,markets,store,limit=None,discovered=()):
    if not key or league not in LEAGUES or not markets:
        raise ProviderError('Configure the odds key and select an event and market')
    sport=LEAGUES[league][0]
    if any(m not in CATALOG or sport not in CATALOG[m].sports or
           (not CATALOG[m].documented and m not in discovered) for m in markets):
        raise ProviderError('This market needs current authorized event discovery before requesting prices')
    used,limit=credit_status(store,limit=limit)
    if len(set(markets))>limit-used:
        raise ProviderError('The local daily cap cannot cover these event markets; choose fewer or wait for reset')
    provider=OddsAPI(key,store,daily_limit=limit,ttl=0)
    response=provider.event_odds(league,event_id,tuple(markets))
    store.cache('event-snapshot-'+league+'-'+event_id+'-'+','.join(sorted(markets)),response)
    quotes,rejected=normalize(response['data'],league,response['received_at'])
    from intelligence.pipeline import Analysis
    fresh=Analysis(quotes=quotes,checked_at=utcnow().isoformat(),
        warnings=[f'{rejected} malformed provider records excluded'] if rejected else [])
    return merge_analysis(current,fresh,[league],markets,store,event_id)
