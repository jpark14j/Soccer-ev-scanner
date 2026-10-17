"""Optional football-data.org v4 adapter. No key, consent or enable flag: no I/O.

Only full-season domestic schedules are accepted. Raw responses/headers are never
cached or logged. This is delayed completed-results research, not a live feed.
"""
from dataclasses import dataclass, field
from datetime import timedelta
from hashlib import sha256
from uuid import uuid4
import json
import os
import sqlite3
import requests
from intelligence.domain import utcnow, parse_time, digest
from intelligence.competitions import COMPETITIONS, expected_games
from intelligence.data_adapters import team_identity
from intelligence.event_data import EventObservation, coverage, ingest, reconciled

TERMS = 'https://www.football-data.org/about'
BASE = 'https://api.football-data.org/v4/competitions/'
# Competition codes are documented by the provider; never accept arbitrary URLs.
CODES = {'Premier League': 'PL', 'Bundesliga': 'BL1', 'Ligue 1': 'FL1',
         'La Liga': 'PD', 'Serie A': 'SA'}
TTL = 21600
DAILY_LIMIT = 6
STATUSES = {'SCHEDULED', 'TIMED', 'IN_PLAY', 'PAUSED', 'FINISHED',
            'SUSPENDED', 'POSTPONED', 'CANCELLED', 'AWARDED'}


def secret(name):
    value = os.getenv(name)
    if value:
        return value
    try:
        import streamlit as st
        return st.secrets.get(name, '')
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return ''


@dataclass(frozen=True)
class ResultsConfig:
    enabled: bool = False
    token: str = field(default='', repr=False)
    use_reviewed: bool = False

    @property
    def problem(self):
        if not self.enabled:
            return 'Optional football-data.org results integration is disabled'
        if not self.token:
            return 'Configure FOOTBALL_DATA_TOKEN in preview Streamlit Secrets'
        if not self.use_reviewed:
            return 'Review provider terms and permitted use before setting FOOTBALL_DATA_USE_REVIEWED=1'
        if not isinstance(self.token, str) or not 8 <= len(self.token) <= 200 or not self.token.isascii() or any(c.isspace() for c in self.token):
            return 'Invalid football-data.org credential format; requests blocked'
        return None


def configuration(getter=None):
    get = getter or secret
    return ResultsConfig(str(get('FOOTBALL_DATA_ENABLED') or '0') == '1',
                         get('FOOTBALL_DATA_TOKEN') or '',
                         str(get('FOOTBALL_DATA_USE_REVIEWED') or '0') == '1')


def season_at(now):
    year = now.year if now.month >= 7 else now.year - 1
    return f'{year}-{str(year+1)[-2:]}'


def cache_key(league, season):
    return 'football-data-v1-' + digest((league, season))


