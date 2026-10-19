"""Chronological fitting and dependence contracts, never performance claims."""
from copy import deepcopy
import numpy as np
import pandas as pd
from intelligence.cross_game_study import groups,clipped_joint,fold,load_report


def test_disjoint_group_selection_is_outcome_blind_and_rejects_shared_teams():
    rows=[{'date':'2025-01-01','home':f'H{i}','away':f'A{i}','p':.6+i*.02,'y':i%2} for i in range(8)]
    rows+=[rows[0]|{'away':'EXTRA'}]  # One team's doubleheader: neither leg is used.
    first,excluded=groups(rows,2)
    changed=[r|{'y':1-r['y']} for r in reversed(rows)]
    second,_=groups(changed,2)
    assert excluded==2 and len(first)==3
    assert [r['ids'] for r in first]==[r['ids'] for r in second]
    names=[t for r in first for game in r['ids'] for t in game]
    assert len(names)==len(set(names)) and 'H0' not in names
    assert all(r['bounds'][0]<=r['p']<=r['bounds'][1] for r in first)


def test_joint_calibration_respects_conditional_bounds():
    rows=[{'p':.49,'bounds':[.4,.7]},{'p':.125,'bounds':[0.,.5]}]
    assert clipped_joint(rows,[35.,1.])==[.7,.5]
    assert clipped_joint(rows,[-35.,1.])[0]==.4


def synthetic():
    rng=np.random.default_rng(991);rows=[]
    for year in (2023,2024,2025):
        for day in range(120):
            for game in range(6):
                p=.35+game*.06
                rows.append({'date':(pd.Timestamp(f'{year}-01-01')+pd.Timedelta(days=day)).date().isoformat(),
                    'home':f'H{game}','away':f'A{game}','p':p,'y':int(rng.random()<p)})
    return rows


def test_later_test_outcomes_do_not_refit_marginal_or_joint_models_or_select_groups():
    rows=synthetic();one=fold(rows,'2024-01-01','2025-01-01','2026-01-01',resamples=10)
    changed=[r|{'y':1-r['y']} if r['date']>='2025-01-01' else r for r in deepcopy(rows)]
    two=fold(changed,'2024-01-01','2025-01-01','2026-01-01',resamples=10)
    assert one['marginal_fit_end']<one['joint_fit_start']<one['test_start']
    assert one['marginal_coefficients']==two['marginal_coefficients']
    for legs in ('2','3'):
        a,b=one['parlays'][legs],two['parlays'][legs]
        assert a['coefficients']==b['coefficients']
        assert a['test_groups_sha256']==b['test_groups_sha256']
        assert a['earlier_joint_calibrator']['metrics']!=b['earlier_joint_calibrator']['metrics']
        assert not a['approved'] and a['executable_price'] is None and a['EV'] is None


def test_published_real_archive_report_has_season_tests_and_never_approves():
    report=load_report();assert report is not None
    assert report['approved_joint_models']==report['approved_models']==report['provider_requests']==0
    assert not report['current_forecasts_enabled'] and not report['mixed_sport_joint_validated']
    assert len(report['reports']['NBA']['folds'])==2
    assert report['reports']['MLB']['folds'][0]['test_n']==2426
    for r in report['reports'].values():
        for f in r['folds']:
            assert f['marginal_fit_end']<f['joint_fit_start']<f['test_start']
            for p in f['parlays'].values():
                assert p['test_n']>=300 and not p['approved']
                assert p['executable_price'] is p['EV'] is None
