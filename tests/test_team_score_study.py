"""Synthetic leakage and probability-coherence contracts, not performance proof."""
from copy import deepcopy
import numpy as np
import pandas as pd
import pytest
from intelligence.team_score_study import features,fit,means,labels,probabilities,count_mass,SPEC


def history():
    rows=[]
    for i in range(160):
        for j in range(2):
            rows.append({'game_id':f'synthetic-{i}-{j}','date':pd.Timestamp('2020-01-01')+pd.Timedelta(days=i),
                'HomeTeam':'H'+str(j),'AwayTeam':'A'+str(j),'FTHG':105+i%8,'FTAG':95+i%6})
    return pd.DataFrame(rows)


def test_date_block_features_never_use_current_or_future_final_scores():
    h=history();first=features(h,'NBA');changed=h.copy();cut=pd.Timestamp('2020-04-01')
    changed.loc[changed.date>=cut,['FTHG','FTAG']]=[150,80]
    second=features(changed,'NBA')
    one={r['game_id']:r for r in first};two={r['game_id']:r for r in second}
    for r in first:
        if r['date']<=cut.date().isoformat():assert r['x']==two[r['game_id']]['x']
    assert any(r['x']!=two[r['game_id']]['x'] for r in first if r['date']>cut.date().isoformat())


def test_joint_score_events_are_coherent_not_multiplied():
    residuals=np.tile(np.array([[-8,-2],[10,5],[-2,-10],[15,20],[-12,8]],dtype=float),(30,1))
    result=probabilities(np.array([[118.,112.]]),residuals,'NBA',SPEC['NBA'],'paired_residual')[0]
    assert np.all((0<=result)&(result<=1))
    assert result[3]<=result[2]<=min(result[0],result[1])
    assert result[2]!=pytest.approx(result[0]*result[1])
    for dispersion in (0.,.2):
        assert count_mass(4.5,dispersion).sum()==pytest.approx(1.,abs=1e-6)
    value=probabilities(np.array([[4.5,4.]]),residuals,'MLB',SPEC['MLB'],'negative_binomial',.2)[0]
    assert value[3]<=value[2]<=min(value[0],value[1])


def test_reviewed_athletics_rename_keeps_earlier_franchise_history_without_changing_archive():
    h=history();h.loc[h.HomeTeam=='H0','HomeTeam']='OAK'
    renamed=h.copy();mask=(renamed.date>='2020-04-01')&(renamed.HomeTeam=='OAK');renamed.loc[mask,'HomeTeam']='ATH'
    a=features(h,'MLB');b=features(renamed,'MLB')
    assert [r['game_id'] for r in a]==[r['game_id'] for r in b]
    assert [r['x'] for r in a]==[r['x'] for r in b]
    assert 'ATH' in set(renamed.HomeTeam)  # Input source is never rewritten.


def test_score_study_report_is_hash_bound_unapproved_and_has_real_sample_sizes():
    from intelligence.team_score_study import load_report
    report=load_report();assert report is not None
    assert report['reports']['NBA']['partitions']['test']['n']>=1200
    assert report['reports']['MLB']['partitions']['test']['n']>=2400
    for r in report['reports'].values():
        assert not r['approved'] and not r['current_forecasts_enabled'] and not r['replaces_incumbent']
        p=r['partitions'];assert p['fit']['end']<p['residual']['start']<p['calibration']['start']<p['test']['start']
