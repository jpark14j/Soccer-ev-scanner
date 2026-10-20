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
    limit=min(limit,9) if type(limit) is int and limit>=0 else 0
    with store.connect() as db:
        row=db.execute('SELECT used FROM budget WHERE day=?',(now.date().isoformat(),)).fetchone()
        monthly=db.execute('SELECT coalesce(sum(used),0) FROM budget WHERE substr(day,1,7)=?',(now.date().isoformat()[:7],)).fetchone()[0]
        from intelligence.request_guard import blocked
        held=blocked(db)
    used=row['used'] if row else 0
    replica=getattr(store,'read_replica',False)
    local_remaining=min(max(0,limit-used),max(0,279-monthly))
    remote=getattr(store,'shared_status',{}).get('envelope',{})
    return {'used':used,'limit':limit,'remaining':0 if held or replica else local_remaining,'recovery_hold':held,
        'monthly_reserved':monthly,'monthly_limit':279,'monthly_remaining':max(0,279-monthly),
        'local_remaining':local_remaining,'local_exhausted':local_remaining==0,
        'availability_reason':'read_only_replica' if replica else 'recovery_hold' if held else 'monthly_cap' if monthly>=279 else 'local_cap' if not local_remaining else 'locally_available',
        'remote_provider_hold':remote.get('held'),
        'external_account_remaining':None,
        'scope_note':'Local reservations describe this saved store only. Production and other consumers of the same account are outside this ledger; external provider credits are unknown.',
        'read_only_replica':replica,**reset_info(now)}


def refresh_reason(*,key_configured,selection_count,cost,quota,cooldown=False):
    if quota.get('read_only_replica'):
        return 'Shared mode uses one background writer. This dashboard replica cannot request sportsbook data; sync committed state instead.'
    if quota.get('recovery_hold'):
        return 'Restored-store requests are held until explicit provider-usage review. A daily reset does not release this hold.'
    if quota.get('monthly_remaining')==0:
        return 'This store has reached its UTC calendar-month reservation ceiling. Midnight does not restore this allowance; provider account credits remain separate and must be reviewed.'
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
