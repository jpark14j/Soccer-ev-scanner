"""Synthetic fixtures verify research behavior, never genuine current prices."""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
import pytest
from conftest import NOW
from intelligence.domain import utcnow
from intelligence.pipeline import Analysis,evaluate_quotes,restore_market_snapshots
from intelligence.research_top import select_top,value_status
from intelligence.quant_decision import decide
from intelligence.odds_diagnostics import inspect_odds
from intelligence.cached_research import synchronize,record_and_label,recheck
from test_readiness_ranking import research_analysis,enable,supported_quote
from test_parlay_intelligence import opposed
from tests_helpers import event_payload


def test_top_prefers_supported_uncertainty_over_inflated_probability(quote):
    a=opposed(research_analysis(quote,[(.90,.60,.98,1.4,80),(.65,.60,.70,1.3,180),(.70,.60,.80,2.,100)]))
    report=select_top(a,now=NOW)
    assert report['pick'].quote.event_id=='research-1'
    assert report['pick'].estimate.probability==.65 and 'Negative' in value_status(report['pick'])
    assert report['parlay'] and report['parlay'].research.joint_probability is None
    assert report['parlay'].research.parlay_ev is None and not report['parlay'].research.executable
    assert decide(a,now=NOW)['best'] is None
    favored={leg.quote.id for values in report['shared_rankings']['rankings'].values() for _,leg in values}
    assert all(q.id not in favored for q in a.quotes[3:])


@pytest.mark.parametrize('failure',['stale','missing','inputs','calibration','bucket','wide','suspended'])
def test_top_cannot_bypass_source_price_or_research_display_requirements(quote,failure):
    a=research_analysis(quote,[(.7,.6,.8,1.8,100)])
    q=a.quotes[0];d=a.advanced_details[q.id]
    if failure=='stale':a.quotes=[replace(q,source_updated_at=(NOW-timedelta(minutes=6)).isoformat())]
    if failure=='missing':a.estimates={};a.advanced_estimates={}
    if failure=='inputs':d['inputs_complete']=False
    if failure=='calibration':d['calibrated']=False
    if failure=='bucket':d['calibration_bin_n']=49
    if failure=='wide':a.estimates[q.id]=replace(a.estimates[q.id],lower=0.,upper=1.)
    if failure=='suspended':a.quotes=[replace(q,suspended=True)]
    report=select_top(a,now=NOW)
    assert report['pick'] is None and report['parlay'] is None


@pytest.mark.parametrize('p,lo,hi,odds,label',[(.7,.6,.8,2.,'Positive'),(.7,.6,.8,1.2,'Negative'),(.6,.4,.75,2.,'Inconclusive')])
def test_value_labels_use_supplied_uncertainty_without_approving_EV(quote,p,lo,hi,odds,label):
    leg=select_top(research_analysis(quote,[(p,lo,hi,odds,100)]),now=NOW)['pick']
    assert label in value_status(leg) and leg.estimated_ev is None


def test_approved_single_stays_in_the_separate_approved_decision(quote,estimate):
    a=Analysis(quotes=[quote],estimates={quote.id:estimate})
    assert select_top(a,now=NOW)['pick'] is None
    assert decide(a,now=NOW)['best'] is not None


def test_legacy_snapshot_is_recovered_without_http_or_freshness_reset(store,quote,monkeypatch):
    r=event_payload(quote);r['data']=[r['data']]
    store.cache('last-success-NBA',r,NOW)
    monkeypatch.setattr('intelligence.pipeline.utcnow',lambda:NOW)
    a=restore_market_snapshots(Analysis(),store,['NBA'])
    assert a.quotes==[quote] and a.quotes[0].received_at==quote.received_at
    assert inspect_odds(a,store,now=NOW)['code']=='current_prices_available'
    later=NOW+timedelta(minutes=6)
    assert inspect_odds(a,store,now=later)['code']=='expired_prices'
    with store.connect() as db:assert db.execute('SELECT count(*) FROM budget').fetchone()[0]==0


