"""Frozen policy, independently fitted competition models; never edge approval."""
from dataclasses import asdict
from pathlib import Path
from datetime import date,timedelta
from collections import Counter
import json
import numpy as np
from intelligence.domain import digest,utcnow
from intelligence.data_adapters import ROOT,pinned_history
from intelligence.competitions import COMPETITIONS
from intelligence.venue_goals import fit,predict
from intelligence.epl_validation import fit_calibrator,calibrated,reliability,metrics,wilson

ASSETS=ROOT/'research_assets/expanded'


def policy():return json.loads((ROOT/'config/expanded_model_policy.json').read_text())


def code_hash():
    files=('competitions.py','event_data.py','data_adapters.py','venue_goals.py','expanded_models.py','expanded_forecasts.py','epl_validation.py')
    return digest({f:(ROOT/'intelligence'/f).read_text() for f in files}|
        {'policy':policy(),'aliases':json.loads((ROOT/'config/team_aliases.json').read_text()),
         'sources':json.loads((ROOT/'config/multi_source_snapshot.json').read_text())})


def model_path(league):return ASSETS/(COMPETITIONS[league].id.replace(':','_')+'.json')


def rows_from_events(events):
    return sorted([{'date':e.event_date,'home':e.home_id,'away':e.away_id,'hg':e.home_score,'ag':e.away_score,
        'fixture_id':e.fixture_id,'season':e.season} for e in events if e.status=='completed'],key=lambda r:(r['date'],r['fixture_id']))


def build(league,directory,destination=None):
    p=policy()
    if league not in p['targets']:raise ValueError('No predeclared expanded model for this competition')
    market=p['targets'][league];events,sources=pinned_history(directory,league);rows=rows_from_events(events)
    for season in ('2022-23','2023-24','2024-25'):
        if not next(s['complete_historical_season'] for s in sources if s['season']==season):
            raise ValueError('Incomplete calibration/validation/final-test season; no model fit')
    forecasts=[];states={};excluded=Counter()
    for r in rows:
        if r['date']<p['calibration_start']:continue
        state=states.setdefault(r['date'],None)
        if state is None:state=states[r['date']]=fit(rows,r['date'],p)
        prediction,reason=predict(state,r['home'],r['away'],r['date'],p)
        if prediction is None:excluded[reason.split(':')[0] if ':' in reason else reason]+=1;continue
        lh,la=state['hg']/state['w'],state['ag']/state['w'];total=lh+la
        baseline=(1-np.exp(-lh))*(1-np.exp(-la)) if market=='btts' else 1-np.exp(-total)*(1+total+total*total/2)
        y=int(r['hg']>0 and r['ag']>0) if market=='btts' else int(r['hg']+r['ag']>2.5)
        forecasts.append({'date':r['date'],'p':prediction[market],'y':y,'league_baseline':float(baseline),'fixture_id':r['fixture_id']})
    calibration=[r for r in forecasts if p['calibration_start']<=r['date']<=p['calibration_end']]
    if len(calibration)<150:raise ValueError('Insufficient calibration support')
    coefficients=fit_calibrator([r['p'] for r in calibration],[r['y'] for r in calibration])
    prevalence=float(np.mean([r['y'] for r in calibration]));periods={}
    for name,start,end in (('validation',p['validation_start'],p['validation_end']),('final_test',p['test_start'],p['test_end']),
                            ('later_partial_monitoring','2025-07-01','9999-12-31')):
        period=[r for r in forecasts if start<=r['date']<=end]
        if not period:continue
        prob=calibrated([r['p'] for r in period],coefficients);y=[r['y'] for r in period];days=[r['date'] for r in period]
        baseline=[prevalence]*len(y);league_baseline=[r['league_baseline'] for r in period];bins=reliability(prob,y)
        high=prob>=.65
        periods[name]={'start':min(days),'end':max(days),'eligible':len(period),
            'model':metrics(prob,y,days,p['bootstrap_resamples'],p['bootstrap_seed']),
            'constant_baseline':metrics(baseline,y,days,p['bootstrap_resamples'],p['bootstrap_seed']),
            'league_poisson_baseline':metrics(league_baseline,y,days,p['bootstrap_resamples'],p['bootstrap_seed']),
            'model_minus_constant':metrics(prob,y,days,p['bootstrap_resamples'],p['bootstrap_seed'],baseline),
            'calibration_bins':bins,'ece':sum(b['n']*abs(b['mean_probability']-b['observed_frequency']) for b in bins if b['n'])/len(y),
            'high_probability_range':{'minimum':.65,'n':int(high.sum()),'observed_frequency':float(np.mean(np.array(y)[high])) if high.sum() else None,
                'frequency_interval':wilson(int(np.array(y)[high].sum()),int(high.sum())) if high.sum()>=50 else [0.,1.],
                'note':'Descriptive frozen range; below 50 outcomes gets a full uncertainty envelope. Not a betting win rate or an independently validated shortlist'}}
    anchor=(date.fromisoformat(rows[-1]['date'])+timedelta(days=1)).isoformat()
    raw_cal=calibrated([r['p'] for r in calibration],coefficients)
    artifact={'model_version':p['version']+'-'+COMPETITIONS[league].id,'league':league,
        'competition_id':COMPETITIONS[league].id,'target':market,'status':'research_model','forecast_validated':False,'edge_approved':False,
        'code_sha256':code_hash(),'generated_at':utcnow().isoformat(),'data_sha256':digest([asdict(e) | {'observed_at':'archive-receipt-not-historical-publication'} for e in events]),
        'policy':p,'sources':sources,'history_n':len(rows),'calibration_n':len(calibration),'excluded_after_train':dict(excluded),
        'coefficients':coefficients,'calibration_bins':reliability(raw_cal,[r['y'] for r in calibration]),'periods':periods,
        'state':fit(rows,anchor,p),'current_rows':[r for r in rows if r['season']=='2026-27'],
        'fixtures':[{k:v for k,v in asdict(e).items() if k in ('home_id','away_id','event_date','status','season')} for e in events if e.season=='2026-27'],
        'limitations':['Per-competition venue scoring counts; no xG, injuries, roster, lineup or player context',
            'Only prior calendar dates enter features; archive publication/correction timing is unverified',
            'Separate fitted parameters and calibration; no cross-league strength transfer',
            'Independent-Poisson score assumption is not a calibrated parlay dependency model',
            'Day-block bootstrap assumes exchangeable independent days; cross-day dependence is unverified',
            'Calibration-bin Wilson envelopes are frequency diagnostics, not event-specific confidence guarantees',
            'Missing/promoted-team exclusions and partial later coverage can bias outcomes',
            'No timestamped historical market prices, independent prospective confirmation or reviewed activation'],
        'betting_roi':None,'model_approval_blockers':['Independent forecasting review/confirmation absent','Historical market baseline absent','No reviewed champion activation']}
    artifact['artifact_sha256']=digest(artifact)
    path=Path(destination) if destination else model_path(league);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(artifact,indent=2,allow_nan=False)+'\n')
    return artifact


def load(league):
    if league not in policy()['targets']:return None
    try:
        r=json.loads(model_path(league).read_text());checksum=r.pop('artifact_sha256')
        if digest(r)!=checksum or r['code_sha256']!=code_hash() or r['edge_approved'] or r['forecast_validated']:return None
        return r|{'artifact_sha256':checksum}
    except (OSError,KeyError,ValueError,TypeError):return None
