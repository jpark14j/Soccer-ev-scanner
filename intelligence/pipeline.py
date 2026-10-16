"""Shared application/headless orchestration. Missing evidence fails closed."""
from collections import Counter
from dataclasses import dataclass, field
import os
from intelligence.domain import Estimate, digest, utcnow, parse_time
from intelligence.evaluation import calibrate, load_report, promotion_reasons
from intelligence.ev import best_prices, market_baselines, qualify
from intelligence.history import load_local, load_soccer
from intelligence.models import VERSIONS, predict
from intelligence.providers import LEAGUES, OddsAPI, ProviderError, normalize
from intelligence.storage import Store
from intelligence.team_codes import history_name


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
    estimates: dict = field(default_factory=dict)


def configured_store():
    from intelligence.ledger import restore
    store = Store(os.getenv('INTELLIGENCE_DB', 'data/intelligence.sqlite3'))
    restore(store,os.getenv('PREDICTION_LEDGER_DIR','ledger'))
    return store


def run_analysis(key, leagues=None, store=None, provider=None, markets=('h2h',), collect_results=None):
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
    if (os.getenv('COLLECT_RESULTS','1')=='1' if collect_results is None else collect_results) and hasattr(provider,'scores'):
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
            result.research.append({'quote_id':q.id,'blockers':['No market-specific spread/total forecast or push-settlement model is connected']})
            continue
        league = q.league
        if league not in histories:
            try:
                directory=os.getenv('HISTORY_DIR','data/history')
                report_directory=os.getenv('MODEL_DIR','data/models')
                histories[league] = load_soccer(league, store) if q.sport == 'Soccer' else load_local(league,directory)
                if histories[league].empty:
                    from intelligence.results import history_from_results
                    histories[league] = history_from_results(league,store)
                if q.sport in ('NBA','MLB') and len(histories[league])<100:
                    archive=load_local(league,os.getenv('RESEARCH_HISTORY_DIR','data/research/history'))
                    if not archive.empty:
                        histories[league]=archive
                        report_directory=os.getenv('RESEARCH_MODEL_DIR','data/research/models')
                reports[league] = load_report(league,report_directory)
                if reports[league] and reports[league].get('data_sha256') != digest(histories[league].to_json(orient='records',date_format='iso')):
                    reports[league] = None
                    result.warnings.append(f'{league}: evaluation dataset differs from loaded history; calibration and validation are disabled')
            except (ValueError, OSError, KeyError):
                excluded['Invalid historical data/model evidence'] += 1
                histories[league], reports[league] = None, None
        history, report = histories[league], reports[league]
        if history is None or history.empty:
            excluded['Historical statistics unavailable'] += 1
            result.research.append({'quote_id':q.id,'blockers':['Historical statistics are unavailable or failed source/licence checks; no probability was estimated']})
            continue
        event_key = (q.league,q.event_id)
        if event_key not in predictions:
            options=set(history.HomeTeam)|set(history.AwayTeam)
            home=history_name(q.sport,q.home,options)
            away=history_name(q.sport,q.away,options)
            predictions[event_key] = predict(history,q.sport,home,away,q.commence_time) if home and away and home!=away else None
        probabilities = predictions[event_key]
        if probabilities is None:
            excluded['Insufficient team history'] += 1
            result.research.append({'quote_id':q.id,'blockers':['Historical team names are unmatched/ambiguous or there are too few earlier games to fit this sport model']})
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
        result.estimates[q.id] = estimate
        opportunity, reason = qualify(q,estimate,now)
        blockers = promotion_reasons(report) if report else ['Matching chronological calibration/test evidence unavailable']
        if report and not enough:
            blockers = blockers + ['Fewer than 50 calibration outcomes in this probability bucket']
        result.research.append({'quote_id':q.id,'probability':p,'model':estimate.model_version,
                                'validated':estimate.validated,'reason':reason,
                                'lower':lower,'upper':upper,'training_end':estimate.training_end,
                                'evidence_id':estimate.evidence_id,'blockers':blockers,
                                'calibration_bin_n':bin_data['n'] if report else 0,
                                'calibration_n':report.get('calibration_n',0) if report else 0,
                                'test_n':report.get('test_n',0) if report else 0,
                                'calibration_gap':report.get('calibration_gap') if report else None,
                                'diagnostic_scores':report.get('metrics') if report else None,
                                'data_source':report.get('data_source','') if report else '',
                                'interval_basis':'Calibration-bin Wilson envelope; not an event-specific confidence guarantee' if report else 'No calibrated uncertainty evidence; full 0–1 envelope'})
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
