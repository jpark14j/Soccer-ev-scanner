"""Fresh-input-only expanded inference and dependency metadata; no edge approval."""
from copy import deepcopy
from datetime import date,timedelta
from dataclasses import asdict
import os
from intelligence.domain import Estimate,digest,parse_time,utcnow
from intelligence.expanded_models import load,policy,rows_from_events
from intelligence.data_adapters import team_identity
from intelligence.competitions import COMPETITIONS
from intelligence.event_data import reconciled
from intelligence.venue_goals import predict,extend
from intelligence.epl_validation import calibrated


def supported(q):
    target=policy()['targets'].get(q.league)
    return q.sport=='Soccer' and (target=='btts' and q.market=='btts' or target=='totals_2.5' and q.market=='totals' and q.point==2.5)


def prepare(league,store,now=None,allow_refresh=None):
    now=now or utcnow();artifact=deepcopy(load(league))
    if not artifact:return {'problem':'Expanded model artifact missing or does not match current code'}
    if parse_time(artifact['generated_at'])>now or artifact['state']['as_of']>now.date().isoformat():
        return {'problem':'Future-dated expanded model state'}
    artifact['source_checked_at']=artifact['generated_at'];artifact['source_kind']='bundled pinned snapshot'
    enabled=os.getenv('MULTI_RESULTS_REFRESH','1')=='1' if allow_refresh is None else allow_refresh
    if enabled:
        from intelligence.public_results import current
        events,meta=current(store,league,now)
        if not meta['ok']:return {'problem':meta['problem']}
        old={r['fixture_id']:r for r in artifact['current_rows']}
        rows=rows_from_events(events);actual={r['fixture_id']:r for r in rows}
        if any(actual.get(k)!=r for k,r in old.items()):
            return {'problem':'Source revised or withdrew completed results; explicit rebuild/review required'}
        if any(r['conflicts'] for r in reconciled(store,artifact['competition_id'],now)):
            return {'problem':'Conflicting result/date observations block this competition until reviewed'}
        extra=[r for r in rows if r['fixture_id'] not in old]
        if extra:
            anchor=max(artifact['state']['as_of'],(date.fromisoformat(max(r['date'] for r in extra))+timedelta(days=1)).isoformat())
            artifact['state']=extend(artifact['state'],extra,anchor,artifact['policy'])
        artifact['fixtures']=[asdict(e) for e in events];artifact['current_rows']=rows
        artifact['source_checked_at']=meta['checked_at'];artifact['source_kind']='cached public current-season observation'
        artifact['data_sha256']=digest((artifact['data_sha256'],meta['sha256']))
    return artifact


def forecast(q,artifact,now=None):
    now=now or utcnow();d={'quote_id':q.id,'validated':False,'status':'research_model','blockers':[]};b=d['blockers']
    if not supported(q):b.append('No frozen competition/market model for this quote');return None,d
    if artifact.get('problem'):b.append(artifact['problem']);return None,d
    if artifact['competition_id']!=COMPETITIONS[q.league].id or artifact['league']!=q.league or artifact['target']!=policy()['targets'][q.league]:
        b.append('Artifact competition/market scope does not match this quote');return None,d
    p=artifact['policy'];start=parse_time(q.commence_time).date().isoformat();c=COMPETITIONS[q.league]
    d.update({'model':artifact['model_version'],'prediction_at':now.isoformat(),'data_sha256':artifact['data_sha256'],
        'model_code_sha256':artifact['code_sha256'],'training_end':artifact['state']['latest']+'T00:00:00+00:00',
        'history_n':artifact['state']['n'],'calibration_n':artifact['calibration_n'],
        'test_n':artifact['periods']['final_test']['eligible'],'calibrated':True,
        'competition_id':c.id,'data_source':'OpenFootball publisher-CC0 source-reported full-time results',
        'source_checked_at':artifact['source_checked_at'],'diagnostic_scores':artifact['periods']['final_test']['model'],
        'model_stage':'Research model; forecasting reliability and betting edge are not approved'})
    if q.status(now)!='current' or q.jurisdiction!='CA-ON':b.append('Current Ontario pregame price required')
    try:home,_=team_identity(c,q.home);away,_=team_identity(c,q.away)
    except ValueError:b.append('Exact reviewed provider-team aliases are missing');return None,d
    if (now.date()-date.fromisoformat(artifact['state']['latest'])).days>p['maximum_result_age_days']:
        b.append('Latest '+q.league+' source result '+artifact['state']['latest']+' exceeds 21-day freshness limit')
    for name,identifier in ((q.home,home),(q.away,away)):
        last=artifact['state']['teams'].get(identifier,{}).get('last')
        if last and (now.date()-date.fromisoformat(last)).days>p['maximum_result_age_days']:
            b.append(name+': team result history is older than the 21-day current-input limit')
    if start<artifact['state']['as_of']:b.append('Future feature state cannot support an earlier fixture')
    missing=[e for e in artifact['fixtures'] if e['event_date']<now.date().isoformat() and e['status']!='completed' and (home in (e['home_id'],e['away_id']) or away in (e['home_id'],e['away_id']))]
    if missing:b.append('Unresolved earlier team fixtures: '+', '.join(sorted({e['event_date'] for e in missing})))
    if not any((e['home_id'],e['away_id'],e['event_date'])==(home,away,start) for e in artifact['fixtures']):
        b.append('Source does not exactly confirm this team pairing and fixture date')
    if q.selection.lower() not in (('yes','no') if q.market=='btts' else ('over','under')):b.append('Unsupported binary selection')
    if b:return None,d
    raw,reason=predict(artifact['state'],home,away,start,p)
    if raw is None:b.append(reason.replace(home,q.home).replace(away,q.away));return None,d
    probability=float(calibrated(raw[artifact['target']],artifact['coefficients']))
    bucket=artifact['calibration_bins'][min(9,int(probability*10))]
    lo,hi=bucket['frequency_interval'] if bucket['n']>=p['minimum_calibration_bin'] else (0.,1.)
    lo,hi=min(lo,probability),max(hi,probability)
    if q.selection.lower() in ('no','under'):probability,lo,hi=1-probability,1-hi,1-lo
    b.extend(artifact['model_approval_blockers'])
    b.append('Player availability, operator settlement rules and current-event uncertainty are unverified')
    if bucket['n']<p['minimum_calibration_bin']:b.append('Fewer than 50 calibration outcomes in this bucket')
    d.update(probability=probability,lower=lo,upper=hi,calibration_bin_n=bucket['n'],evidence_id=artifact['artifact_sha256'],
        interval_basis='95% historical calibration-bin frequency envelope; not an event-specific confidence interval',
        method='Per-competition venue-specific Poisson strengths with frozen monotone calibration',
        dependency_groups={'event':q.provider+':'+q.event_id,'teams':[home,away],'competition':c.id,'joint_validated':False},
        available_features=['Earlier team home/away goals scored/conceded','Competition scoring environment'],
        result_based_rest_days={name:(date.fromisoformat(start)-date.fromisoformat(artifact['state']['teams'][team]['last'])).days for name,team in (('home',home),('away',away))},
        rest_note='Derived from prior completed dates; not used as a fitted effect or verified full-schedule rest')
    estimate=Estimate(probability,lo,hi,artifact['model_version'],d['training_end'],artifact['artifact_sha256'],False,
        tuple(b),'Soccer',q.league,q.market)
    return estimate,d
