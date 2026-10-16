from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import pytest
from conftest import NOW
from intelligence.bankroll import analyze
from intelligence.performance import metrics,breakdown


def test_hypothetical_losses_and_exposure_are_shown_without_kelly():
    risk=analyze(1000)
    assert risk['kelly_amount'] is None
    assert risk['scenarios'][0]['maximum_loss']==2.5
    assert risk['scenarios'][-1]['three_equal_stakes_maximum_loss']==60
    assert risk['scenarios'][-1]['exceeds_portfolio_cap_for_three']


@pytest.mark.parametrize('flags',[{}, {'validated':True},{'price_verified':True}])
def test_kelly_cannot_be_enabled_by_unvalidated_probability_or_theoretical_price(flags):
    result=analyze(1000,odds=2,probability=.65,lower=.6,upper=.7,**flags)
    assert result['kelly_amount'] is None


def test_fractional_kelly_is_conservative_capped_and_sensitive_to_uncertainty():
    args={'odds':1.9,'probability':.65,'lower':.6,'upper':.7,'validated':True,'price_verified':True}
    result=analyze(1000,**args)
    assert result['kelly_amount']==pytest.approx(5)
    assert len(result['sensitivity'])==3 and all(row['hypothetical_amount']<=5 for row in result['sensitivity'])
    zero=analyze(1000,**(args|{'lower':.5,'upper':.65}))
    assert zero['kelly_amount']==0 and 'Avoid' in zero['reason']
    wide=analyze(1000,**(args|{'lower':.3,'upper':.9}))
    assert wide['kelly_amount'] is None and 'too wide' in wide['reason']


@pytest.mark.parametrize('amount',[0,-1,float('nan'),True])
def test_invalid_bankroll_inputs(amount):
    with pytest.raises(ValueError):analyze(amount)


def test_performance_counts_losses_pushes_voids_and_suppresses_weak_intervals(store,opportunity):
    for i,outcome in enumerate(('win','loss','push','void')):
        o=replace(opportunity,quote=replace(opportunity.quote,event_id=f'fixture-{i}'))
        id=store.publish(o,origin='backtest',now=NOW)
        store.settle(id,outcome,'synthetic software fixture','https://example.test/result',now=NOW+timedelta(days=2))
    rows=store.records('backtest'); result=metrics(rows)
    assert result['wins']==1 and result['losses']==1 and result['pushes']==1 and result['voids']==1
    assert result['decisive_sample']==2 and result['roi']==pytest.approx(-.1/3)
    assert result['win_rate_interval'] is None # two decisions share the physical game
    assert result['roi_interval'] is None and result['day_blocks']==1
    assert breakdown(rows,'parlay_size')['1']['published']==4
    assert store.records('forward')==[]


def test_performance_day_block_interval_requires_actual_sample(store,opportunity):
    id=store.publish(opportunity,origin='backtest',now=NOW)
    store.settle(id,'win','fixture result','https://example.test/result',now=NOW+timedelta(days=2))
    seed=store.records('backtest')[0]
    rows=[]
    for i in range(35):
        row=deepcopy(seed); row['id']=str(i)
        at=NOW+timedelta(days=i+2)
        row['settled_at']=at.isoformat();row['payload']['quote']['commence_time']=(at-timedelta(hours=1)).isoformat()
        row['outcome']='loss' if i%2 else 'win'
        rows.append(row)
    result=metrics(rows)
    assert result['day_blocks']==35 and result['roi_interval'] is not None
    assert result['win_rate_interval'] is not None and result['decisive_sample']==35
    assert result['roi_interval'][0]<=result['roi']<=result['roi_interval'][1]
    assert 'unverified' in result['roi_interval_method']


def test_empty_performance_never_invents_returns():
    result=metrics([])
    assert result['wins']==0 and result['settled']==0
    assert result['win_rate'] is None and result['roi'] is None and result['roi_interval'] is None
