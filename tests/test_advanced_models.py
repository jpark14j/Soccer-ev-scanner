"""Synthetic outcome data tests only; genuine diagnostics are separate artifacts."""
from dataclasses import replace
from datetime import timedelta
import numpy as np
import pandas as pd
import pytest
from conftest import NOW
from intelligence.advanced_models import make_context,probability,research_joint,forecast_problem
from intelligence.market_validation import evaluate,load_reports
from intelligence.parlay_research import select_candidates,contradictory_scores
from intelligence.pipeline import Analysis
from intelligence.domain import Estimate


def history(sport,n=600):
    k=np.arange(n)
    h=(100+(k*3)%25) if sport=='NBA' else ((k*3)%8) if sport=='MLB' else (k%4)
    a=(95+(k*7)%23) if sport=='NBA' else ((k*5+1)%8) if sport=='MLB' else ((k+2)%3)
    return pd.DataFrame({'date':pd.date_range('2023-01-01',periods=n),
        'HomeTeam':np.where(k%2,'Home','Away'),'AwayTeam':np.where(k%2,'Away','Home'),
        'FTHG':h,'FTAG':a})


def qfor(quote,sport,market='totals',selection='Over',point=None):
    return replace(quote,sport=sport,league='Premier League' if sport=='Soccer' else sport,
        market=market,selection=selection,point=point if point is not None else (220.5 if sport=='NBA' else 8.5 if sport=='MLB' else 2.5))


@pytest.mark.parametrize('sport',['NBA','Soccer','MLB'])
def test_sport_specific_probabilities_and_complementary_half_lines(quote,sport):
    data=history(sport)
    q=qfor(quote,sport)
    c=make_context(data,sport,'Home','Away',quote.commence_time,as_of=NOW)
    assert c is not None and c.weights.sum()==pytest.approx(1)
    p=probability(c,q)
    assert 0<=p<=1
    assert p+probability(c,replace(q,selection='Under'))==pytest.approx(1)
    assert c.history_n==len(data) and c.version.startswith(sport.lower() if sport!='Soccer' else 'soccer')
    if sport!='Soccer':
        assert np.all(c.home_scores!=c.away_scores)


@pytest.mark.parametrize('sport',['NBA','Soccer','MLB'])
def test_analysis_time_cutoff_prevents_future_or_same_day_leakage(quote,sport):
    data=history(sport)
    as_of=pd.Timestamp('2024-05-01T00:00:00Z')
    before=make_context(data,sport,'Home','Away',quote.commence_time,as_of=as_of)
    altered=data.copy()
    altered.loc[altered.date>=pd.Timestamp('2024-05-01'),['FTHG','FTAG']]=999
    after=make_context(altered,sport,'Home','Away',quote.commence_time,as_of=as_of)
    assert np.array_equal(before.home_scores,after.home_scores)
    assert np.array_equal(before.away_scores,after.away_scores)
    assert np.allclose(before.weights,after.weights)
    assert before.training_end<as_of.isoformat()


def test_soccer_joint_uses_shared_score_outcomes_not_product(quote):
    data=history('Soccer'); q=qfor(quote,'Soccer')
    btts=replace(q,market='btts',selection='Yes',point=None)
    over=replace(q,point=.5)
    c=make_context(data,'Soccer','Home','Away',q.commence_time,as_of=NOW)
    joint=research_joint(c,[btts,over])
    assert joint['validated'] is False and joint['ev'] is None
    assert joint['probability']==pytest.approx(probability(c,btts))
    assert joint['probability']>probability(c,btts)*probability(c,over)
    assert research_joint(c,[btts,replace(over,event_id='different',home='Unrelated')]) is None


def test_integer_quarter_player_and_corners_forecasts_are_refused(quote):
    for line in (2.,2.25,2.75):
        q=qfor(quote,'Soccer',point=line)
        assert forecast_problem(q)
    prop=replace(quote,market='player_points',participant='Test Player',selection='Over',point=20.5)
    assert 'player/corners history' in forecast_problem(prop)
    assert 'player/corners history' in forecast_problem(replace(qfor(quote,'Soccer'),market='totals_corners',point=9.5))


