"""Read-only evidence from the actual session, source cache and frozen artifacts.

Available results are not automatically the snapshot used for inference. Training
provenance, feature freshness, execution and approval are separate facts.
"""
from collections import Counter
from intelligence.domain import utcnow, parse_time, digest
from intelligence.current_results import CODES, configuration, cached_status
from intelligence.competitions import COMPETITIONS
from intelligence.parlay_research import quote_problem


def quote_inventory(analysis, now=None):
    now = now or utcnow()
    end = parse_time(analysis.slate['window_end']) if analysis.slate.get('window_end') else None
    counts = Counter(q.id for q in analysis.quotes)
    partition = Counter()
    statuses = Counter()
    origins = Counter()
    current_games = set()
    stale_games = set()
    for q in analysis.quotes:
        status = q.status(now)
        statuses[status] += 1
        origins[analysis.quote_origins.get(q.id,{}).get('origin','unattributed analysis input')] += 1
        try:
            start = parse_time(q.commence_time)
            inside = now < start and (end is None or start <= end)
        except (ValueError,TypeError):
            partition['invalid_or_other_ineligible'] += 1
            continue
        if not inside:
            partition['outside_window_or_started_inspection'] += 1
        elif status == 'stale':
            partition['stale_upcoming_in_window'] += 1
            stale_games.add((q.league,q.event_id))
        elif counts[q.id] == 1 and not quote_problem(q,now):
            partition['current_eligible'] += 1
            current_games.add((q.league,q.event_id))
        else:
            partition['invalid_or_other_ineligible'] += 1
    return {'observations':len(analysis.quotes),'unique_quote_ids':len(counts),
        'duplicate_observation_rows':sum(n-1 for n in counts.values()),
        'status_counts':dict(statuses),'origin_counts':dict(origins),
        'current_eligible':partition['current_eligible'],
        'stale_upcoming_in_window':partition['stale_upcoming_in_window'],
        'outside_window_or_started_inspection':partition['outside_window_or_started_inspection'],
        'invalid_or_other_ineligible':partition['invalid_or_other_ineligible'],
        'games_with_current_prices':len(current_games),'games_with_stale_observations':len(stale_games),
        'price_expiry_seconds':300,'saved_snapshot_retention_seconds':604800,
        'note':'Counts are individual bookmaker/selection/line observations, not games. Saved snapshots are retained up to seven days; timestamps are never reset. The default 30-minute retrieval cache does not extend five-minute price eligibility. Stale upcoming prices are also a current-price gap, not actionable odds. No refresh is performed by this diagnostic.'}


def results_revision(store, now=None):
    """Changes only on source/permission/status changes, not on page navigation."""
    now = now or utcnow()
    config = configuration()
    return digest((config.enabled,config.problem,
        {league:cached_status(store,league,now) for league in CODES}))