def parse(raw, league, season, observed_at, now=None):
    """Exact reviewed aliases only; numeric source IDs are bound within a snapshot.

    Never guess an unknown club from shortName, abbreviations or fuzzy similarity.
    Provider IDs remain provenance, not invented cross-provider identity mappings.
    """
    now = now or utcnow()
    if league not in CODES or season != season_at(now) or len(raw) > 2_000_000:
        raise ValueError('Unsupported results scope or oversized payload')
    payload = json.loads(raw)
    c = COMPETITIONS[league]
    expected = expected_games(c, season)
    matches = payload['matches']
    if (payload['competition']['code'] != CODES[league] or payload['competition']['type'] != 'LEAGUE'
        or str(payload['filters']['season']) != season[:4]
        or set(payload['filters']) - {'season'}
        or not isinstance(matches, list) or len(matches) != expected
        or payload['resultSet']['count'] != len(matches)):
        raise ValueError('Incomplete, filtered or wrong-competition full-season fixture response')
    events = []
    source_ids = set()
    bindings = {}
    reverse = {}
    statuses = {}
    for match in matches:
        identifier = match['id']
        if type(identifier) is not int or identifier <= 0 or identifier in source_ids:
            raise ValueError('Invalid or duplicate source fixture ID')
        source_ids.add(identifier)
        if (match['competition']['code'] != CODES[league] or match['stage'] != 'REGULAR_SEASON'
            or match['season']['startDate'][:4] != season[:4]):
            raise ValueError('Fixture competition/season/stage mismatch')
        identities = []
        for side in ('homeTeam', 'awayTeam'):
            club = match[side]
            source_id = club['id']
            if type(source_id) is not int or source_id <= 0:
                raise ValueError('Missing source team ID')
            try:
                identity, name = team_identity(c, club['name'])
            except (ValueError, TypeError):
                raise ValueError('Unreviewed provider team name; exact alias review required') from None
            if bindings.get(source_id, identity) != identity or reverse.get(identity, source_id) != source_id:
                raise ValueError('Conflicting source team identity bindings')
            bindings[source_id] = identity
            reverse[identity] = source_id
            identities.append((identity, name))
        start = parse_time(match['utcDate'])
        updated = parse_time(match['lastUpdated'])
        day = start.date().isoformat()
        if not season[:4]+'-07-01' <= day <= str(int(season[:4])+1)+'-06-30' or updated > parse_time(observed_at):
            raise ValueError('Fixture outside season or future source update')
        status = match['status']
        if status not in STATUSES:
            raise ValueError('Unknown provider fixture status')
        statuses[str(identifier)] = status
        finished = status == 'FINISHED'
        hg = ag = None
        if finished:
            score = match['score']
            hg, ag = score['fullTime']['home'], score['fullTime']['away']
            if (score['duration'] != 'REGULAR' or any(type(v) is not int or not 0 <= v <= 30 for v in (hg, ag))
                or not start + timedelta(minutes=90) <= updated <= now):
                raise ValueError('Unverified regular-time final score or completion timestamp')
        normalized = 'completed' if finished else 'scheduled' if status in ('SCHEDULED', 'TIMED') and start > now else 'unresolved'
        e = EventObservation(c.id, season, 'football-data.org', str(identifier),
            identities[0][0], identities[1][0], identities[0][1], identities[1][1], day,
            normalized, hg, ag, observed_at, updated.isoformat(), TERMS,
            'source_reported_ft', start.isoformat()).validate(now)
        events.append(e)
    if len({e.fixture_id for e in events}) != len(events):
        raise ValueError('Duplicate home/away fixture in domestic season')
    health = coverage(events, c, season, now)
    if not health['complete_fixture_schedule']:
        raise ValueError('Missing or unbalanced full-season fixture schedule')
    if payload['resultSet']['played'] != health['completed']:
        raise ValueError('Reported completed count does not reconcile')
    return events, health, statuses, bindings


def _reserve(store, now):
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS football_data_requests(at TEXT NOT NULL)')
        db.execute('BEGIN IMMEDIATE')
        from intelligence.request_guard import blocked
        if blocked(db):return False
        rows = db.execute('SELECT at FROM football_data_requests WHERE at>=?',
                          ((now-timedelta(days=1)).isoformat(),)).fetchall()
        times = [parse_time(r['at']) for r in rows]
        if any(t > now for t in times) or sum(t.date() == now.date() for t in times) >= DAILY_LIMIT or sum(t > now-timedelta(minutes=1) for t in times) >= 10:
            return False
        db.execute('INSERT INTO football_data_requests VALUES(?)', (now.isoformat(),))
    return True


def current(store, league, now=None, config=None, session=None, allow_fetch=True):
    now=now or utcnow()
    try:return _current(store,league,now,config,session,allow_fetch)
    except (sqlite3.Error,OSError):
        return [],{'ok':False,'provider':'football-data.org','failure_code':'storage',
            'problem':'Results storage unavailable; check database path, permissions and disk. No readiness inferred.'}
    except ValueError:
        return [],{'ok':False,'provider':'football-data.org','failure_code':'storage_integrity',
            'problem':'Saved results integrity failed; inspection/reconciliation required'}


