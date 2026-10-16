"""Explicit, quota-controlled research refresh; no timer or paid service activation."""
from dataclasses import replace
import os
from intelligence.domain import utcnow
from intelligence.pipeline import run_analysis
from intelligence.providers import OddsAPI, LEAGUES, ProviderError


def credit_status(store, now=None):
    day=(now or utcnow()).date().isoformat()
    try:
        limit=int(os.getenv('ODDS_DAILY_CREDITS','16'))
        if not 0<=limit<=10000:
            raise ValueError()
    except ValueError:
        raise ProviderError('The local odds credit cap is invalid; configure a non-negative integer. Refresh is disabled.') from None
    with store.connect() as db:
        row=db.execute('SELECT used FROM budget WHERE day=?',(day,)).fetchone()
    used=row['used'] if row else 0
    return used,limit


def refresh_research(current,key,leagues,store):
    leagues=list(dict.fromkeys(leagues))
    if not key or not leagues or not set(leagues)<=set(LEAGUES):
        raise ProviderError('Configure the odds key and select supported competitions before refreshing')
    used,limit=credit_status(store)
    if limit-used<len(leagues):
        raise ProviderError('Not enough local daily credits for the selected competitions. Select fewer competitions or wait for the next UTC day; no budget was reset.')
    provider=OddsAPI(key,store,daily_limit=limit,ttl=0)
    # Fresh requests intentionally bypass only the time cache after a user click.
    # Existing provider reservations/retries still apply. Scores are not polled.
    fresh=run_analysis(key,leagues,store,provider,collect_results=False)
    result=replace(current,
        quotes=[q for q in current.quotes if q.league not in leagues]+fresh.quotes,
        opportunities=[o for o in current.opportunities if o.quote.league not in leagues]+fresh.opportunities,
        research=[],estimates={},errors=[],warnings=list(dict.fromkeys(current.warnings+fresh.warnings)),
        checked_at=fresh.checked_at,baseline={},
        exclusions=fresh.exclusions)
    retained={q.id for q in result.quotes if q.league not in leagues}
    result.research=[r for r in current.research if r.get('quote_id') in retained]+fresh.research
    result.estimates={id:e for id,e in getattr(current,'estimates',{}).items() if id in retained}|fresh.estimates
    result.baseline={id:b for id,b in current.baseline.items() if id in retained}|fresh.baseline
    result.errors=[error for error in current.errors if not any(error.startswith(league+':') for league in leagues)]+fresh.errors
    return result
