"""Portable EPL inference, public-source refresh and conservative research ranking."""
from copy import deepcopy
from datetime import date,timedelta
from hashlib import sha256
import json
import os
from uuid import uuid4
import requests
from intelligence.domain import Estimate,digest,parse_time,utcnow
from intelligence.epl_source import ROOT,SEASONS,SOURCE,team,identity,decode
from intelligence.epl_goal_model import advance,add_result,rates,probabilities
from intelligence.epl_validation import ARTIFACT_PATH,code_hash,calibrated


def load_artifact(path=ARTIFACT_PATH):
    try:
        value=json.loads(path.read_text())
        checksum=value.pop('artifact_sha256')
        if checksum!=digest(value) or value['code_sha256']!=code_hash() or value['approved'] is not False:
            return None
        value['artifact_sha256']=checksum
        return value
    except (OSError,ValueError,KeyError,TypeError):
        return None


def supported(q):
    return q.sport=='Soccer' and q.league=='Premier League' and (q.market=='btts' or q.market=='totals' and q.point==2.5)


def _download(session,url):
    # Fixed public URLs only; no API credentials or user-supplied URLs/headers.
    response=session.get(url,timeout=6,allow_redirects=False,stream=True)
    try:
        if response.status_code!=200:
            raise ValueError('Public source unavailable')
        chunks=[];size=0
        for chunk in response.iter_content(65536):
            size+=len(chunk)
            if size>2_000_000:
                raise ValueError('Public source exceeds size limit')
            chunks.append(chunk)
        return b''.join(chunks)
    finally:
        response.close()


def refresh(artifact,store,now=None,session=None):
    """At most one two-file attempt per rolling day in this shared local store."""
    now=now or utcnow();key='epl-public-v1-'+artifact['artifact_sha256'];owner=uuid4().hex
    cached=store.cached(key,86400,now)
    if cached is not None:
        return cached
    if not store.claim_fetch(key,owner,now):
        return {'ok':False,'reason':'Public results refresh already in progress'}
    result={'ok':False,'checked_at':now.isoformat(),'reason':'Public results unavailable; bundled source dates still apply'}
    # Reserve the attempt before network I/O; reruns cannot repeatedly fetch failures.
    store.cache(key,result,now)
    owned=session is None;session=session or requests.Session()
    try:
        license_raw=_download(session,ROOT+'master/LICENSE.md')
        if sha256(license_raw).hexdigest()!=artifact['reviewed_license_sha256']:
            result['reason']='Public source license changed; human rights review required'
        else:
            raw=_download(session,ROOT+'master/'+SEASONS[-1]+'/en.1.json')
            rows,fixtures=decode(raw,SEASONS[-1])
            if any(r['date']>=now.date().isoformat() for r in rows):
                raise ValueError('Same-day/future completed scores need review')
            previous={identity(r):r for r in artifact['current_rows']}
            current={identity(r):r for r in rows}
            if any(current.get(k)!=r for k,r in previous.items()):
                result['reason']='Public history removed or revised an existing result; rebuild/review required'
            else:
                result={'ok':True,'checked_at':now.isoformat(),'rows':rows,'fixtures':fixtures,
                        'source_sha256':sha256(raw).hexdigest(),'source_url':ROOT+'master/'+SEASONS[-1]+'/en.1.json'}
        store.cache(key,result,now)
    except (ValueError,KeyError,TypeError):
        result['reason']='Public result contract invalid; human review required'
        store.cache(key,result,now)
    except (requests.RequestException,OSError):
        store.cache(key,result,now)  # No raw exception, response or request credentials in logs/UI.
    finally:
        if owned:
            session.close()
        store.release_fetch(key,owner)
    return result


def prepare(store,now=None,artifact=None,allow_refresh=None):
    now=now or utcnow();artifact=deepcopy(artifact or load_artifact())
    if not artifact:
        return {'problem':'Portable EPL artifact missing, altered or does not match current model code'}
    try:
        if parse_time(artifact['generated_at'])>now or artifact['state']['anchor']>now.date().isoformat():
            return {'problem':'Model artifact contains future-dated features or generation time'}
        allow_refresh=os.getenv('EPL_PUBLIC_REFRESH','1')=='1' if allow_refresh is None else allow_refresh
        observation=refresh(artifact,store,now) if allow_refresh else None
        artifact['source_check']=observation.get('checked_at') if observation else artifact['generated_at']
        if observation and not observation['ok']:
            # A failed request may use still-current bundled data; licensing/correction failures cannot.
            reason=observation['reason']
            if 'license changed' in reason or 'revised' in reason or 'review required' in reason:
                return {'problem':reason}
            artifact['refresh_warning']=reason
        if observation and observation['ok']:
            previous={identity(r) for r in artifact['current_rows']}
            extra=[r for r in observation['rows'] if identity(r) not in previous]
            if extra:
                anchor=max(artifact['state']['anchor'],(date.fromisoformat(max(r['date'] for r in extra))+timedelta(days=1)).isoformat())
                advance(artifact['state'],anchor,artifact['policy'])
                for row in extra:
                    add_result(artifact['state'],row,artifact['policy'])
            artifact['fixtures']=[r for r in artifact['fixtures'] if r['season']!=SEASONS[-1]]+observation['fixtures']
            artifact['current_rows']=observation['rows']
            artifact['data_sha256']=digest((artifact['data_sha256'],observation['source_sha256']))
        return artifact
    except (ValueError,KeyError,TypeError):
        return {'problem':'Public source/model contract failed validation; no probability inferred'}


