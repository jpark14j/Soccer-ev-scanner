"""Chronological calibration and untouched test evaluation for research models."""
from datetime import timedelta
import math
import json
from pathlib import Path
import numpy as np
from intelligence.domain import digest, parse_time, utcnow
from intelligence.models import VERSIONS, predict


def model_code_hash():
    root=Path(__file__).parent
    return digest({name:(root/name).read_text() for name in ('models.py','soccer.py','evaluation.py')})


def calibrate(probabilities, temperature):
    p = np.clip(np.asarray(probabilities, dtype=float), 1e-12, 1.) ** (1 / temperature)
    return (p / p.sum()).tolist()


def scores(probabilities, outcomes):
    p = np.clip(np.array(probabilities), 1e-12, 1 - 1e-12)
    y = np.eye(p.shape[1])[np.array(outcomes)]
    return {'brier': float(np.mean(np.sum((p-y)**2, axis=1))),
            'log_loss': float(np.mean(-np.log(p[np.arange(len(p)), outcomes])))}


def wilson(successes, n):
    if n < 1:
        return (0., 1.)
    z = 1.96
    p = successes / n
    mid = (p + z*z/(2*n)) / (1+z*z/n)
    half = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)) / (1+z*z/n)
    return max(0., mid-half), min(1., mid+half)


def promotion_reasons(report):
    reasons = []
    if report.get('test_n', 0) < 200 or report.get('calibration_n', 0) < 200:
        reasons.append('At least 200 calibration and 200 untouched test events required')
    if not report.get('baseline_timing_verified'):
        reasons.append('Market baseline observation timestamps unavailable/unverified')
    if not report.get('beats_market_with_uncertainty', False):
        reasons.append('No statistically supported held-out improvement over market')
    if report.get('calibration_gap', 1) > .05:
        reasons.append('Held-out calibration gap exceeds five percentage points')
    try:
        if (parse_time(report['generated_at'])-parse_time(report['data_end'])).days>90:
            reasons.append('Historical dataset is too old for current publication')
    except (KeyError,ValueError,TypeError):
        reasons.append('Historical recency evidence missing')
    if not report.get('data_source'):
        reasons.append('Historical source provenance missing')
    return reasons