def test_paired_nba_residuals_retain_score_dependence(quote):
    data=history('NBA')
    data.FTAG=data.FTHG-10
    c=make_context(data,'NBA','Home','Away',quote.commence_time,as_of=NOW)
    assert np.cov(c.home_scores,c.away_scores)[0,1]>0
    assert np.var(c.home_scores-c.away_scores)<1


def test_btts_score_constraints_and_player_contradictions(quote):
    base=qfor(quote,'Soccer'); yes=replace(base,market='btts',selection='Yes',point=None)
    assert contradictory_scores([yes,replace(base,selection='Under',point=1.5)])
    no=replace(yes,selection='No')
    assert not contradictory_scores([no,replace(base,point=4.5)])
    draw=replace(base,market='h2h',selection='Draw',point=None)
    assert contradictory_scores([no,draw,replace(base,point=.5)])
    prop=replace(quote,market='player_points',participant='Test Player',selection='Over',point=25.5)
    opposite=replace(prop,selection='Under')
    assert not select_candidates(Analysis(quotes=[prop,opposite]),now=NOW).candidates
    threes=replace(prop,market='player_threes',point=5.5)
    low_points=replace(prop,selection='Under',point=16.5)
    assert not select_candidates(Analysis(quotes=[threes,low_points]),now=NOW).candidates
    other=replace(prop,participant='Other Player')
    c=select_candidates(Analysis(quotes=[prop,other]),now=NOW).candidates[0]
    assert c.parlay_ev is None and any('Same event' in w for w in c.warnings)


def test_same_game_research_joint_never_promotes_or_prices_candidate(quote):
    data=history('NBA'); q=replace(quote,market='spreads',point=-5.5)
    t=replace(q,market='totals',selection='Over',point=220.5)
    ctx=make_context(data,'NBA','Home','Away',q.commence_time,as_of=NOW)
    estimates={r.id:Estimate(probability(ctx,r),0,1,ctx.version,ctx.training_end,'',False,(),r.sport,r.league,r.market) for r in (q,t)}
    analysis=Analysis(quotes=[q,t],advanced_estimates=estimates,score_contexts={('NBA',q.event_id):ctx})
    candidate=select_candidates(analysis,now=NOW).candidates[0]
    assert candidate.scenario_joint and not candidate.scenario_joint['validated']
    assert candidate.joint_probability is None and candidate.parlay_ev is None and not candidate.executable
    lo,hi=candidate.probability_bounds
    assert lo-1e-9<=candidate.scenario_joint['probability']<=hi+1e-9


def test_chronological_diagnostics_have_no_fabricated_betting_roi():
    report=evaluate(history('Soccer'),'Soccer','Synthetic fixture, not live research evidence')
    assert report['status']=='research' and report['roi'] is None
    assert report['calibration_start']<report['test_start']
    assert all(t['test_n']>0 and t['roi'] is None and t['betting_win_rate'] is None for t in report['tasks'])
    assert all(0<=t['classification_accuracy']<=1 and len(t['accuracy_interval'])==2 for t in report['tasks'])
    for real in load_reports():
        assert real['status']=='research' and real['roi'] is None
        assert real['tasks'] and not real['profitable_edge_established']


def test_event_filter_can_focus_same_game_without_other_events_dominating(quote):
    a=replace(quote,market='spreads',point=-5.5)
    b=replace(a,market='totals',selection='Over',point=220.5)
    unrelated=replace(quote,event_id='unrelated',home='Other Home',away='Other Away',selection='Other Home')
    result=select_candidates(Analysis(quotes=[a,b,unrelated]),event_ids=[quote.event_id],now=NOW)
    assert len(result.candidates)==1 and all(l.quote.event_id==quote.event_id for l in result.candidates[0].legs)
    assert not select_candidates(Analysis(quotes=[a,b]),event_ids=[],now=NOW).candidates
