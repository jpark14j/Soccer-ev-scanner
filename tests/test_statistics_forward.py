"""Synthetic pregame record and coherent-probability contracts; no real picks."""
from copy import deepcopy
from datetime import timedelta
import json, sqlite3
from unittest.mock import patch
import pytest
from intelligence.domain import utcnow
from intelligence.statistics_forward import record
from intelligence.current_score_research import masks, load_report
from intelligence.score_distribution import score_distribution


def row(now):
    return {'fixture_id':'synthetic-only','kickoff':(now+timedelta(days=1)).isoformat(),
        'forecast_at':now.isoformat(),'source_observed_at':now.isoformat(),'research_eligible':True,
        'probability':.6,'lower':.4,'upper':.8,'evidence_id':'synthetic-not-evidence',
        'model_version':'synthetic-only','observed_odds':None,'ev':None,'approved':False}


def test_pregame_records_immutable_never_backfilled_or_rewritten(store):
    now=utcnow();r=row(now);assert len(record(store,[r],now))==1
    assert record(store,[r],now)==[]
    with store.connect() as db:
        assert db.execute('SELECT count(*) FROM statistics_forecasts').fetchone()[0]==1
        with pytest.raises(sqlite3.IntegrityError):db.execute("UPDATE statistics_forecasts SET at='2000-01-01'")
        with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM statistics_forecasts')
    with pytest.raises(ValueError):record(store,[r],now+timedelta(days=2))


@pytest.mark.parametrize('change',['stale','future_source','started','not_eligible','approved','priced','ev','invalid'])
def test_unsafe_statistics_are_not_recorded(store,change):
    now=utcnow();r=row(now)
    if change=='stale':r['source_observed_at']=(now-timedelta(hours=6)).isoformat()
    if change=='future_source':r['source_observed_at']=(now+timedelta(seconds=1)).isoformat()
    if change=='started':r['kickoff']=(now-timedelta(seconds=1)).isoformat()
    if change=='not_eligible':r['research_eligible']=False
    if change=='approved':r['approved']=True
    if change=='priced':r['observed_odds']=2.
    if change=='ev':r['ev']=.1
    if change=='invalid':r['probability']=float('nan')
    with pytest.raises(ValueError):record(store,[r],now)
    with store.connect() as db:assert db.execute('SELECT count(*) FROM statistics_forecasts').fetchone()[0]==0


def test_correlated_two_and_three_leg_events_sum_score_cells_not_marginals():
    legs,joint=masks();mass=score_distribution(2.3,1.1).mass
    two=float(mass[joint['home_over_2.5']].sum())
    product=float(mass[legs[('h2h','Home',None)]].sum()*mass[legs[('totals','Over',2.5)]].sum())
    assert abs(two-product)>.01
    three=float(mass[joint['home_btts_under_4.5']].sum())
    assert three==pytest.approx(mass[2,1]+mass[3,1])
    assert three<=mass[legs[('btts','Yes',None)]].sum()


def test_joint_recent_holdout_is_versioned_and_has_no_approval_or_price():
    r=load_report();assert r and not r['approved'] and not r['joint_validated'] and not r['replaces_incumbent']
    assert r['calibration_end']<r['test_start'] and r['test_start']=='2025-07-01'
    assert r['test_end']=='2026-05-16' and r['excluded_test_games']==16
    assert all(t['test_n']==290 and t['calibration_n']>=200 for t in r['reports'].values())
    assert r['reports']['home_btts_under_4.5']['metrics']['binary_brier']['value']>r['reports']['home_btts_under_4.5']['baseline']['binary_brier']['value']


def test_current_score_research_fails_closed_without_completion_or_on_tampered_artifact(store):
    from intelligence.current_score_research import candidates
    assert candidates(store)==[]
    with patch('intelligence.current_score_research.load_report',return_value=None):assert candidates(store)==[]


def test_source_import_has_no_external_provider_network_path(store,tmp_path):
    from intelligence.statistics_import import import_files,protected_counts
    before=protected_counts(store)
    (tmp_path/'manifest.json').write_text('[]')
    with pytest.raises(ValueError):import_files(store,tmp_path)
    assert before==protected_counts(store)


@pytest.mark.parametrize('held_scope',['underlying','totals','btts'])
def test_sgp_respects_underlying_and_every_leg_model_hold(store,held_scope):
    from intelligence.current_score_research import candidates
    report=load_report();now=utcnow()
    artifact={'historical_completion_sha256':report['completion_sha256'],'model_version':'synthetic-base',
        'artifact_sha256':'synthetic-base-evidence','state':{},'policy':{}}
    event={'home_id':'synthetic-home','away_id':'synthetic-away','home':'Synthetic Home','away':'Synthetic Away',
        'fixture_id':'synthetic-fixture','event':'Synthetic Home vs Synthetic Away',
        'kickoff':(now+timedelta(days=1)).isoformat(),'source_observed_at':now.isoformat()}
    def held(s,contract,model):
        if held_scope=='underlying' and model.model_version=='synthetic-base':return 'Synthetic underlying hold'
        if model.model_version==report['model_version'] and contract.market==held_scope:return 'Synthetic leg hold'
    with patch('intelligence.current_soccer.prepare_openliga',return_value=artifact),patch('intelligence.fixture_research.soccer_forecasts',return_value=([event],'')),patch('intelligence.current_score_research.predict',return_value=({'home_rate':2.3,'away_rate':1.1},'')),patch('intelligence.lifecycle.research_hold',side_effect=held):
        rows=candidates(store,now)
    if held_scope in ('underlying','totals'):assert not rows
    else:assert rows and all(len(r['legs'])==2 for r in rows)
