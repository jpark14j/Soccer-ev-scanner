"""Forensic odds availability from saved data only. Never initiates a refresh."""
from collections import Counter
from dataclasses import replace
from datetime import timedelta
import sqlite3
from intelligence.domain import utcnow,parse_time
from intelligence.diagnostics import quote_inventory
from intelligence.odds_snapshots import read,restore
from intelligence.parlay_research import quote_problem,leg_evidence
from intelligence.research_ranking import evidence_problem
from intelligence.research_top import SourceChecks
from intelligence.quota import quota_details


def inspect_odds(analysis,store,books=None,now=None,cap=9,retrieval_cache_seconds=1800):
    now=now or utcnow()
    try:
        snapshots,facts=read(store,now)
        from intelligence.pipeline import Analysis
        stored=restore(Analysis(slate=dict(analysis.slate)),store,{s['league'] for s in snapshots},now)
        with store.connect() as db:
            present=db.execute("SELECT name FROM sqlite_master WHERE name='store_identity'").fetchone()
            identity=dict(db.execute('SELECT instance,created_at FROM store_identity WHERE id=1').fetchone()) if present else None
        quota=quota_details(store,cap,now)
    except (sqlite3.Error,OSError):
        return {'code':'storage_unavailable','message':'Saved odds storage is unavailable; no current-price readiness can be inferred.',
            'next_action':'Check the preview database path and storage health before requesting prices.','network_requests':0}
    inventory=quote_inventory(analysis,now);stored_inventory=quote_inventory(stored,now)
    selected=[q for q in analysis.quotes if books is None or q.bookmaker in books]
    visible=replace(analysis,quotes=selected);visible_inventory=quote_inventory(visible,now)
    modeled=0;model_blocks=Counter();checks=SourceChecks(store,now)
    for q in selected:
        if quote_problem(q,now):continue
        end=analysis.slate.get('window_end')
        if end and parse_time(q.commence_time)>parse_time(end):continue
        leg=leg_evidence(q,analysis,now);problem=evidence_problem(leg,now) or checks.check(leg)
        if problem:model_blocks[problem]+=1
        else:modeled+=1
    raw_quotes=[q for s in snapshots for q in s['quotes']]
    if visible_inventory['current_eligible']:
        code='current_prices_available';message='Current Ontario prices are available.'
        action='Inspect model requirements below when current prices have no eligible research estimate.'
    elif inventory['current_eligible']:
        code='view_filters';message='Current Ontario prices exist outside the selected sportsbook view.'
        action='Review Sportsbooks in view; changing this view does not request odds.'
    elif stored_inventory['current_eligible']:
        code='newer_saved_prices';message='Fresh saved prices exist outside this session snapshot or competition scope.'
        action='Use Recheck saved research to apply saved prices without an API request; check competition scope.'
    elif inventory['stale_upcoming_in_window'] or stored_inventory['stale_upcoming_in_window']:
        code='expired_prices';message='Saved upcoming prices have expired; results freshness does not refresh sportsbook odds.'
        action='Inspect quota and retrieval-cache status. Request a deliberate capped refresh only when permitted; repeated refreshes inside the cache window cannot make an old source timestamp current.'
    elif inventory['observations'] or raw_quotes:
        code='outside_window_or_ineligible';message='Stored observations are started, outside the scan window, expired beyond retention or otherwise ineligible.'
        action='Inspect source timestamps, scan window and provenance in the expanded audit; do not use old prices.'
    else:
        code='no_saved_prices';message='No usable individual-price observations are saved in this store/session.'
        action='Check store identity and the last query audit. A new store, an empty provider response or an unrun scan are different causes; a healthy database alone does not establish saved odds.'
    if quota.get('recovery_hold'):
        action='Restored-store requests are held. Inspect records and obtain an explicit provider-usage review before refresh; a UTC reset does not release the hold.'
    elif quota['remaining']==0 and code!='current_prices_available':
        action+=' Local odds allowance exhausted; wait until '+quota['next_reset_toronto']+'. The provider account quota is separate.'
    last_receipt=max((s['received_at'] for s in snapshots),default=None)
    return {'code':code,'message':message,'next_action':action,'observed_at':now.isoformat(),
        'store_identity':identity,'stored_snapshot_facts':facts,'stored_observation_rows':len(raw_quotes),
        'stored_unique_quote_ids':len({q.id for q in raw_quotes}),
        'saved_rejected_observation_rows':sum(s['rejected'] for s in snapshots),
        'stored_snapshots_beyond_retention':sum(not s['within_retention'] for s in snapshots),
        'session_prices':inventory,'restorable_stored_prices':stored_inventory,'visible_prices':visible_inventory,
        'model_eligible_individual_observations':modeled,'model_exclusions':dict(model_blocks),
        'session_errors':list(analysis.errors),'query_status_counts':dict(Counter(q.get('status','unknown') for q in analysis.slate.get('queries',[]))),
        'quota':quota,'network_requests':0,
        'latest_saved_receipt':last_receipt.isoformat() if last_receipt else None,
        'receipt_plus_configured_retrieval_TTL':(last_receipt+timedelta(seconds=retrieval_cache_seconds)).isoformat() if last_receipt else None,
        'note':'Raw stored rows may repeat a selection across snapshots; current and model-eligible counts are separate. Store identity needs a prior record to establish a reset. This audit does not contact providers.'}
