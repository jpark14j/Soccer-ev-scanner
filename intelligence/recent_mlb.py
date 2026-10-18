"""Full 2025 regular-season held-out MLB research from the preserved archive.

This evaluates the available data honestly; it does not make a 2025 archive a
2026 feed. Current forecasts remain blocked. No requests or model promotion.
"""
import json
from pathlib import Path
from intelligence.domain import digest,utcnow
from intelligence.team_rating import replay,fit_temperature
from intelligence.models import predict
from intelligence.evaluation import calibrate
from intelligence.epl_validation import fit_calibrator,calibrated,reliability,metrics


def code_hash():
    return digest({n:Path(__file__).with_name(n).read_text() for n in ('recent_mlb.py','team_rating.py','models.py','evaluation.py')})


def evaluate(history,manifest,resamples=1000):
    if set(history.date.dt.year)!={2023,2024,2025} or not manifest.get('commercial_use') or not manifest.get('normalized_sha256'):
        raise ValueError('Preserved source-verified 2023–25 MLB archive required')
    rows,_=replay(history,'MLB')
    warm=[r for r in rows if r['date']<'2024-01-01']
    cal=[r for r in rows if '2024-01-01'<=r['date']<'2025-01-01']
    test=[r for r in rows if r['date']>='2025-01-01']
    if min(len(warm),len(cal),len(test))<2000:raise ValueError('Insufficient season coverage')
    coefficients=fit_calibrator([r['p'] for r in cal],[r['y'] for r in cal])
    ps=calibrated([r['p'] for r in test],coefficients).tolist();y=[r['y'] for r in test];days=[r['date'] for r in test]
    baseline=(sum(r['y'] for r in warm)+1)/(len(warm)+2)
    paired={}
    for label,records in [('cal',cal),('test',test)]:
        paired[label]=[]
        for r in records:
            v=predict(history,'MLB',r['home'],r['away'],r['date']+'T00:00:00+00:00')
            if v is not None:paired[label].append(r|{'incumbent':v[0]})
    t=fit_temperature([r|{'p':r['incumbent']} for r in paired['cal']]);both=paired['test']
    ip=[calibrate([r['incumbent'],1-r['incumbent']],t)[0] for r in both]
    ep=calibrated([r['p'] for r in both],coefficients).tolist();by=[r['y'] for r in both];bd=[r['date'] for r in both]
    cp=calibrated([r['p'] for r in cal],coefficients).tolist();bins=reliability(ps,y)
    r={'schema':1,'sport':'MLB','model_version':'mlb-full-season-elo-research-1','generated_at':utcnow().isoformat(),
        'source':manifest,'data_sha256':digest(history.to_json(orient='records',date_format='iso')),'code_sha256':code_hash(),
        'data_end':history.date.max().date().isoformat(),'history_n':len(history),'training_end':'2023-12-31',
        'calibration_start':'2024-01-01','calibration_end':'2024-12-31','test_start':'2025-01-01','test_end':max(days),
        'calibration_n':len(cal),'test_n':len(test),'coefficients':coefficients,
        'metrics':metrics(ps,y,days,resamples,81294),'baseline':metrics([baseline]*len(y),y,days,resamples,81294),
        'calibration_bins':reliability(cp,[r['y'] for r in cal]),'test_reliability':bins,
        'ece':sum(b['n']*abs(b['mean_probability']-b['observed_frequency']) for b in bins if b['n'])/len(y),
        'paired_test_n':len(both),'incumbent_metrics':metrics(ip,by,bd,resamples,81294),
        'minus_incumbent':metrics(ep,by,bd,resamples,81294,ip),
        'approved':False,'replaces_incumbent':False,'current_forecasts_enabled':False,
        'limitations':['2026 results and verified current fixtures are unavailable; no current MLB forecast is enabled',
            'Regular-season source only; ties and suspended/resumed games were excluded by the preserved importer',
            'No starting-pitcher, bullpen, park, lineup or weather adjustments',
            'Complete season split is a new diagnostic on archive data already examined in this project',
            'Same-date outcomes are withheld from all predictions on that date; calibration uses 2024 only',
            'No timestamped sportsbook baseline, independently confirmed advantage or betting return']}
    r['evidence_id']=digest(r);return r


def load_report():
    try:
        r=json.loads((Path(__file__).resolve().parents[1]/'research_assets/recent_mlb.json').read_text());checksum=r.pop('evidence_id')
        if digest(r)!=checksum or r['code_sha256']!=code_hash() or r['approved'] or r['current_forecasts_enabled']:return None
        return r|{'evidence_id':checksum}
    except (OSError,ValueError,TypeError,KeyError):return None


def main():
    import argparse
    from intelligence.history import load_licensed
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--history-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    manifest=json.loads((a.history_dir/'mlb.source.json').read_text());r=evaluate(load_licensed('MLB',a.history_dir),manifest)
    a.output.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:r[k] for k in ('test_n','metrics','baseline','incumbent_metrics','minus_incumbent','ece','approved')}))


if __name__=='__main__':main()
