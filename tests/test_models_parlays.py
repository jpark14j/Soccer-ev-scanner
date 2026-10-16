from dataclasses import replace
import math
import pandas as pd
import pytest
from conftest import NOW
from intelligence.history import clean_history, seasons
from intelligence.soccer import poisson_1x2, independent_prediction, match_team
from intelligence.models import predict, poisson_count_over
from intelligence.evaluation import calibrate, scores, wilson, promotion_reasons
from intelligence.parlays import analyze, joint_bounds, CombinedPrice, JointEstimate


def history(sport='Soccer'):
    dates=pd.date_range('2024-01-01',periods=180,freq='D')
    h,a=(2,1) if sport!='NBA' else (110,100)
    return pd.DataFrame({'date':dates,'Date':dates.strftime('%d/%m/%Y'),
        'HomeTeam':['Home' if i%2 else 'Away' for i in range(180)],
        'AwayTeam':['Away' if i%2 else 'Home' for i in range(180)],
        'FTHG':[h+(i%3) for i in range(180)],'FTAG':[a+(i%2) for i in range(180)]})


def test_soccer_mass_and_symmetry():
    h,d,a=poisson_1x2(1.3,1.3)
    assert sum((h,d,a))==pytest.approx(1)
    assert h==pytest.approx(a)
    assert match_team('Unrelated Team',{'Home','Away'}) is None


def test_no_same_day_or_future_results_used():
    data=history()
    kickoff='2024-05-01T10:00:00Z'
    expected=independent_prediction(data,'Home','Away',kickoff)
    altered=data.copy()
    altered.loc[altered.date>=pd.Timestamp('2024-05-01'),['FTHG','FTAG']]=999
    assert expected==independent_prediction(altered,'Home','Away',kickoff)


@pytest.mark.parametrize('sport',['Soccer','NBA','MLB'])
def test_separate_models_produce_probability_mass(sport):
    p=predict(history(sport),sport,'Home','Away','2024-06-25T18:00:00Z')
    assert p and sum(p)==pytest.approx(1)
    assert all(0<=x<=1 for x in p)
    assert len(p)==(3 if sport=='Soccer' else 2)
    assert predict(pd.DataFrame(),sport,'Home','Away','2024-06-25T18:00:00Z') is None


def test_count_probability_and_integer_push_semantics():
    assert poisson_count_over(0.,2.5)==0.
    assert poisson_count_over(1.,0.5)==pytest.approx(1-math.exp(-1))
    with pytest.raises(ValueError): poisson_count_over(-1,2)


def test_clean_history_rejects_conflicts_and_deduplicates():
    data=history()
    assert len(clean_history(pd.concat([data,data])))==len(data)
    changed=data.iloc[[0]].copy(); changed.FTHG=99
    with pytest.raises(ValueError,match='Conflicting'): clean_history(pd.concat([data,changed]))
    assert seasons(NOW)==('2425','2526','2627')


def test_calibration_scores_and_promotion_gate():
    p=calibrate([.6,.4],1.)
    assert p==pytest.approx([.6,.4])
    assert scores([[.5,.5]],[0])['brier']==pytest.approx(.5)
    assert scores([[.5,.5]],[0])['log_loss']==pytest.approx(math.log(2))
    lo,hi=wilson(60,100)
    assert lo<.6<hi
    assert promotion_reasons({'test_n':1000,'calibration_n':1000})


def test_parlay_does_not_assume_independence_or_multiply_prices(opportunity):
    second=replace(opportunity,quote=replace(opportunity.quote,event_id='fixture-two'))
    analysis=analyze([opportunity,second],now=NOW)
    assert analysis['status']=='theoretical'
    assert analysis['odds'] is None and analysis['ev'] is None
    assert analysis['probability_bounds']==pytest.approx((.3,.65))
    with pytest.raises(ValueError): analyze([opportunity,opportunity],now=NOW)


def test_genuine_combined_quote_joint_evidence_and_restrictions_required(opportunity):
    second=replace(opportunity,quote=replace(opportunity.quote,event_id='fixture-two'))
    legs=[opportunity,second]
    ids=tuple(sorted(o.quote.id for o in legs))
    price=CombinedPrice('betmgm_ca_on',ids,3.,'2026-10-16T01:59:00Z',True,'test-quote-evidence')
    # Test joint p .5 differs from the independence product .4225.
    joint=JointEstimate(.5,.45,.55,ids,'test-joint-evidence',True)
    result=analyze(legs,price,joint,NOW)
    assert result['status']=='qualifying' and result['ev']==pytest.approx(.5)
    assert analyze(legs,replace(price,restrictions_verified=False),joint,NOW)['status']=='theoretical'
    assert analyze(legs,replace(price,bookmaker='betrivers_ca_on'),joint,NOW)['status']=='theoretical'
    with pytest.raises(ValueError): analyze(legs,price,replace(joint,probability=.9,upper=.95),NOW)


@pytest.mark.parametrize('sport',['NBA','MLB'])
def test_nba_mlb_future_results_do_not_change_forecast(sport):
    data=history(sport)
    before=predict(data,sport,'Home','Away','2024-05-01T10:00:00Z')
    data.loc[data.date>=pd.Timestamp('2024-05-01'),['FTHG','FTAG']]=999
    assert predict(data,sport,'Home','Away','2024-05-01T10:00:00Z')==before


def test_test_period_is_not_used_to_choose_calibration():
    from intelligence.evaluation import evaluate_history
    data=pd.concat([history().assign(date=lambda f:f.date+pd.Timedelta(days=180*i)) for i in range(4)],ignore_index=True)
    data['AvgH']=2.5; data['AvgD']=3.2; data['AvgA']=3.0
    before=evaluate_history(data,'Soccer','Premier League','synthetic-test-only')
    data.loc[data.date==data.date.max(),'FTHG']=0
    after=evaluate_history(data,'Soccer','Premier League','synthetic-test-only')
    assert before['temperature']==after['temperature']
    assert before['status']=='research'
    assert not before['baseline_timing_verified']
    assert before['calibration_start']<before['test_start']


def test_licensing_gate_requires_manifest_and_disables_free_commercial_downloads(tmp_path,monkeypatch):
    from intelligence.history import load_local, load_soccer
    monkeypatch.delenv('FOOTBALL_DATA_PERSONAL_RESEARCH',raising=False)
    monkeypatch.setenv('HISTORY_DIR',str(tmp_path))
    assert load_soccer('Premier League').empty
    history('NBA').drop(columns=['date']).to_csv(tmp_path/'nba.csv',index=False)
    with pytest.raises(ValueError,match='manifest'): load_local('NBA',tmp_path)


def test_mutually_exclusive_same_event_parlay_is_rejected(opportunity):
    other=replace(opportunity,quote=replace(opportunity.quote,selection='Away'))
    with pytest.raises(ValueError,match='Mutually exclusive'): analyze([opportunity,other],now=NOW)
