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
    advanced_estimates: dict = field(default_factory=dict)
    advanced_details: dict = field(default_factory=dict)
    score_contexts: dict = field(default_factory=dict)
    quota: dict = field(default_factory=dict)
    slate: dict = field(default_factory=dict)
    processing: dict = field(default_factory=dict)
    focused_model: dict = field(default_factory=dict)
    expanded_models: dict = field(default_factory=dict)
    quote_origins: dict = field(default_factory=dict)
    evaluated_at: str = ''


def configured_store():
    from intelligence.ledger import restore
    store = Store(os.getenv('INTELLIGENCE_DB', 'data/intelligence.sqlite3'))
    restore(store,os.getenv('PREDICTION_LEDGER_DIR','ledger'))
    return store


def run_analysis(key, leagues=None, store=None, provider=None, markets=('h2h',), collect_results=None, autonomous=False, window_hours=48):
    store = store or configured_store()
    leagues = list(LEAGUES) if leagues is None else leagues
    provider = provider or OddsAPI(key, store, daily_limit=int(os.getenv('ODDS_DAILY_CREDITS','9')),
                                   ttl=int(os.getenv('ODDS_CACHE_SECONDS','1800')))
    if autonomous:
        from intelligence.slate import run_slate
        return run_slate(key,leagues,store,provider,window_hours=window_hours,collect_results=collect_results)
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
            store.cache('last-success-'+league+'-'+','.join(sorted(markets)), response)
            if set(markets)=={'h2h'}:
                store.cache('last-success-'+league,response)
        except (ProviderError, ValueError) as exc:
            # Only ProviderError uses safe locally generated messages.
            message = str(exc) if isinstance(exc, ProviderError) else 'Invalid provider contract'
            result.errors.append(f'{league}: {message}')
            response = store.cached('last-success-'+league+'-'+','.join(sorted(markets)), 604800)
            if response is None and set(markets)=={'h2h'}:
                response=store.cached('last-success-'+league,604800)
            if response is None:
                continue
        quotes, rejected = normalize(response['data'], league, response['received_at'],now=utcnow())
        result.quotes.extend(quotes)
        excluded['Invalid/ambiguous provider records'] += rejected
    result=restore_market_snapshots(result,store,leagues)
    if (os.getenv('COLLECT_RESULTS','1')=='1' if collect_results is None else collect_results) and hasattr(provider,'scores'):
        from intelligence.results import collect
        try:
            collect(provider,store,[league for league in leagues if league in ('NBA','MLB')])
        except (ProviderError,ValueError):
            result.warnings.append('Recent completed-result collection unavailable; no outcomes inferred')
    result.exclusions=dict(excluded)
    return evaluate_quotes(result,store)


def restore_market_snapshots(result,store,leagues):
    """Restore private cached featured/event observations without resetting age."""
    import json
    from datetime import timedelta
    by_id={q.id:q for q in result.quotes}
    for q in result.quotes:
        result.quote_origins.setdefault(q.id,{'origin':'analysis input','received_at':q.received_at})
    now=utcnow()
    with store.connect() as db:
        for league in leagues:
            if league not in LEAGUES:
                continue
            rows=db.execute('SELECT at,payload FROM cache WHERE key LIKE ? OR key LIKE ?',
                ('last-success-'+league+'-%','event-snapshot-'+league+'-%')).fetchall()
            for row in rows:
                try:
                    age=now-parse_time(row['at'])
                    if not timedelta(0)<=age<=timedelta(days=7):
                        continue
                    response=json.loads(row['payload'])
                    quotes,_=normalize(response['data'],league,response['received_at'],now)
                    for q in quotes:
                        old=by_id.get(q.id)
                        if old is None or (parse_time(q.source_updated_at),parse_time(q.received_at))>(parse_time(old.source_updated_at),parse_time(old.received_at)):
                            by_id[q.id]=q
                            result.quote_origins[q.id]={'origin':'restored private cache','cache_recorded_at':row['at'],'received_at':q.received_at}
                except (ValueError,KeyError,TypeError):
                    result.warnings.append('A malformed cached market snapshot was ignored')
    result.quotes=list(by_id.values())
    return result