def test_same_session_applies_new_saved_odds_and_withdrawal_without_a_scan(store,quote,monkeypatch):
    now=utcnow();q=replace(quote,source_updated_at=now.isoformat(),received_at=now.isoformat(),commence_time=(now+timedelta(days=1)).isoformat())
    snapshot={'analysis':Analysis(),'stored_at':'original loaded time'}
    synchronize(snapshot,store)
    r=event_payload(q);r['data']=[r['data']];store.cache('last-success-NBA-h2h',r,now)
    with patch('intelligence.providers.OddsAPI._get',side_effect=AssertionError('No odds requests')):
        updated=synchronize(snapshot,store)
    assert updated.quotes==[q] and snapshot['stored_at']=='original loaded time'
    later=now+timedelta(seconds=1)
    monkeypatch.setattr('intelligence.odds_snapshots.utcnow',lambda:later)
    store.cache('last-success-NBA-h2h',{'data':[],'received_at':later.isoformat()},later)
    assert not synchronize(snapshot,store).quotes


def test_newer_complete_empty_scope_does_not_resurrect_an_older_price(store,quote):
    from intelligence.odds_snapshots import restore
    r=event_payload(quote);r['data']=[r['data']]
    store.cache('last-success-NBA',r,NOW)
    later=NOW+timedelta(seconds=10)
    store.cache('last-success-NBA-h2h',{'data':[],'received_at':later.isoformat()},later)
    assert not restore(Analysis(quotes=[quote]),store,['NBA'],later).quotes
    audit=inspect_odds(Analysis(),store,now=later)
    assert audit['stored_observation_rows']==1 and audit['restorable_stored_prices']['current_eligible']==0


def test_zero_price_audit_distinguishes_filters_missing_and_ineligible(store,quote):
    assert inspect_odds(Analysis(),store,now=NOW)['code']=='no_saved_prices'
    a=Analysis(quotes=[quote])
    assert inspect_odds(a,store,books=set(),now=NOW)['code']=='view_filters'
    a=Analysis(quotes=[replace(quote,jurisdiction='US')])
    assert inspect_odds(a,store,now=NOW)['code']=='outside_window_or_ineligible'
    raw=event_payload(quote);raw['data']=[raw['data']];store.cache('last-success-NBA-h2h',raw,NOW)
    assert inspect_odds(Analysis(),store,now=NOW)['code']=='newer_saved_prices'


@pytest.mark.parametrize('league',['Premier League','Bundesliga','Ligue 1'])
def test_actual_frozen_forecast_can_be_replayed_model_only_without_a_price(store,quote,monkeypatch,league):
    enable(monkeypatch);now=utcnow();q,_=supported_quote(store,quote,league,now)
    a=evaluate_quotes(Analysis(quotes=[q]),store,allow_results_fetch=False)
    # Add the favored side, with an actual synthetic price object, using the same
    # real frozen function; original software fixtures do not assert live coverage.
    from intelligence.current_soccer import forecast
    artifact=a.focused_model if league=='Premier League' else a.expanded_models[league]
    if a.estimates[q.id].probability<=.5:
        q=replace(q,selection='No' if q.market=='btts' else 'Under' if q.selection=='Over' else 'Over')
        a=evaluate_quotes(Analysis(quotes=[q]),store,allow_results_fetch=False)
    record_and_label(a,store)
    later=now+timedelta(minutes=6)
    result=select_top(a,store,now=later)
    assert result['pick'] is None and result['model_only'] is not None
    assert result['model_only'].estimate==a.estimates[q.id] and result['parlay'] is None
    assert decide(a,now=later)['best'] is None
    with patch('intelligence.pipeline.utcnow',return_value=later),patch('intelligence.cached_research.utcnow',return_value=later):
        cleared=recheck(a,store)
    assert not cleared.estimates
    assert select_top(cleared,store,now=later)['model_only'] is not None
    assert select_top(a,store,now=now+timedelta(hours=6,seconds=1))['model_only'] is None


