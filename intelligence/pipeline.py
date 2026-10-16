"""Shared application/headless orchestration. Missing evidence fails closed."""
from collections import Counter
from dataclasses import dataclass, field
import os
from intelligence.domain import Estimate, utcnow, parse_time
from intelligence.evaluation import calibrate, load_report, promotion_reasons
from intelligence.ev import best_prices, market_baselines, qualify
from intelligence.history import load_local, load_soccer
from intelligence.models import VERSIONS, predict
from intelligence.providers import LEAGUES, OddsAPI, ProviderError, normalize
from intelligence.storage import Store


@dataclass
class Analysis:
    quotes: list = field(default_factory=list)
    opportunities: list = field(default_factory=list)
    research: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    exclusions: dict = field(default_factory=dict)
    baseline: dict = field(default_factory=dict)
    checked_at: str = ''


def configured_store():
    from intelligence.ledger import restore
    store = Store(os.getenv('INTELLIGENCE_DB', 'data/intelligence.sqlite3'))
    restore(store,os.getenv('PREDICTION_LEDGER_DIR','ledger'))
    return store


def run_analysis(key, leagues=None, store=None, provider=None, markets=('h2h',)):
    store = store or configured_store()
    leagues = list(LEAGUES) if leagues is None else leagues
    provider = provider or OddsAPI(key, store, daily_limit=int(os.getenv('ODDS_DAILY_CREDITS','16')),
                                   ttl=int(os.getenv('ODDS_CACHE_SECONDS','1800')))
    result = Analysis(checked_at=utcnow().isoformat())
    excluded = Counter()
    for league in leagues:
        if league not in LEAGUES:
            result.errors.append(f'{league}: Unsupported competition')
            continue
        try:
            response = provider.odds(league, markets)
            if not isinstance(response['data'], list):
                raise ProviderError('Odds provider event list missing')
            store.cache('last-success-'+league, response)
        except (ProviderError, ValueError) as exc:
            # Only ProviderError uses safe locally generated messages.
            message = str(exc) if isinstance(exc, ProviderError) else 'Invalid provider contract'
            result.errors.append(f'{league}: {message}')
            response = store.cached('last-success-'+league, 86400)
            if response is None:
                continue
        quotes, rejected = normalize(response['data'], league, response['received_at'],now=utcnow())
        result.quotes.extend(quotes)
        excluded['Invalid/ambiguous provider records'] += rejected
    if os.getenv('COLLECT_RESULTS','1')=='1' and hasattr(provider,'scores'):
        from intelligence.results import collect
        try:
            collect(provider,store,[league for league in leagues if league in ('NBA','MLB')])
        except (ProviderError,ValueError):
            result.warnings.append('Recent completed-result collection unavailable; no outcomes inferred')
    now = utcnow()
    predictions, histories, reports = {}, {}, {}
    for q in result.quotes:
        if q.status(now) != 'current':
            excluded[q.status(now)] += 1
            continue
        if q.jurisdiction != 'CA-ON':
            excluded['Ontario feed not established'] += 1
            continue
        if q.market != 'h2h':
            excluded['No validated model for market'] += 1
            continue
        league = q.league
        if league not in histories:
            try:
                histories[league] = load_soccer(league, store) if q.sport == 'Soccer' else load_local(league, os.getenv('HISTORY_DIR','data/history'))
                if histories[league].empty:
                    from intelligence.results import history_from_results
                    histories[league] = history_from_results(league,store)
                reports[league] = load_report(league, os.getenv('MODEL_DIR','data/models'))
            except (ValueError, OSError, KeyError):
                excluded['Invalid historical data/model evidence'] += 1
                histories[league], reports[league] = None, None
        history, report = histories[league], reports[league]
        if history is None or history.empty:
            excluded['Historical statistics unavailable'] += 1
            continue
        event_key = (q.league,q.event_id)
        if event_key not in predictions:
            predictions[event_key] = predict(history,q.sport,q.home,q.away,q.commence_time)
        probabilities = predictions[event_key]
        if probabilities is None:
            excluded['Insufficient team history'] += 1
            continue
        names = [q.home,'Draw',q.away] if q.sport == 'Soccer' else [q.home,q.away]
        if q.selection not in names:
            excluded['Unknown h2h selection'] += 1
            continue
        if report:
            probabilities = calibrate(probabilities,report['temperature'])
        p = probabilities[names.index(q.selection)]
        interval, enough = (0.,1.), False
        if report:
            bin_data = report['calibration_bins'][min(9,int(p*10))]
            interval = bin_data['interval']
            enough = bin_data['n'] >= 50
        # Envelope contains the forecast as well as the empirical bin interval.
        lower, upper = min(p,interval[0]), max(p,interval[1])
        prior = history[history.date < parse_time(q.commence_time).replace(tzinfo=None,hour=0,minute=0,second=0,microsecond=0)]
        estimate = Estimate(p,lower,upper,VERSIONS[q.sport],prior.date.max().isoformat()+'+00:00',
                            report['evidence_id'] if report else '',
                            bool(report and not promotion_reasons(report) and enough),
                            ('Empirical calibration interval is not a guarantee for this event',
                             'Lineups, injuries and current player availability not modeled',
                             'Provider quote may change or be suspended before execution'),
                            q.sport,q.league,q.market)
        opportunity, reason = qualify(q,estimate,now)
        result.research.append({'quote_id':q.id,'probability':p,'model':estimate.model_version,
                                'validated':estimate.validated,'reason':reason})
        if opportunity:
            result.opportunities.append(opportunity)
        else:
            excluded[reason] += 1
    result.opportunities = best_prices(result.opportunities)
    result.exclusions = dict(excluded)
    result.baseline = market_baselines(result.quotes, now)
    return result


def publish_current(result, store, now=None):
    """Recheck expiry at publication; renders must not revive cached recommendations."""
    now = now or utcnow()
    published = []
    for o in result.opportunities:
        eligible, _ = qualify(o.quote,o.estimate,now)
        if eligible:
            published.append(store.publish(eligible, now=now))
    return published
