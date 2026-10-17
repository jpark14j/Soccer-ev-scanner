"""Synthetic inference tests are separate from the genuine committed evaluations."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from unittest.mock import patch
from pathlib import Path
import json
import pytest
from intelligence.domain import utcnow,Estimate
from intelligence.competitions import COMPETITIONS
from intelligence.data_adapters import team_identity
from intelligence.expanded_models import load,policy,code_hash
from intelligence.expanded_forecasts import prepare,forecast,supported
from intelligence.venue_goals import fit,predict,extend
from intelligence.pipeline import Analysis,evaluate_quotes
from intelligence.processing import record_shadow_forecasts,shadow_statistics
from intelligence.multi_readiness import process_expanded_paper,readiness
from intelligence.research_state import evidence_state,BLOCKED,EXPERIMENTAL


def expanded_quote(quote,league,now=None):
    now=now or utcnow()
    home,away=('Bayern Munich','Borussia Dortmund') if league=='Bundesliga' else ('PSG','Monaco')
    return replace(quote,sport='Soccer',league=league,home=home,away=away,event=home+' vs '+away,
        market='btts' if league=='Bundesliga' else 'totals',selection='Yes' if league=='Bundesliga' else 'Over',
        point=None if league=='Bundesliga' else 2.5,commence_time=(now+timedelta(days=1)).isoformat(),
        source_updated_at=(now-timedelta(seconds=30)).isoformat(),received_at=(now-timedelta(seconds=10)).isoformat())


def usable_artifact(q,now):
    a=deepcopy(load(q.league));assert a
    a['generated_at']=(now-timedelta(minutes=1)).isoformat()
    a['state']['as_of']=(now-timedelta(days=1)).date().isoformat();a['state']['latest']=(now-timedelta(days=2)).date().isoformat()
    h,_=team_identity(COMPETITIONS[q.league],q.home);aw,_=team_identity(COMPETITIONS[q.league],q.away)
    for identifier in (h,aw):a['state']['teams'][identifier]['last']=(now-timedelta(days=2)).date().isoformat()
    a['fixtures']=[{'home_id':h,'away_id':aw,'event_date':q.commence_time[:10],'status':'scheduled','season':'2026-27'}]
    a['source_checked_at']=now.isoformat()
    return a


@pytest.mark.parametrize('league,cal,test',[('Bundesliga',306,275),('Ligue 1',333,306)])
def test_genuine_evaluation_artifacts_periods_denominators_and_no_approval(league,cal,test):
    a=load(league);assert a and a['code_sha256']==code_hash()
    assert a['calibration_n']==cal and a['periods']['final_test']['eligible']==test
    assert a['policy']['train_end']<a['policy']['calibration_start']<a['policy']['validation_start']<a['policy']['test_start']
    assert a['periods']['validation']['end']<a['periods']['final_test']['start']
    metrics=a['periods']['final_test']
    assert metrics['constant_baseline']['n']==metrics['model']['n']==metrics['league_poisson_baseline']['n']==test
    assert metrics['model_minus_constant']['binary_brier']['interval'][0]<0<metrics['model_minus_constant']['binary_brier']['interval'][1]
    assert a['status']=='research_model' and not a['forecast_validated'] and not a['edge_approved'] and a['betting_roi'] is None


@pytest.mark.parametrize('league',['Bundesliga','Ligue 1'])
def test_research_probabilities_complements_and_dependency_metadata(quote,league):
    now=utcnow();q=expanded_quote(quote,league,now);a=usable_artifact(q,now)
    e,d=forecast(q,a,now);other,_=forecast(replace(q,selection='No' if q.market=='btts' else 'Under'),a,now)
    assert e and other and e.valid() and e.probability+other.probability==pytest.approx(1)
    assert e.lower==pytest.approx(1-other.upper) and not e.validated
    assert not d['dependency_groups']['joint_validated'] and len(d['dependency_groups']['teams'])==2
    assert d['competition_id']==COMPETITIONS[league].id and d['result_based_rest_days']
    analysis=Analysis(quotes=[q],estimates={q.id:e},advanced_estimates={q.id:e},advanced_details={q.id:d})
    assert evidence_state(q,analysis,now)[0]==EXPERIMENTAL
    from intelligence.parlay_research import leg_evidence
    assert leg_evidence(q,analysis,now).estimated_ev is None


@pytest.mark.parametrize('failure',['stale','missing_score','unknown_team','too_few','wrong_market','stale_price','stale_team'])
def test_current_input_and_market_failures_cannot_create_probabilities(quote,failure):
    now=utcnow();q=expanded_quote(quote,'Bundesliga',now);a=usable_artifact(q,now)
    if failure=='stale':a['state']['latest']='2026-01-01'
    if failure=='missing_score':a['fixtures'].append(a['fixtures'][0]|{'event_date':(now-timedelta(days=4)).date().isoformat(),'status':'unresolved'})
    if failure=='unknown_team':q=replace(q,home='Unverified Club')
    if failure=='too_few':a['state']['teams'][team_identity(COMPETITIONS[q.league],q.home)[0]]['n']=2
    if failure=='wrong_market':q=replace(q,market='h2h')
    if failure=='stale_price':q=replace(q,source_updated_at=(now-timedelta(minutes=10)).isoformat())
    if failure=='stale_team':a['state']['teams'][team_identity(COMPETITIONS[q.league],q.home)[0]]['last']='2025-01-01'
    e,d=forecast(q,a,now)
    assert e is None and d['blockers']


def test_cross_competition_parameters_are_never_used_for_another_league(quote):
    now=utcnow();q=expanded_quote(quote,'Ligue 1',now)
    e,d=forecast(q,load('Bundesliga'),now)
    assert e is None and 'scope' in d['blockers'][0]


def test_team_features_never_use_same_day_or_future_results_and_incremental_matches_refit():
    p=policy();day='2026-10-15'
    rows=[{'date':'2026-10-13','home':'h','away':'a','hg':2,'ag':1}]
    future=rows[0]|{'date':day,'hg':25}
    assert fit(rows+[future],day,p)==fit(rows,day,p)
    a=extend(fit(rows,day,p),[future],'2026-10-16',p);b=fit(rows+[future],'2026-10-16',p)
    assert a['hg']==pytest.approx(b['hg']) and a['teams']['h']['home']['gf']==pytest.approx(b['teams']['h']['home']['gf'])
    assert a['teams']['h']['w2']==pytest.approx(b['teams']['h']['w2'])
    with pytest.raises(ValueError):extend(a,[future],'2026-10-14',p)
    assert predict(a,'h','a','2026-10-14',p)[0] is None


def test_pipeline_uses_expanded_model_before_unsupported_legacy_history(store,quote):
    now=utcnow();q=expanded_quote(quote,'Bundesliga',now);a=usable_artifact(q,now)
    with patch('intelligence.expanded_forecasts.prepare',return_value=a),patch('intelligence.pipeline.load_soccer',side_effect=AssertionError('Wrong fallback')):
        result=evaluate_quotes(Analysis(quotes=[q]),store)
    assert q.id in result.estimates and not result.opportunities
    assert result.estimates[q.id].model_version.startswith('venue-goals-1-')


def test_real_stale_inputs_and_epl_artifact_stay_unchanged(store,quote):
    from intelligence.epl_forecasts import load_artifact
    frozen=load_artifact();now=utcnow()
    for league in ('Bundesliga','Ligue 1'):
        q=expanded_quote(quote,league,now);a=prepare(league,store,now,allow_refresh=False)
        e,d=forecast(q,a,now)
        assert e is None and any('freshness' in b for b in d['blockers'])
    assert load_artifact()==frozen


def test_source_corrections_and_cross_source_conflicts_fail_closed(store,quote):
    now=utcnow();q=expanded_quote(quote,'Bundesliga',now);a=usable_artifact(q,now)
    fake={'ok':True,'checked_at':now.isoformat(),'sha256':'synthetic-revision'}
    with patch('intelligence.expanded_forecasts.load',return_value=a),patch('intelligence.public_results.current',return_value=([],fake)):
        result=prepare(q.league,store,now,True)
    assert 'revised or withdrew' in result['problem']


def test_paper_forecasts_are_immutable_and_labeled_without_operator_returns(store,quote):
    now=utcnow();q=expanded_quote(quote,'Bundesliga',now);a=usable_artifact(q,now);e,d=forecast(q,a,now)
    analysis=Analysis(quotes=[q],estimates={q.id:e},advanced_estimates={q.id:e},advanced_details={q.id:d},expanded_models={q.league:a})
    assert record_shadow_forecasts(analysis,store,now)==1 and record_shadow_forecasts(analysis,store,now)==0
    with store.connect() as db:
        payload=json.loads(db.execute('SELECT payload FROM shadow_forecasts').fetchone()[0])
        assert payload['target_scope']=='expanded_source_ft' and payload['model_code_sha256']==code_hash()
    h,_=team_identity(COMPETITIONS[q.league],q.home);aw,_=team_identity(COMPETITIONS[q.league],q.away)
    analysis.expanded_models[q.league]['current_rows']=[{'home':h,'away':aw,'date':q.commence_time[:10],'hg':0,'ag':0}]
    assert process_expanded_paper(store,analysis,now)==0
    assert process_expanded_paper(store,analysis,now+timedelta(days=2))==1
    assert shadow_statistics(store)['scored_forecast_labels']==1 and not store.records()
    assert shadow_statistics(store)['betting_roi'] is None


def test_nba_mlb_current_readiness_is_not_inferred_from_archives(store,quote,monkeypatch):
    import pandas as pd
    history=pd.DataFrame({'date':pd.date_range('2015-01-01',periods=300),'HomeTeam':['Home']*300,
        'AwayTeam':['Away']*300,'FTHG':[110]*300,'FTAG':[100]*300})
    now=utcnow();q=replace(quote,source_updated_at=now.isoformat(),received_at=now.isoformat(),commence_time=(now+timedelta(days=1)).isoformat())
    monkeypatch.setattr('intelligence.pipeline.load_local',lambda *a:history)
    result=evaluate_quotes(Analysis(quotes=[q]),store)
    assert not result.estimates and any('90 days old' in b for b in result.research[0]['blockers'])
    rows=readiness(result,store,now)
    assert all('Blocked:' in r['current_forecast'] for r in rows if r['sport'] in ('NBA','MLB'))


def test_four_page_diagnostics_include_expanded_models_without_new_scan(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    from ui_navigation import navigate
    monkeypatch.setenv('INTELLIGENCE_DB',str(tmp_path/'ui.sqlite3'));monkeypatch.setenv('ODDS_API_KEY','synthetic-ui-only')
    with patch('intelligence.pipeline.run_analysis',return_value=Analysis()) as scan:
        app=AppTest.from_file(Path('app.py').resolve(),default_timeout=40).run()
        navigate(app,'Performance Tracker')
        assert any('Bundesliga' in e.label and 'research model' in e.label for e in app.expander)
        assert any('Ligue 1' in e.label and 'research model' in e.label for e in app.expander)
        navigate(app,'Best Picks & Parlays')
        select=next(s for s in app.selectbox if s.key=='picks_competition')
        assert 'Bundesliga' in select.options and 'World Cup' in select.options
        select.set_value('Bundesliga').run()
        navigate(app,'Model & Data Diagnostics')
        assert not app.exception and scan.call_count==1
