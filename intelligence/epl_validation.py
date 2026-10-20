"""Reproducible chronological diagnostics; no betting prices or model approval."""
from collections import Counter
from datetime import date,timedelta
from hashlib import sha256
from pathlib import Path
import json
import math
import numpy as np
from intelligence.domain import digest,utcnow
from intelligence.epl_source import SEASONS,SOURCE,LICENSE_URL,REVISION,decode,source_record,identity
from intelligence.epl_goal_model import fit,rates,probabilities

ROOT=Path(__file__).resolve().parents[1]
POLICY_PATH=ROOT/'config/epl_forecast_policy.json'
ARTIFACT_PATH=ROOT/'research_assets/epl/model.json'


def policy():
    return json.loads(POLICY_PATH.read_text())


def code_hash():
    names=('epl_source.py','epl_goal_model.py','epl_validation.py','epl_forecasts.py')
    return digest({name:(ROOT/'intelligence'/name).read_text() for name in names}|
                  {'policy':policy(),'source_snapshot':json.loads((ROOT/'config/epl_source_snapshot.json').read_text())})


def logit(p):
    p=np.clip(np.asarray(p,dtype=float),1e-8,1-1e-8)
    return np.log(p/(1-p))


def calibrated(p,coefficients):
    z=coefficients[0]+coefficients[1]*logit(p)
    return 1/(1+np.exp(-np.clip(z,-35,35)))


def fit_calibrator(p,y):
    """Monotone Platt map, ridge toward identity, calibration period only."""
    x=np.column_stack((np.ones(len(p)),logit(p)));y=np.asarray(y)
    beta=np.array([0.,1.]);prior=beta.copy()
    for _ in range(100):
        probability=calibrated(p,beta)
        gradient=x.T@(probability-y)+(beta-prior)
        hessian=(x.T*(probability*(1-probability)))@x+np.eye(2)
        step=np.linalg.solve(hessian,gradient)
        candidate=beta-step;candidate[1]=max(0.,candidate[1])
        if np.max(np.abs(candidate-beta))<1e-8:
            return candidate.tolist()
        beta=candidate
    raise ValueError('Calibration did not converge')


def wilson(hits,n):
    if not n:
        return [0.,1.]
    p=hits/n;z=1.959963984540054;d=1+z*z/n
    center=(p+z*z/(2*n))/d
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0.,center-half),min(1.,center+half)]


def reliability(p,y):
    bins=[]
    for index in range(10):
        mask=(np.asarray(p)>=index/10)&(np.asarray(p)<(index+1)/10 if index<9 else np.asarray(p)<=1)
        values=np.asarray(y)[mask];forecasts=np.asarray(p)[mask];n=len(values)
        bins.append({'lower':index/10,'upper':(index+1)/10,'n':n,
                     'mean_probability':float(np.mean(forecasts)) if n else None,
                     'observed_frequency':float(np.mean(values)) if n else None,
                     'frequency_interval':wilson(int(sum(values)),n)})
    return bins


def scores(p,y):
    p=np.clip(np.asarray(p),1e-8,1-1e-8);y=np.asarray(y)
    return np.column_stack(((p-y)**2,-(y*np.log(p)+(1-y)*np.log(1-p)),(p>=.5)==y))


def metrics(p,y,days,resamples,seed,baseline=None):
    values=scores(p,y)
    if baseline is not None:
        values-=scores(baseline,y)
    unique=sorted(set(days));blocks=[values[np.asarray(days)==d] for d in unique]
    sums=np.array([b.sum(axis=0) for b in blocks]);counts=np.array([len(b) for b in blocks])
    rng=np.random.default_rng(seed)
    samples=rng.integers(0,len(blocks),size=(resamples,len(blocks)))
    boot=sums[samples].sum(axis=1)/counts[samples].sum(axis=1)[:,None]
    return {name:{'value':float(values[:,i].mean()),'interval':np.quantile(boot[:,i],[.025,.975]).tolist()}
            for i,name in enumerate(('binary_brier','log_loss','classification_accuracy'))}|{'n':len(y),'utc_day_blocks':len(blocks)}