def _current(store, league, now=None, config=None, session=None, allow_fetch=True):
    """One bounded GET/cache miss; six requests/day/store, six-hour failure cache.

    A 429 blocks this adapter for 24 hours; no redirects, automatic retries or
    odds requests. Caches contain only validated observations and safe metadata.
    """
    now = now or utcnow()
    config = config or configuration()
    failure = lambda reason,code='unavailable': ([], {'ok': False, 'problem': reason, 'provider': 'football-data.org','failure_code':code})
    if config.problem:
        code='disabled' if not config.enabled else 'missing_credential' if not config.token else 'use_not_reviewed' if not config.use_reviewed else 'invalid_credential'
        return failure(config.problem,code)
    if league not in CODES:
        return failure('Competition not in reviewed provider allowlist')
    season = season_at(now)
    key = cache_key(league, season)
    cached = store.cached(key, TTL, now)
    if cached is not None:
        return _restore(cached, store, league, now)
    from intelligence.results_journal import latest
    accepted=latest(store,league,season)
    # Migrate a successful pre-journal cache before a failed attempt can replace
    # it. Restoration validates bindings/conflicts; no receipt time is reset.
    with store.connect() as db:
        old=db.execute('SELECT payload FROM cache WHERE key=?',(key,)).fetchone()
    previous=json.loads(old['payload']) if old else None
    if not accepted and previous and previous.get('ok'):
        _restore(previous,store,league,now)
        accepted=latest(store,league,season)
    if accepted and 0 <= (now-parse_time(accepted['checked_at'])).total_seconds()<TTL:
        return _restore(accepted,store,league,now)
    if not allow_fetch:
        return failure('No fresh cached results; use Refresh soccer results only to verify the source','missing_fresh_snapshot')
    if store.cached('football-data-cooldown', 86400, now):
        return failure('Provider rate limit: results refresh paused for 24 hours','provider_rate_limit')
    owner = uuid4().hex
    if not store.claim_fetch(key, owner, now):
        return failure('Results refresh already in progress','refresh_in_progress')
    owned = session is None
    result = {'ok': False, 'problem': 'Results connection unavailable; no new current coverage verified',
              'provider': 'football-data.org', 'checked_at': now.isoformat(),'failure_code':'transport_connection'}
    try:
        if not _reserve(store, now):
            return failure('Results request limit reached; no HTTP request made','quota')
        # Crash-safe failure entry before I/O. Never persist authentication data.
        store.cache(key, result, now)
        session = session or requests.Session()
        response = session.get(BASE+CODES[league]+'/matches', params={'season': int(season[:4])},
            headers={'X-Auth-Token': config.token}, timeout=(5, 10), allow_redirects=False, stream=True)
        try:
            if response.status_code != 200:
                result['failure_code']='http_'+str(response.status_code)
                result['problem'] = {401: 'Provider authentication failed; check preview Secrets',
                    403: 'Provider account does not permit this competition/season',
                    429: 'Provider rate limit: results refresh paused for 24 hours'}.get(response.status_code, 'Results provider returned an unavailable response')
                if response.status_code == 429:
                    store.cache('football-data-cooldown', {'limited': True}, now)
            else:
                chunks = []
                size = 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > 2_000_000:
                        raise ValueError('Oversized results response')
                    chunks.append(chunk)
                raw = b''.join(chunks)
                if config.token.encode() in raw:
                    raise ValueError('Reflected credentials')
                events, health, statuses, bindings = parse(raw, league, season, now.isoformat(), now)
                from dataclasses import asdict
                result.update(ok=True, problem=None, events=[asdict(e) for e in events], coverage=health,
                    sha256=sha256(raw).hexdigest(), source_url=BASE+CODES[league]+'/matches?season='+season[:4],
                    license_reference=TERMS, provider_statuses=statuses, team_bindings=bindings)
                result.pop('failure_code',None)
        finally:
            response.close()
    except (ValueError, KeyError, TypeError, OverflowError, AttributeError) as error:
        result['ok'] = False
        # Only fixed codes, never response/exception text, enter UI/cache/logs.
        message=str(error)
        result['failure_code']=('schema_identity' if 'identity' in message.lower() or 'team name' in message.lower() else
            'schema_coverage' if any(word in message.lower() for word in ('season','fixture','count','schedule')) else 'schema')
        result['problem'] = 'Results schema, identity or full-season coverage failed; review required'
    except requests.Timeout:
        result['failure_code']='transport_timeout'
        result['problem']='Results provider timed out; previous accepted results retained for inspection'
    except requests.exceptions.SSLError:
        result['failure_code']='transport_tls'
        result['problem']='Results secure connection failed; no source verification inferred'
    except (requests.RequestException, OSError):
        pass  # Never surface exception strings, headers or response bodies.
    finally:
        if owned and session is not None:
            session.close()
        store.cache(key, result, now)
        store.release_fetch(key, owner)
    return _restore(result, store, league, now)


def _restore(result, store, league, now):
    meta = {k: v for k, v in result.items() if k != 'events'}
    if not result['ok']:
        return [], meta
    events = [EventObservation(**e).validate(now) for e in result['events']]
    meta['coverage']=coverage(events,COMPETITIONS[league],season_at(now),now)
    bindings = [('team', str(k), v) for k, v in result['team_bindings'].items()]
    bindings += [('fixture', e.source_event_id, e.fixture_id) for e in events]
    binding_problem = False
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS football_data_bindings(kind TEXT,id TEXT,identity TEXT,PRIMARY KEY(kind,id))')
        db.execute('BEGIN IMMEDIATE')
        for kind, identifier, identity in bindings:
            old = db.execute('SELECT identity FROM football_data_bindings WHERE kind=? AND id=?', (kind, identifier)).fetchone()
            if old and old['identity'] != identity:
                binding_problem = True
                break
        if not binding_problem:
            db.executemany('INSERT OR IGNORE INTO football_data_bindings VALUES(?,?,?)', bindings)
    if binding_problem:
        meta.update(ok=False, failure_code='reconciliation',problem='Provider team or fixture ID changed identity; manual review required')
        store.cache(cache_key(league, season_at(now)), result | {'ok': False, 'problem': meta['problem'],'failure_code':'reconciliation'}, parse_time(result['checked_at']))
        return [], meta
    ingest(store, events, meta, now)
    conflicts = [r for r in reconciled(store, COMPETITIONS[league].id, now) if r['conflicts']]
    # A completed result disappearing from a later full snapshot is not silently
    # accepted, even when a provider changes team/source IDs or the kickoff date.
    actual = {e.fixture_id for e in events}
    withdrawn = any(r['observation']['season'] == season_at(now) and r['observation']['status'] == 'completed'
                    and r['fixture_id'] not in actual for r in reconciled(store, COMPETITIONS[league].id, now))
    if conflicts or withdrawn:
        meta.update(ok=False, failure_code='reconciliation',problem='Conflicting scores, dates, bindings or withdrawn results require reconciliation')
        store.cache(cache_key(league, season_at(now)), result | {'ok': False, 'problem': meta['problem'],'failure_code':'reconciliation'}, parse_time(result['checked_at']))
    if meta['ok']:
        from intelligence.results_journal import accept
        accept(store,league,season_at(now),result)
    return events if meta['ok'] else [], meta


