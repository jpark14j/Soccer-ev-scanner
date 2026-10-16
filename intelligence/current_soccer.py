"""Optional results bridge to frozen research models; approval rules stay frozen."""
from copy import deepcopy
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from hashlib import sha256
from intelligence.domain import utcnow, parse_time, digest
from intelligence.current_results import configuration, current


def prepare_epl(store, now=None):
    from intelligence.epl_forecasts import prepare
    if not configuration().enabled:
        return prepare(store, now)
    return _prepare('Premier League', store, now)


def prepare_expanded(league, store, now=None):
    from intelligence.expanded_forecasts import prepare
    if not configuration().enabled:
        return prepare(league, store, now)
    return _prepare(league, store, now)


def _prepare(league, store, now=None):
    from intelligence.epl_forecasts import load_artifact
    from intelligence.expanded_models import load
    from intelligence.epl_source import team
    from intelligence.venue_goals import extend
    from intelligence.epl_goal_model import advance, add_result
    now = now or utcnow()
    epl = league == 'Premier League'
    artifact = deepcopy(load_artifact() if epl else load(league))
    if not artifact:
        return {'problem': 'Frozen research artifact missing or code hash mismatch'}
    anchor = 'anchor' if epl else 'as_of'
    if parse_time(artifact['generated_at']) > now or artifact['state'][anchor] > now.date().isoformat():
        return {'problem': 'Future-dated frozen model state'}
    events, meta = current(store, league, now)
    if not meta['ok']:
        return {'problem': meta['problem'], 'results_provider': 'football-data.org'}
    if (now-parse_time(meta['checked_at'])).total_seconds() >= 21600:
        return {'problem': 'Current-results observation is stale'}
    if meta['coverage']['unresolved_past'] or any(e.status == 'unresolved' for e in events):
        return {'problem': 'Full-season source contains unresolved, postponed, suspended or uncompleted past fixtures',
                'results_provider': 'football-data.org', 'coverage': meta['coverage']}
    rows = []
    for e in events:
        # Preserve frozen prior-calendar-date feature construction, even if a
        # provider reports a same-day completed match with an exact timestamp.
        if e.status != 'completed' or e.event_date >= now.date().isoformat():
            continue
        home, away = (team(e.home_name), team(e.away_name)) if epl else (e.home_id, e.away_id)
        if not home or not away:
            return {'problem': 'Provider identity is missing a reviewed frozen-model alias'}
        row = {'season': e.season, 'date': e.event_date, 'home': home, 'away': away,
               'hg': e.home_score, 'ag': e.away_score}
        if not epl:
            row['fixture_id'] = e.fixture_id
        rows.append(row)
    key = lambda r: (r['season'], r['home'], r['away'])
    old = {key(r): r for r in artifact['current_rows']}
    actual = {key(r): r for r in rows}
    if any(actual.get(k) != r for k, r in old.items()):
        return {'problem': 'Provider revised, moved or omitted frozen completed fixtures; manual reconciliation required'}
    extra = sorted((r for r in rows if key(r) not in old), key=lambda r: (r['date'], r['home'], r['away']))
    if extra:
        day = max(artifact['state'][anchor],
                  (date.fromisoformat(max(r['date'] for r in extra))+timedelta(days=1)).isoformat())
        if epl:
            advance(artifact['state'], day, artifact['policy'])
            for row in extra:
                add_result(artifact['state'], row, artifact['policy'])
        else:
            artifact['state'] = extend(artifact['state'], extra, day, artifact['policy'])
    if epl:
        fixtures = []
        for e in events:
            if e.status != 'completed':
                h, a = team(e.home_name), team(e.away_name)
                if not h or not a:
                    return {'problem': 'Fixture identity is missing a reviewed frozen-model alias'}
                fixtures.append({'season': e.season, 'date': e.event_date, 'home': h, 'away': a})
        artifact['fixtures'] = fixtures
        artifact['source_check'] = meta['checked_at']
    else:
        artifact['fixtures'] = [asdict(e) for e in events]
        artifact['source_checked_at'] = meta['checked_at']
    adapter_sha256 = digest({name:sha256(Path(__file__).with_name(name+'.py').read_bytes()).hexdigest()
                            for name in ('current_results','current_soccer')})
    artifact.update(current_rows=rows, source_kind='football-data.org delayed completed results',
                    results_provider='football-data.org', results_coverage=meta['coverage'],
                    results_source_url=meta['source_url'], results_observed_at=meta['checked_at'],
                    results_sha256=meta['sha256'], results_events=[asdict(e) for e in events],
                    results_adapter_sha256=adapter_sha256,
                    data_sha256=digest((artifact['data_sha256'], meta['sha256'], adapter_sha256)))
    return artifact


def forecast(q, artifact, now=None):
    """Apply additional source checks, then the unchanged model's original gates."""
    from intelligence.epl_forecasts import forecast as epl
    from intelligence.expanded_forecasts import forecast as expanded
    now = now or utcnow()
    model = epl if q.league == 'Premier League' else expanded
    if artifact.get('results_provider') == 'football-data.org' and not artifact.get('problem'):
        from intelligence.data_adapters import team_identity
        from intelligence.competitions import COMPETITIONS
        problem = None
        if (now-parse_time(artifact['results_observed_at'])).total_seconds() >= 21600:
            problem = 'Results verification expired; refresh results before forecasting'
        try:
            h, _ = team_identity(COMPETITIONS[q.league], q.home)
            a, _ = team_identity(COMPETITIONS[q.league], q.away)
            matches = [e for e in artifact['results_events'] if (e['home_id'], e['away_id']) == (h, a)]
            if (len(matches) != 1 or matches[0]['status'] != 'scheduled'
                or parse_time(matches[0]['kickoff']) != parse_time(q.commence_time)):
                problem = 'Provider must exactly confirm this scheduled fixture and kickoff time'
        except (ValueError, KeyError, TypeError):
            problem = 'Exact provider fixture/team reconciliation unavailable'
        if problem:
            return None, {'quote_id': q.id, 'validated': False, 'blockers': [problem]}
    estimate, detail = model(q, artifact, now)
    if artifact.get('results_provider') == 'football-data.org':
        detail.update(data_source='football-data.org delayed source-reported regular-time results',
            results_source_url=artifact.get('results_source_url'), results_sha256=artifact.get('results_sha256'),
            results_adapter_sha256=artifact.get('results_adapter_sha256'),
            source_checked_at=artifact.get('results_observed_at'),
            results_provider='football-data.org', results_scope='Research target; not operator settlement')
    return estimate, detail


def paper_result_matches(quote, artifact):
    """Keyed-provider labels require the exact originally recorded kickoff too."""
    if artifact.get('results_provider') != 'football-data.org':
        return True  # Preserve the existing explicitly date-only public target.
    try:
        from intelligence.data_adapters import team_identity
        from intelligence.competitions import COMPETITIONS
        h, _ = team_identity(COMPETITIONS[quote['league']], quote['home'])
        a, _ = team_identity(COMPETITIONS[quote['league']], quote['away'])
        return sum(e['status']=='completed' and (e['home_id'], e['away_id'])==(h, a)
            and parse_time(e['kickoff'])==parse_time(quote['commence_time'])
            for e in artifact['results_events']) == 1
    except (KeyError, ValueError, TypeError):
        return False
