"""Source-verified regular-season NBA research, separate from approved models.

Four publisher CC BY 4.0 files; reciprocal team rows must reconcile exactly.
The final season is never used to choose settings or calibration. No downloads
on page load, no sportsbook probabilities and no automatic model promotion.
"""
from hashlib import sha256
from pathlib import Path
import io, json
import numpy as np
import pandas as pd
from intelligence.domain import digest, utcnow
from intelligence.epl_validation import calibrated, fit_calibrator, reliability, metrics
from intelligence.team_rating import replay, fit_temperature
from intelligence.models import predict as incumbent_predict
from intelligence.evaluation import calibrate

SEASONS = ('2022-23', '2023-24', '2024-25', '2025-26')
LICENSE = 'https://boxscorelab.com/downloads/'
ATTRIBUTION = 'BoxScoreLab (boxscorelab.com), NBA team game results, CC BY 4.0. Modified: reconcile reciprocal rows and retain regular-season final scores. Publisher permission; underlying third-party rights and league endorsement are not established.'
VERSION = 'nba-recent-season-elo-research-1'


def parse(content, season, now=None):
    """Reject an entire incomplete/conflicting file; do not silently drop rows."""
    from intelligence.team_codes import NBA
    now = now or utcnow()
    if season not in SEASONS or len(content) > 2_000_000:
        raise ValueError('Unreviewed NBA season or oversized file')
    frame = pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False)
    required = {'season','team','game_date','opponent','home','result','points','opponent_points','point_diff'}
    if not required <= set(frame) or len(frame) != 2460:
        raise ValueError('NBA source must contain 2460 reciprocal regular-season rows')
    code = {c: codes[0] for codes in NBA.values() for c in codes}
    rows = {}; counts = {}
    for r in frame.to_dict('records'):
        if r['season'] != season or r['team'] not in code or r['opponent'] not in code or r['home'] not in ('True','False'):
            raise ValueError('Unreviewed NBA team, season or venue')
        home = r['home'] == 'True'; team, opponent = code[r['team']], code[r['opponent']]
        day = pd.Timestamp(r['game_date'])
        if (str(day.date()) != r['game_date'] or not f'{season[:4]}-10-01' <= r['game_date'] <= f'{int(season[:4])+1}-04-30'
            or day.date() >= now.date() or team == opponent):
            raise ValueError('NBA date outside reviewed completed regular season')
        a, b = int(r['points']), int(r['opponent_points'])
        if not 40 <= a <= 250 or not 40 <= b <= 250 or a == b or int(r['point_diff']) != a-b or r['result'] != ('W' if a>b else 'L'):
            raise ValueError('Invalid NBA final score')
        key = (r['game_date'], team, opponent)
        if key in rows: raise ValueError('Duplicate NBA team game')
        rows[key] = (home, a, b); counts[team] = counts.get(team, 0)+1
    if len(counts) != 30 or set(counts.values()) != {82}:
        raise ValueError('Incomplete NBA regular-season team coverage')
    games = []
    for (day, team, opponent), (home, a, b) in sorted(rows.items()):
        reverse = rows.get((day, opponent, team))
        if not reverse or reverse[1:] != (b,a) or home and reverse[0]:
            raise ValueError('NBA reciprocal scores or home venue conflict')
        # The publisher marks neutral-site games as away for both teams.
        # Exclude them explicitly; never invent a home team or home advantage.
        if not home and not reverse[0]: continue
        if home:
            games.append({'game_id': 'boxscorelab:'+day+':'+team+':'+opponent,
                'season': season, 'Date': pd.Timestamp(day).strftime('%d/%m/%Y'), 'date': pd.Timestamp(day),
                'HomeTeam': team, 'AwayTeam': opponent, 'FTHG': a, 'FTAG': b})
    return pd.DataFrame(games)


def load_bundle(directory, now=None):
    root = Path(directory); manifest = json.loads((root/'manifest.json').read_text())
    sources = []; frames = []
    for season in SEASONS:
        name = 'nba-'+season+'.csv'; entries = [r for r in manifest if r['file'] == name]
        if len(entries) != 1: raise ValueError('Missing NBA download provenance')
        m = entries[0]; raw = (root/name).read_bytes()
        if (m.get('http') != 200 or m.get('url') != 'https://boxscorelab.com/downloads/'+season+'-team-game-results.csv'
            or sha256(raw).hexdigest() != m.get('sha256')):
            raise ValueError('NBA source provenance/hash differs')
        frames.append(parse(raw, season, now)); sources.append(m)
    return pd.concat(frames, ignore_index=True).sort_values(['date','game_id']).reset_index(drop=True), sources


