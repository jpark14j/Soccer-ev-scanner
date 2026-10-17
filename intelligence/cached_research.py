"""Re-evaluate a saved scan when results change, without any HTTP requests."""
from dataclasses import replace
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
    fresh = replace(analysis,processing=dict(analysis.processing),exclusions={})
    fresh = evaluate_quotes(fresh,store,allow_results_fetch=False)
    return record_and_label(fresh,store)


def synchronize(snapshot, store):
    revision = results_revision(store)
    old = snapshot.get('results_revision')
    changed = old is not None and old != revision
    if old is None:
        from intelligence.diagnostics import competition_diagnostics
        changed = any(r['cached_snapshot_differs_from_used'] or
            (r['current_source_verification_fresh'] and r['current_supported_prices']>0 and not r['used_current_snapshot'])
            for r in competition_diagnostics(snapshot['analysis'],store))
    if changed:
        snapshot['analysis'] = recheck(snapshot['analysis'],store)
    snapshot['results_revision'] = results_revision(store)
    return snapshot['analysis']
