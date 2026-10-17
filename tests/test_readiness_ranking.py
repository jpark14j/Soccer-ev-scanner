"""Synthetic contracts only. No test payload is a real current result or price."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
import json
import pytest
from conftest import NOW
from intelligence.domain import utcnow, Estimate, parse_time
from intelligence.pipeline import Analysis, evaluate_quotes, restore_market_snapshots
from intelligence.current_results import current, cache_key, ResultsConfig
from intelligence.current_soccer import prepare_epl, prepare_expanded, forecast
from intelligence.diagnostics import competition_diagnostics, quote_inventory, results_revision, readiness_export
from intelligence.research_state import model_health
from intelligence.research_ranking import rank_research, RANKINGS, comparison, evidence_problem
from intelligence.parlay_research import leg_evidence, build_candidate
from intelligence.cached_research import synchronize, recheck, record_and_label
from test_current_results import CONFIG, Session, Response, payload


def enable(monkeypatch):
    monkeypatch.setenv('FOOTBALL_DATA_ENABLED','1')
    monkeypatch.setenv('FOOTBALL_DATA_TOKEN',CONFIG.token)
    monkeypatch.setenv('FOOTBALL_DATA_USE_REVIEWED','1')


def cached_source(store, league, now=None):
    now = now or utcnow()
    events, meta = current(store,league,now,CONFIG,Session(Response(payload(league,now))))
    assert meta['ok']
    return events, meta


def supported_quote(store, base, league, now):
    events, meta = cached_source(store,league,now)
    artifact = prepare_epl(store,now,allow_fetch=False) if league=='Premier League' else prepare_expanded(league,store,now,allow_fetch=False)
    assert not artifact.get('problem')
    for event in events:
        if event.status!='scheduled' or event.event_date<=now.date().isoformat():continue
        q=replace(base,sport='Soccer',league=league,home=event.home_name,away=event.away_name,
            event_id=league+'-synthetic',event=event.home_name+' vs '+event.away_name,
            commence_time=event.kickoff,market='totals' if league=='Ligue 1' else 'btts',
            point=2.5 if league=='Ligue 1' else None,selection='Over' if league=='Ligue 1' else 'Yes',
            source_updated_at=now.isoformat(),received_at=now.isoformat())
        if forecast(q,artifact,now)[0]:return q,meta
    raise AssertionError('Synthetic mature-team fixture expected')


@pytest.mark.parametrize('league',['Premier League','Bundesliga','Ligue 1'])
def test_diagnostics_report_available_source_without_inventing_inference(store,quote,monkeypatch,league):
    enable(monkeypatch);now=utcnow();events,meta=cached_source(store,league,now)
    q=replace(quote,sport='Soccer',league=league,market='h2h')
    a=Analysis(quotes=[q])
    row=next(r for r in competition_diagnostics(a,store,now) if r['competition']==league)
    assert row['current_source']=='football-data.org' and row['current_completed']==meta['coverage']['completed']
    assert row['latest_result']==meta['coverage']['latest_completed'] and row['past_unresolved']==0
    assert row['historical_training_source']=='OpenFootball publisher-CC0 pinned history'
    assert row['current_source_verification_fresh'] and row['used_current_snapshot'] is None
    assert row['current_forecast'].startswith('Not executed:') and row['current_estimates']==0
    assert row['model_status']=='Research model' and row['validation']=='Not approved'
    monkeypatch.setenv('FOOTBALL_DATA_ENABLED','0')
    old=next(r for r in competition_diagnostics(a,store,now) if r['competition']==league)
    assert old['current_source']!='football-data.org' and old['latest_result']=='2026-09-20'
    assert old['historical_training_source']==row['historical_training_source']


@pytest.mark.parametrize('league',['Premier League','Bundesliga','Ligue 1'])
def test_real_model_functions_execute_conditionally_but_remain_research_only(store,quote,monkeypatch,league):
    enable(monkeypatch);now=utcnow();q,meta=supported_quote(store,quote,league,now)
    with patch('intelligence.providers.OddsAPI.odds',side_effect=AssertionError('No odds requests')),patch('intelligence.current_results.requests.Session.get',side_effect=AssertionError('Cache only')):
        a=evaluate_quotes(Analysis(quotes=[q]),store,allow_results_fetch=False)
        record_and_label(a,store,now+timedelta(seconds=1))
    row=next(r for r in competition_diagnostics(a,store) if r['competition']==league)
    assert row['current_estimates']==row['snapshot_estimates']==row['inference_attempts']==1
    assert row['current_forecast'].startswith('Research inference executed')
    assert row['used_current_snapshot']['body_sha256']==meta['sha256']
    assert row['available_current_snapshot_sha256']==meta['sha256']
    assert not row['cached_snapshot_differs_from_used'] and not a.estimates[q.id].validated and not a.opportunities
    report=readiness_export(a,store)
    assert CONFIG.token not in json.dumps(report) and report['prices']['current_eligible']==1
    from intelligence.processing import shadow_statistics
    stats=shadow_statistics(store)
    assert stats['private_forecasts']==1 and stats['scored_forecast_labels']==0 and stats['betting_roi'] is None
    assert not store.records()


def test_source_revision_rechecks_session_with_no_http_and_keeps_original_scan_time(store,quote,monkeypatch):
    now=utcnow()
    from test_epl_predictions import soccer_quote
    q=soccer_quote(quote,now)
    snapshot={'analysis':Analysis(quotes=[q]),'stored_at':'original scan timestamp'}
    synchronize(snapshot,store)
    enable(monkeypatch);q,meta=supported_quote(store,quote,'Premier League',now)
    snapshot['analysis'].quotes=[q]
    with patch('intelligence.current_results.requests.Session.get',side_effect=AssertionError('No HTTP')):
        a=synchronize(snapshot,store)
        assert q.id in a.estimates
        first=a
        assert synchronize(snapshot,store) is first
    assert snapshot['stored_at']=='original scan timestamp'
    with store.connect() as db:assert db.execute('SELECT count(*) FROM budget').fetchone()[0]==0


def test_expired_source_revision_removes_estimates_without_refreshing_odds_or_results(store,quote,monkeypatch):
    enable(monkeypatch);now=utcnow();q,meta=supported_quote(store,quote,'Premier League',now)
    a=evaluate_quotes(Analysis(quotes=[q]),store,allow_results_fetch=False)
    snapshot={'analysis':a};synchronize(snapshot,store)
    later=now+timedelta(hours=6,seconds=1)
    # Keep a synthetic price current to isolate source expiry, not odds expiry.
    a.quotes=[replace(q,source_updated_at=later.isoformat(),received_at=later.isoformat())]
    with patch('intelligence.diagnostics.utcnow',return_value=later),patch('intelligence.pipeline.utcnow',return_value=later),patch('intelligence.cached_research.utcnow',return_value=later),patch('intelligence.current_results.requests.Session.get',side_effect=AssertionError('No HTTP')):
        fresh=synchronize(snapshot,store)
    assert not fresh.estimates and 'No fresh cached results' in fresh.research[0]['blockers'][0]
    row=next(r for r in competition_diagnostics(fresh,store,later) if r['competition']=='Premier League')
    assert not row['current_source_verification_fresh'] and row['current_forecast'].startswith('Blocked:')


def test_cached_refresh_reports_newer_available_snapshot_until_re_evaluated(store,quote,monkeypatch):
    # Isolate a newer receipt from fixture-date rollover. A late wall clock made
    # the synthetic source finish 23:50 kickoffs just after midnight otherwise.
    enable(monkeypatch);now=utcnow().replace(hour=8,minute=0,second=0,microsecond=0);q,meta=supported_quote(store,quote,'Bundesliga',now)
    with patch('intelligence.pipeline.utcnow',return_value=now):
        a=evaluate_quotes(Analysis(quotes=[q]),store,allow_results_fetch=False)
    later=now+timedelta(hours=6,seconds=1)
    # A genuine adapter call is exercised against a TEST transport after cache expiry.
    _,updated=cached_source(store,'Bundesliga',later)
    assert updated['sha256']!=meta['sha256']
    row=next(r for r in competition_diagnostics(a,store,later) if r['competition']=='Bundesliga')
    assert row['cached_snapshot_differs_from_used'] and row['used_current_snapshot']['body_sha256']==meta['sha256']
    assert row['available_current_snapshot_sha256']==updated['sha256']
    # Initial session also repairs a stale shared-analysis cache using saved data only.
    snapshot={'analysis':a}
    with patch('intelligence.current_results.requests.Session.get',side_effect=AssertionError('No HTTP')),\
         patch('intelligence.pipeline.utcnow',return_value=later),\
         patch('intelligence.diagnostics.utcnow',return_value=later),\
         patch('intelligence.cached_research.utcnow',return_value=later):
        fresh=synchronize(snapshot,store)
    assert fresh is not a


def research_analysis(quote, specs, now=NOW):
    quotes=[];estimates={};details={}
    for i,(probability,lo,hi,odds,bucket) in enumerate(specs):
        q=replace(quote,event_id=f'research-{i}',home=f'Home {i}',away=f'Away {i}',selection=f'Home {i}',odds=odds,
            source_updated_at=now.isoformat(),received_at=now.isoformat(),commence_time=(now+timedelta(days=1)).isoformat())
        e=Estimate(probability,lo,hi,'synthetic-research-1',(now-timedelta(days=2)).isoformat(),'test-evidence',False,(),'NBA','NBA','h2h')
        d={'quote_id':q.id,'calibrated':True,'calibration_bin_n':bucket,'calibration_n':300,'test_n':300,
            'prediction_at':now.isoformat(),'blockers':['Unvalidated research']}
        quotes.append(q);estimates[q.id]=e;details[q.id]=d
    return Analysis(quotes=quotes,estimates=estimates,advanced_estimates=estimates,advanced_details=details,research=list(details.values()))


def test_three_rankings_separate_win_probability_difference_and_reliability(quote):
    a=research_analysis(quote,[(.80,.65,.90,1.10,80),(.60,.45,.75,2.0,80),(.55,.50,.60,1.50,200)])
    report=rank_research(a,now=NOW)['rankings']
    assert report[RANKINGS[0]][0][1].quote.event_id=='research-2'
    assert report[RANKINGS[1]][0][1].quote.event_id=='research-0'
    assert report[RANKINGS[2]][0][1].quote.event_id=='research-1'
    assert all(leg.quote.event_id!='research-0' for _,leg in report[RANKINGS[2]])
    assert all(leg.estimated_ev is None for rows in report.values() for _,leg in rows)


@pytest.mark.parametrize('probability,odds',[(.369,2.18),(.323,2.30)])
def test_reported_below_break_even_examples_are_not_positive_difference_candidates(quote,probability,odds):
    a=research_analysis(quote,[(probability,probability-.10,probability+.10,odds,100),
        (1-probability,1-probability-.10,1-probability+.10,1.72,100)])
    report=rank_research(a,now=NOW)['rankings']
    assert report[RANKINGS[1]][0][1].estimate.probability==1-probability
    gap=comparison(leg_evidence(a.quotes[0],a,NOW))
    assert gap['difference']==pytest.approx(probability-1/odds) and gap['difference']<0
    assert all(leg.quote.id!=a.quotes[0].id for _,leg in report[RANKINGS[2]])
    assert not gap['validated_edge']


@pytest.mark.parametrize('failure',['wide','bin','calibration','test','uncalibrated','stale_price','source_expired'])
def test_insufficient_evidence_never_forces_research_shortlist(quote,failure):
    a=research_analysis(quote,[(.9,.85,.95,2.,100)])
    q=a.quotes[0];d=a.advanced_details[q.id]
    if failure=='wide':a.estimates[q.id]=replace(a.estimates[q.id],lower=0,upper=1)
    if failure=='bin':d['calibration_bin_n']=49
    if failure=='calibration':d['calibration_n']=99
    if failure=='test':d['test_n']=None
    if failure=='uncalibrated':d['calibrated']=False
    if failure=='stale_price':a.quotes=[replace(q,source_updated_at=(NOW-timedelta(minutes=6)).isoformat())]
    if failure=='source_expired':d.update(results_provider='football-data.org',source_checked_at=(NOW-timedelta(hours=6)).isoformat())
    report=rank_research(a,now=NOW)
    assert all(not rows for rows in report['rankings'].values())


def test_uncertain_positive_difference_is_not_ev_or_proven_advantage(quote):
    a=research_analysis(quote,[(.6,.4,.75,2.,100)])
    leg=rank_research(a,now=NOW)['rankings'][RANKINGS[2]][0][1]
    gap=comparison(leg)
    assert gap['difference']>0 and gap['difference_envelope'][0]<0
    assert not gap['envelope_entirely_above_break_even'] and leg.estimated_ev is None


def test_422_stale_observations_are_partitioned_not_mislabeled_as_games(quote):
    old=[replace(quote,event_id=f'old-{i}',commence_time=(NOW-timedelta(days=1)).isoformat(),source_updated_at=(NOW-timedelta(days=2)).isoformat(),received_at=(NOW-timedelta(days=2)).isoformat()) for i in range(400)]
    upcoming=[replace(quote,event_id=f'future-{i}',source_updated_at=(NOW-timedelta(minutes=10)).isoformat()) for i in range(22)]
    a=Analysis(quotes=old+upcoming,slate={'window_end':(NOW+timedelta(days=2)).isoformat()},quote_origins={q.id:{'origin':'restored private cache'} for q in old+upcoming})
    report=quote_inventory(a,NOW)
    assert report['status_counts']['stale']==422
    assert report['outside_window_or_started_inspection']==400 and report['stale_upcoming_in_window']==22
    assert report['origin_counts']['restored private cache']==422 and report['current_eligible']==0
    assert report['duplicate_observation_rows']==0 and report['games_with_stale_observations']==22
    assert not rank_research(a,now=NOW)['rankings'][RANKINGS[0]]


def test_duplicate_quotes_and_wrong_jurisdiction_do_not_become_actionable(quote):
    a=Analysis(quotes=[quote,quote,replace(quote,event_id='unverified',jurisdiction='US')])
    report=quote_inventory(a,NOW)
    assert report['current_eligible']==0 and report['duplicate_observation_rows']==1
    assert report['invalid_or_other_ineligible']==3


def test_restore_preserves_quote_origin_and_timestamps_without_reserving_odds(store,quote,monkeypatch):
    from tests_helpers import event_payload
    response=event_payload(quote);response['data']=[response['data']]
    store.cache('last-success-NBA-h2h',response,NOW)
    monkeypatch.setattr('intelligence.pipeline.utcnow',lambda:NOW)
    a=restore_market_snapshots(Analysis(),store,['NBA'])
    assert a.quotes[0].source_updated_at==quote.source_updated_at
    assert a.quote_origins[a.quotes[0].id]['origin']=='restored private cache'
    with store.connect() as db:assert db.execute('SELECT count(*) FROM budget').fetchone()[0]==0


def test_high_probability_legs_never_approve_joint_price_or_parlay_ev(quote):
    a=research_analysis(quote,[(.8,.7,.9,1.2,100),(.8,.7,.9,1.2,100)])
    legs=tuple(leg_evidence(q,a,NOW) for q in a.quotes)
    candidate,reason=build_candidate(legs,a,NOW)
    assert candidate and not candidate.executable and candidate.combined_odds is None
    assert candidate.parlay_ev is None and candidate.joint_probability is None
    assert candidate.leg_comparison['supported_calibration_legs']==2
    assert candidate.leg_comparison['minimum_individual_probability']==.8
    assert candidate.leg_comparison['joint_probability'] is None


def test_inference_remains_inspectable_when_prices_expire(store,quote,monkeypatch):
    enable(monkeypatch);now=utcnow();q,_=supported_quote(store,quote,'Ligue 1',now)
    a=evaluate_quotes(Analysis(quotes=[q]),store,allow_results_fetch=False)
    row=next(r for r in competition_diagnostics(a,store,now+timedelta(minutes=6)) if r['competition']=='Ligue 1')
    assert row['snapshot_estimates']==1 and row['current_estimates']==0
    assert row['current_forecast'].startswith('Inference was executed')
    assert row['current_eligible_prices']==0


def test_unsupported_market_cannot_be_reported_as_execution_of_a_frozen_model(store,quote,monkeypatch):
    enable(monkeypatch);now=utcnow();q,_=supported_quote(store,quote,'Bundesliga',now)
    q=replace(q,market='h2h',selection=q.home)
    a=evaluate_quotes(Analysis(quotes=[q]),store,allow_results_fetch=False)
    row=next(r for r in competition_diagnostics(a,store) if r['competition']=='Bundesliga')
    assert row['current_eligible_prices']==1 and row['current_supported_prices']==0
    assert row['inference_attempts']==0 and row['current_forecast'].startswith('Not executed:')
    assert row['unsupported_current_markets']=={'h2h':1}


def test_latest_completed_source_result_is_separate_from_prior_date_model_features(store,quote,monkeypatch):
    enable(monkeypatch);now=NOW.replace(hour=23,minute=50);p=payload('Bundesliga',now)
    today=next(m for m in p['matches'] if m['utcDate'][:10]==now.date().isoformat())
    today.update(utcDate=now.replace(hour=0,minute=0,second=0,microsecond=0).isoformat(),status='FINISHED')
    today['score']['fullTime']={'home':2,'away':1};p['resultSet']['played']+=1
    assert current(store,'Bundesliga',now,CONFIG,Session(Response(p)))[1]['ok']
    prepared=prepare_expanded('Bundesliga',store,now,allow_fetch=False)
    a=Analysis(expanded_models={'Bundesliga':prepared})
    row=next(r for r in competition_diagnostics(a,store,now) if r['competition']=='Bundesliga')
    assert row['latest_result']==now.date().isoformat()
    assert row['prepared_current_snapshot']['latest_feature_result']<row['latest_result']
    assert row['used_current_snapshot'] is None and row['snapshot_estimates']==0


def test_preview_results_only_refresh_synchronizes_all_three_model_views(tmp_path,quote,monkeypatch):
    from streamlit.testing.v1 import AppTest
    from intelligence.storage import Store
    from ui_navigation import navigate
    enable(monkeypatch);now=utcnow();store=Store(tmp_path/'ui.sqlite3')
    monkeypatch.setenv('INTELLIGENCE_DB',store.path);monkeypatch.setenv('ODDS_API_KEY','synthetic-ui-key-only')
    monkeypatch.setenv('PAID_ANALYST_APPROVED','0')
    monkeypatch.setenv('PREDICTION_LEDGER_DIR',str(tmp_path/'empty-ledger'))
    qs=[supported_quote(store,quote,league,now)[0] for league in ('Premier League','Bundesliga','Ligue 1')]
    with patch('intelligence.pipeline.run_analysis',return_value=Analysis(quotes=qs,checked_at=now.isoformat())) as scans,patch('intelligence.current_results.requests.Session.get',side_effect=AssertionError('Cached only')):
        app=AppTest.from_file(Path('app.py').resolve(),default_timeout=40).run()
        navigate(app,'Settings')
        next(b for b in app.button if b.label=='Refresh soccer results only').click().run()
        assert not app.exception
        navigate(app,'AI Dashboard')
        assert next(m for m in app.metric if m.label=='Games with model research').value=='3'
        captions=' '.join(c.value for c in app.caption)
        assert 'Their current source results also end September 20' not in captions
        for league in ('Premier League','Bundesliga','Ligue 1'):
            assert any(league+' · current source: football-data.org' in c.value and 'Research inference executed' in c.value for c in app.caption)
        navigate(app,'Model & Data Diagnostics')
        next(b for b in app.button if b.key=='readiness_export').click().run()
        assert not app.exception and len(app.get('download_button'))==1 and scans.call_count==1
        assert CONFIG.token not in ' '.join(j.value for j in app.json)
    with store.connect() as db:assert db.execute('SELECT count(*) FROM budget').fetchone()[0]==0


def test_ranking_selector_switches_views_without_scans(tmp_path,quote,monkeypatch):
    from streamlit.testing.v1 import AppTest
    from ui_navigation import navigate
    now=utcnow();a=research_analysis(quote,[(.8,.65,.9,1.1,100),(.6,.45,.75,2.,100)],now)
    monkeypatch.setenv('INTELLIGENCE_DB',str(tmp_path/'ranking.sqlite3'));monkeypatch.setenv('ODDS_API_KEY','synthetic-ui-key-only')
    monkeypatch.setenv('PREDICTION_LEDGER_DIR',str(tmp_path/'empty-ledger'))
    with patch('intelligence.pipeline.run_analysis',return_value=a) as scans:
        app=AppTest.from_file(Path('app.py').resolve(),default_timeout=40).run()
        for name in RANKINGS:
            next(s for s in app.selectbox if s.key=='dashboard_ranking').set_value(name).run()
            assert not app.exception
        navigate(app,'Best Picks & Parlays')
        assert list(next(s for s in app.selectbox if s.key=='picks_ranking').options)==list(RANKINGS)
        assert len(app.sidebar.radio[0].options)==4 and scans.call_count==1


def test_cache_only_recheck_cannot_download_even_an_opted_in_legacy_personal_feed(store,quote,monkeypatch):
    from test_epl_predictions import soccer_quote
    monkeypatch.setenv('FOOTBALL_DATA_PERSONAL_RESEARCH','1')
    now=utcnow();q=replace(soccer_quote(quote,now),market='h2h',selection='Arsenal')
    with patch('intelligence.history.requests.Session.get',side_effect=AssertionError('No network')) as calls:
        a=recheck(Analysis(quotes=[q]),store)
    assert not a.estimates and calls.call_count==0