def evaluate(history, sources, resamples=1000):
    """2022–24 warmup, 2024–25 calibration, untouched 2025–26 final test.

    Fixed existing NBA Elo settings. Earlier test dates update ratings; the
    calibrator remains frozen. This is retrospective rolling evaluation, not
    evidence of historical publication or market-beating performance.
    """
    if set(history.season) != set(SEASONS): raise ValueError('Four complete source seasons required')
    rows, ratings = replay(history, 'NBA')
    warm = [r for r in rows if r['date'] < '2024-07-01']
    cal = [r for r in rows if '2024-07-01' <= r['date'] < '2025-07-01']
    test = [r for r in rows if r['date'] >= '2025-07-01']
    if len(warm)!=2460 or not 1200<=len(cal)<=1230 or not 1200<=len(test)<=1230:
        raise ValueError('Incomplete season partitions')
    coefficients = fit_calibrator([r['p'] for r in cal], [r['y'] for r in cal])
    ps = calibrated([r['p'] for r in test], coefficients).tolist(); y = [r['y'] for r in test]; days = [r['date'] for r in test]
    baseline = (sum(r['y'] for r in warm)+1)/(len(warm)+2)
    cp = calibrated([r['p'] for r in cal], coefficients).tolist()
    paired={}
    for label,records in [('cal',cal),('test',test)]:
        paired[label]=[]
        for r in records:
            value=incumbent_predict(history,'NBA',r['home'],r['away'],r['date']+'T00:00:00+00:00')
            if value is not None:paired[label].append(r|{'incumbent':value[0]})
    incumbent_temperature=fit_temperature([r|{'p':r['incumbent']} for r in paired['cal']])
    both=paired['test'];by=[r['y'] for r in both];bd=[r['date'] for r in both]
    ip=[calibrate([r['incumbent'],1-r['incumbent']],incumbent_temperature)[0] for r in both]
    ep=calibrated([r['p'] for r in both],coefficients).tolist()
    opening=[i for i,r in enumerate(test) if r['date'] <= '2025-11-03']
    report = {'schema':1, 'sport':'NBA', 'league':'NBA', 'model_version':VERSION,
        'generated_at':utcnow().isoformat(), 'source':sources, 'license_reference':LICENSE, 'attribution':ATTRIBUTION,
        'data_end':history.date.max().date().isoformat(), 'history_n':len(history),
        'data_sha256':digest(history.to_json(orient='records',date_format='iso')),
        'code_sha256':code_hash(), 'training_end':'2024-06-30', 'calibration_start':'2024-07-01',
        'calibration_end':'2025-06-30', 'test_start':'2025-07-01', 'test_end':max(days),
        'excluded_neutral_games':{s:1230-int((history.season==s).sum()) for s in SEASONS},
        'calibration_n':len(cal), 'test_n':len(test), 'coefficients':coefficients,
        'metrics':metrics(ps,y,days,resamples,89147),
        'baseline':metrics([baseline]*len(y),y,days,resamples,89147),
        'minus_baseline':metrics(ps,y,days,resamples,89147,[baseline]*len(y)),
        'paired_test_n':len(both),'incumbent_temperature':incumbent_temperature,
        'incumbent_metrics':metrics(ip,by,bd,resamples,89147),
        'minus_incumbent':metrics(ep,by,bd,resamples,89147,ip),
        'opening_14_days':metrics([ps[i] for i in opening],[y[i] for i in opening],[days[i] for i in opening],resamples,89147),
        'calibration_bins':reliability(cp,[r['y'] for r in cal]), 'test_reliability':reliability(ps,y),
        'ece':sum(b['n']*abs(b['mean_probability']-b['observed_frequency']) for b in reliability(ps,y) if b['n'])/len(y),
        'ratings':ratings, 'approved':False, 'replaces_incumbent':False, 'current_forecasts_enabled':False,
        'limitations':['Regular season only; playoff games and preseason excluded',
            'No roster, injury, pace or lineup inputs; offseason roster changes are unmodeled',
            'Date-only archives cannot prove original score availability; prior dates only',
            'Day-block uncertainty assumes exchangeable days; longer dependence remains',
            'No current fixture feed, observed-price baseline, betting edge or prospective confirmation',
            'Calibration ranges are historical frequency ranges, not event-specific confidence guarantees']}
    report['evidence_id'] = digest(report)
    return report


def code_hash():
    return digest({n:Path(__file__).with_name(n).read_text() for n in ('recent_nba.py','team_rating.py','models.py','evaluation.py')})


def load_report(path=None):
    path = path or Path(__file__).resolve().parents[1]/'research_assets/recent_nba.json'
    try:
        r = json.loads(Path(path).read_text()); checksum = r.pop('evidence_id')
        if digest(r) != checksum or r['code_sha256'] != code_hash() or r['approved'] or r['replaces_incumbent']:
            return None
        return r|{'evidence_id':checksum}
    except (OSError,ValueError,KeyError,TypeError): return None


def main():
    import argparse
    p = argparse.ArgumentParser(description='Offline recent NBA season validation; no network or promotion')
    p.add_argument('--bundle',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a = p.parse_args(); history,sources = load_bundle(a.bundle); report = evaluate(history,sources)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:report[k] for k in ('history_n','data_end','test_n','metrics','baseline','ece','approved')}))


if __name__ == '__main__': main()
