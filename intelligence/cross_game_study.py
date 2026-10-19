"""Offline walk-forward and cross-game parlay calibration diagnostics.

Only reviewed score archives are accepted by the CLI. No downloads, historical
publication claims, current forecasts, executable tickets or model promotion.
Different games are not presumed independent: that product is a named baseline,
and an earlier-period joint calibrator is compared on later games.
"""
from collections import Counter
from pathlib import Path
from math import prod
import json
import numpy as np
from intelligence.domain import digest,utcnow
from intelligence.team_rating import replay
from intelligence.epl_validation import calibrated,fit_calibrator,metrics,reliability
from intelligence.joint_research import bounds

VERSION='date-block-cross-game-diagnostic-1'
FOLDS={'NBA':(('2023-07-01','2024-07-01','2025-07-01'),('2024-07-01','2025-07-01','2026-07-01')),
       'MLB':(('2024-01-01','2025-01-01','2026-01-01'),)}
DESTINATION=Path(__file__).resolve().parents[1]/'research_assets/cross_game_study.json'


def groups(rows,legs):
    """Disjoint same-day favorite groups, ordered by identity, never outcomes.

    Repeated-team days (e.g. MLB doubleheaders) are excluded in their entirety
    for that team. No game/team is reused across groups of a given leg count.
    Leftovers are discarded, never selected retrospectively for wins.
    """
    if legs not in (2,3):raise ValueError('Two or three legs required')
    byday={}
    for r in rows:byday.setdefault(r['date'],[]).append(r)
    result=[];excluded=0
    for day,batch in sorted(byday.items()):
        counts=Counter(t for r in batch for t in (r['home'],r['away']))
        eligible=sorted((r for r in batch if counts[r['home']]==counts[r['away']]==1),key=lambda r:(r['home'],r['away']))
        excluded+=len(batch)-len(eligible)
        for offset in range(0,len(eligible)-legs+1,legs):
            selected=eligible[offset:offset+legs]
            ps=[max(r['p'],1-r['p']) for r in selected]
            y=int(all(r['y']==int(r['p']>=.5) for r in selected))
            result.append({'date':day,'ids':[(r['home'],r['away']) for r in selected],
                'p':prod(ps),'y':y,'bounds':bounds(ps)})
    return result,excluded


def clipped_joint(rows,coefficients):
    p=calibrated([r['p'] for r in rows],coefficients)
    return [float(np.clip(v,*r['bounds'])) for v,r in zip(p,rows)]


def assessment(p,rows,resamples,baseline=None):
    y=[r['y'] for r in rows];days=[r['date'] for r in rows]
    bins=reliability(p,y)
    return {'metrics':metrics(p,y,days,resamples,17841,baseline),
        **({} if baseline is not None else {'reliability':bins,
            'ece':sum(b['n']*abs(b['mean_probability']-b['observed_frequency']) for b in bins if b['n'])/len(rows)})}


