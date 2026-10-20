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
        rank=(EVIDENCE_STATES.index(state),*leg_rank(leg,now))
        old=unique.get(q.key)
        # Compare prices only within identical evidence; never prefer a stale price.
        if old is None or EVIDENCE_STATES.index(state)<EVIDENCE_STATES.index(old[0]) or (
            state==old[0] and q.odds>old[1].quote.odds):
            unique[q.key]=(state,leg,rank)
    return [(state,leg) for state,leg,_ in sorted(unique.values(),key=lambda row:row[2])]


def model_health(analysis,store=None,now=None):
    """The same per-competition evidence drives overview and expanded diagnostics."""
    from intelligence.diagnostics import competition_diagnostics,quote_inventory
    now=now or utcnow()
    competitions=competition_diagnostics(analysis,store,now)
    epl=next(r for r in competitions if r['competition']=='Premier League')
    inventory=quote_inventory(analysis,now)
    reasons=[]
    if epl['source_problem']:reasons.append(epl['source_problem'])
    latest=epl['latest_result']
    if latest:
        age=(now.date()-parse_time(latest+'T00:00:00+00:00').date()).days
        if age>21:reasons.append(f'EPL results are {age} days old (latest {latest}); the 21-day source gate blocks forecasts')
    if epl['past_unresolved']:
        reasons.append(f"{epl['past_unresolved']} past EPL fixtures have no source score; affected team forecasts remain blocked")
    if inventory['stale_upcoming_in_window']:
        reasons.append(f"{inventory['stale_upcoming_in_window']} saved upcoming-price observations are stale; they are inspection-only and need genuinely refreshed prices before use")
    if not inventory['current_eligible']:reasons.append('No current Ontario price is verified in this snapshot')
    reasons.extend(['All three soccer models remain research-only; no new model has reviewed recommendation approval',
        'Player logs, injuries and confirmed lineups are missing; player-prop forecasts are unavailable',
        'Current NBA/MLB feature coverage is insufficient; older archives do not supply current statistics',
        'Joint parlay calibration, verified sportsbook restrictions and actual combined prices are unavailable'])
    times=lambda attribute:[parse_time(getattr(q,attribute)) for q in analysis.quotes if q.status(now)!='invalid timestamp']
    source,received=times('source_updated_at'),times('received_at')
    return {'source_latest':latest,'source_checked_at':epl['source_check'],
        'source_check_kind':epl['current_source'] if epl['current_source']=='football-data.org' else 'existing analysis / bundled snapshot',
        'unresolved_scores':epl['past_unresolved'] or 0,'missing_dates':{},
        'latest_odds_source':max(source).isoformat() if source else None,
        'latest_odds_receipt':max(received).isoformat() if received else None,
        'quote_statuses':inventory['status_counts'],'quote_inventory':inventory,
        'model_version':epl['model'],'model_status':'research-only' if epl['model_status']=='Research model' else 'unavailable',
        'source_problem':epl['source_problem'],'competitions':competitions,
        'reasons':list(dict.fromkeys(reasons)),
        'specific_blockers':list(dict.fromkeys(b for r in analysis.research for b in r.get('blockers',[])))}
