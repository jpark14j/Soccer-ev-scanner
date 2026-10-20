"""Coherent dependence probabilities and fitting isolation, not accuracy proof."""
from itertools import product
from copy import deepcopy
import numpy as np
import pytest
from intelligence.dependence_study import state_probability,attach,fit,all_win,load_report


@pytest.mark.parametrize('ps,theta',[([.65,.7],-.99),([.8,.65],.99),([.6,.7,.8],-1/3),([.6,.7,.8],1.)])
def test_joint_distribution_preserves_marginals_and_total_mass(ps,theta):
    states=list(product((0,1),repeat=len(ps)))
    mass=[state_probability(ps,s,theta) for s in states]
    assert min(mass)>=0 and sum(mass)==pytest.approx(1.)
    for i,p in enumerate(ps):assert sum(v for v,s in zip(mass,states) if s[i])==pytest.approx(p)
    assert state_probability(ps,[1]*len(ps),0.)==pytest.approx(np.prod(ps))
    assert state_probability(ps,[1]*len(ps),theta)!=pytest.approx(np.prod(ps))


def test_coherent_ranges_refuse_impossible_negative_three_way_dependence():
    with pytest.raises(ValueError):state_probability([.5]*3,[1]*3,-.5)


def test_dependence_fit_uses_calibration_states_and_does_not_read_later_outcomes():
    earlier=[{'date':f'2024-01-{day:02d}','home':f'H{i}','away':f'A{i}','p':.6,'y':int(day%2==0)} for day in range(1,29) for i in range(6)]
    training,_=attach(earlier,3);theta=fit(training,3)
    later=[r|{'date':r['date'].replace('2024','2025')} for r in earlier]
    one,_=attach(later,3);changed=[r|{'y':1-r['y']} for r in later];two,_=attach(changed,3)
    assert all_win(one,theta)==all_win(two,theta)
    assert theta==fit(training,3)
    assert abs(theta)>0 and abs(theta)<1


def test_real_archive_joint_results_are_hash_verified_and_not_promoted():
    r=load_report();assert r is not None and r['approved_joint_models']==r['approved_models']==0
    for sport in r['reports'].values():
        for f in sport['folds']:
            assert f['marginal_fit_end']<f['dependence_fit_start']<f['test_start']
            for t in f['tasks'].values():
                assert t['test_n']>=300 and not t['approved']
                assert t['actual_combined_odds'] is t['EV'] is None