def build(cache_dir,destination=ARTIFACT_PATH):
    p=policy();rows=[];sources=[];fixtures=[];raws={}
    snapshot=json.loads((ROOT/'config/epl_source_snapshot.json').read_text())
    if snapshot['revision']!=REVISION:
        raise ValueError('Source revision differs from reviewed snapshot')
    license_raw=(Path(cache_dir)/'LICENSE.md').read_bytes()
    if sha256(license_raw).hexdigest()!=snapshot['files']['LICENSE.md']:
        raise ValueError('Source license differs from reviewed snapshot')
    for season in SEASONS:
        raw=(Path(cache_dir)/(season+'_en.1.json')).read_bytes()
        if sha256(raw).hexdigest()!=snapshot['files'][season+'/en.1.json']:
            raise ValueError('History differs from reviewed pinned snapshot: '+season)
        parsed,missing=decode(raw,season);rows.extend(parsed);fixtures.extend(missing)
        sources.append(source_record(raw,season));raws[season]=raw
    rows.sort(key=lambda r:(r['date'],identity(r)))
    today=utcnow().date().isoformat()
    if any(r['date']>=today for r in rows):
        raise ValueError('Public history contains same-day or future completed results')
    predictions=[];skipped=Counter();states={}
    for row in rows:
        if row['date']<p['calibration_start']:
            continue
        if row['date'] not in states:
            states[row['date']]=fit(rows,row['date'],p)
        state=states[row['date']]
        lambdas,reason=rates(state,row['home'],row['away'],row['date'],p)
        if lambdas is None:
            skipped[reason]+=1;continue
        raw=probabilities(*lambdas)
        base=probabilities(state['hg']/state['w'],state['ag']/state['w'])
        predictions.append({'date':row['date'],'season':row['season'],'raw':raw,'league_poisson':base,
                            'y':{'btts':int(row['hg']>0 and row['ag']>0),'totals_2.5':int(row['hg']+row['ag']>2.5)}})
    cal=[r for r in predictions if p['calibration_start']<=r['date']<=p['calibration_end']]
    test=[r for r in predictions if p['test_start']<=r['date']<=p['test_end']]
    recent=[r for r in predictions if r['date']>p['test_end']]
    tasks={}
    for market in p['markets']:
        cp=[r['raw'][market] for r in cal];cy=[r['y'][market] for r in cal]
        if len(cal)<200 or len(test)<200:
            raise ValueError('Too few eligible calibration or test outcomes')
        coefficients=fit_calibrator(cp,cy);constant=float(np.mean(cy))
        cprob=calibrated(cp,coefficients)
        task={'calibration_n':len(cal),'coefficients':coefficients,'calibration_bins':reliability(cprob,cy),
              'constant_baseline_probability':constant,'periods':{}}
        for name,period in (('held_out',test),('later_partial_coverage',recent)):
            if not period:
                continue
            y=[r['y'][market] for r in period];days=[r['date'] for r in period]
            prob=calibrated([r['raw'][market] for r in period],coefficients)
            baseline=[constant]*len(y);league=[r['league_poisson'][market] for r in period]
            bins=reliability(prob,y)
            task['periods'][name]={'start':min(days),'end':max(days),
                'model':metrics(prob,y,days,p['bootstrap_resamples'],p['bootstrap_seed']),
                'constant_baseline':metrics(baseline,y,days,p['bootstrap_resamples'],p['bootstrap_seed']),
                'league_poisson_baseline':metrics(league,y,days,p['bootstrap_resamples'],p['bootstrap_seed']),
                'model_minus_constant':metrics(prob,y,days,p['bootstrap_resamples'],p['bootstrap_seed'],baseline),
                'calibration_bins':bins,
                'ece':sum(b['n']*abs(b['mean_probability']-b['observed_frequency']) for b in bins if b['n'])/len(y),
                'positive_rate':float(np.mean(y))}
        tasks[market]=task
    anchor=(date.fromisoformat(rows[-1]['date'])+timedelta(days=1)).isoformat()
    current=[r for r in rows if r['season']==SEASONS[-1]]
    artifact={'model_version':p['model_version'],'code_sha256':code_hash(),'policy':p,
        'generated_at':utcnow().isoformat(),'status':'research_only','approved':False,
        'data_sha256':digest(rows),'source':SOURCE,'license_url':LICENSE_URL,'revision':REVISION,
        'reviewed_license_sha256':sha256(license_raw).hexdigest(),
        'sources':sources,'state':fit(rows,anchor,p),'fixtures':fixtures,
        'current_rows':current,'current_rows_sha256':digest(current),'tasks':tasks,
        'coverage':{'completed_total':len(rows),'calibration_eligible':len(cal),'test_eligible':len(test),
                    'calibration_available':sum(p['calibration_start']<=r['date']<=p['calibration_end'] for r in rows),
                    'test_available':sum(p['test_start']<=r['date']<=p['test_end'] for r in rows),
                    'excluded_after_train':dict(skipped)},
        'limitations':['Goals-only independent-Poisson score assumption; no injuries, lineups, player statistics or xG',
            'Preceding UTC dates only; archive does not prove historical publication/revision timing',
            'Exploratory held-out diagnostics: overlapping archive periods were examined by earlier project models',
            'No historical sportsbook lines or odds; no market baseline, ROI, profitability or tradable edge established',
            '95% UTC-day block bootstrap assumes exchangeable independent day blocks; cross-day dependence is unverified',
            'Wilson calibration-bin frequency envelopes are not event-specific uncertainty guarantees',
            'Later periods are partial coverage; missing scores and excluded promoted teams can bias diagnostics',
            'Manual independent model review, prospective confirmation and all existing promotion gates remain required'],
        'betting_roi':None,'actual_wagers':None}
    artifact['artifact_sha256']=digest(artifact)
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(artifact,indent=2,allow_nan=False)+'\n')
    return artifact
