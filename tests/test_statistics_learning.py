"""Synthetic prospective-learning lifecycle; never historical winning claims."""
from datetime import timedelta
import json
import pytest
from conftest import NOW
from intelligence.domain import digest
from intelligence.statistics_forward import ensure,monitoring
from intelligence.statistics_learning import lock,update,source_rows


def add(store,day,outcome=None):
    at=NOW+timedelta(days=day);kick=at+timedelta(hours=4)
    r={'fixture_id':f'synthetic-{day}','event':'Synthetic Home vs Synthetic Away','home':'Synthetic Home','away':'Synthetic Away',
        'model_version':'synthetic-model','league':'Bundesliga','market':'btts','selection':'Yes','point':None,
        'probability':.6,'lower':.45,'upper':.75,'forecast_at':at.isoformat(),'kickoff':kick.isoformat()}
    key=digest(r)
    with store.connect() as db:
        db.execute('INSERT INTO statistics_forecasts VALUES(?,?,?,?)',(key,at.isoformat(),kick.isoformat(),json.dumps(r)))
        if outcome is not None:
            value={'all_selections_won':outcome,'source_observed_at':(kick+timedelta(hours=2)).isoformat()}
            db.execute('INSERT INTO statistics_outcomes VALUES(?,?,?)',(key,(kick+timedelta(hours=2)).isoformat(),json.dumps(value)))
    return key


def test_prelock_data_is_retained_but_cannot_train_new_challengers(store):
    ensure(store)
    for i in range(8):add(store,i,i%2==0)
    result=update(store,NOW+timedelta(days=10))
    assert result['new_challengers']==0 and not result['automatic_promotion']
    assert len(source_rows(store))==8 and monitoring(store)['unique_pregame_decisions']==8


def test_locked_training_future_capture_and_one_evaluation_without_promotion(store,tmp_path,monkeypatch):
    policy={'training_minimum':2,'calibration_minimum':2,'partition_minimum_day_blocks':1,
        'blend_grid':[0.,.5,1.],'test_days':2,'test_minimum':1,'test_minimum_day_blocks':1,
        'bootstrap_resamples':50,'seed':1}
    path=tmp_path/'synthetic-test-policy.json';path.write_text(json.dumps(policy))
    monkeypatch.setattr('intelligence.statistics_learning.POLICY',path)
    lock(store,NOW-timedelta(days=1));ensure(store)
    for i in range(4):add(store,i,i%2==0)
    created=update(store,NOW+timedelta(days=5))
    assert created['new_challengers']==1
    key=add(store,6)
    captured=update(store,NOW+timedelta(days=6,hours=1))
    assert captured['new_pregame_challenger_forecasts']==1
    with store.connect() as db:
        value={'all_selections_won':False,'source_observed_at':(NOW+timedelta(days=6,hours=6)).isoformat()}
        db.execute('INSERT INTO statistics_outcomes VALUES(?,?,?)',(key,value['source_observed_at'],json.dumps(value)))
    evaluated=update(store,NOW+timedelta(days=12))
    assert evaluated['new_evaluations']==1 and not evaluated['automatic_promotion']
    assert update(store,NOW+timedelta(days=13))['new_evaluations']==0
    with store.connect() as db:
        result=json.loads(db.execute('SELECT payload FROM statistics_challenger_evaluations').fetchone()[0])
        assert not result['approved'] and result['report']['metrics']['n']==1
        with pytest.raises(Exception):db.execute('DELETE FROM statistics_challengers')


def test_monitoring_uses_first_snapshot_instead_of_counting_repeated_refreshes(store):
    ensure(store);key=add(store,0,True)
    with store.connect() as db:
        r=json.loads(db.execute('SELECT payload FROM statistics_forecasts WHERE id=?',(key,)).fetchone()[0])
        r['forecast_at']=(NOW+timedelta(hours=1)).isoformat();r['probability']=.7
        db.execute('INSERT INTO statistics_forecasts VALUES(?,?,?,?)',(digest(r),r['forecast_at'],r['kickoff'],json.dumps(r)))
    report=monitoring(store)
    assert report['recorded_snapshots']==2 and report['unique_pregame_decisions']==1
    assert report['groups'][0]['brier']==pytest.approx(.16) and report['groups'][0]['paper_roi'] is None
