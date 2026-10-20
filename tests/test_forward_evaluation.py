"""Software-only provider fixtures and prospective record math; no real outcomes."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json,sqlite3
import pytest
from intelligence.domain import utcnow,parse_time,digest
from intelligence.pipeline import Analysis,evaluate_quotes
from intelligence.forward_testing import lock_protocol,capture,reconcile,records,hypothetical_return,source_fixture
from intelligence.model_reliability import scorecards,sample_plan,scored_report
from intelligence.results_journal import latest,accept
from intelligence.current_results import season_at
from intelligence.event_data import EventObservation,ingest
from test_readiness_ranking import enable,supported_quote


def actual_function_fixture(store,quote,monkeypatch):
    enable(monkeypatch);now=utcnow();lock_protocol(store,now-timedelta(seconds=10))
    q,_=supported_quote(store,quote,'Premier League',now)
    a=evaluate_quotes(Analysis(quotes=[q]),store,allow_results_fetch=False)
    assert a.estimates
    return a,q,now


def save_final(store,q,hg,ag,later):
    snapshot=deepcopy(latest(store,q.league,season_at(later)))
    e,_=source_fixture(store,q,later)
    for r in snapshot['events']:
        r['observed_at']=later.isoformat()
        if r['source_event_id']==e['source_event_id']:
            r.update(status='completed',home_score=hg,away_score=ag,
                source_updated_at=(parse_time(q.commence_time)+timedelta(hours=2)).isoformat())
    snapshot.update(checked_at=later.isoformat(),sha256=digest(snapshot['events']))
    accept(store,q.league,season_at(later),snapshot)
    ingest(store,[EventObservation(**e) for e in snapshot['events']],snapshot,later)


def test_dedup_first_pregame_contract_across_books_sides_and_refreshes(store,quote,monkeypatch):
    a,q,now=actual_function_fixture(store,quote,monkeypatch)
    e=a.estimates[q.id];d=a.advanced_details[q.id]
    other=replace(q,bookmaker='betrivers_ca_on',bookmaker_name='BetRivers Ontario',odds=2.1)
    opposite=replace(q,selection='No')
    a.quotes.extend([other,opposite])
    a.estimates.update({other.id:e,opposite.id:replace(e,probability=1-e.probability,lower=1-e.upper,upper=1-e.lower)})
    a.advanced_estimates.update({other.id:a.estimates[other.id],opposite.id:a.estimates[opposite.id]})
    a.advanced_details.update({other.id:d,opposite.id:d})
    result=capture(a,store)
    assert result['recorded']==1 and capture(a,store)['recorded']==0
    old=records(store)[0]
    assert old['payload']['ranking_version']=='risk-research-1' and old['payload']['protocol_locked_before_forecast']
    assert old['payload']['observed_price_at_recording']['decimal']==2.1
    changed=replace(e,probability=e.probability-.01)
    a.quotes=[q];a.advanced_estimates={};a.estimates={q.id:changed}
    assert capture(a,store)['recorded']==0 and records(store)[0]['payload']==old['payload']
    with store.connect() as db:
        with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM forward_forecasts')
        with pytest.raises(sqlite3.IntegrityError):db.execute("UPDATE forward_protocols SET at='2020-01-01'")


def test_forward_records_label_exact_final_and_keep_both_hits_and_misses(store,quote,monkeypatch):
    a,q,now=actual_function_fixture(store,quote,monkeypatch);assert capture(a,store)['recorded']==1
    later=parse_time(q.commence_time)+timedelta(days=1)
    save_final(store,q,0,0,later)
    assert reconcile(store,later)['labeled']==1 and reconcile(store,later)['labeled']==0
    row=records(store)[0]
    assert row['label']['outcome']=='loss' and row['label']['hypothetical_score_contract_return']==-1
    card=scorecards(store,later)['groups'][0]
    assert card['scores']['n']==1 and card['scores']['metrics']['binary_brier']['value']==pytest.approx(row['payload']['estimate']['probability']**2)
    assert card['scores']['metrics']['binary_brier']['interval'] is None
    assert card['completed_cohort_review']['n']==0  # Running cohort cannot trigger review.
    assert card['state']=='Under forward evaluation' and card['review_blockers'] and not card['automatic_approval']


def test_hindsight_cannot_create_record_or_count_legacy_records_as_confirmation(store,quote,monkeypatch):
    a,q,now=actual_function_fixture(store,quote,monkeypatch)
    assert capture(a,store,parse_time(q.commence_time)+timedelta(hours=3))['recorded']==0
    assert scorecards(store)['recorded']==0
    from intelligence.processing import record_shadow_forecasts
    record_shadow_forecasts(Analysis(quotes=[quote],estimates={}),store)
    assert scorecards(store)['recorded']==0


def test_expired_price_can_record_only_actual_retained_forecast_without_returns(store,quote,monkeypatch):
    a,q,now=actual_function_fixture(store,quote,monkeypatch)
    assert capture(a,store,now+timedelta(minutes=6))['recorded']==1
    assert records(store)[0]['payload']['observed_price_at_recording'] is None


def test_source_conflict_quarantines_without_rewriting_forecast_or_previous_label(store,quote,monkeypatch):
    a,q,now=actual_function_fixture(store,quote,monkeypatch);capture(a,store)
    later=parse_time(q.commence_time)+timedelta(days=1);save_final(store,q,1,1,later);reconcile(store,later)
    old=records(store)[0]
    save_final(store,q,0,0,later+timedelta(seconds=1));reconcile(store,later+timedelta(seconds=1))
    new=records(store)[0]
    assert new['quarantined'] and new['label']==old['label'] and new['payload']==old['payload']
    report=scorecards(store,later+timedelta(seconds=1))
    assert report['groups'][0]['state']=='Suspended' and report['groups'][0]['scores']['n']==0
    from intelligence.lifecycle import research_hold
    assert research_hold(store,q,a.estimates[q.id])


@pytest.mark.parametrize('fractions,expected',[((1,0,0),1.),((0,1,0),0.),((0,0,1),-1.),((.5,.5,0),.5),((0,.5,.5),-.5)])
def test_hypothetical_score_contract_settles_full_push_and_half_states(fractions,expected):
    assert hypothetical_return(fractions,2.)==expected


def test_precision_and_power_planning_is_not_a_short_streak_approval_rule():
    p=sample_plan()
    assert p['IID_worst_case_calibration_n']==385 and p['paired_Brier_planning_n']>4900
    assert 'not approval cutoffs' in p['sample_requirement']


def test_storage_failure_is_safe_and_no_forward_success_is_inferred():
    from intelligence.forward_testing import update
    class Broken:
        def connect(self):raise sqlite3.OperationalError('private credential text')
    result=update(Analysis(),Broken())
    assert result['failure_code']=='storage_or_integrity' and 'private credential' not in str(result)


def test_protocol_timestamp_cannot_be_backdated_after_lock(store):
    from conftest import NOW
    identifier=lock_protocol(store,NOW)
    with pytest.raises(ValueError,match='protocol lock'):lock_protocol(store,NOW-timedelta(days=1))
    with store.connect() as db:
        assert db.execute('SELECT at FROM forward_protocols WHERE id=?',(identifier,)).fetchone()[0]==NOW.isoformat()


def test_postponed_or_rescheduled_fixture_is_not_scored(store,quote,monkeypatch):
    a,q,now=actual_function_fixture(store,quote,monkeypatch);capture(a,store)
    later=parse_time(q.commence_time)+timedelta(days=1)
    saved=deepcopy(latest(store,q.league,season_at(later)))
    original,_=source_fixture(store,q,later)
    for event in saved['events']:
        if event['source_event_id']==original['source_event_id']:
            event.update(status='unresolved',kickoff=(later+timedelta(days=1)).isoformat(),event_date=(later+timedelta(days=1)).date().isoformat(),observed_at=later.isoformat())
    saved.update(checked_at=later.isoformat(),sha256=digest(saved['events']))
    accept(store,q.league,season_at(later),saved)
    result=reconcile(store,later)
    assert result['labeled']==0 and result['blocked'] and records(store)[0]['label'] is None


def test_registry_scopes_leagues_and_reviewed_suspension_does_not_fall_back(store):
    from test_lifecycle import synthetic_report
    from intelligence.lifecycle import register_artifact,change_champion,active_champion,suspension_reason
    from conftest import NOW
    evidence={'fresh_unseen_period_verified':True,'commercial_data_rights_verified':True,
        'operator_scope_verified':True,'forward_decisions':100,'paired_improvement_lower':.001,
        'verification_source':'https://example.test/independent-audit'}
    identifiers=[]
    for league in ('League A','League B'):
        r=synthetic_report();r['league']=league;r['evidence_id']=digest({k:v for k,v in r.items() if k!='evidence_id'})
        identifier=register_artifact(store,r);identifiers.append(identifier)
        change_champion(store,identifier,evidence,'https://example.test/review',now=NOW)
    assert active_champion(store,'NBA','h2h') is None
    assert active_champion(store,'NBA','h2h',league='League A')['league']=='League A'
    change_champion(store,identifiers[0],{},'https://example.test/suspension','suspend',NOW)
    assert active_champion(store,'NBA','h2h',league='League A') is None
    assert active_champion(store,'NBA','h2h',league='League B')['league']=='League B'
    assert suspension_reason(store,'NBA','League A','h2h','synthetic-only')


def test_cluster_metrics_have_actual_baseline_intervals_and_no_ticket_profitability():
    from conftest import NOW
    from intelligence.model_reliability import scored_report
    p=json.loads(__import__('pathlib').Path('config/forward_research_policy.json').read_text())
    rows=[]
    for i in range(80):
        rows.append({'payload':{'estimate':{'probability':.6},'forecast_at':(NOW+timedelta(days=i)).isoformat(),
            'baseline':{'probability':.5}},'label':{'outcome':'win' if i%5<3 else 'loss','hypothetical_score_contract_return':1 if i%5<3 else -1}})
    report=scored_report(rows,p)
    assert report['n']==80 and report['metrics']['binary_brier']['value']==pytest.approx(.24)
    assert report['minus_recorded_constant']['binary_brier']['value']==pytest.approx(-.01)
    assert report['minus_recorded_constant']['binary_brier']['interval'] is not None
    assert report['calibration'][0]['model_minus_frequency_interval'] is not None
    assert report['accepted_ticket_ROI'] is None