def test_top_cards_are_prominent_unapproved_and_navigation_never_scans(tmp_path,quote,monkeypatch):
    from streamlit.testing.v1 import AppTest
    from ui_navigation import navigate
    now=utcnow();a=opposed(research_analysis(quote,[(.7,.6,.8,1.8,100)]*3,now))
    monkeypatch.setenv('INTELLIGENCE_DB',str(tmp_path/'preview.sqlite3'));monkeypatch.setenv('ODDS_API_KEY','synthetic-preview-only')
    monkeypatch.setenv('PAID_ANALYST_APPROVED','0');monkeypatch.setenv('PREDICTION_LEDGER_DIR',str(tmp_path/'empty-ledger'))
    with patch('intelligence.pipeline.run_analysis',return_value=a) as scans,patch('openai.OpenAI',side_effect=AssertionError('No paid calls')):
        app=AppTest.from_file(Path('app.py').resolve(),default_timeout=40).run()
        navigate(app,'AI Dashboard')
        labels=[s.value for s in app.subheader]
        assert labels.index("AI's Top Research Pick — Experimental")<labels.index("Today's Best-Supported Bet")
        assert any(s.value=="AI's Top Research Parlay" for s in app.subheader)
        assert any('NO QUALIFYING BET' in s.value for s in app.info)
        navigate(app,'Best Picks & Parlays');navigate(app,'AI Dashboard')
        assert scans.call_count==1 and not app.exception and len(app.sidebar.radio[0].options)==5


def test_model_only_card_never_displays_its_old_odds_or_price_comparison(tmp_path,quote,estimate,monkeypatch):
    from streamlit.testing.v1 import AppTest
    from intelligence.parlay_research import ResearchLeg
    from intelligence.research_ranking import RANKINGS
    q=replace(quote,odds=9.87,sport='Soccer',league='Premier League',market='btts',selection='Yes')
    e=replace(estimate,validated=False,sport=q.sport,league=q.league,market=q.market)
    model=ResearchLeg(q,1/q.odds,e,'research',{'prediction_at':NOW.isoformat(),'source_checked_at':NOW.isoformat()})
    result={'pick':None,'parlay':None,'model_only':model,'method':'evidence first','parlay_method':'marginal evidence',
        'input_blockers':{},'exclusions':{'stale':1},'model_only_exclusions':{},'parlay_exclusions':{},
        'shared_rankings':{'rankings':{key:[] for key in RANKINGS}}}
    monkeypatch.setenv('PAID_ANALYST_APPROVED','0')
    script="""from intelligence.top_research_ui import render_summary
from intelligence.pipeline import Analysis
from intelligence.storage import Store
render_summary(Analysis(),Store(DB_PATH),set())
""".replace('DB_PATH',repr(str(tmp_path/'ui.sqlite3')))
    with patch('intelligence.top_research_ui.select_top',return_value=result),patch('intelligence.top_research_ui.inspect_odds',return_value={'code':'expired_prices','message':'Expired','next_action':'Inspect saved data'}):
        app=AppTest.from_string(script).run()
    assert not app.exception
    text=' '.join(str(node.value) for nodes in (app.markdown,app.caption,app.text,app.info) for node in nodes)
    assert 'Model-only research forecast' in text and '9.87' not in text and 'Sportsbook break-even' not in text


def test_changed_source_proof_blocks_priced_and_retained_top_research(store,quote,monkeypatch):
    from intelligence.current_results import cached_status
    enable(monkeypatch);now=utcnow();q,_=supported_quote(store,quote,'Premier League',now)
    a=evaluate_quotes(Analysis(quotes=[q]),store,allow_results_fetch=False)
    if a.estimates[q.id].probability<=.5:
        q=replace(q,selection='No')
        a=evaluate_quotes(Analysis(quotes=[q]),store,allow_results_fetch=False)
    state=cached_status(store,q.league,now)
    with patch('intelligence.current_results.cached_status',return_value=state|{'sha256':'new-source-content'}),patch('intelligence.providers.OddsAPI._get',side_effect=AssertionError('No odds requests')):
        current=select_top(a,store,now=now+timedelta(seconds=1))
        expired=select_top(a,store,now=now+timedelta(minutes=6))
        audit=inspect_odds(a,store,now=now+timedelta(seconds=1))
    assert current['pick'] is current['parlay'] is current['model_only'] is None
    assert expired['model_only'] is None and audit['model_eligible_individual_observations']==0
    assert any('inputs differ' in key for key in audit['model_exclusions'])


def test_unavailable_storage_is_diagnosed_and_does_not_invent_a_record(quote):
    import sqlite3
    class BrokenStore:
        def connect(self):raise sqlite3.OperationalError('private details must stay private')
    a=Analysis()
    audit=inspect_odds(a,BrokenStore(),now=NOW)
    report=select_top(a,BrokenStore(),now=NOW)
    assert audit['code']=='storage_unavailable' and report['model_only'] is None
    assert 'private details' not in str((audit,report))
