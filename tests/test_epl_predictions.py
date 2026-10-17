"""Synthetic contract fixtures test software, never claimed as model evidence."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from unittest.mock import patch
import numpy as np
import pytest
from conftest import NOW
from intelligence.domain import digest,utcnow
from intelligence.epl_source import decode,identity,team,ROOT,SEASONS
from intelligence.epl_goal_model import fit,rates,probabilities,add_result
from intelligence.epl_validation import policy,calibrated,fit_calibrator,metrics,reliability,code_hash
from intelligence.epl_forecasts import load_artifact,prepare,forecast,refresh,high_probability_research,supported
from intelligence.pipeline import Analysis,evaluate_quotes
from intelligence.processing import record_shadow_forecasts,label_public_epl,shadow_statistics


def soccer_quote(quote,now=NOW):
    return replace(quote,sport='Soccer',league='Premier League',event_id='epl-test-only',
        event='Arsenal vs Chelsea',home='Arsenal',away='Chelsea',market='btts',selection='Yes',
        commence_time=(now+timedelta(days=1)).isoformat(),
        source_updated_at=(now-timedelta(seconds=30)).isoformat(),received_at=(now-timedelta(seconds=10)).isoformat())


def synthetic_artifact(q,now=NOW):
    a=deepcopy(load_artifact());assert a
    a['generated_at']=(now-timedelta(minutes=1)).isoformat()
    a['state']['anchor']=(now-timedelta(days=1)).date().isoformat()
    a['state']['latest']=(now-timedelta(days=2)).date().isoformat()
    a['fixtures']=[{'home':team(q.home),'away':team(q.away),'date':q.commence_time[:10],'season':SEASONS[-1]}]
    a['source_check']=now.isoformat()
    return a


def test_contract_handles_unplayed_without_turning_into_zero():
    matches=[{'date':'2026-10-17','team1':'Arsenal FC','team2':'Chelsea FC','score':[]},
        {'date':'2026-10-16','team1':'Chelsea FC','team2':'Arsenal FC','score':{'ft':[2,0]}}]
    raw=json.dumps({'matches':matches}).encode()
    rows,missing=decode(raw,SEASONS[-1])
    assert len(rows)==len(missing)==1 and rows[0]['hg']==2
    assert 'hg' not in missing[0]
    with pytest.raises(ValueError):
        decode(json.dumps({'matches':matches+[matches[0]]}).encode(),SEASONS[-1])
    matches[0]['team1']='Almost Arsenal'
    with pytest.raises(ValueError):
        decode(json.dumps({'matches':matches}).encode(),SEASONS[-1])


def test_source_rejects_malformed_scores_unknown_teams_dates_and_size():
    match={'date':'2026-10-17','team1':'Arsenal FC','team2':'Chelsea FC','score':{'ft':[True,0]}}
    for update in ({},{'date':'2025-10-17'},{'team1':'Unknown Club'}):
        with pytest.raises(ValueError):
            decode(json.dumps({'matches':[match|update]}).encode(),SEASONS[-1])
    with pytest.raises(ValueError):
        decode(b' '*2_000_001,SEASONS[-1])
    with pytest.raises(ValueError):
        decode(b'{"matches":["malformed"]}',SEASONS[-1])
    assert team('Brighton and Hove Albion')=='Brighton' and team('Arsenal?') is None


def test_prior_day_only_features_and_incremental_equivalence():
    p=policy();row={'date':'2026-10-14','home':'Arsenal','away':'Chelsea','hg':1,'ag':2}
    same=row|{'date':'2026-10-15','hg':30};future=row|{'date':'2026-10-16','hg':30}
    assert fit([row,same,future],'2026-10-15',p)==fit([row],'2026-10-15',p)
    state=fit([row],'2026-10-15',p)
    with pytest.raises(ValueError):
        add_result(state,same,p)
    from intelligence.epl_goal_model import advance
    advance(state,'2026-10-17',p);add_result(state,same,p)
    expected=fit([row,same],'2026-10-17',p)
    assert state['hg']==pytest.approx(expected['hg'])
    assert state['teams']['Arsenal']['w2']==pytest.approx(expected['teams']['Arsenal']['w2'])
    assert rates(state,'Arsenal','Chelsea','2026-10-17',p)[0] is None
    with pytest.raises(ValueError):
        advance(state,'2026-10-16',p)


def test_poisson_and_monotone_calibration_probabilities():
    probabilities_=probabilities(1.3,1.1)
    assert all(0<v<1 for v in probabilities_.values())
    assert probabilities(0,1)['btts']==0
    raw=np.linspace(.1,.9,100);labels=(np.arange(100)%3>0).astype(int)
    coefficients=fit_calibrator(raw,labels)
    result=calibrated(raw,coefficients)
    assert coefficients[1]>=0 and np.all(np.diff(result)>=0)
    assert np.isfinite(result).all() and ((result>0)&(result<1)).all()


def test_day_block_diagnostics_include_denominators_and_baseline_differences():
    report=metrics([.8,.2,.7,.4],[1,0,0,1],['a','a','b','b'],100,12,[.5]*4)
    assert report['n']==4 and report['utc_day_blocks']==2
    assert report['binary_brier']['value']==pytest.approx(np.mean([.04,.04,.49,.36])-.25)
    assert len(report['log_loss']['interval'])==2
    assert reliability([.65]*50,[1]*30+[0]*20)[6]['n']==50


def test_portable_real_evaluation_integrity_and_no_profit_claim(tmp_path):
    a=load_artifact();assert a and a['code_sha256']==code_hash()
    assert a['coverage']['completed_total']==2298
    assert a['coverage']['calibration_eligible']==363 and a['coverage']['test_eligible']==368
    for task in a['tasks'].values():
        assert task['calibration_n']==363
        test=task['periods']['held_out']
        assert test['model']['n']==test['constant_baseline']['n']==368
        assert test['model']['utc_day_blocks']==109
        assert 'model_minus_constant' in test
    assert a['approved'] is False and a['betting_roi'] is None and a['actual_wagers'] is None
    a['tasks']['btts']['coefficients'][0]+=1
    path=tmp_path/'altered.json';path.write_text(json.dumps(a))
    assert load_artifact(path) is None


def test_valid_input_research_inference_and_complements(store,quote):
    q=soccer_quote(quote);a=synthetic_artifact(q)
    e,d=forecast(q,a,NOW);other,od=forecast(replace(q,selection='No'),a,NOW)
    assert e and e.valid() and not e.validated and d['calibrated']
    assert e.probability+other.probability==pytest.approx(1)
    assert e.lower==pytest.approx(1-other.upper)
    assert d['prediction_at']==NOW.isoformat() and d['test_n']==368
    assert d['calibration_n']==363 and 'event-specific' in d['interval_basis']
    total=replace(q,market='totals',point=2.5,selection='Over')
    assert forecast(total,a,NOW)[0]
    assert not supported(replace(total,point=3.5)) and not supported(replace(q,market='h2h'))
    analysis=Analysis(quotes=[q],estimates={q.id:e},advanced_details={q.id:d})
    assert not high_probability_research(analysis,NOW)
    from intelligence.parlay_research import leg_evidence
    leg=leg_evidence(q,analysis,NOW)
    assert leg.model_status=='research' and leg.estimated_ev is None


@pytest.mark.parametrize('change', ['stale','unverified','missing_team','unresolved','future_artifact','unknown_selection','fixture_date','few_games'])
def test_missing_or_outdated_inputs_never_emit_forecast(store,quote,change):
    q=soccer_quote(quote);a=synthetic_artifact(q)
    if change=='stale':a['state']['latest']='2026-08-01'
    if change=='unverified':q=replace(q,jurisdiction='unverified')
    if change=='missing_team':q=replace(q,home='Made-up Club')
    if change=='unresolved':a['fixtures'].append(a['fixtures'][0]|{'date':'2026-10-10'})
    if change=='future_artifact':a['state']['anchor']='2026-10-18'
    if change=='unknown_selection':q=replace(q,selection='Maybe')
    if change=='fixture_date':a['fixtures'][0]['date']='2026-10-18'
    if change=='few_games':a['state']['teams']['Arsenal']['n']=2
    estimate,detail=forecast(q,a,NOW)
    assert estimate is None and detail['blockers']


def test_real_bundled_data_gap_is_explicit_and_not_patched_over(store,quote):
    q=soccer_quote(quote,utcnow());a=prepare(store,allow_refresh=False)
    e,d=forecast(q,a)
    assert e is None
    assert any('2026-09-20' in s and 'freshness' in s for s in d['blockers'])
    assert any('Unresolved earlier fixture' in s for s in d['blockers'])


def test_pipeline_connects_focused_model_before_legacy_missing_history(store,quote):
    now=utcnow();q=soccer_quote(quote,now);a=synthetic_artifact(q,now)
    with patch('intelligence.epl_forecasts.prepare',return_value=a),patch('intelligence.pipeline.load_soccer',side_effect=AssertionError('No legacy history required')):
        result=evaluate_quotes(Analysis(quotes=[q]),store)
    assert result.estimates[q.id].model_version==policy()['model_version']
    assert not result.opportunities
    assert result.advanced_details[q.id]['calibrated']
    from intelligence.analyst_context import build_context,select_local,render_plan
    context=build_context(result,now=now)
    response,_=render_plan(select_local('What soccer probabilities are supported?',context),context)
    assert 'Research estimate' in response and 'Not an approved probability' in response


class PublicSession:
    def __init__(self,license_raw,results):
        self.responses=[license_raw,results];self.urls=[]
    def get(self,url,**kwargs):
        self.urls.append(url)
        assert url.startswith(ROOT+'master/') and 'headers' not in kwargs
        raw=self.responses.pop(0)
        class Response:
            status_code=200
            def iter_content(self,size):yield raw
            def close(self):pass
        return Response()


def public_payload(a):
    fixtures=[{'date':r['date'],'team1':r['home'] if r['home']!='Wolves' else 'Wolverhampton Wanderers FC',
               'team2':r['away'] if r['away']!='Wolves' else 'Wolverhampton Wanderers FC','score':{'ft':[r['hg'],r['ag']]}}
              for r in a['current_rows']]
    return json.dumps({'matches':fixtures}).encode()


def test_public_refresh_cache_no_credentials_no_odds_budget_spend(store,quote):
    a=load_artifact();license_raw=b'synthetic license text';a['reviewed_license_sha256']=sha256(license_raw).hexdigest()
    session=PublicSession(license_raw,public_payload(a))
    first=refresh(a,store,NOW,session);second=refresh(a,store,NOW+timedelta(hours=1),session)
    assert first==second and first['ok'] and len(session.urls)==2
    with store.connect() as db:
        assert db.execute('SELECT count(*) FROM budget').fetchone()[0]==0


def test_license_change_blocks_and_only_fetches_license(store):
    a=load_artifact();session=PublicSession(b'new license',b'not fetched')
    result=refresh(a,store,NOW,session)
    assert not result['ok'] and 'license changed' in result['reason'] and len(session.urls)==1
    with patch('intelligence.epl_forecasts.refresh',return_value=result):
        assert 'problem' in prepare(store,NOW,synthetic_artifact(soccer_quote_for_prepare()),True)


def soccer_quote_for_prepare():
    from intelligence.domain import Quote
    return Quote('the-odds-api','Soccer','Premier League','test','test','Arsenal','Chelsea',
        '2026-10-17T01:00:00+00:00','test','test','btts','Yes',None,'',2.,NOW.isoformat(),NOW.isoformat(),'CA-ON')


def test_changed_history_requires_rebuild_and_future_artifact_blocked(store,quote):
    a=load_artifact();license_raw=b'synthetic license';a['reviewed_license_sha256']=sha256(license_raw).hexdigest()
    revised=deepcopy(a);revised['current_rows'][0]['hg']+=1
    result=refresh(a,store,NOW,PublicSession(license_raw,public_payload(revised)))
    assert not result['ok'] and 'revised' in result['reason']
    a['generated_at']=(NOW+timedelta(days=1)).isoformat()
    assert 'future' in prepare(store,NOW,a,False)['problem']


def test_public_failure_is_cached_and_raw_error_cannot_leak(store):
    import requests
    a=load_artifact()
    class Failure:
        calls=0
        def get(self,*args,**kwargs):
            self.calls+=1
            raise requests.ConnectionError('DO-NOT-LEAK-SYNTHETIC-CREDENTIAL')
    session=Failure()
    result=refresh(a,store,NOW,session)
    assert not result['ok'] and 'DO-NOT-LEAK' not in json.dumps(result)
    assert refresh(a,store,NOW+timedelta(hours=2),session)==result and session.calls==1


def test_incremental_public_results_update_features_without_refitting_calibrator(store):
    now=utcnow();a=load_artifact()
    missing=next(r for r in a['fixtures'] if r['season']==SEASONS[-1] and r['date']<now.date().isoformat())
    extra=missing|{'hg':2,'ag':1}  # Synthetic software-test outcome only.
    observation={'ok':True,'checked_at':now.isoformat(),'rows':a['current_rows']+[extra],
        'fixtures':[r for r in a['fixtures'] if r['season']==SEASONS[-1] and identity(r)!=identity(extra)],
        'source_sha256':'synthetic-test-only'}
    with patch('intelligence.epl_forecasts.refresh',return_value=observation):
        updated=prepare(store,now,a,True)
    assert updated['state']['n']==a['state']['n']+1
    assert updated['state']['latest']==max(extra['date'],a['state']['latest'])
    assert updated['tasks']==a['tasks'] and updated['data_sha256']!=a['data_sha256']
    assert identity(extra) not in [identity(r) for r in updated['fixtures']]


def test_snapshot_hashes_prevent_training_on_unverified_cache(tmp_path):
    from intelligence.epl_validation import build
    (tmp_path/'LICENSE.md').write_text('unreviewed license')
    with pytest.raises(ValueError,match='license differs'):
        build(tmp_path,tmp_path/'not-created.json')
    assert not (tmp_path/'not-created.json').exists()


def test_forward_records_never_backdated_labels_are_not_ticket_results(store,quote):
    q=soccer_quote(quote);a=synthetic_artifact(q);e,d=forecast(q,a,NOW)
    analysis=Analysis(quotes=[q],estimates={q.id:e},advanced_estimates={q.id:e},advanced_details={q.id:d})
    assert record_shadow_forecasts(analysis,store,NOW)==1
    assert record_shadow_forecasts(analysis,store,NOW)==0
    assert record_shadow_forecasts(analysis,store,NOW+timedelta(days=2))==0
    finished=deepcopy(a);finished['current_rows']=[{'date':q.commence_time[:10],'home':'Arsenal','away':'Chelsea',
        'hg':0,'ag':0,'season':SEASONS[-1]}]
    assert label_public_epl(store,finished,NOW)==0
    assert label_public_epl(store,finished,NOW+timedelta(days=2))==1
    assert label_public_epl(store,finished,NOW+timedelta(days=2))==0
    stats=shadow_statistics(store)
    assert stats['scored_forecast_labels']==1 and stats['betting_roi'] is None
    group=next(iter(stats['by_sport_market_model'].values()))
    assert group['misses']==1 and group['hits']==0 and group['labeled']==1
    assert group['calibration_bins'] and group['betting_roi'] is None
    assert not store.records() and not store.records('backtest')
    with store.connect() as db:
        stored=json.loads(db.execute('SELECT payload FROM shadow_forecasts').fetchone()[0])
        assert stored['model_code_sha256']==code_hash() and stored['target_scope']=='source_reported_ft'
        assert db.execute('SELECT outcome FROM shadow_outcomes').fetchone()[0]=='miss'
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE shadow_forecasts SET at='2000-01-01'")


def test_high_probability_ranking_needs_independent_support_not_price(quote):
    q=soccer_quote(quote);a=synthetic_artifact(q);e,d=forecast(q,a,NOW)
    e=replace(e,probability=.8,lower=.7,upper=.9)
    d=d|{'high_probability_evidence':True,'calibration_bin_n':100}
    analysis=Analysis(quotes=[q],estimates={q.id:e},advanced_details={q.id:d})
    assert len(high_probability_research(analysis,NOW))==1
    d['high_probability_evidence']=False
    assert not high_probability_research(analysis,NOW)
    d['high_probability_evidence']=True;d['calibration_bin_n']=3
    assert not high_probability_research(analysis,NOW)
    d['calibration_bin_n']=100;analysis.estimates[q.id]=replace(e,lower=0,upper=1)
    assert not high_probability_research(analysis,NOW)
