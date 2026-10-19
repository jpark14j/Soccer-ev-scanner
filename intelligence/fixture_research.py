"""Quote-free research from reconciled fixtures and unchanged frozen soccer models.

No fake Quote, price, sportsbook, kickoff or market-derived forecast is created.
No network, promotion, publication, bet or remote write occurs here. NBA/MLB keep
their existing recency gates; unavailable features produce an explicit blocker.
"""
from datetime import date, timedelta
from itertools import combinations
from types import SimpleNamespace
from intelligence.domain import utcnow, parse_time, digest
from intelligence.epl_validation import calibrated
from intelligence.current_soccer import prepare_epl, prepare_expanded
from intelligence.data_adapters import team_identity
from intelligence.competitions import COMPETITIONS
from intelligence.joint_research import bounds
from intelligence.research_ranking import MIN_CALIBRATION_BIN, MIN_CALIBRATION, MIN_TEST, MAX_ENVELOPE_WIDTH

SOCCER = ('Premier League', 'Bundesliga', 'Ligue 1')


def fixture_games(store,now=None,hours=168):
    """Fresh exact source fixtures for navigation; not model predictions/prices."""
    from intelligence.openliga import current
    now=now or utcnow()
    events,meta=current(store,'Bundesliga',now)
    sources=[('Bundesliga','Soccer',events,meta)]
    from intelligence.free_results import current as public_current
    from intelligence.nba_current import current as nba_current
    for league in ('Premier League','Ligue 1'):
        es,ms=public_current(store,league,now);sources.append((league,'Soccer',es,ms))
    es,ms=nba_current(store,now);sources.append(('NBA','NBA',es,ms))
    return [{'sport':sport,'league':league,'event_id':e.fixture_id,
        'event':e.home_name+' vs '+e.away_name,'start':e.kickoff,
        'home_id':e.home_id,'away_id':e.away_id,'statistics_fixture':True}
        for league,sport,events,meta in sources if meta['ok'] for e in events if e.status=='scheduled' and e.kickoff
        and now+timedelta(minutes=15)<parse_time(e.kickoff)<=now+timedelta(hours=hours)]


def soccer_forecasts(league, artifact, now, hours):
    """Use a fresh full-season provider reconciliation, never just an old schedule."""
    if artifact.get('problem'):
        return [], artifact['problem']
    if artifact.get('results_provider') not in ('football-data.org','openligadb','sportscore'):
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
                'fixture_id': digest((c.id, e['season'], h, a)), 'kickoff': start.isoformat(),
                'market': market, 'point': None if market == 'btts' else 2.5,
                'selection': ('Yes' if positive else 'No') if market == 'btts' else ('Over' if positive else 'Under'),
                'probability': p, 'lower': lo, 'upper': hi, 'fair_odds': 1/p,
                'model_version': artifact['model_version'], 'evidence_id': artifact['artifact_sha256'],
                'data_sha256': artifact['data_sha256'], 'history_n': state['n'],
                'training_end': state['latest'], 'calibration_n': task['calibration_n'],
                'calibration_bin_n': bucket['n'], 'test_n': task['periods']['held_out']['model']['n'] if epl else task['periods']['final_test']['eligible'],
                'source_observed_at': artifact['results_observed_at'], 'source': artifact['results_provider'], 'forecast_at': now.isoformat(),
                'validated': False, 'status': 'Experimental fixture forecast; not a betting pick',
                'sportsbook': None, 'observed_odds': None, 'ev': None,
                'limitations': ['Historical calibration-bin range, not a guaranteed event confidence interval',
                    'No independent prospective confirmation or model approval',
                    'Injuries, lineups, operator rules and a current Ontario price are unverified']}
            row['research_eligible'] = (row['calibration_bin_n'] >= MIN_CALIBRATION_BIN
                and row['calibration_n'] >= MIN_CALIBRATION and row['test_n'] >= MIN_TEST
                and row['upper']-row['lower'] <= MAX_ENVELOPE_WIDTH)
            if not row['research_eligible']:
                row['limitations'].append('Existing calibration sample or uncertainty research-ranking requirements are not met; inspection only')
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
        if (artifact.get('problem') or artifact.get('results_provider') not in ('football-data.org','openligadb')) and league in ('Premier League','Bundesliga'):
            from intelligence.current_soccer import prepare_openliga
            fallback = prepare_openliga(league, store, now)
            if not fallback.get('problem') or fallback.get('results_provider') == 'openligadb' and fallback.get('coverage'):
                artifact = fallback
        if league in ('Premier League','Ligue 1') and (artifact.get('problem') or artifact.get('results_provider') not in ('football-data.org','openligadb')):
            from intelligence.free_results import prepare as public_prepare
            public=public_prepare(league,store,now)
            if not public.get('problem') or public.get('results_provider')=='sportscore':artifact=public
        found, problem = soccer_forecasts(league, artifact, now, hours)
        from intelligence.lifecycle import research_hold
        for row in found:
            # Existing suspension/proof-conflict checks require only contract
            # and model scope; this is not a Quote and has no fictitious price.
            contract=SimpleNamespace(**{k:row[k] for k in ('sport','league','market','point')})
            model=SimpleNamespace(**{k:row[k] for k in ('model_version','evidence_id')})
            held=research_hold(store,contract,model)
            if held:problem=held
            else:rows.append(row)
        if problem:
            blockers[league] = problem
    # No transfer from soccer, archive-time travel or odds-implied substitution.
    for sport in ('NBA', 'MLB'):
        if leagues is None or sport in leagues:
            blockers[sport] = 'Current licensed team results, exact upcoming fixtures and matching calibrated sport-model inputs are not available in the shared store; historical studies do not activate a forecast'
    if 'NBA' in blockers:
        from intelligence.nba_current import forecasts as nba_forecasts
        nba,problem=nba_forecasts(store,now,hours)
        from intelligence.lifecycle import research_hold
        for row in nba:
            contract=SimpleNamespace(**{k:row[k] for k in ('sport','league','market','point')})
            model=SimpleNamespace(**{k:row[k] for k in ('model_version','evidence_id')})
            held=research_hold(store,contract,model)
            if held:problem=held
            else:rows.append(row)
        if problem:blockers['NBA']=problem
        else:blockers.pop('NBA')
    if 'MLB' in blockers:
        blockers['MLB']='Retrosheet stops in 2025. The tested free Sporting Events MLB export contains tournament placeholders without teams or game times, not 2026 results. SportScore has no documented baseball endpoint. No licensed account-free current/postseason source has been verified; regular-season Elo cannot authorize postseason forecasts.'
    rows.sort(key=lambda r: (r['upper']-r['lower'], -r['probability'], r['kickoff'], r['fixture_id'], r['market']))
    return {'forecasts': rows[:100], 'blockers': blockers, 'provider_requests': 0, 'paid_ai_requests': 0,
        'approved_models': 0, 'forward_records_created': 0,
        'note': 'Computed from saved verified inputs at display time; not claimed as durable pregame records. Current-price research and approved bets remain separate.'}


