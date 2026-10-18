"""Synthetic software contracts; not real scores, prices or model improvements."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from unittest.mock import patch
import pytest
from intelligence.domain import utcnow
from intelligence.fixture_research import collect, soccer_forecasts, combinations_for
from intelligence.current_soccer import prepare_epl, prepare_expanded, forecast
from test_readiness_ranking import enable, supported_quote


@pytest.mark.parametrize('league', ['Premier League', 'Bundesliga', 'Ligue 1'])
def test_quote_free_forecast_matches_frozen_price_model_without_fake_prices(store, quote, monkeypatch, league):
    enable(monkeypatch); now=utcnow(); q, _=supported_quote(store, quote, league, now)
    artifact=prepare_epl(store, now, allow_fetch=False) if league=='Premier League' else prepare_expanded(league, store, now, allow_fetch=False)
    rows, _=soccer_forecasts(league, artifact, now, 168)
    match=next(r for r in rows if r['home']==q.home and r['away']==q.away and r['market']==q.market)
    chosen=replace(q, selection=match['selection'],point=match['point'])
    estimate, detail=forecast(chosen, artifact, now)
    assert estimate and match['probability']==pytest.approx(estimate.probability)
    assert (match['lower'],match['upper'])==pytest.approx((estimate.lower,estimate.upper))
    assert match['observed_odds'] is match['sportsbook'] is match['ev'] is None
    assert match['fair_odds']==pytest.approx(1/match['probability'])
    assert not match['validated'] and match['calibration_n'] and match['test_n']
    # Fixture research does not need an odds credential, fresh price or Quote.
    monkeypatch.delenv('ODDS_API_KEY',raising=False)
    with patch('intelligence.providers.OddsAPI',side_effect=AssertionError('No provider')):
        result=collect(store, now, 168, [league])
    assert result['forecasts'] and result['provider_requests']==0 and result['forward_records_created']==0
    assert not store.records()


@pytest.mark.parametrize('change', ['expired','unresolved','old_team','future_features','missing_keyed_source'])
def test_expired_missing_or_unreconciled_features_never_emit_forecasts(store, quote, monkeypatch, change):
    enable(monkeypatch); now=utcnow(); q,_=supported_quote(store,quote,'Premier League',now)
    artifact=prepare_epl(store,now,allow_fetch=False)
    if change=='expired': artifact['results_observed_at']=(now-timedelta(hours=6)).isoformat()
    if change=='unresolved': artifact['results_events'][0]['status']='unresolved'
    if change=='old_team':
        for t in artifact['state']['teams'].values():t['latest']='2025-01-01'
    if change=='future_features': artifact['current_rows'][0]['date']=now.date().isoformat()
    if change=='missing_keyed_source': artifact.pop('results_provider')
    rows, problem=soccer_forecasts('Premier League',artifact,now,168)
    assert not rows and problem


def test_missing_data_all_sports_stay_blocked_without_network(store):
    result=collect(store,hours=168)
    assert not result['forecasts'] and {'Premier League','NBA','MLB'} <= result['blockers'].keys()
    assert result['provider_requests']==result['paid_ai_requests']==result['approved_models']==0


def synthetic_rows(now):
    return [{'sport':sport,'league':sport,'home_id':'home'+str(i),'away_id':'away'+str(i),
        'fixture_id':str(i),'kickoff':(now+timedelta(days=1)).isoformat(),
        'source_observed_at':now.isoformat(),'forecast_at':now.isoformat(),
        'probability':p,'lower':p-.1,'upper':p+.1,'evidence_id':'synthetic-only'}
        for i,(sport,p) in enumerate([('NBA',.7),('Soccer',.65),('MLB',.6)])]


def test_two_three_and_mixed_sport_logical_bounds_never_claim_joint_validation_or_ev():
    now=utcnow(); rows=synthetic_rows(now)
    two=combinations_for(rows,2,now=now); three=combinations_for(rows,3,now=now)
    assert two and len(three)==1 and len(three[0]['legs'])==3
    c=three[0]
    assert c['logical_probability_bounds']==pytest.approx([0.,.6])
    assert c['fair_odds_range']==pytest.approx([1/.6,None])
    assert c['joint_probability'] is c['combined_odds'] is c['ev'] is None
    assert not c['independence_assumed'] and not c['executable'] and not c['joint_validated']


@pytest.mark.parametrize('change', ['duplicate_game','shared_team','stale','started','future_observation'])
def test_incompatible_or_expired_fixture_legs_are_rejected(change):
    now=utcnow();rows=synthetic_rows(now)[:2]
    if change=='duplicate_game':rows[1]['fixture_id']=rows[0]['fixture_id']
    if change=='shared_team':rows[1].update(sport=rows[0]['sport'],home_id=rows[0]['home_id'])
    if change=='stale':rows[1]['source_observed_at']=(now-timedelta(hours=6)).isoformat()
    if change=='started':rows[1]['kickoff']=(now-timedelta(minutes=1)).isoformat()
    if change=='future_observation':rows[1]['forecast_at']=(now+timedelta(seconds=1)).isoformat()
    assert not combinations_for(rows,2,now=now)


def test_historical_evidence_is_fingerprinted_and_never_promotes():
    from intelligence.fixture_research_ui import historical_evidence
    reports=historical_evidence()
    assert set(reports)=={'NBA','MLB'}
    for r in reports.values():
        assert r['calibration_start']<r['test_start']<r['data_end']
        assert r['test_n']>200 and r['paired_test_n']>200
        assert r['paired_minus_incumbent']['binary_brier']['interval'][0]<0<r['paired_minus_incumbent']['binary_brier']['interval'][1]
        assert not r['approved'] and not r['replaces_incumbent'] and not r['current_forecasts_enabled']
