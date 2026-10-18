"""Quote-free research from reconciled fixtures and unchanged frozen soccer models.

No fake Quote, price, sportsbook, kickoff or market-derived forecast is created.
No network, promotion, publication, bet or remote write occurs here. NBA/MLB keep
their existing recency gates; unavailable features produce an explicit blocker.
"""
from datetime import date, timedelta
from itertools import combinations
from intelligence.domain import utcnow, parse_time, digest
from intelligence.epl_validation import calibrated
from intelligence.current_soccer import prepare_epl, prepare_expanded
from intelligence.data_adapters import team_identity
from intelligence.competitions import COMPETITIONS
from intelligence.joint_research import bounds

SOCCER = ('Premier League', 'Bundesliga', 'Ligue 1')


def soccer_forecasts(league, artifact, now, hours):
    """Use a fresh full-season provider reconciliation, never just an old schedule."""
    if artifact.get('problem'):
        return [], artifact['problem']
    if artifact.get('results_provider') != 'football-data.org':
        return [], 'Fresh reconciled full-season results and exact scheduled kickoffs are unavailable'
    if not 0 <= (now-parse_time(artifact['results_observed_at'])).total_seconds() < 21600:
        return [], 'Results verification expired; saved odds do not repair it'
    events = artifact['results_events']
    if any(e['status'] == 'unresolved' for e in events):
        return [], 'Unresolved or postponed earlier fixtures block this competition'
    state = artifact['state']; policy = artifact['policy']; epl = league == 'Premier League'
    if not 0 <= (now.date()-date.fromisoformat(state['latest'])).days <= policy['maximum_result_age_days']:
        return [], 'Completed results are too old or future-dated for current inference'
    # All prior-day features must precede the forecast; same-day finals are not
    # incorporated just because the provider can return them with timestamps.
    if any(r['date'] >= now.date().isoformat() for r in artifact['current_rows']):
        return [], 'Same-day or future completed features require reconciliation'
    from intelligence.epl_source import team
    from intelligence.epl_goal_model import rates, probabilities
    from intelligence.venue_goals import predict
    rows = []; reasons = []
    for e in events:
        if e['status'] != 'scheduled' or not e.get('kickoff'):
            continue
        start = parse_time(e['kickoff'])
        if not now+timedelta(minutes=15) < start <= now+timedelta(hours=hours):
            continue
        if start.date().isoformat() != e['event_date']:
            reasons.append('Fixture date and exact kickoff disagree'); continue
        c = COMPETITIONS[league]
        h, _ = team_identity(c, e['home_name']); a, _ = team_identity(c, e['away_name'])
        if (h, a) != (e['home_id'], e['away_id']):
            reasons.append('Fixture team identities do not reconcile'); continue
        home, away = (team(e['home_name']), team(e['away_name'])) if epl else (h, a)
        team_last_key = 'latest' if epl else 'last'
        if any(not state['teams'].get(t, {}).get(team_last_key) or
            not 0 <= (now.date()-date.fromisoformat(state['teams'][t][team_last_key])).days <= policy['maximum_result_age_days']
            for t in (home, away)):
            reasons.append('Participating team results are missing, stale or future-dated'); continue
        day = start.date().isoformat()
        if epl:
            lambdas, problem = rates(state, home, away, day, policy)
            raw = probabilities(*lambdas) if lambdas else None
            tasks = artifact['tasks']
        else:
            raw, problem = predict(state, home, away, day, policy)
            tasks = {artifact['target']: artifact}
        if raw is None:
            reasons.append(problem); continue
        for target, task in tasks.items():
            p = float(calibrated(raw[target], task['coefficients']))
            bucket = task['calibration_bins'][min(9, int(p*10))]
            lo, hi = bucket['frequency_interval'] if bucket['n'] >= policy['minimum_calibration_bin'] else (0., 1.)
            lo, hi = min(lo, p), max(hi, p)
            positive = p >= .5
            if not positive:
                p, lo, hi = 1-p, 1-hi, 1-lo
            market = 'btts' if target == 'btts' else 'totals'
            row = {'sport': 'Soccer', 'league': league, 'event': e['home_name']+' vs '+e['away_name'],
                'home': e['home_name'], 'away': e['away_name'], 'home_id': h, 'away_id': a,
                'fixture_id': digest((league, e['season'], h, a)), 'kickoff': start.isoformat(),
                'market': market, 'point': None if market == 'btts' else 2.5,
                'selection': ('Yes' if positive else 'No') if market == 'btts' else ('Over' if positive else 'Under'),
                'probability': p, 'lower': lo, 'upper': hi, 'fair_odds': 1/p,
                'model_version': artifact['model_version'], 'evidence_id': artifact['artifact_sha256'],
                'data_sha256': artifact['data_sha256'], 'history_n': state['n'],
                'training_end': state['latest'], 'calibration_n': task['calibration_n'],
                'calibration_bin_n': bucket['n'], 'test_n': task['periods']['held_out']['model']['n'] if epl else task['periods']['final_test']['eligible'],
                'source_observed_at': artifact['results_observed_at'], 'forecast_at': now.isoformat(),
                'validated': False, 'status': 'Experimental fixture forecast; not a betting pick',
                'sportsbook': None, 'observed_odds': None, 'ev': None,
                'limitations': ['Historical calibration-bin range, not a guaranteed event confidence interval',
                    'No independent prospective confirmation or model approval',
                    'Injuries, lineups, operator rules and a current Ontario price are unverified']}
            rows.append(row)
    return rows, '; '.join(sorted(set(reasons))) or ('No verified upcoming fixture in this date window' if not rows else '')