def combinations_for(rows, size=2, limit=3, now=None):
    """Logical joint ranges without a silent independence or executable-price claim."""
    if size not in (2, 3) or not 1 <= limit <= 3:
        raise ValueError('Bounded 2/3-leg research only')
    now = now or utcnow()
    pool = [r for r in rows if r.get('research_eligible') is True
        and now+timedelta(minutes=15) < parse_time(r['kickoff']) <= now+timedelta(hours=168)
        and 0 <= (now-parse_time(r['source_observed_at'])).total_seconds() < 21600
        and 0 <= (now-parse_time(r['forecast_at'])).total_seconds() < 21600]
    # A large NBA slate must not hide every soccer/mixed-sport combination.
    # Round-robin reviewed league groups, retaining input rank inside each.
    groups={}
    for r in pool:groups.setdefault(r['league'],[]).append(r)
    pool=[group[i] for i in range(24) for group in groups.values() if i<len(group)][:24]
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


def daily_combinations(rows,size=2,now=None):
    """Up to three transparent scopes, without manufacturing missing sports."""
    now=now or utcnow();result=[]
    sports=sorted({r['sport'] for r in rows})
    for sport in sports:
        candidates=combinations_for([r for r in rows if r['sport']==sport],size,1,now)
        if candidates:result+=candidates
    if len(sports)>1:
        # Separate the sports into a bounded pool so the best all-NBA option
        # cannot crowd out a genuinely mixed research combination.
        pool=[]
        for sport in sports:pool += [r for r in rows if r['sport']==sport][:8]
        # Use the same rejection and evidence rules; only mixed subsets enter.
        mixed=[]
        for legs in combinations(pool,size):
            if len({r['sport'] for r in legs})<2:continue
            mixed += combinations_for(list(legs),size,1,now)
        if mixed:
            mixed.sort(key=lambda c:(sum(r['upper']-r['lower'] for r in c['legs']),-min(r['probability'] for r in c['legs']),tuple(r['fixture_id'] for r in c['legs'])))
            result.append(mixed[0])
    return result[:3]


def forward_combinations(rows,now=None):
    """Bound-only prospective records, separate from point-probability models."""
    now=now or utcnow();result=[]
    for size in (2,3):
        for c in daily_combinations(rows,size,now):
            legs=c['legs']
            result.append(c|{'kind':'bounded_cross_game','research_eligible':True,'validated':False,
                'fixture_id':digest(sorted(r['fixture_id'] for r in legs)),
                'event':' + '.join(r['event'] for r in legs),
                'kickoff':min((r['kickoff'] for r in legs),key=parse_time),
                'sport':legs[0]['sport'] if len({r['sport'] for r in legs})==1 else 'Mixed',
                'league':' + '.join(sorted({r['league'] for r in legs})),
                'model_version':' + '.join(sorted({r['model_version'] for r in legs})),
                'evidence_id':digest(sorted(r['evidence_id'] for r in legs)),
                'data_sha256':digest(sorted(r['data_sha256'] for r in legs)),
                'source_observed_at':min((r['source_observed_at'] for r in legs),key=parse_time),
                'forecast_at':now.isoformat(),'probability':None,'lower':None,'upper':None,
                'observed_odds':None})
    return result
