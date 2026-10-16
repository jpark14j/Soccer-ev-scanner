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
    args = parser.parse_args()
    store = configured_store()
    if args.command=='import-free-history':
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
