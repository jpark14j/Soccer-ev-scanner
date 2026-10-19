"""The Odds API adapter. Requests use only licensed public endpoints, not scraping."""
import re
import json
import uuid
from typing import Protocol
import requests
from intelligence.domain import Quote, finite, parse_time, utcnow, digest
from intelligence.registry import eligible_book

LEAGUES = {
    'NBA': ('NBA', 'basketball_nba'), 'MLB': ('MLB', 'baseball_mlb'),
    'Premier League': ('Soccer', 'soccer_epl'), 'La Liga': ('Soccer', 'soccer_spain_la_liga'),
    'Bundesliga': ('Soccer', 'soccer_germany_bundesliga'), 'Serie A': ('Soccer', 'soccer_italy_serie_a'),
    'Ligue 1': ('Soccer', 'soccer_france_ligue_one'), 'MLS': ('Soccer', 'soccer_usa_mls'),
    'Champions League': ('Soccer', 'soccer_uefa_champs_league'),
}
# Provider market keys do not establish actual Ontario availability.
PROP_MARKETS = {
    'NBA': ('player_points', 'player_rebounds', 'player_assists', 'player_threes', 'player_double_double', 'player_triple_double'),
    'Soccer': ('btts', 'double_chance', 'player_anytime_goalscorer', 'player_shots_on_target', 'alternate_totals_corners', 'alternate_totals_cards'),
    'MLB': ('pitcher_strikeouts', 'batter_hits', 'batter_total_bases', 'batter_home_runs', 'batter_rbis', 'h2h_1st_5_innings', 'totals_1st_5_innings'),
}


class ProviderError(RuntimeError):
    """Only safe, locally generated text; never include request URLs or payloads."""


class OddsProvider(Protocol):
    def odds(self, league: str, markets: tuple = ('h2h',)) -> dict: ...
    def event_odds(self, league: str, event_id: str, markets: tuple) -> dict: ...


class OddsAPI:
    def __init__(self, key, store, daily_limit=9, ttl=1800, session=None):
        self.key, self.store = key, store
        self.daily_limit = min(daily_limit,9) if type(daily_limit) is int and daily_limit>=0 else 0
        self.ttl = ttl
        self.session = session or requests.Session()
        # Refuse redirect hops while retaining the existing injectable transport
        # contract (get(url, params, timeout)). Real Requests raises before a hop.
        if isinstance(self.session,requests.Session):self.session.max_redirects=0

    def _get(self, path, params, cost, now=None):
        if not self.key:
            raise ProviderError('ODDS_API_KEY is not configured')
        now = now or utcnow()
        # A hash isolates caches by account without storing the API credential.
        cache_key = digest(('odds-v1', digest(self.key), path, params))
        # Even explicit refreshes coalesce identical requests within 60 seconds.
        # Original source/receipt timestamps are preserved, including empty feeds.
        effective_ttl=max(60,self.ttl)
        cached = self.store.cached(cache_key, effective_ttl, now)
        if cached is not None:
            return cached
        observation=self.store.cached('provider-quota-observation',300,now)
        if (cost and observation and observation.get('account_fingerprint')==digest(self.key)
            and type(observation.get('remaining')) is int and observation['remaining']<cost):
            raise ProviderError('Provider account allowance recently observed below request cost; no request made')
        owner=uuid.uuid4().hex
        if not self.store.claim_fetch(cache_key,owner,now):
            raise ProviderError('This request is already refreshing in another session; reuse the cache or try again shortly')
        try:
            cached=self.store.cached(cache_key,effective_ttl,now)
            if cached is not None:
                return cached
            return self._fetch(path,params,cost,cache_key,now)
        finally:
            self.store.release_fetch(cache_key,owner)

    def _fetch(self,path,params,cost,cache_key,now):
        # One attempt per explicit collection. A timeout cannot establish whether
        # the provider charged the request, so it must not cause another request.
        if not cost and not self.store.authorize_discovery():
            raise ProviderError('Provider discovery blocked: read-only replica, shared hold or bounded discovery limit')
        if cost and not self.store.reserve(cost, self.daily_limit, now):
            raise ProviderError('Daily API credit budget exhausted or held; cached data may be stale')
        try:
            response = self.session.get('https://api.the-odds-api.com/v4/' + path,
                params=params | {'apiKey': self.key}, timeout=(5, 25))
        except requests.RequestException:
            self.store.observed_charge(None,expected=cost,now=now)
            raise ProviderError('Odds provider connection failed; billing is unknown and requests are held for review') from None
        try:
            if not self.store.observed_charge(response.headers.get('x-requests-last'),expected=cost,now=now):
                raise ProviderError('Provider cost was unexpected or unverifiable; requests held for review')
            if response.status_code != 200:
                raise ProviderError(f'Odds provider returned HTTP {response.status_code}; check plan/access')
            try:
                payload = response.json()
            except ValueError:
                raise ProviderError('Odds provider returned invalid JSON') from None
            if len(self.key)>=8 and self.key in json.dumps(payload,ensure_ascii=False):
                raise ProviderError('Provider response reflected credential material; no data was saved')
            # Only numeric quota observations are retained, never arbitrary header
            # text, URLs or account credentials. This is not account-wide authority.
            def counter(name):
                v=response.headers.get(name)
                return int(v) if isinstance(v,str) and v.isascii() and v.isdigit() and len(v)<=10 else None
            result = {'data': payload, 'received_at': utcnow().isoformat(),
                      'credits_remaining': counter('x-requests-remaining'),
                      'credits_last': counter('x-requests-last')}
            self.store.cache(cache_key, result)
            self.store.cache('provider-quota-observation',{
                'observed_at':result['received_at'],'remaining':result['credits_remaining'],
                'used':counter('x-requests-used'),'last_cost':result['credits_last'],
                'account_fingerprint':digest(self.key)})
            return result
        finally:
            close=getattr(response,'close',None)
            if callable(close):close()

    def odds(self, league, markets=('h2h',)):
        if league not in LEAGUES or not markets or not set(markets) <= {'h2h', 'spreads', 'totals'}:
            raise ValueError('Unsupported league or featured market')
        return self._get(f'sports/{LEAGUES[league][1]}/odds',
                         {'regions': 'ca', 'markets': ','.join(sorted(set(markets))), 'oddsFormat': 'decimal', 'dateFormat': 'iso'}, len(set(markets)))

    def events(self,league):
        if league not in LEAGUES:
            raise ValueError('Unsupported league')
        return self._get(f'sports/{LEAGUES[league][1]}/events',{'dateFormat':'iso'},0)

    def event_markets(self,league,event_id):
        if league not in LEAGUES or not re.fullmatch(r'[A-Za-z0-9_-]+',event_id):
            raise ValueError('Invalid event identifier')
        return self._get(f'sports/{LEAGUES[league][1]}/events/{event_id}/markets',
            {'regions':'ca','dateFormat':'iso'},1)

    def scores(self, league, days_from=3):
        if league not in LEAGUES or days_from not in (1,2,3):
            raise ValueError('Unsupported score request')
        return self._get(f'sports/{LEAGUES[league][1]}/scores',
                         {'daysFrom':days_from,'dateFormat':'iso'},2)

    def event_odds(self, league, event_id, markets):
        if league not in LEAGUES or not re.fullmatch(r'[A-Za-z0-9_-]+', event_id):
            raise ValueError('Invalid event identifier')
        if not markets or not all(re.fullmatch(r'[a-z0-9_]+', m) for m in markets) or len(markets) > 10:
            raise ValueError('Invalid market request')
        return self._get(f'sports/{LEAGUES[league][1]}/events/{event_id}/odds',
                         {'regions': 'ca', 'markets': ','.join(sorted(set(markets))), 'oddsFormat': 'decimal', 'dateFormat': 'iso'}, len(set(markets)))