def collect(store, now=None, hours=48, leagues=None):
    """Bounded cache-only inference; valid inputs can work while prices are absent."""
    now = now or utcnow()
    if type(hours) is not int or not 1 <= hours <= 168:
        raise ValueError('Fixture research window must be 1–168 hours')
    rows = []; blockers = {}
    for league in SOCCER:
        if leagues is not None and league not in leagues:
            continue
        artifact = prepare_epl(store, now, allow_fetch=False) if league == 'Premier League' else prepare_expanded(league, store, now, allow_fetch=False)
        found, problem = soccer_forecasts(league, artifact, now, hours)
        rows.extend(found)
        if problem:
            blockers[league] = problem
    # No transfer from soccer, archive-time travel or odds-implied substitution.
    for sport in ('NBA', 'MLB'):
        if leagues is None or sport in leagues:
            blockers[sport] = 'Current licensed team results, exact upcoming fixtures and matching calibrated sport-model inputs are not available in the shared store; historical studies do not activate a forecast'
    rows.sort(key=lambda r: (r['upper']-r['lower'], -r['probability'], r['kickoff'], r['fixture_id'], r['market']))
    return {'forecasts': rows[:100], 'blockers': blockers, 'provider_requests': 0, 'paid_ai_requests': 0,
        'approved_models': 0, 'forward_records_created': 0,
        'note': 'Computed from saved verified inputs at display time; not claimed as durable pregame records. Current-price research and approved bets remain separate.'}


def combinations_for(rows, size=2, limit=3, now=None):
    """Logical joint ranges without a silent independence or executable-price claim."""
    if size not in (2, 3) or not 1 <= limit <= 3:
        raise ValueError('Bounded 2/3-leg research only')
    now = now or utcnow()
    pool = [r for r in rows if now+timedelta(minutes=15) < parse_time(r['kickoff']) <= now+timedelta(hours=168)
        and 0 <= (now-parse_time(r['source_observed_at'])).total_seconds() < 21600
        and 0 <= (now-parse_time(r['forecast_at'])).total_seconds() < 300][:24]
    result = []
    for legs in combinations(pool, size):
        if len({r['fixture_id'] for r in legs}) != size:
            continue
        if any(a['sport'] == b['sport'] and {a['home_id'], a['away_id']} & {b['home_id'], b['away_id']}
            for a, b in combinations(legs, 2)):
            continue
        if any(not 0 <= r['lower'] <= r['probability'] <= r['upper'] <= 1 or not r['evidence_id'] for r in legs):
            continue
        logical = bounds([r['probability'] for r in legs])
        uncertainty = [max(0., sum(r['lower'] for r in legs)-size+1), min(r['upper'] for r in legs)]
        result.append({'legs': legs, 'joint_probability': None, 'joint_validated': False,
            'logical_probability_bounds': logical, 'marginal_envelope_bounds': uncertainty,
            'fair_odds_range': [1/logical[1] if logical[1] else None, 1/logical[0] if logical[0] else None],
            'combined_odds': None, 'executable': False, 'ev': None, 'independence_assumed': False,
            'limitations': ['Different games and sports can still share model errors and other dependencies',
                'Logical bounds conditional on marginal estimates; not a calibrated joint forecast',
                'No accepted sportsbook ticket, combined price, parlay EV or validated joint probability']})
    result.sort(key=lambda c: (sum(r['upper']-r['lower'] for r in c['legs']), -min(r['probability'] for r in c['legs']),
        tuple(r['fixture_id'] for r in c['legs'])))
    return result[:limit]
