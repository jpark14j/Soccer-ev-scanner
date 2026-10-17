"""Prospective model scorecards: precision/power plans and review, not promotion.

Prediction-model review is distinct from execution/value approval. Prospective
records are self-recorded evidence; independent external verification is absent.
"""
from collections import defaultdict
from datetime import timedelta
from statistics import NormalDist
import json,math,sqlite3
from pathlib import Path
import numpy as np
from intelligence.domain import utcnow,parse_time,digest
from intelligence.forward_testing import records,POLICY
from intelligence.epl_validation import metrics

STATES=('Experimental','Under forward evaluation','Eligible for approval review','Approved','Suspended')


def sample_plan(policy=None):
    p=policy or json.loads(POLICY.read_text());alpha=1-p['confidence']
    z=NormalDist().inv_cdf(1-alpha/2);power=NormalDist().inv_cdf(p['power'])
    if not 0<p['calibration_precision_half_width']<.5 or not 0<p['minimum_relevant_brier_improvement']<1 or not 0<p['paired_difference_planning_sd']<=1:
        raise ValueError('Invalid prespecified precision/power inputs')
    return {'confidence':p['confidence'],'target_calibration_half_width':p['calibration_precision_half_width'],
        'IID_worst_case_calibration_n':math.ceil(z*z*.25/p['calibration_precision_half_width']**2),
        'paired_Brier_planning_n':math.ceil((z+power)**2*p['paired_difference_planning_sd']**2/p['minimum_relevant_brier_improvement']**2),
        'paired_SD_assumption':p['paired_difference_planning_sd'],'detectable_Brier_difference':p['minimum_relevant_brier_improvement'],
        'power':p['power'],'sample_requirement':'Planning approximations, not approval cutoffs. Dependence increases required information; actual block-interval precision and calibration must pass. Existing gates still apply.'}


def scored_report(rows,p):
    pairs=[(r['payload']['estimate']['probability'],1 if r['label']['outcome']=='win' else 0,
        r['payload']['baseline']['probability'],r['payload']['forecast_at'][:10]) for r in rows]
    if not pairs:return {'n':0,'metrics':None,'minus_recorded_constant':None,'calibration':[]}
    prob,y,base,days=map(list,zip(*pairs));blocks=len(set(days))
    main=metrics(prob,y,days,1000,81731);difference=metrics(prob,y,days,1000,81731,base)
    if blocks<p['minimum_time_blocks']:
        for report in (main,difference):
            for value in report.values():
                if isinstance(value,dict):value['interval']=None
    bins=[]
    # Day-cluster calibration gaps; retain all forecast outcomes, not just hits.
    for index in range(10):
        ix=[i for i,v in enumerate(prob) if min(9,int(v*10))==index]
        if not ix:continue
        dated=defaultdict(list)
        for i in ix:dated[days[i]].append(prob[i]-y[i])
        interval=None
        if len(dated)>=p['minimum_time_blocks'] and len({y[i] for i in ix})==2:
            sums=np.array([sum(v) for _,v in sorted(dated.items())]);counts=np.array([len(v) for _,v in sorted(dated.items())])
            draws=np.random.default_rng(81731+index).integers(0,len(dated),(1000,len(dated)))
            # Bonferroni diagnostic intervals across ten predeclared bins.
            alpha=(1-p['confidence'])/10
            interval=np.quantile(sums[draws].sum(axis=1)/counts[draws].sum(axis=1),[alpha/2,1-alpha/2]).tolist()
        bins.append({'range':[index/10,(index+1)/10],'n':len(ix),'UTC_day_blocks':len(dated),
            'mean_probability':float(np.mean([prob[i] for i in ix])),'observed_frequency':float(np.mean([y[i] for i in ix])),
            'model_minus_frequency_interval':interval})
    returns=[r['label']['hypothetical_score_contract_return'] for r in rows if r['label']['hypothetical_score_contract_return'] is not None]
    return {'n':len(rows),'UTC_day_blocks':blocks,'metrics':main,'minus_recorded_constant':difference,
        'calibration':bins,'score_contract_hypothetical_return':sum(returns) if returns else None,
        'score_contract_priced_n':len(returns),'accepted_ticket_ROI':None,
        'interval_scope':'UTC-day cluster bootstrap; cross-day/shared-model dependence, rare outcomes and optional stopping can invalidate nominal coverage; not external certification'}


def scope_key(p):
    return json.dumps(p['scope'],sort_keys=True,separators=(',',':'))


