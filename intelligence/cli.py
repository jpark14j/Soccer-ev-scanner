"""Operator commands. No paid endpoints or automatic notifications on import."""
import argparse
import json
import os
from pathlib import Path
from intelligence.evaluation import evaluate_history
from intelligence.history import load_local, load_soccer
from intelligence.pipeline import configured_store, run_analysis
from intelligence.providers import LEAGUES


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command',required=True)
    multi=sub.add_parser('import-multi-history',help='Import verified pinned multi-league files into the private normalized ledger')
    multi.add_argument('--directory',required=True)
    multi.add_argument('--download',action='store_true',help='One-off maximum 36 hash-verified public pinned files; never a paid endpoint')
    expanded=sub.add_parser('evaluate-expanded',help='Reproduce predeclared expanded models; no current market or paid API request')
    expanded.add_argument('--league',choices=['Bundesliga','Ligue 1'],required=True)
    expanded.add_argument('--directory',required=True)
    epl=sub.add_parser('evaluate-epl',help='Reproduce frozen EPL diagnostics from pinned public snapshots; no paid calls')
    epl.add_argument('--cache-directory',required=True)
    epl.add_argument('--output',default='research_assets/epl/model.json')
    epl.add_argument('--download',action='store_true',help='Download the eight hash-verified public pinned files first (no account)')
    evaluate = sub.add_parser('evaluate')
    evaluate.add_argument('--league',choices=list(LEAGUES),required=True)
    evaluate.add_argument('--source',help='Provenance/licence reference for local history')
    advanced=sub.add_parser('evaluate-markets')
    advanced.add_argument('--league',choices=list(LEAGUES),required=True)
    advanced.add_argument('--history-directory',default='data/research/history')
    advanced.add_argument('--output-directory',default='data/research/advanced_models')
    sub.add_parser('scan')
    archive_import=sub.add_parser('import-free-history')
    archive_import.add_argument('--sport',choices=['NBA','MLB'],required=True)
    archive_import.add_argument('--directory',default='data/research/history')
    settle=sub.add_parser('settle')
    settle.add_argument('--prediction-id',required=True)
    settle.add_argument('--outcome',choices=['win','loss','push','void'],required=True)
    settle.add_argument('--result',required=True)
    settle.add_argument('--source',required=True)
    settle.add_argument('--closing-odds',type=float)
    settle.add_argument('--closing-source')
    settle.add_argument('--closing-observed-at')
    cycle=sub.add_parser('research-cycle')
    cycle.add_argument('--offline',action='store_true',help='Inspect storage/models without data requests')
    cycle.add_argument('--leagues',default='NBA,Premier League,MLB')
    backup=sub.add_parser('backup')
    backup.add_argument('--output',required=True,help='New private SQLite destination, never Git')
    sub.add_parser('backup-remote',help='Explicit optional private off-host snapshot and readback; disabled until configured')
    recover=sub.add_parser('restore-remote',help='Restore to a NEW private file with all provider requests held')
    recover.add_argument('--object',required=True)
    recover.add_argument('--output',required=True)
    recovery_review=sub.add_parser('review-recovery-budget',help='Operator-only usage review; never a chat action')
    recovery_review.add_argument('--odds-used',required=True,type=int)
    recovery_review.add_argument('--results-used',required=True,type=int)
    recovery_review.add_argument('--reference',required=True)
    challenger=sub.add_parser('train-challenger')
    challenger.add_argument('--league',choices=list(LEAGUES),required=True)
    challenger.add_argument('--history-directory',default='data/research/history')
    review=sub.add_parser('review-model')
    review.add_argument('--artifact-id',required=True)
    review.add_argument('--evidence-file',required=True)
    review.add_argument('--review-reference',required=True)
    review.add_argument('--action',choices=['promote','rollback','suspend'],required=True)
    args = parser.parse_args()
    store = configured_store()
    if args.command=='import-multi-history':
        from intelligence.data_adapters import import_history,download_snapshot
        if args.download:download_snapshot(args.directory)
        print(json.dumps(import_history(store,args.directory),indent=2))
    elif args.command=='evaluate-expanded':
        from intelligence.expanded_models import build
        report=build(args.league,args.directory)
        print(json.dumps({'league':args.league,'model':report['model_version'],'calibration_n':report['calibration_n'],
            'periods':report['periods'],'status':report['status'],'edge_approved':False},indent=2))
    elif args.command=='evaluate-epl':
        if args.download:
            from intelligence.epl_source import ROOT,REVISION
            from intelligence.epl_forecasts import _download
            from intelligence.epl_validation import ROOT as PROJECT_ROOT
            from hashlib import sha256
            import requests
            snapshot=json.loads((PROJECT_ROOT/'config/epl_source_snapshot.json').read_text())
            target=Path(args.cache_directory);target.mkdir(parents=True,exist_ok=True)
            with requests.Session() as session:
                for name,expected in snapshot['files'].items():
                    raw=_download(session,ROOT+REVISION+'/'+name)
                    if sha256(raw).hexdigest()!=expected:
                        raise ValueError('Pinned source content differs from reviewed hash')
                    (target/name.replace('/','_')).write_bytes(raw)
        from intelligence.epl_validation import build
        report=build(args.cache_directory,args.output)
        print(json.dumps({'model':report['model_version'],'coverage':report['coverage'],
            'held_out':{k:v['periods']['held_out'] for k,v in report['tasks'].items()},'approved':False},indent=2))
    elif args.command=='research-cycle':
        from intelligence.worker import run_cycle
        leagues=[s.strip() for s in args.leagues.split(',') if s.strip()]
        if not set(leagues)<=set(LEAGUES):
            parser.error('Unsupported research competition')
        print(json.dumps(run_cycle(store,leagues,offline=args.offline),indent=2))
    elif args.command=='backup':
        from intelligence.persistence import backup_store
        print(json.dumps(backup_store(store,args.output),indent=2))
    elif args.command=='backup-remote':
        from intelligence.remote_backup import upload
        print(json.dumps(upload(store),indent=2))
    elif args.command=='restore-remote':
        from intelligence.remote_backup import restore
        print(json.dumps(restore(args.object,args.output),indent=2))
    elif args.command=='review-recovery-budget':
        from intelligence.request_guard import reviewed_release
        reviewed_release(store,args.odds_used,args.results_used,args.reference)
        print('Recovery usage review recorded; provider account and shared-budget limitations still apply')
    elif args.command=='train-challenger':
        from intelligence.history import load_licensed
        from intelligence.lifecycle import train_challenger
        frame=load_licensed(args.league,args.history_directory)
        stem=args.league.lower().replace(' ','_')
        manifest=json.loads((Path(args.history_directory)/(stem+'.source.json')).read_text())
        print(json.dumps(train_challenger(frame,LEAGUES[args.league][0],args.league,
            str(manifest.get('attribution','Provenance-checked local history')),store),indent=2))
    elif args.command=='review-model':
        from intelligence.lifecycle import change_champion
        change_champion(store,args.artifact_id,json.loads(Path(args.evidence_file).read_text()),args.review_reference,args.action)
        print('Reviewed registry action recorded; matching current model/data evidence is still required by the pipeline')
    elif args.command=='import-free-history':
        from intelligence.free_history import import_snapshot
        print(json.dumps(import_snapshot(args.sport,args.directory),indent=2))
    elif args.command=='evaluate-markets':
        from intelligence.history import load_licensed
        from intelligence.market_validation import evaluate as evaluate_markets
        from intelligence.chat_privacy import redact
        stem=args.league.lower().replace(' ','_')
        frame=load_licensed(args.league,args.history_directory)
        manifest=json.loads((Path(args.history_directory)/(stem+'.source.json')).read_text())
        source=redact(str(manifest.get('attribution','Provenance-checked local historical dataset')),
                      tuple(os.getenv(n,'') for n in ('ODDS_API_KEY','OPENAI_API_KEY','TELEGRAM_BOT_TOKEN')))
        report=evaluate_markets(frame,LEAGUES[args.league][0],source)
        target=Path(args.output_directory);target.mkdir(parents=True,exist_ok=True)
        (target/(LEAGUES[args.league][0].lower()+'-advanced-research.json')).write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({'status':report['status'],'tasks':len(report['tasks']),
                          'test_sizes':[t['test_n'] for t in report['tasks']],
                          'roi':None,'note':'Fixed-threshold diagnostics, not a sportsbook betting backtest'},indent=2))
    elif args.command=='settle':
        from intelligence.ledger import archive
        store.settle(args.prediction_id,args.outcome,args.result,args.source,args.closing_odds,
                     closing_source=args.closing_source,closing_observed_at=args.closing_observed_at)
        archive(store,os.getenv('PREDICTION_LEDGER_DIR','ledger'))
        print('Evidence-backed settlement appended; prior records remain immutable')
    elif args.command=='evaluate':
        sport = LEAGUES[args.league][0]
        history = load_soccer(args.league,store) if sport=='Soccer' else load_local(args.league,os.getenv('HISTORY_DIR','data/history'))
        source = 'https://www.football-data.co.uk/data.php' if sport=='Soccer' else args.source
        if not source:
            parser.error('--source is required for licensed local history')
        report = evaluate_history(history,sport,args.league,source)
        directory = Path(os.getenv('MODEL_DIR','data/models'))
        directory.mkdir(parents=True,exist_ok=True)
        path = directory/(args.league.lower().replace(' ','_')+'.json')
        path.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({'report':str(path),'status':report['status'],'test_n':report['test_n'],
                          'metrics':report['metrics'],'blockers':report['promotion_blockers']},indent=2))
    else:
        result = run_analysis(os.getenv('ODDS_API_KEY',''),store=store)
        print(json.dumps({'quotes':len(result.quotes),'qualifying':len(result.opportunities),
                          'errors':result.errors,'exclusions':result.exclusions},indent=2))


if __name__=='__main__':
    main()
