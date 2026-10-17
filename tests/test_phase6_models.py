"""Statistical contracts and real offline report integrity; no current API data."""
import json
from pathlib import Path
import numpy as np
import pytest
from intelligence.domain import digest
from intelligence.phase6_evaluation import fit_beta,beta_probability,settlement_masks,DESTINATION,POLICY
from intelligence.score_distribution import score_distribution,settlement,state_label


def test_beta_calibration_is_monotone_finite_and_deterministic():
    p=np.linspace(.1,.9,300);y=(np.arange(300)%3==0).astype(int)
    b=fit_beta(p,y)
    assert b[1]>=0 and b[2]>=0 and b==fit_beta(p,y)
    grid=beta_probability(np.linspace(.001,.999,300),b)
    assert np.all(np.isfinite(grid)) and np.all(np.diff(grid)>=0) and np.all((grid>0)&(grid<1))
    x=np.column_stack((np.ones(p.size),np.log(p),-np.log1p(-p)))
    gradient=x.T@(beta_probability(p,b)-y)+np.array([1.,3.,3.])*(np.array(b)-[0,1,1])
    assert abs(gradient[0])<1e-5
    assert all(abs(g)<1e-5 if coefficient>1e-10 else g>=-1e-5 for coefficient,g in zip(b[1:],gradient[1:]))


@pytest.mark.parametrize('p,y',[(np.array([.5]*99),np.zeros(99)),(np.array([float('nan')]*100),np.zeros(100)),(np.array([.5]*100),np.full(100,2))])
def test_beta_refuses_unsupported_calibration_data(p,y):
    with pytest.raises(ValueError):fit_beta(p,y)


def test_joint_state_masks_partition_every_score_and_preserve_half_settlement():
    p=json.loads(POLICY.read_text());grid=score_distribution(1.7,1.1,-.05).mass
    for contracts in p['settlement_tasks'].values():
        states=settlement_masks(contracts)
        assert np.all(sum(states.values())==1)
        assert sum(float(grid[mask].sum()) for mask in states.values())==pytest.approx(1.)
        for h,a in ((0,0),(1,1),(2,1),(1,2)):
            expected=tuple(state_label(settlement(m,s,line,'HOME','AWAY',h,a)) for m,s,line in contracts)
            assert states[expected][h,a]
    quarter=settlement_masks(p['settlement_tasks']['home_plus_0.25_and_under_3'])
    assert any('half-win' in state for state in quarter) and any('push' in state for state in quarter)
    totals=settlement_masks(p['settlement_tasks']['BTTS_yes_and_over_2.25'])
    assert any('half-loss' in state for state in totals)


def test_phase6_report_has_matched_samples_uncertainty_and_no_activation():
    from intelligence.data_adapters import ROOT
    r=json.loads(DESTINATION.read_text());checksum=r.pop('sha256')
    assert checksum==digest(r) and r['policy_sha256']==digest(json.loads(POLICY.read_text()))
    assert r['code_sha256']==digest({name:(ROOT/'intelligence'/name).read_text() for name in ('phase6_evaluation.py','quant_models.py','score_distribution.py','quant_evaluation.py')})
    assert not r['independent_confirmation'] and r['models_approved']==r['joint_probabilities_approved']==0
    for league,v in r['leagues'].items():
        if league in ('La Liga','Serie A'):assert v['blocked'];continue
        assert v['fit_training_end']=='2023-06-30' and v['refit_training_end']=='2024-06-30'
        for target,t in v['markets'].items():
            for method in ('static_dc_beta','annual_refit_dc_platt'):
                lo,hi=t['methods'][method]['minus_frozen']['binary_brier']['interval']
                assert lo<=0<=hi
                assert t['methods'][method]['metrics']['n']==t['test_n']
        for joint in v['joint_settlement_research'].values():
            assert not joint['joint_approved'] and joint['actual_combined_price'] is joint['EV'] is None
            assert joint['all_full_win']['metrics']['n']==v['common_test_n']
            assert joint['all_full_win']['prior_calibration_bins'] and joint['settlement_state_proper_scores']
