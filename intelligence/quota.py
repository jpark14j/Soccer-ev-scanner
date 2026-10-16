"""Budget timing; local reset is not a provider account quota reset."""
from datetime import timedelta
from zoneinfo import ZoneInfo
from intelligence.domain import utcnow


def reset_info(now=None):
    now=now or utcnow()
    tomorrow=(now+timedelta(days=1)).replace(hour=0,minute=0,second=0,microsecond=0)
    local=tomorrow.astimezone(ZoneInfo('America/Toronto'))
    return {'next_reset_utc':tomorrow.isoformat(),'next_reset_toronto':local.strftime('%Y-%m-%d %H:%M %Z'),
            'seconds_until_reset':max(0,int((tomorrow-now).total_seconds()))}


def quota_details(store,limit,now=None):
    now=now or utcnow()
    with store.connect() as db:
        row=db.execute('SELECT used FROM budget WHERE day=?',(now.date().isoformat(),)).fetchone()
    used=row['used'] if row else 0
    return {'used':used,'limit':limit,'remaining':max(0,limit-used),**reset_info(now)}


def refresh_reason(*,key_configured,selection_count,cost,quota,cooldown=False):
    if not key_configured:
        return 'The existing ODDS_API_KEY is not configured.'
    if not selection_count:
        return 'Select at least one competition and market.'
    if cooldown:
        return 'A request was attempted less than 60 seconds ago. Wait before trying again.'
    if cost>quota['remaining']:
        return (f'Refresh needs up to {cost} local credits; {quota["remaining"]} remain. '
                f'Next local reset: {quota["next_reset_toronto"]} ({quota["next_reset_utc"]}). '
                'Choose fewer competitions/markets or inspect stale snapshots. The cap has not been raised.')
    return ''
