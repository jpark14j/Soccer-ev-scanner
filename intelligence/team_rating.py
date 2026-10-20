"""Fixed Elo challengers, evaluated by whole dates. Never approved by this module.

NBA updates include a bounded score-margin factor. MLB uses wins/losses only:
starter, bullpen and park effects are missing. No odds are fitted as features.
"""
from copy import deepcopy
from math import log, log10
import json
from pathlib import Path
import numpy as np
from intelligence.domain import digest, utcnow
from intelligence.evaluation import predict as incumbent_predict, calibrate, scores
from intelligence.epl_validation import metrics, reliability

SETTINGS = {
    'NBA': {'k': 20., 'home': 65., 'margin': True},
    'MLB': {'k': 8., 'home': 30., 'margin': False},
}
VERSION = 'date-block-elo-challenger-1'


def probability(ratings, home, away, sport):
    p = SETTINGS[sport]
    return 1 / (1 + 10 ** (-(ratings.get(home, 1500.) - ratings.get(away, 1500.) + p['home']) / 400))


def replay(history, sport):
    """All forecasts on one date precede every update on that date.

    Retrospective dates are not verified historical publication times. Earlier
    test dates may update later test features, but never refit calibration.
    """
    if sport not in SETTINGS or len(history) < 500:
        raise ValueError('At least 500 source-verified NBA/MLB games required')
    ratings = {}; result = []
    for day, batch in history.sort_values('date').groupby('date', sort=True):
        changes = {}
        for row in batch.itertuples():
            p = probability(ratings, row.HomeTeam, row.AwayTeam, sport)
            result.append({'date': day.date().isoformat(), 'home': row.HomeTeam, 'away': row.AwayTeam,
                'p': p, 'y': int(row.FTHG > row.FTAG)})
            factor = min(2., max(.5, log(1 + abs(row.FTHG - row.FTAG)))) if SETTINGS[sport]['margin'] else 1.
            delta = SETTINGS[sport]['k'] * factor * (int(row.FTHG > row.FTAG) - p)
            changes[row.HomeTeam] = changes.get(row.HomeTeam, 0.) + delta
            changes[row.AwayTeam] = changes.get(row.AwayTeam, 0.) - delta
        for name, delta in changes.items():
            ratings[name] = ratings.get(name, 1500.) + delta
    return result, ratings


def fit_temperature(rows):
    return min([.5 + i * .05 for i in range(31)], key=lambda t: scores(
        [calibrate([r['p'], 1-r['p']], t) for r in rows], [0 if r['y'] else 1 for r in rows])['log_loss'])


def evaluate(history, sport, source, resamples=1000):
    """Fixed 60/20/20 date partitions, calibration-only temperature selection.

    This archive was inspected previously in this project. These are held-out
    fitting diagnostics, not a new independent prospective confirmation.
    """
    rows, ratings = replay(history, sport)
    days = sorted({r['date'] for r in rows})
    cal_start, test_start = days[int(len(days)*.6)], days[int(len(days)*.8)]
    warm = [r for r in rows if r['date'] < cal_start]
    cal = [r for r in rows if cal_start <= r['date'] < test_start]
    test = [r for r in rows if r['date'] >= test_start]
    temperature = fit_temperature(cal)
    baseline = (sum(r['y'] for r in warm)+1)/(len(warm)+2)
    # Evaluate the existing sport-specific model on the same supported test
    # cohort. Its separate calibrator sees calibration dates only.
    paired = {'cal': [], 'test': []}
    for row in cal + test:
        p = incumbent_predict(history, sport, row['home'], row['away'], row['date']+'T00:00:00+00:00')
        if p is not None:
            paired['cal' if row['date'] < test_start else 'test'].append(dict(row, incumbent=p[0]))
    incumbent_t = fit_temperature([dict(r, p=r['incumbent']) for r in paired['cal']]) if paired['cal'] else None
    ps = [calibrate([r['p'], 1-r['p']], temperature)[0] for r in test]
    y = [r['y'] for r in test]; dates = [r['date'] for r in test]
    both = paired['test'] if incumbent_t else []
    cp = [calibrate([r['p'], 1-r['p']], temperature)[0] for r in both]
    ip = [calibrate([r['incumbent'], 1-r['incumbent']], incumbent_t)[0] for r in both] if incumbent_t else []
    cy = [r['y'] for r in both]; cd = [r['date'] for r in both]
    bins = reliability(ps, y)
    report = {'sport': sport, 'model_version': VERSION+'-'+sport.lower(), 'status': 'unapproved historical challenger',
        'generated_at': utcnow().isoformat(), 'data_source': source, 'data_end': history.date.max().date().isoformat(),
        'data_sha256': digest(history.to_json(orient='records', date_format='iso')),
        'code_sha256': digest(Path(__file__).read_text()), 'settings': deepcopy(SETTINGS[sport]),
        'calibration_start': cal_start, 'test_start': test_start, 'calibration_n': len(cal), 'test_n': len(test),
        'temperature': temperature, 'metrics': metrics(ps, y, dates, resamples, 19741),
        'training_prevalence_baseline': metrics([baseline]*len(test), y, dates, resamples, 19741),
        'calibration_bins': bins,
        'ece': sum(b['n']*abs(b['mean_probability']-b['observed_frequency']) for b in bins if b['n'])/len(test),
        'paired_test_n': len(both), 'incumbent_metrics': metrics(ip, cy, cd, resamples, 19741) if both else None,
        'paired_minus_incumbent': metrics(cp, cy, cd, resamples, 19741, ip) if both else None,
        'approved': False, 'replaces_incumbent': False, 'current_forecasts_enabled': False,
        'uncertainty': 'Day-block bootstrap score intervals and calibration-bin frequency intervals; not event-specific confidence guarantees',
        'limitations': ['Test dates were previously inspected in this project; independent prospective confirmation is absent',
            'Date-only archive availability/correction timing is unverified; all same-day outcomes withheld',
            'Bootstrap assumes exchangeable independent days; shared-team and temporal dependence remain',
            'No historical observed market baseline, starter/player context, betting returns or parlay validation',
            'Stale archives cannot authorize current inference; no model is promoted automatically']}
    report['evidence_id'] = digest(report)
    return report


def main():
    import argparse
    from intelligence.history import load_local
    p = argparse.ArgumentParser(description='Offline source-verified team-sport challenger evaluation; no downloads')
    p.add_argument('--history-dir', default='data/research/history')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(); reports = {}
    for sport in SETTINGS:
        history = load_local(sport, args.history_dir)
        manifest = json.loads((Path(args.history_dir)/(sport.lower()+'.source.json')).read_text())
        reports[sport] = evaluate(history, sport, manifest['attribution'])
    output = {'schema': 1, 'reports': reports, 'provider_requests': 0, 'paid_ai_requests': 0,
        'models_promoted': 0, 'forward_records_created': 0}
    output['sha256'] = digest(output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, allow_nan=False)+'\n')
    print(json.dumps({s: {'test_n': r['test_n'], 'brier': r['metrics']['binary_brier']['value'],
        'log_loss': r['metrics']['log_loss']['value'], 'incumbent_brier': r['incumbent_metrics']['binary_brier']['value'] if r['incumbent_metrics'] else None,
        'paired_interval': r['paired_minus_incumbent']['binary_brier']['interval'] if r['paired_minus_incumbent'] else None} for s,r in reports.items()}))


if __name__ == '__main__':
    main()