def status(store, config=None, now=None):
    """Read-only connection facts, with no credentials or external requests."""
    now = now or utcnow()
    config = config or configuration()
    return {'provider': 'football-data.org', 'enabled': config.enabled,
            'credential_configured': bool(config.token), 'use_reviewed': config.use_reviewed,
            'problem': config.problem, 'maximum_requests_per_UTC_day_per_store': DAILY_LIMIT,
            'cache_hours': TTL//3600, 'live_results': False,
            'leagues': {league:cached_status(store,league,now) for league in CODES}}


def cached_status(store, league, now=None):
    """Read metadata, including expired receipt dates, without fetching/ingesting."""
    now = now or utcnow()
    try:
        from intelligence.results_journal import latest,retained_observations
        key=cache_key(league,season_at(now))
        with store.connect() as db:
            row=db.execute('SELECT payload FROM cache WHERE key=?',(key,)).fetchone()
        attempt=json.loads(row['payload']) if row else None
        accepted=latest(store,league,season_at(now))
        if not accepted and attempt and attempt.get('ok'):accepted=attempt
        data=attempt or accepted
        retained=retained_observations(store,COMPETITIONS[league].id)
        if not data:
            return {'provider':'football-data.org','available':False,'fresh':False,
                'failure_code':'missing_snapshot','retained_normalized':retained,
                'problem':'No current-season results snapshot has been observed in this store'}
        checked = parse_time(data['checked_at'])
        fresh = 0 <= (now-checked).total_seconds() < TTL
        result = {k:data[k] for k in ('ok','checked_at','coverage','sha256','problem','source_url','failure_code') if k in data}
        result.update(provider='football-data.org',available=True,fresh=fresh,retained_normalized=retained,
            last_attempt={k:attempt[k] for k in ('ok','checked_at','problem','failure_code') if k in attempt} if attempt else None,
            cache_recoverable_without_HTTP=not attempt and bool(accepted) and fresh)
        if accepted:
            events=[EventObservation(**e).validate(parse_time(accepted['checked_at'])) for e in accepted['events']]
            health=coverage(events,COMPETITIONS[league],season_at(now),now)
            result['last_success']={'checked_at':accepted['checked_at'],'sha256':accepted['sha256'],'coverage':health,
                'fresh':0<=(now-parse_time(accepted['checked_at'])).total_seconds()<TTL}
            result['coverage']=health
        else:result['last_success']=None
        if not fresh:
            result['problem'] = 'Results verification expired; a download timestamp is not a completed-result date'
            result['failure_code']='expired_verification'
            if checked>now:
                result.update(problem='Results receipt is future-dated; no current readiness inferred',failure_code='future_verification')
        # Reconciliation failures cannot be hidden by an otherwise valid cache.
        with store.connect() as db:
            has_events = bool(db.execute("SELECT name FROM sqlite_master WHERE name='event_observations'").fetchone())
        if has_events and any(r['conflicts'] for r in reconciled(store, COMPETITIONS[league].id, now)):
            result.update(ok=False,problem='Conflicting normalized results require manual reconciliation')
        return result
    except (ValueError,TypeError,KeyError):
        return {'provider':'football-data.org','available':False,'fresh':False,
                'failure_code':'storage_integrity',
                'problem':'Cached source metadata is invalid; no readiness inferred'}
    except (sqlite3.Error,OSError):
        return {'provider':'football-data.org','available':False,'fresh':False,'failure_code':'storage',
            'problem':'Results storage unavailable; check database path, permissions and disk'}