def forecast(q,artifact,now=None):
    now=now or utcnow();detail={'quote_id':q.id,'blockers':[],'validated':False,'status':'research_only'}
    blockers=detail['blockers']
    if not supported(q):
        blockers.append('Focused model covers EPL BTTS and exactly 2.5 total goals only')
        return None,detail
    if artifact.get('problem'):
        blockers.append(artifact['problem']);return None,detail
    detail.update({'model':artifact['model_version'],'prediction_at':now.isoformat(),
        'training_end':artifact['state']['latest']+'T00:00:00+00:00','history_n':artifact['state']['n'],
        'data_sha256':artifact['data_sha256'],'model_code_sha256':artifact['code_sha256'],
        'data_source':SOURCE,'source_checked_at':artifact['source_check']})
    if q.status(now)!='current' or q.jurisdiction!='CA-ON':
        blockers.append('Current Ontario quote required; stale or in-play prices are ineligible')
    home,away=team(q.home),team(q.away)
    start=parse_time(q.commence_time).date().isoformat()
    if not home or not away or home==away:
        blockers.append('Provider team names do not match the explicit public-source aliases')
    if start<artifact['state']['anchor']:
        blockers.append('Current feature state cannot be used for historical/backdated inference')
    if (now.date()-date.fromisoformat(artifact['state']['latest'])).days>artifact['policy']['maximum_result_age_days']:
        blockers.append(f"Latest source result {artifact['state']['latest']} exceeds the {artifact['policy']['maximum_result_age_days']}-day freshness limit")
    missing=[r for r in artifact['fixtures'] if r['date']<now.date().isoformat() and
             (home in (r['home'],r['away']) or away in (r['home'],r['away'])) and r['season']==SEASONS[-1]]
    if missing:
        blockers.append('Unresolved earlier fixture scores for participating teams: '+', '.join(sorted(set(r['date'] for r in missing))))
    matching=[r for r in artifact['fixtures'] if (r['home'],r['away'],r['date'])==(home,away,start)]
    if not matching:
        blockers.append('Public fixture schedule does not exactly confirm this provider pairing and UTC date')
    market='btts' if q.market=='btts' else 'totals_2.5'
    positive=q.selection.lower() in ('yes','over')
    if q.selection.lower() not in (('yes','no') if market=='btts' else ('over','under')):
        blockers.append('Unrecognized binary selection')
    task=artifact['tasks'][market]
    detail.update({'calibration_n':task['calibration_n'],'test_n':task['periods']['held_out']['model']['n'],
                   'diagnostic_scores':task['periods']['held_out']['model'],
                   'evidence_id':artifact['artifact_sha256'],'calibrated':True})
    if blockers:
        return None,detail
    lambdas,reason=rates(artifact['state'],home,away,start,artifact['policy'])
    if lambdas is None:
        blockers.append(reason);return None,detail
    probability=float(calibrated(probabilities(*lambdas)[market],task['coefficients']))
    bin_data=task['calibration_bins'][min(9,int(probability*10))]
    adequate=bin_data['n']>=artifact['policy']['minimum_calibration_bin']
    lower,upper=bin_data['frequency_interval'] if adequate else (0.,1.)
    lower,upper=min(probability,lower),max(probability,upper)
    if not positive:
        probability,lower,upper=1-probability,1-upper,1-lower
    blockers.extend(['No independent prospective confirmation or reviewed champion activation',
                     'No timestamped historical market baseline; profitability and betting EV are unestablished',
                     'Operator settlement scope, injuries and lineups remain unverified'])
    if not adequate:
        blockers.append('Fewer than 50 calibration outcomes support this probability bucket')
    detail.update({'probability':probability,'lower':lower,'upper':upper,'calibration_bin_n':bin_data['n'],
        'interval_basis':'95% calibration-bin Wilson frequency envelope; not an event-specific confidence interval',
        'method':'Time-decayed shrunk Poisson goal strengths; monotone calibration fitted only on 2023–24',
        'raw_positive_probability':probabilities(*lambdas)[market],
        'drift_ece':task['periods'].get('later_partial_coverage',{}).get('ece'),
        'high_probability_evidence':False})
    # Historical exploration alone is not credible independent confirmation for ranking.
    estimate=Estimate(probability,lower,upper,artifact['model_version'],detail['training_end'],
        artifact['artifact_sha256'],False,tuple(blockers),'Soccer','Premier League',q.market)
    return estimate,detail


def high_probability_research(analysis,now=None):
    from intelligence.epl_validation import policy
    now=now or utcnow();p=policy();rows=[]
    for q in analysis.quotes:
        estimate=analysis.estimates.get(q.id);detail=analysis.advanced_details.get(q.id,{})
        if (estimate and estimate.valid() and q.status(now)=='current' and q.jurisdiction=='CA-ON'
            and detail.get('calibrated') and detail.get('high_probability_evidence') is True
            and detail.get('calibration_bin_n',0)>=p['minimum_calibration_bin']
            and estimate.probability>=p['high_probability_minimum']
            and estimate.lower>=p['high_probability_lower_minimum']
            and estimate.upper-estimate.lower<=p['high_probability_maximum_width']):
            rows.append((q,estimate,detail))
    return sorted(rows,key=lambda r:(-r[1].lower,-r[1].probability,r[0].id))[:3]
