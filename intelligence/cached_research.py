"""Re-evaluate a saved scan when results change, without any HTTP requests."""
from dataclasses import replace,asdict
import json
from intelligence.domain import utcnow, parse_time
from intelligence.diagnostics import results_revision


def record_and_label(analysis, store, now=None):
    from intelligence.processing import ensure_processing, record_shadow_forecasts, label_public_epl
    from intelligence.multi_readiness import process_expanded_paper
    from intelligence.current_soccer import prepare_epl
    now = now or utcnow()
    ensure_processing(store)
    analysis.processing['cached_research_forecasts_recorded'] = record_shadow_forecasts(analysis,store,now)
    with store.connect() as db:
        pending = [json.loads(r['payload']) for r in db.execute('SELECT f.payload FROM shadow_forecasts f LEFT JOIN shadow_outcomes o ON f.id=o.id WHERE o.id IS NULL')]
    ended = [p for p in pending if parse_time(p['quote']['commence_time'])<now]
    analysis.processing['pending_expanded_leagues'] = sorted({p['quote']['league'] for p in ended if p.get('target_scope')=='expanded_source_ft'})
    if any(p.get('target_scope')=='source_reported_ft' for p in ended) and not analysis.focused_model:
        analysis.focused_model = prepare_epl(store,now,allow_fetch=False)
    analysis.processing['cached_epl_labels'] = label_public_epl(store,analysis.focused_model,now)
    analysis.processing['cached_expanded_labels'] = process_expanded_paper(store,analysis,now,allow_results_fetch=False)
    return analysis


def recheck(analysis, store):
    from intelligence.pipeline import evaluate_quotes
    # Do not mutate another Streamlit session's cached analysis object.
    processing=dict(analysis.processing)
    saved=dict(processing.get('previously_recorded_research_only',{}))
    for q in analysis.quotes:
        e=analysis.advanced_estimates.get(q.id) or analysis.estimates.get(q.id)
        d=analysis.advanced_details.get(q.id,{})
        if e and d.get('prediction_at') and d.get('results_provider')=='football-data.org':
            saved[q.id]={'quote':asdict(q),'estimate':asdict(e),'model_evidence':dict(d),
                'scope':'Previously computed research; prices are not current unless reverified separately'}
    now=utcnow()
    recent=[]
    for key,value in saved.items():
        try:
            if (0<=(now-parse_time(value['model_evidence']['prediction_at'])).total_seconds()<21600
                and parse_time(value['quote']['commence_time'])>now):recent.append((key,value))
        except (ValueError,TypeError,KeyError):continue
    processing['previously_recorded_research_only']=dict(sorted(recent,key=lambda item:item[1]['model_evidence']['prediction_at'],reverse=True)[:1000])
    fresh = replace(analysis,processing=processing,exclusions={})
    fresh = evaluate_quotes(fresh,store,allow_results_fetch=False)
    return record_and_label(fresh,store)


def synchronize(snapshot, store):
    from intelligence.odds_snapshots import revision as odds_revision,restore
    from intelligence.providers import LEAGUES
    market_revision=odds_revision(store)
    market_changed=snapshot.get('market_revision')!=market_revision
    restored_changed=False
    if market_changed:
        analysis=snapshot['analysis']
        scope=snapshot.get('scope',())
        leagues=scope[0] if scope and isinstance(scope[0],(tuple,list)) else list(LEAGUES)
        restored=restore(replace(analysis,quotes=list(analysis.quotes),quote_origins=dict(analysis.quote_origins),warnings=list(analysis.warnings)),store,leagues)
        restored_changed=restored.quotes!=analysis.quotes
        if restored_changed:snapshot['analysis']=restored
    revision = results_revision(store)
    old = snapshot.get('results_revision')
    with store.connect() as db:
        reviews=[]
        for name in ('model_actions','forward_issues'):
            if db.execute("SELECT 1 FROM sqlite_master WHERE name=?",(name,)).fetchone():
                reviews.append((name,db.execute('SELECT count(*) FROM '+name).fetchone()[0]))
    from intelligence.domain import digest
    review_revision=digest(reviews)
    review_changed=snapshot.get('review_revision')!=review_revision and any(n for _,n in reviews)
    changed = restored_changed or review_changed or old is not None and old != revision
    if old is None:
        from intelligence.diagnostics import competition_diagnostics
        changed = changed or any(r['cached_snapshot_differs_from_used'] or
            (r['current_source_verification_fresh'] and r['current_supported_prices']>0 and not r['used_current_snapshot'])
            for r in competition_diagnostics(snapshot['analysis'],store))
    if changed:
        snapshot['analysis'] = recheck(snapshot['analysis'],store)
    snapshot['results_revision'] = results_revision(store)
    snapshot['market_revision'] = market_revision
    snapshot['review_revision'] = review_revision
    return snapshot['analysis']