def evaluate_quotes(result,store,*,allow_results_fetch=True):
    """Rebuild model evidence for merged featured/event quotes without fetching odds."""
    from intelligence.advanced_models import make_context,probability,forecast_problem
    result.opportunities=[]
    result.research=[]
    result.estimates={}
    result.advanced_estimates={}
    result.advanced_details={}
    result.score_contexts={}
    result.expanded_models={}
    result.focused_model={}
    excluded=Counter(result.exclusions)
    now = utcnow()
    result.evaluated_at=now.isoformat()
    from intelligence.epl_forecasts import supported
    from intelligence.current_soccer import prepare_epl as prepare,forecast
    focused=None
    predictions, histories, reports, champions, history_hashes = {}, {}, {}, {}, {}
    from intelligence.book_optimizer import scoped_quotes
    for q in scoped_quotes(result,now):
        if q.status(now) != 'current':
            excluded[q.status(now)] += 1
            continue
        if q.jurisdiction != 'CA-ON':
            excluded['Ontario feed not established'] += 1
            continue
        if supported(q):
            if focused is None:
                focused=prepare(store,now) if allow_results_fetch else prepare(store,now,allow_fetch=False)
                result.focused_model=focused
            estimate,detail=forecast(q,focused,now)
            result.research.append(detail)
            result.advanced_details[q.id]=detail
            if estimate:
                result.estimates[q.id]=estimate
                result.advanced_estimates[q.id]=estimate
            excluded['Focused EPL model remains research-only' if estimate else 'Focused EPL input/evidence gate']+=1
            continue
        from intelligence.expanded_forecasts import supported as expanded_supported
        from intelligence.current_soccer import prepare_expanded as expanded_prepare,forecast as expanded_forecast
        if expanded_supported(q):
            if q.league not in result.expanded_models:
                result.expanded_models[q.league]=(expanded_prepare(q.league,store,now) if allow_results_fetch else
                    expanded_prepare(q.league,store,now,allow_fetch=False))
            estimate,detail=expanded_forecast(q,result.expanded_models[q.league],now)
            result.research.append(detail);result.advanced_details[q.id]=detail
            if estimate:
                result.estimates[q.id]=estimate;result.advanced_estimates[q.id]=estimate
            excluded['Expanded model remains research-only' if estimate else 'Expanded current-data gate']+=1
            continue
        league = q.league
        if league not in histories:
            try:
                directory=os.getenv('HISTORY_DIR','data/history')
                report_directory=os.getenv('MODEL_DIR','data/models')
                histories[league] = ((load_soccer(league,store) if allow_results_fetch else load_soccer(league,store,allow_fetch=False))
                    if q.sport=='Soccer' else load_local(league,directory))
                if histories[league].empty:
                    from intelligence.results import history_from_results
                    histories[league] = history_from_results(league,store)
                if q.sport in ('NBA','MLB') and len(histories[league])<100:
                    archive=load_local(league,os.getenv('RESEARCH_HISTORY_DIR','data/research/history'))
                    if not archive.empty:
                        histories[league]=archive
                        report_directory=os.getenv('RESEARCH_MODEL_DIR','data/research/models')
                reports[league] = load_report(league,report_directory)
                from intelligence.lifecycle import active_champion
                champions[league]=active_champion(store,q.sport,'h2h')
                if reports[league] and reports[league].get('data_sha256') != digest(histories[league].to_json(orient='records',date_format='iso')):
                    reports[league] = None
                    result.warnings.append(f'{league}: evaluation dataset differs from loaded history; calibration and validation are disabled')
            except (ValueError, OSError, KeyError):
                excluded['Invalid historical data/model evidence'] += 1
                histories[league], reports[league], champions[league] = None, None, None
        history, report = histories[league], reports[league]
        if history is None or history.empty:
            excluded['Historical statistics unavailable'] += 1
            blockers=['Historical statistics are unavailable or failed source/licence checks; no probability was estimated']
            if q.league=='Premier League':
                blockers.insert(0,'The portable calibrated EPL model covers BTTS and exactly 2.5-goal totals; this market is outside that evaluation')
            result.research.append({'quote_id':q.id,'blockers':blockers})
            continue
        if q.sport in ('NBA','MLB') and (now.date()-history.date.max().date()).days>90:
            result.research.append({'quote_id':q.id,'blockers':[
                f'{q.sport} source history ends {history.date.max().date().isoformat()}, more than 90 days old; no current forecast was inferred',
                'Historical diagnostics remain available; complete current team and availability inputs are needed']})
            excluded['Stale current sport features']+=1
            continue
        event_key = (q.league,q.event_id)
        if league not in history_hashes:
            history_hashes[league]=digest(history.to_json(orient='records',date_format='iso'))
        problem=forecast_problem(q)
        if event_key not in result.score_contexts and not problem:
            result.score_contexts[event_key]=make_context(history,q.sport,q.home,q.away,q.commence_time,as_of=now)
        context=result.score_contexts.get(event_key)
        advanced_p=probability(context,q) if context is not None and not problem else None
        if advanced_p is not None:
            estimate=Estimate(advanced_p,0.,1.,context.version,context.training_end,'',False,
                ('Score-distribution research is not a calibrated live probability',context.method,
                 'Operator settlement rules, injuries and confirmed lineups are unverified'),q.sport,q.league,q.market)
            result.advanced_estimates[q.id]=estimate
            result.advanced_details[q.id]={'quote_id':q.id,'probability':advanced_p,'model':context.version,
                'validated':False,'lower':0.,'upper':1.,'training_end':context.training_end,
                'data_sha256':history_hashes[league],
                'history_n':context.history_n,'method':context.method,
                'interval_basis':'Full 0–1 envelope: no validated event-specific uncertainty calibration',
                'blockers':['No validated live-line probability or market-beating evidence',
                            'Fixed-threshold historical diagnostics do not validate every live line',
                            'Missing current injuries/lineups and verified operator settlement scope']}
        if q.market!='h2h':
            if advanced_p is not None:
                result.estimates[q.id]=result.advanced_estimates[q.id]
                result.research.append(result.advanced_details[q.id])
            else:
                result.research.append({'quote_id':q.id,'blockers':[problem or 'Insufficient source-backed team history for this score model']})
            excluded['Advanced market remains research-only']+=1
            continue
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
        approved=bool(report and champions.get(league) and champions[league].get('evidence_id')==report.get('evidence_id'))
        estimate = Estimate(p,lower,upper,VERSIONS[q.sport],prior.date.max().isoformat()+'+00:00',
                            report['evidence_id'] if report else '',
                            bool(report and approved and not promotion_reasons(report) and enough),
                            ('Empirical calibration interval is not a guarantee for this event',
                             'Lineups, injuries and current player availability not modeled',
                             'Provider quote may change or be suspended before execution'),
                            q.sport,q.league,q.market)
        result.estimates[q.id] = estimate
        opportunity, reason = qualify(q,estimate,now)
        blockers = promotion_reasons(report) if report else ['Matching chronological calibration/test evidence unavailable']
        if not approved:
            blockers=blockers+['No reviewed champion activation matches this exact model artifact']
        if report and not enough:
            blockers = blockers + ['Fewer than 50 calibration outcomes in this probability bucket']
        result.research.append({'quote_id':q.id,'probability':p,'model':estimate.model_version,
                                'validated':estimate.validated,'reason':reason,
                                'lower':lower,'upper':upper,'training_end':estimate.training_end,
                                'evidence_id':estimate.evidence_id,'blockers':blockers,
                                'data_sha256':history_hashes[league],
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