def competition_diagnostics(analysis=None, store=None, now=None):
    import json
    from intelligence.data_adapters import ROOT
    from intelligence.expanded_models import load, policy
    from intelligence.epl_forecasts import load_artifact
    now = now or utcnow()
    config = configuration()
    try:
        audit = json.loads((ROOT/'research_assets/source_coverage.json').read_text())
    except (ValueError,OSError):
        audit = {}
    rows = []
    from intelligence.book_optimizer import scoped_quotes
    scoped_ids = {q.id for q in scoped_quotes(analysis,now)} if analysis else set()
    for c in COMPETITIONS.values():
        historical = audit.get(c.name,{})
        bundle = load_artifact() if c.name=='Premier League' else load(c.name) if c.name in policy()['targets'] else None
        prepared = (analysis.focused_model if c.name=='Premier League' else analysis.expanded_models.get(c.name,{})) if analysis else {}
        prepared = prepared or {}
        public = next((r for r in historical.get('coverage',[]) if r['season']=='2026-27'),{})
        available = cached_status(store,c.name,now) if store and c.name in CODES and config.enabled else {}
        if config.enabled and c.name in CODES:
            provider = 'football-data.org'
            health = available.get('coverage',{})
            latest = health.get('latest_completed')
            checked = available.get('checked_at')
            source_problem = config.problem or available.get('problem')
            if not available.get('ok') or not available.get('fresh'):
                source_problem = source_problem or 'No fresh verified results snapshot is available'
            source_fresh = bool(available.get('ok') and available.get('fresh') and not config.problem)
            missing = health.get('unresolved_past')
        else:
            provider = prepared.get('source_kind','OpenFootball bundled current-season snapshot') if c.sport=='Soccer' and historical else 'No current source verified'
            latest = prepared.get('state',{}).get('latest') or public.get('latest_completed') or historical.get('data_through')
            checked = prepared.get('source_checked_at') or prepared.get('source_check') or historical.get('checked_at')
            missing = public.get('unresolved_past')
            if prepared.get('fixtures'):
                missing = sum((e.get('date') or e.get('event_date')) < now.date().isoformat()
                    and e.get('status','unresolved')!='completed' and e.get('season')=='2026-27' for e in prepared['fixtures'])
            source_problem = prepared.get('problem')
            source_fresh = False
            health = public
        if latest and (now.date()-parse_time(latest+'T00:00:00+00:00').date()).days>21:
            source_problem = source_problem or 'Current results exceed the 21-day freshness limit'
        if missing:
            source_problem = source_problem or 'Unresolved earlier source fixtures'
        if c.sport in ('NBA','MLB'):
            source_problem = 'Current-season context/history insufficient; player/availability features unverified'
        used = None
        if prepared and not prepared.get('problem'):
            used = {'provider':prepared.get('results_provider',prepared.get('source_kind','bundled snapshot')),
                'body_sha256':prepared.get('results_sha256'), 'feature_data_sha256':prepared.get('data_sha256'),
                'latest_feature_result':prepared.get('state',{}).get('latest'),
                'observed_at':prepared.get('results_observed_at') or checked}
        switched = bool(used and available.get('sha256') and used['body_sha256']!=available['sha256'])
        source_problem = source_problem or ('Newer cached results have not been applied to this analysis' if switched else None)
        quotes = [q for q in getattr(analysis,'quotes',[]) if q.league==c.name]
        from intelligence.epl_forecasts import supported as epl_supported
        from intelligence.expanded_forecasts import supported as expanded_supported
        supported_quotes = [q for q in quotes if epl_supported(q) or expanded_supported(q)]
        supported_ids = {q.id for q in supported_quotes}
        details = [r for r in getattr(analysis,'research',[]) if r.get('quote_id') in supported_ids]
        estimated = [q for q in supported_quotes if (q.id in getattr(analysis,'estimates',{}) or q.id in getattr(analysis,'advanced_estimates',{}))]
        actionable_estimates = [q for q in estimated if q.id in scoped_ids and not quote_problem(q,now)]
        current_prices = [q for q in quotes if q.id in scoped_ids and not quote_problem(q,now)]
        blockers = list(dict.fromkeys(b for r in details for b in r.get('blockers',[])))
        if c.sport in ('NBA','MLB'):
            inference_status = 'Blocked: '+source_problem
        elif not bundle:
            inference_status = 'Not implemented for this competition/market'
        elif source_problem or prepared.get('problem'):
            inference_status = 'Blocked: '+(prepared.get('problem') or source_problem)
        elif actionable_estimates:
            inference_status = f'Research inference executed: {len(actionable_estimates)} estimates with current eligible prices'
        elif estimated:
            inference_status = 'Inference was executed in this snapshot; associated prices are no longer current'
        elif details:
            inference_status = 'Inference attempted; inputs blocked: '+(blockers[0] if blockers else 'inspect per-market requirements')
        else:
            target = 'BTTS or totals exactly 2.5' if c.name=='Premier League' else 'BTTS' if c.name=='Bundesliga' else 'totals exactly 2.5'
            inference_status = 'Not executed: a current Ontario '+target+' quote and per-event input checks are required'
        rows.append({'competition':c.name,'competition_id':c.id,'sport':c.sport,
            'coverage':'Verified historical snapshot; raw files need private import' if historical else 'Discovery target; no dataset integrated',
            'historical_completed':historical.get('completed',historical.get('rows',0)),
            'historical_training_source':'OpenFootball publisher-CC0 pinned history' if c.sport=='Soccer' and historical else historical.get('source','No historical source integrated'),
            'historical_training_cutoff':bundle.get('policy',{}).get('train_end') if bundle else None,
            'current_source':provider,'latest_result':latest,'past_unresolved':missing,
            'current_completed':health.get('completed'),'source_check':checked,
            'current_source_verification_fresh':source_fresh,'source_problem':source_problem,
            'available_current_snapshot_sha256':available.get('sha256'),
            'prepared_current_snapshot':used,'used_current_snapshot':used if details or estimated else None,
            'cached_snapshot_differs_from_used':switched,
            'model':bundle['model_version'] if bundle else 'No frozen current model',
            'model_status':'Research model' if bundle else 'Unavailable',
            'model_input_readiness':('Blocked: '+(prepared.get('problem') or source_problem)) if prepared.get('problem') or source_problem else 'Prepared; per-event gates still apply' if used else 'Results checks available; model inputs have not been assessed',
            'current_forecast':inference_status,'inference_attempts':len(details),
            'snapshot_estimates':len(estimated),'current_estimates':len(actionable_estimates),
            'last_inference_at':max((r.get('prediction_at','') for r in details),default=None) or None,
            'current_eligible_prices':len(current_prices),
            'current_supported_prices':sum(q.id in scoped_ids and not quote_problem(q,now) for q in supported_quotes),
            'unsupported_current_markets':dict(Counter(q.market for q in current_prices if q.id not in supported_ids)),
            'model_blockers':blockers,'validation':'Not approved','betting_edge':'Not approved'})
    return rows


def readiness_export(analysis, store, now=None):
    now = now or utcnow()
    return {'format':'sports-intelligence-readiness-v1','observed_at':now.isoformat(),
        'analysis_loaded_at':analysis.checked_at,'model_evaluated_at':analysis.evaluated_at,
        'competitions':competition_diagnostics(analysis,store,now),
        'prices':quote_inventory(analysis,now),
        'note':'Read-only evidence from this running app, not a historical backtest or a model approval. No API calls are made by export.'}
