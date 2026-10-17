"""Synthetic research contracts; no payload is a real current opportunity."""
from dataclasses import replace
from datetime import timedelta
import json
import pytest
from conftest import NOW
from test_readiness_ranking import research_analysis
from intelligence.research_top import select_top
from intelligence.risk_research import sensitivity
from intelligence.joint_research import analyze,bounds
from intelligence.score_distribution import score_distribution
from intelligence.parlay_intelligence import physical_game


def test_risk_ranking_distinguishes_probability_price_and_existing_evidence(quote):
    a=research_analysis(quote,[(.90,.6,.98,1.4,80),(.65,.6,.7,1.3,180),(.7,.6,.8,2.,100)])
    result=select_top(a,now=NOW);r=result['risk_rankings']
    assert result['pick'].quote.event_id=='research-1'  # Existing engine preserved.
    assert r['most_likely'][0].quote.event_id=='research-0'
    assert r['best_risk_adjusted'].quote.event_id=='research-2' and result['recommended']==r['best_risk_adjusted']
    info=sensitivity(r['best_risk_adjusted'])
    assert info['lower_margin_per_range']==pytest.approx(.1/.2)
    assert info['model_loss_probability']==pytest.approx(.3) and info['estimated_EV'] is None and not info['approved']


def test_probability_fallback_and_missing_disagreement_are_explicit(quote):
    result=select_top(research_analysis(quote,[(.7,.6,.8,1.2,100),(.8,.6,.9,1.1,100)]),now=NOW)
    r=result['risk_rankings']
    assert r['best_risk_adjusted'] is None and r['default'].estimate.probability==.8
    assert 'fallback' in r['default_mode'] and sensitivity(r['default'])['current_model_disagreement'] is None


def legs(quote):
    a=research_analysis(quote,[(.7,.6,.8,1.8,100)]*3)
    r=select_top(a,now=NOW)
    return r['parlay'].research.legs


def test_multi_game_joint_is_not_a_probability_product(quote):
    values=legs(quote);r=analyze(values,NOW)
    assert r['format']=='Multi-game parlay' and not r['independence_assumed']
    assert r['joint_probability'] is r['combined_price'] is r['parlay_EV'] is None
    assert r['logical_all_full_win_bounds']==pytest.approx([.4,.7])


def test_same_game_and_mixed_keep_dependence_and_score_states(quote):
    base=legs(quote)[0]
    q=replace(base.quote,sport='Soccer',league='Premier League',home='Arsenal',away='Chelsea',market='btts',point=None,selection='Yes')
    one=replace(base,quote=q);two=replace(one,quote=replace(q,market='totals',point=2.25,selection='Over'))
    no_model=analyze((one,two),NOW)
    assert no_model['logical_all_full_win_bounds'] is None and no_model['format']=='Same-game parlay'
    r=analyze((one,two),NOW,{physical_game(q):score_distribution(1.5,1.1)})
    states=r['components'][0]['evidence']['states']
    assert sum(x['probability'] for x in states)==pytest.approx(1.)
    assert any('half-loss' in x['leg_outcomes'] for x in states)
    assert r['joint_probability'] is None and not r['joint_validated'] and not r['executable']
    three=replace(one,quote=replace(q,event_id='other',home='Liverpool',away='Everton'))
    mixed=analyze((one,two,three),NOW,{physical_game(q):score_distribution(1.5,1.1)})
    assert mixed['format']=='Mixed parlay' and mixed['logical_all_full_win_bounds'] is not None
    assert not mixed['independence_assumed'] and mixed['joint_probability'] is None


@pytest.mark.parametrize('failure',['contradictory','book','stale','repeat'])
def test_invalid_joint_contracts_are_rejected(quote,failure):
    a,b=legs(quote)
    if failure in ('contradictory','repeat'):
        b=replace(a,quote=replace(a.quote,selection=a.quote.away if failure=='contradictory' else a.quote.selection))
    if failure=='book':b=replace(b,quote=replace(b.quote,bookmaker='different'))
    if failure=='stale':b=replace(b,quote=replace(b.quote,source_updated_at=(NOW-timedelta(minutes=6)).isoformat()))
    with pytest.raises(ValueError):analyze((a,b),NOW)


@pytest.mark.parametrize('values',[[],[float('nan')],[1.01],[-.1]])
def test_logical_bounds_refuse_invalid_component_probabilities(values):
    with pytest.raises(ValueError):bounds(values)


def test_real_joint_report_is_reproducible_historical_research_not_approval():
    from intelligence.joint_validation import DESTINATION
    from intelligence.domain import digest
    from pathlib import Path
    r=json.loads(DESTINATION.read_text());checksum=r.pop('sha256')
    assert digest(r)==checksum and r['code_sha256']==digest(Path('intelligence/joint_validation.py').read_text())
    assert r['test_previously_inspected'] and not r['independent_confirmation'] and r['approved_joint_models']==0
    for league,v in r['leagues'].items():
        assert v['n']=={'Premier League':342,'Bundesliga':210,'Ligue 1':272}[league]
        for task,t in v['tasks'].items():
            assert t['all_full_win']['model']['n']==v['n'] and len(t['stability_by_quarter'])>=3
            assert len(t['sensitivity_range_width_quantiles'])==4 and not t['joint_approved']
            assert t['EV'] is t['executable_combined_price'] is None
