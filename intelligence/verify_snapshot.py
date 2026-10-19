"""Offline acceptance of an EXISTING private snapshot; no source/store writes.

A consistent SQLite backup is inspected in a temporary directory. This cannot
bootstrap a store, persist forecasts, request provider data or approve a model.
The result describes this source receipt at inspection time, not live sportsbook
availability or future persistence guarantees.
"""
from pathlib import Path
from contextlib import closing
import argparse,json,sqlite3,tempfile
from intelligence.domain import utcnow,parse_time


def inspect(path,now=None,expected_instance=None):
    path=Path(path)
    if not path.is_file():raise ValueError('An existing research snapshot is required; empty initialization is forbidden')
    now=now or utcnow()
    with tempfile.TemporaryDirectory(prefix='offline-research-acceptance-') as folder:
        destination=Path(folder)/'inspection.sqlite3'
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as source:
            with closing(sqlite3.connect(destination)) as target:source.backup(target)
        from intelligence.storage import Store
        from intelligence.background import verify_assets
        from intelligence.fixture_research import collect
        from intelligence.current_score_research import candidates
        from intelligence.statistics_forward import monitoring
        from intelligence.openliga import current
        from intelligence.positive_ev import shortlist,EMPTY
        from intelligence.pipeline import Analysis
        store=Store(destination,read_replica=True)
        with store.connect() as db:
            if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('Snapshot integrity failed')
            instance=db.execute('SELECT instance FROM store_identity WHERE id=1').fetchone()[0]
            if expected_instance and instance!=expected_instance:raise ValueError('Unexpected recovered store identity')
            tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'statistics_forecasts' not in tables:raise ValueError('Prospective research ledger is not present')
            if db.execute('SELECT count(*) FROM statistics_forecasts WHERE at>=kickoff').fetchone()[0]:raise ValueError('A stored forecast was not recorded before kickoff')
            original_records=db.execute('SELECT count(*) FROM statistics_forecasts').fetchone()[0]
        verify_assets(store)
        events,meta=current(store,'Bundesliga',now)
        research=collect(store,now,168,['Premier League','Bundesliga','Ligue 1'])
        eligible=[r for r in research['forecasts'] if r['research_eligible']]
        sgps=[r for r in candidates(store,now) if r['research_eligible']]
        for r in eligible+sgps:
            if not now<parse_time(r['kickoff'])<=now+__import__('datetime').timedelta(days=7):raise ValueError('Research outside reviewed future window')
            if r.get('approved') or r.get('joint_validated') or r.get('ev') is not None:raise ValueError('Experimental research falsely approved or priced')
        monitor=monitoring(store)
        from intelligence.prediction_accuracy import summary as accuracy,saved_for_display
        recorded_singles=saved_for_display(store,eligible,now)
        recorded_sgps=saved_for_display(store,sgps,now)
        # With no verified price evidence the main page must remain empty.
        gate=shortlist(Analysis(),store,(),(),now)
        if gate['qualified']:raise ValueError('Unpriced research was promoted into a qualifying bet')
        with store.connect() as db:
            if db.execute('SELECT count(*) FROM statistics_forecasts').fetchone()[0]!=original_records:raise ValueError('Verification recorded forecasts')
        from intelligence.dependence_study import load_report
        report=load_report()
        return {'scope':'Offline inspection of existing snapshot; not authenticated hosted-page or live-price verification',
            'inspected_at':now.isoformat(),'store_instance':instance,'integrity':'ok','frozen_assets_verified':9,
            'Bundesliga':{'source_ok':meta['ok'],'current_research_ready':bool(eligible or sgps),'source_observed_at':meta.get('checked_at'),
                'coverage':meta.get('coverage'),'experimental_singles':len(eligible),
                'experimental_two_leg_sgp':sum(len(r['legs'])==2 for r in sgps),
                'experimental_three_leg_sgp':sum(len(r['legs'])==3 for r in sgps)},
            'accuracy':accuracy(store,now),'recorded_singles_displayable':len(recorded_singles),
            'recorded_sgps_displayable':len(recorded_sgps),'prospective_snapshots':monitor['recorded_snapshots'],'distinct_pregame_decisions':monitor['unique_pregame_decisions'],
            'verified_outcomes':sum(g['labeled'] for g in monitor['groups']),
            'positive_ev_slots_empty_without_verified_prices':gate['qualified']==0,'empty_message':EMPTY,
            'dependence_report_verified':report is not None,'approved_joint_models':0,
            'NBA':{'status':'BLOCKED','reason':'Current reviewed fixture identities and offseason input readiness unavailable'},
            'MLB':{'status':'BLOCKED','reason':'Permitted 2026 results and current fixtures unavailable'},
            'provider_requests':0,'source_writes':0,'new_forecasts':0,'models_promoted':0}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--store',type=Path,required=True);p.add_argument('--expected-instance');a=p.parse_args()
    try:print(json.dumps(inspect(a.store,expected_instance=a.expected_instance),allow_nan=False))
    except Exception:
        print(json.dumps({'status':'verification failed','provider_requests':0,'source_writes':0}));raise SystemExit(1) from None


if __name__=='__main__':main()