def scorecards(store,now=None):
    now=now or utcnow();rows=records(store);groups=defaultdict(list)
    with store.connect() as db:
        protocols={r['id']:dict(r) for r in db.execute('SELECT * FROM forward_protocols')}
    for row in rows:groups[scope_key(row['payload'])].append(row)
    cards=[]
    for key,group in sorted(groups.items()):
        scope=group[0]['payload']['scope'];protocol=protocols[scope['protocol_id']]
        config=json.loads(protocol['payload']);p=config['policy'];locked=parse_time(protocol['at'])
        integrity=digest(config)==protocol['id'] and locked<=now
        independent=[r for r in group if integrity and r['payload']['protocol_locked_before_forecast']
            and locked<=parse_time(r['payload']['forecast_at'])<=parse_time(r['at'])<parse_time(r['payload']['quote']['commence_time'])
            and not r['quarantined']]
        settled=[r for r in independent if r['label'] and r['label']['outcome'] in ('win','loss')]
        report=scored_report(settled,p);cohorts=defaultdict(list)
        for r in independent:cohorts[int((parse_time(r['payload']['forecast_at'])-locked).total_seconds()//(30*86400))].append(r)
        stability=[];review_rows=[]
        for i,values in sorted(cohorts.items()):
            labeled=[r for r in values if r['label'] and r['label']['outcome'] in ('win','loss')]
            end=locked+timedelta(days=30*(i+1));s=scored_report(labeled,p)
            fully_labeled=len(labeled)==len(values)
            if end<=now and fully_labeled:review_rows.extend(labeled)
            stability.append({'index':i,'cohort_end':end.isoformat(),'complete_calendar_period':end<=now,
                'fully_labeled':fully_labeled,'pending':len(values)-len(labeled),
                'n':s['n'],'mean_Brier_minus_constant':s['minus_recorded_constant']['binary_brier']['value'] if s['n'] else None})
        review=scored_report(review_rows,p)
        blockers=[]
        if not integrity:blockers.append('Forward protocol integrity failed')
        if config.get('reliability_code_sha256')!=digest(Path(__file__).read_text()):blockers.append('Reliability analysis code differs from the prospective lock; a matching reviewed analysis is required')
        if len(independent)!=len(group):blockers.append('Some records are pre-lock or quarantined and cannot count as independent confirmation')
        if review['n']<100:blockers.append('Existing minimum 100 fully evaluated forward decisions has not been reached; count alone cannot establish precision')
        diff=review['minus_recorded_constant'];interval=diff['binary_brier']['interval'] if diff else None
        if not interval:blockers.append('Insufficient UTC-day blocks for paired uncertainty')
        elif interval[1]>=0 or (interval[1]-interval[0])/2>p['minimum_relevant_brier_improvement']:
            blockers.append('Paired improvement/precision versus pre-recorded constant baseline is not sufficient')
        calibration=review['calibration']
        if not calibration or any(not b['model_minus_frequency_interval'] or max(abs(v) for v in b['model_minus_frequency_interval'])>p['calibration_precision_half_width'] for b in calibration):
            blockers.append('Observed calibration buckets lack adequate precision or acceptable gap')
        closed=[s for s in stability if s['complete_calendar_period']]
        if any(not s['fully_labeled'] for s in closed):blockers.append('Completed calendar cohorts still have missing outcomes; no selective settled-only review')
        completed=[s for s in closed if s['fully_labeled']]
        if len(completed)<2:blockers.append('Fewer than two completed and fully labeled 30-day cohorts; stability is unestablished')
        deterioration=bool(completed and completed[-1]['mean_Brier_minus_constant']>0)
        if deterioration:blockers.append('Latest completed cohort is worse than recorded baseline; investigate deterioration')
        state='Eligible for approval review' if not blockers else 'Under forward evaluation' if group else 'Experimental'
        if not integrity or any(r['quarantined'] for r in group):state='Suspended'
        from intelligence.lifecycle import active_champion,suspension_reason
        reviewed=active_champion(store,scope['sport'],scope['market'],league=scope['league'],now=now)
        suspension=suspension_reason(store,scope['sport'],scope['league'],scope['market'],scope['model_version'])
        if suspension:state='Suspended';blockers.append(suspension)
        elif state!='Suspended' and reviewed and reviewed.get('evidence_id')==scope['evidence_id'] and reviewed.get('model_version')==scope['model_version']:
            if scope['point'] is None or reviewed.get('contract_point')==scope['point']:state='Approved'
        cards.append({'scope':scope,'state':state,'recorded':len(group),'independent_pregame_records':len(independent),
            'quarantined':sum(r['quarantined'] for r in group),'protocol_locked_at':protocol['at'],'scores':report,
            'completed_cohort_review':review,
            'stability':stability,'monitoring':'Review deterioration at completed cohort boundary' if deterioration else 'No eligible deterioration conclusion',
            'planning':sample_plan(p),'review_blockers':blockers,'automatic_approval':False,
            'prediction_model_review':'External verification and explicit reviewed registry action remain required',
            'betting_opportunity_approved':False,'betting_limitations':['Market benchmark and execution/value evidence remain separate','No actual combined tickets or sportsbook settlement verification']})
    return {'recorded':len(rows),'labeled':sum(bool(r['label']) for r in rows),
        'quarantined':sum(r['quarantined'] for r in rows),'groups':cards,'states':list(STATES),
        'policy':json.loads(POLICY.read_text()),'planning':sample_plan(),'automatic_approval':False,
        'note':'First pregame contract/model/protocol records; books and opposing sides deduplicated. Legacy paper and backtests remain separate. No accepted-ticket profitability claim.'}


def status_for(store,sport,league,market,model_version,now=None,point=None,evidence_id=None):
    try:
        found=[c for c in scorecards(store,now)['groups'] if all(c['scope'][k]==v for k,v in
            {'sport':sport,'league':league,'market':market,'model_version':model_version,'point':point}.items())
            and (evidence_id is None or c['scope']['evidence_id']==evidence_id)]
        states={c['state'] for c in found}
        state='Suspended' if 'Suspended' in states else 'Approved' if states=={'Approved'} else 'Eligible for approval review' if states=={'Eligible for approval review'} else 'Under forward evaluation' if found else 'Experimental'
        from intelligence.lifecycle import suspension_reason
        if suspension_reason(store,sport,league,market,model_version):state='Suspended'
        return {'state':state,'recorded':sum(c['recorded'] for c in found),'groups':found,'betting_approved':False}
    except (sqlite3.Error,OSError,ValueError,KeyError):
        return {'state':'Experimental','recorded':None,'problem':'Forward reliability evidence unavailable; no approval inferred','betting_approved':False}