def fold(rows,cal_start,test_start,test_end,resamples=500):
    warm=[r for r in rows if r['date']<cal_start]
    cal=[r for r in rows if cal_start<=r['date']<test_start]
    test=[r for r in rows if test_start<=r['date']<test_end]
    days=sorted({r['date'] for r in cal})
    if len(days)<60 or min(len(warm),len(cal),len(test))<500:raise ValueError('Insufficient chronological season coverage')
    cut=days[len(days)//2]
    marginal_fit=[r for r in cal if r['date']<cut]
    joint_period=[r for r in cal if r['date']>=cut]
    coeff=fit_calibrator([r['p'] for r in marginal_fit],[r['y'] for r in marginal_fit])
    def apply(records):
        return [r|{'p':float(p)} for r,p in zip(records,calibrated([r['p'] for r in records],coeff))]
    jc,tc=apply(joint_period),apply(test)
    base=(sum(r['y'] for r in warm)+1)/(len(warm)+2)
    bp=[base]*len(test);raw=[r['p'] for r in test];mp=[r['p'] for r in tc]
    result={'calibration_start':cal_start,'test_start':test_start,'test_end_exclusive':test_end,
        'marginal_fit_end':marginal_fit[-1]['date'],'joint_fit_start':joint_period[0]['date'],
        'warm_n':len(warm),'marginal_fit_n':len(marginal_fit),'joint_period_n':len(jc),'test_n':len(test),
        'marginal_coefficients':coeff,'selection_policy':'Model favorite after earlier marginal calibration; no sportsbook-implied probabilities',
        'singles':{'raw_elo':assessment(raw,test,resamples),'calibrated_elo':assessment(mp,test,resamples),
            'training_home_frequency':assessment(bp,test,resamples),
            'calibrated_minus_raw':assessment(mp,test,resamples,raw)},'parlays':{}}
    for legs in (2,3):
        fit_rows,ex_cal=groups(jc,legs);test_rows,ex_test=groups(tc,legs)
        if min(len(fit_rows),len(test_rows))<40:
            result['parlays'][str(legs)]={'blocked':'Fewer than 40 disjoint calibration/test groups','approved':False};continue
        joint_coeff=fit_calibrator([r['p'] for r in fit_rows],[r['y'] for r in fit_rows])
        predicted=clipped_joint(test_rows,joint_coeff);product=[r['p'] for r in test_rows]
        baseline=(sum(r['y'] for r in fit_rows)+1)/(len(fit_rows)+2)
        result['parlays'][str(legs)]={'calibration_n':len(fit_rows),'test_n':len(test_rows),
            'excluded_repeated_team_games':{'calibration':ex_cal,'test':ex_test},
            'test_groups_sha256':digest([{'day':r['date'],'ids':r['ids']} for r in test_rows]),
            'coefficients':joint_coeff,'hypothetical_independence_product':assessment(product,test_rows,resamples),
            'earlier_joint_calibrator':assessment(predicted,test_rows,resamples),
            'prior_joint_frequency':assessment([baseline]*len(test_rows),test_rows,resamples),
            'calibrator_minus_product':assessment(predicted,test_rows,resamples,product),
            'logical_bound_width_quantiles':np.quantile([r['bounds'][1]-r['bounds'][0] for r in test_rows],[0,.5,.95,1]).tolist(),
            'approved':False,'current_joint_forecast':False,'executable_price':None,'EV':None}
    # These are configuration checks, never approvals inferred from a p-value.
    result['approved']=False
    return result


def code_hash():
    return digest({n:Path(__file__).with_name(n).read_text() for n in
        ('cross_game_study.py','team_rating.py','epl_validation.py','joint_research.py')})


def evaluate(history,sport,source,resamples=500):
    if sport not in FOLDS:raise ValueError('Reviewed NBA or MLB archive required')
    games=history.copy()
    if sport=='MLB':
        # Reviewed franchise identity only; the relocation/park effect is absent.
        for column in ('HomeTeam','AwayTeam'):games[column]=games[column].replace({'ATH':'OAK'})
    if 'game_id' not in games or games.game_id.duplicated().any():raise ValueError('Unique historical game identities required')
    rows,_=replay(games,sport)
    return {'sport':sport,'source':source,'history_n':len(games),'data_end':games.date.max().date().isoformat(),
        'data_sha256':digest(games.to_json(orient='records',date_format='iso')),
        'folds':[fold(rows,*spec,resamples=resamples) for spec in FOLDS[sport]],'approved':False}


def build(nba,mlb,nba_source,mlb_source,resamples=500):
    report={'schema':1,'version':VERSION,'generated_at':utcnow().isoformat(),'code_sha256':code_hash(),
        'reports':{'NBA':evaluate(nba,'NBA',nba_source,resamples),'MLB':evaluate(mlb,'MLB',mlb_source,resamples)},
        'approved_models':0,'approved_joint_models':0,'current_forecasts_enabled':False,
        'mixed_sport_joint_validated':False,'provider_requests':0,'paid_requests':0,
        'method':'Whole-date Elo replay; first-half earlier-season marginal calibration; second-half disjoint-group joint calibration; later full-season test',
        'limitations':['Previously inspected archives: chronological fitting isolation is not independent prospective confirmation',
            'Independence products are hypothetical comparison baselines, never validated joint forecasts',
            'Joint recalibration describes this deterministic favorite-group policy only; not arbitrary user parlays or mixed sports',
            'Conditional Frechet bounds rely on marginal estimates and are not uncertainty confidence intervals',
            'Day-block score intervals omit cross-day/team dependence, source revisions and model-selection uncertainty',
            'No current NBA fixture/offseason readiness or permitted 2026 MLB results/fixture source; forecasts remain disabled',
            'No injuries, lineups, starting pitchers, observed prices, executable tickets or positive-EV evidence',
            'ATH/OAK franchise reconciliation does not model MLB relocation and park changes']}
    report['sha256']=digest(report);return report


def load_report(path=DESTINATION):
    try:
        r=json.loads(Path(path).read_text());checksum=r.pop('sha256')
        if digest(r)!=checksum or r['code_sha256']!=code_hash() or r['approved_models'] or r['approved_joint_models'] or r['current_forecasts_enabled']:return None
        return r|{'sha256':checksum}
    except (OSError,ValueError,TypeError,KeyError):return None


def summary():
    r=load_report()
    return {'state':'offline historical comparison verified' if r else 'offline report unavailable or mismatched',
        'report_sha256':r['sha256'] if r else None,'approved_joint_models':0,'current_joint_forecasts':False,
        'mixed_sport_joint_validated':False}


def main():
    import argparse
    from intelligence.recent_nba import load_bundle
    from intelligence.history import load_licensed
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--nba-bundle',required=True,type=Path);p.add_argument('--history-dir',required=True,type=Path);p.add_argument('--output',default=DESTINATION,type=Path);a=p.parse_args()
    nba,sources=load_bundle(a.nba_bundle);mlb=load_licensed('MLB',a.history_dir)
    result=build(nba,mlb,sources,json.loads((a.history_dir/'mlb.source.json').read_text()))
    a.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({s:[{'test_start':f['test_start'],'test_n':f['test_n'],
        'single_brier':f['singles']['calibrated_elo']['metrics']['binary_brier']['value'],
        'parlays':{k:{'n':v.get('test_n'),'brier_difference':v.get('calibrator_minus_product',{}).get('metrics',{}).get('binary_brier')} for k,v in f['parlays'].items()}}
        for f in r['folds']] for s,r in result['reports'].items()}))


if __name__=='__main__':main()
