"""Scheduler-neutral research worker. Online/background mode is disabled by default."""
import json
import os
import uuid
from intelligence.domain import utcnow
from intelligence.data_settings import load_settings
from intelligence.lifecycle import registry_status
from intelligence.persistence import storage_status
from intelligence.pipeline import run_analysis
from intelligence.providers import OddsAPI
from intelligence.ledger import archive


def run_cycle(store,leagues,*,offline=True):
    settings=load_settings();now=utcnow();identifier=uuid.uuid4().hex
    if not offline and not all(os.getenv(name)=='1' for name in
            ('RESEARCH_WORKER_ENABLED','RESEARCH_DURABLE_STORAGE_VERIFIED','RESEARCH_DATA_RIGHTS_VERIFIED')):
        raise ValueError('Online worker disabled: explicit worker, durable-storage and permitted-data configuration are required')
    # These attestations are deployment requirements, not proof obtained by code.
    owner=uuid.uuid4().hex
    if not store.claim_fetch('autonomous-worker-cycle',owner,now):
        raise ValueError('Another research cycle is already running')
    try:
        summary={'mode':'offline inspection' if offline else 'explicit online research',
                 'paid_ai_requests':0,'storage':storage_status(store),'models':registry_status(store)}
        if not offline:
            provider=OddsAPI(os.getenv('ODDS_API_KEY',''),store,daily_limit=settings.daily_limit,ttl=settings.cache_seconds)
            result=run_analysis(provider.key,leagues,store,provider,collect_results=settings.collect_results,
                                autonomous=True,window_hours=settings.window_hours)
            archive(store,os.getenv('PREDICTION_LEDGER_DIR','ledger'))
            summary.update(discovered_events=len(result.slate.get('events',[])),processing=result.processing,
                           status='partial coverage; no automatic model promotion')
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS research_runs(id TEXT PRIMARY KEY,at TEXT NOT NULL,payload TEXT NOT NULL)')
            db.executescript('''
            CREATE TRIGGER IF NOT EXISTS run_no_update BEFORE UPDATE ON research_runs BEGIN SELECT RAISE(ABORT,'Immutable research run'); END;
            CREATE TRIGGER IF NOT EXISTS run_no_delete BEFORE DELETE ON research_runs BEGIN SELECT RAISE(ABORT,'Immutable research run'); END;
            ''')
            db.execute('INSERT INTO research_runs VALUES(?,?,?)',(identifier,now.isoformat(),json.dumps(summary,allow_nan=False)))
        return summary
    finally:
        store.release_fetch('autonomous-worker-cycle',owner)