def normalize(payload, league, received_at, now=None):
    """Return genuine quotes only. Malformed/missing timestamps are rejected.

    This provider offers no universal suspension feed; presence means observed in
    feed, not confirmed executable at an operator or immune to intervening suspension.
    """
    now = now or utcnow()
    events = payload if isinstance(payload, list) else [payload]
    quotes, rejected = [], 0
    for event in events:
        if not isinstance(event, dict):
            rejected += 1
            continue
        try:
            home, away = event['home_team'], event['away_team']
            if not isinstance(home,str) or not isinstance(away,str) or home==away:
                raise ValueError('Invalid competitors')
            if not isinstance(event.get('bookmakers',[]),list):
                raise ValueError('Invalid bookmakers')
            if not home or not away or event.get('sport_key') != LEAGUES[league][1] or not event['id']:
                raise ValueError('Event identity mismatch')
            parse_time(event['commence_time'])
            parse_time(received_at)
            for book in event.get('bookmakers', []):
                if not isinstance(book,dict) or not isinstance(book.get('markets',[]),list):
                    rejected += 1
                    continue
                for market in book.get('markets', []):
                    if not isinstance(market,dict) or not isinstance(market.get('outcomes',[]),list):
                        rejected += 1
                        continue
                    updated = market.get('last_update') or book.get('last_update')
                    for outcome in market.get('outcomes', []):
                        try:
                            if not isinstance(outcome,dict):
                                raise ValueError('Invalid outcome')
                            parse_time(updated)
                            price, point = outcome['price'], outcome.get('point')
                            if not finite(price) or price <= 1 or (point is not None and not finite(point)):
                                raise ValueError('Invalid number')
                            if not all(isinstance(v,str) and v.strip() for v in (outcome.get('name'),book.get('key'),market.get('key'))):
                                raise ValueError('Missing identity')
                            if not isinstance(outcome.get('description',''),str):
                                raise ValueError('Invalid participant identity')
                            quotes.append(Quote('the-odds-api', LEAGUES[league][0], league, event['id'],
                                f'{home} vs {away}', home, away, event['commence_time'], book['key'],
                                book.get('title', book['key']), market['key'], outcome['name'], point,
                                outcome.get('description', ''), price, updated, received_at,
                                'CA-ON' if eligible_book(book['key'], now) else 'unverified',
                                bool(market.get('suspended', False) or outcome.get('suspended', False))))
                        except (KeyError, TypeError, ValueError):
                            rejected += 1
        except (KeyError, TypeError, ValueError):
            rejected += 1
    # Reject ambiguous duplicate selections rather than selecting an arbitrary price.
    counts = {}
    for quote in quotes:
        counts[quote.id] = counts.get(quote.id, 0) + 1
    return [q for q in quotes if counts[q.id] == 1], rejected + sum(n for n in counts.values() if n > 1)
