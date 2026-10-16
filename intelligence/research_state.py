"""Read-only research categories and health facts. Never fetches or fits models."""
from collections import Counter
from intelligence.domain import utcnow,parse_time
from intelligence.book_optimizer import scoped_quotes,leg_rank
from intelligence.parlay_research import quote_problem,leg_evidence
from intelligence.ev import qualify

APPROVED='Approved opportunity'
EXPERIMENTAL='Experimental / research-only'
PRICE_ONLY='Price-only research'
BLOCKED='Blocked / unavailable'
EVIDENCE_STATES=(APPROVED,EXPERIMENTAL,PRICE_ONLY,BLOCKED)


def evidence_state(q,analysis,now=None):
    now=now or utcnow()
    leg=leg_evidence(q,analysis,now)
    if quote_problem(q,now):
        return BLOCKED,leg
    if leg.estimate and qualify(q,leg.estimate,now)[0]:
        return APPROVED,leg
    if leg.estimate:
        return EXPERIMENTAL,leg
    from intelligence.epl_forecasts import supported
    from intelligence.expanded_forecasts import supported as expanded_supported
    if leg.model_details.get('model') or (supported(q) or expanded_supported(q)) and leg.blockers:
        return BLOCKED,leg
    return PRICE_ONLY,leg


def singles(analysis,bookmakers=None,sports=None,markets=None,statuses=None,now=None):
    now=now or utcnow();unique={};counts=Counter(q.id for q in analysis.quotes)
    for q in scoped_quotes(analysis,now):
        if (bookmakers is not None and q.bookmaker not in bookmakers or sports is not None and q.sport not in sports
            or markets is not None and q.market not in markets):
            continue
        state,leg=evidence_state(q,analysis,now)
        if counts[q.id]!=1:
            state=BLOCKED
        if statuses is not None and state not in statuses:
            continue
        rank=(EVIDENCE_STATES.index(state),*leg_rank(leg,now),-q.odds)
        old=unique.get(q.key)
        # Compare prices only within identical evidence; never prefer a stale price.
        if old is None or EVIDENCE_STATES.index(state)<EVIDENCE_STATES.index(old[0]) or (
            state==old[0] and q.odds>old[1].quote.odds):
            unique[q.key]=(state,leg,rank)
    return [(state,leg) for state,leg,_ in sorted(unique.values(),key=lambda row:row[2])]


def model_health(analysis,store=None,now=None):
    """Describe existing observations; downloading a file is never a freshness fix."""
    from intelligence.epl_forecasts import load_artifact
    from intelligence.epl_source import SEASONS
    now=now or utcnow();bundle=load_artifact();model=getattr(analysis,'focused_model',{}) or bundle
    observations=None
    if bundle and store:
        observations=store.cached('epl-public-v1-'+bundle['artifact_sha256'],86400,now)
    problem=model.get('problem') if model else 'Portable EPL artifact missing or differs from current code'
    if observations and not observations.get('ok'):
        problem=observations.get('reason','Public result observation unavailable')
    state=model.get('state',{}) if model else {}
    current_rows=observations.get('rows',[]) if observations and observations.get('ok') else []
    latest=max((r['date'] for r in current_rows),default=state.get('latest'))
    fixtures=observations['fixtures'] if observations and observations.get('ok') else model.get('fixtures',[]) if model else []
    missing=[r for r in fixtures if r['season']==SEASONS[-1] and r['date']<now.date().isoformat()]
    checked=(observations or {}).get('checked_at') or (model or {}).get('source_check')
    # Generation is a bundled snapshot receipt, not a new live results verification.
    if not checked and bundle:
        checked=bundle['generated_at']
    quotes=analysis.quotes
    statuses=Counter(q.status(now) for q in quotes)
    def latest_time(attribute):
        times=[]
        for q in quotes:
            try:times.append(parse_time(getattr(q,attribute)))
            except (ValueError,TypeError):pass
        return max(times,default=None)
    source,received=latest_time('source_updated_at'),latest_time('received_at')
    details=[b for row in analysis.research for b in row.get('blockers',[])]
    reasons=[]
    if problem:reasons.append(problem)
    if latest:
        age=(now.date()-parse_time(latest+'T00:00:00+00:00').date()).days
        if age>21:reasons.append(f'EPL results are {age} days old (latest {latest}); the 21-day source gate blocks forecasts')
    else:reasons.append('Current EPL result coverage is unavailable')
    if missing:reasons.append(f'{len(missing)} past EPL fixtures have no source score; affected team forecasts remain blocked')
    if statuses.get('stale'):reasons.append(f'{statuses["stale"]} odds observations are stale and cannot support current selections')
    if not any(q.status(now)=='current' and q.jurisdiction=='CA-ON' for q in quotes):
        reasons.append('No current Ontario price is verified in this snapshot')
    reasons.extend(['EPL goal-strength model is research-only; no new model has reviewed recommendation approval',
                    'Player logs, injuries and confirmed lineups are missing; player-prop forecasts are unavailable',
                    'Current NBA/MLB feature coverage is insufficient; older archive diagnostics do not supply current statistics',
                    'Joint parlay calibration, verified sportsbook restrictions and actual combined prices are unavailable'])
    return {'source_latest':latest,'source_checked_at':checked,
        'source_check_kind':'cached public refresh' if observations else 'existing analysis / bundled snapshot',
        'unresolved_scores':len(missing),'missing_dates':dict(Counter(r['date'] for r in missing)),
        'latest_odds_source':source.isoformat() if source else None,
        'latest_odds_receipt':received.isoformat() if received else None,
        'quote_statuses':dict(statuses),'model_version':(bundle or {}).get('model_version'),
        'model_status':'research-only' if bundle else 'unavailable','source_problem':problem,
        'reasons':list(dict.fromkeys(reasons)),'specific_blockers':list(dict.fromkeys(details))}