def evaluate_history(history, sport, league, data_source):
    """Rolling forecasts; date blocks prevent same-day leakage.

    First 60% of dates is warmup, next 20% fits temperature, final 20% is test.
    Test history may update using earlier settled days, never same/future day.
    No threshold or calibrator is selected on the test period. A market baseline
    without timestamped pregame observations cannot promote a model.
    """
    if history.empty or len(history) < 200:
        raise ValueError('Insufficient genuine historical events')
    days = sorted(history.date.unique())
    cal_start, test_start = days[int(len(days)*.6)], days[int(len(days)*.8)]
    warmup=history[history.date<cal_start]
    warm_outcomes=[(0 if r.FTHG>r.FTAG else 1 if r.FTHG==r.FTAG else 2) if sport=='Soccer' else (0 if r.FTHG>r.FTAG else 1) for _,r in warmup.iterrows()]
    counts=np.bincount(warm_outcomes,minlength=3 if sport=='Soccer' else 2)+1
    simple_baseline=(counts/counts.sum()).tolist()
    sets = {'calibration': [], 'test': []}
    for _, row in history[history.date >= cal_start].iterrows():
        kickoff = row.date.isoformat() + '+00:00'
        probs = predict(history, sport, row.HomeTeam, row.AwayTeam, kickoff)
        if probs is None:
            continue
        outcome = (0 if row.FTHG > row.FTAG else 1 if row.FTHG == row.FTAG else 2) if sport == 'Soccer' else (0 if row.FTHG > row.FTAG else 1)
        cols = ('AvgH', 'AvgD', 'AvgA') if sport == 'Soccer' else ('AvgH', 'AvgA')
        baseline = None
        try:
            odds = [float(row[c]) for c in cols]
            if all(math.isfinite(o) and o > 1 for o in odds):
                inv = [1/o for o in odds]
                baseline = [p/sum(inv) for p in inv]
        except (ValueError, KeyError, TypeError):
            pass
        # Imported datasets may supply a real observation time and scheduled start.
        # Date-only baseline prices have no guaranteed tradable observation time.
        timed = False
        try:
            timed = parse_time(row['market_observed_at']) < parse_time(row['commence_time'])
        except (ValueError, TypeError, KeyError):
            pass
        bucket = 'calibration' if row.date < test_start else 'test'
        sets[bucket].append({'p': probs, 'outcome': outcome, 'baseline': baseline, 'timed': timed})
    cal, test = sets['calibration'], sets['test']
    if not cal or not test:
        raise ValueError('No supported chronological calibration/test predictions')
    temperature = min([.5 + i*.05 for i in range(31)],
                      key=lambda t: scores([calibrate(r['p'], t) for r in cal], [r['outcome'] for r in cal])['log_loss'])
    test_p = [calibrate(r['p'], temperature) for r in test]
    bins = []
    for index in range(10):
        pairs = [(p, int(r['outcome'] == j)) for r in cal for j,p in enumerate(calibrate(r['p'], temperature)) if min(9, int(p*10)) == index]
        n, wins = len(pairs), sum(y for _,y in pairs)
        bins.append({'n': n, 'wins': wins, 'interval': wilson(wins, n)})
    gap = 0.
    for index in range(10):
        pairs = [(p, int(r['outcome']==j)) for r,ps in zip(test,test_p) for j,p in enumerate(ps) if min(9,int(p*10))==index]
        if pairs:
            gap += abs(sum(p-y for p,y in pairs)) / (len(test)*len(test_p[0]))
    common = [(r,p) for r,p in zip(test,test_p) if r['baseline'] is not None]
    baseline_metrics, beats = None, False
    if common:
        baseline_metrics = scores([r['baseline'] for r,_ in common], [r['outcome'] for r,_ in common])
        diffs = []
        log_diffs = []
        for r,p in common:
            y = np.eye(len(p))[r['outcome']]
            diffs.append(sum((np.array(r['baseline'])-y)**2) - sum((np.array(p)-y)**2))
            log_diffs.append(-math.log(r['baseline'][r['outcome']])+math.log(p[r['outcome']]))
        # Paired normal interval is diagnostic; event dependence can still reduce
        # effective sample size. Require both metrics to improve beyond uncertainty.
        beats = all(len(d)>1 and np.mean(d) - 1.96*np.std(d,ddof=1)/math.sqrt(len(d)) > 0 for d in (diffs, log_diffs))
    report = {'schema':1, 'sport':sport, 'league':league, 'market':'h2h',
              'model_version':VERSIONS[sport], 'code_sha256':model_code_hash(), 'generated_at':utcnow().isoformat(),
              'expires_at':(utcnow()+timedelta(days=30)).isoformat(),
              'data_source':data_source, 'data_sha256':digest(history.to_json(orient='records', date_format='iso')),
              'data_end':history.date.max().isoformat()+'+00:00',
              'calibration_start':str(cal_start), 'test_start':str(test_start),
              'calibration_n':len(cal), 'test_n':len(test), 'temperature':temperature,
              'metrics':scores(test_p,[r['outcome'] for r in test]),
              'simple_baseline_metrics':scores([simple_baseline]*len(test),[r['outcome'] for r in test]),
              'baseline_metrics':baseline_metrics, 'baseline_n':len(common),
              'baseline_timing_verified':bool(common) and len(common)==len(test) and all(r['timed'] for r,_ in common),
              'beats_market_with_uncertainty':bool(beats), 'calibration_gap':float(gap), 'calibration_bins':bins}
    report['promotion_blockers'] = promotion_reasons(report)
    report['status'] = 'eligible' if not report['promotion_blockers'] else 'research'
    report['evidence_id'] = digest(report)
    return report


def load_report(league, directory='data/models', now=None):
    path = Path(directory) / (league.lower().replace(' ', '_') + '.json')
    if not path.exists():
        return None
    report = json.loads(path.read_text())
    expected = report.get('evidence_id')
    if digest({k:v for k,v in report.items() if k != 'evidence_id'}) != expected:
        return None
    if report.get('code_sha256') != model_code_hash():
        return None
    if report.get('league') != league or report.get('model_version') != VERSIONS.get(report.get('sport')):
        return None
    if not parse_time(report['generated_at']) <= (now or utcnow()) <= parse_time(report['expires_at']):
        return None
    return report
