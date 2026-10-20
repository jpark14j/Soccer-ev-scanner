"""Synthetic pregame records/results. Never live performance evidence."""
from datetime import timedelta
from copy import deepcopy
from dataclasses import replace
import json,sqlite3
import pytest
from conftest import NOW
from intelligence.statistics_forward import record,reconcile,ensure
from intelligence.prediction_accuracy import summary,saved_for_display
from intelligence.openliga import save,current
from test_current_statistics import season


def row(event,n,now):
    r={'fixture_id':event.fixture_id,'event':event.home_name+' vs '+event.away_name,
        'home':event.home_name,'away':event.away_name,'league':'Bundesliga','sport':'Soccer',
        'kickoff':event.kickoff,'forecast_at':now.isoformat(),'source_observed_at':now.isoformat(),
        'model_version':'SYNTHETIC-accuracy-'+str(n),'evidence_id':'synthetic-only',
        'research_eligible':True,'approved':False,'validated':False,'probability':.6,'lower':.4,'upper':.8,
        'market':'h2h','selection':event.home_name,'point':None}
    if n>1:
        r['legs']=[{k:r[k] for k in ('market','selection','point')}, {'market':'btts','selection':'Yes','point':None}]
        if n==3:r['legs'].append({'market':'totals','selection':'Over','point':2.5})
        r['joint_probability']=.4;r['joint_validated']=False
    return r


def prepare(store):
    raw=season(NOW)
    for i in range(3):raw[i].update(matchIsFinished=False,matchResults=[],matchDateTimeUTC=(NOW+timedelta(days=(1,2,5)[i])).isoformat())
    save(store,json.dumps(raw).encode(),'Bundesliga',NOW.isoformat(),NOW)
    events=current(store,'Bundesliga',NOW)[0];predictions=[]
    for e in events[:3]:
        for n in (1,2,3):predictions.append(row(e,n,NOW))
    record(store,predictions,NOW)
    return raw,predictions


def test_verified_results_settle_original_singles_and_all_parlay_legs_once(store):
    raw,predictions=prepare(store)
    assert all(v['accuracy'] is None for v in summary(store,NOW)['formats'].values())
    # One fixture wins every leg, one loses the winner leg, one stays pending.
    later=NOW+timedelta(days=3,hours=4)
    for i,h,a in [(0,2,1),(1,0,1)]:
        raw[i].update(matchIsFinished=True,matchResults=[{'resultTypeKind':'After90Minutes','pointsTeam1':h,'pointsTeam2':a}])
    save(store,json.dumps(raw).encode(),'Bundesliga',later.isoformat(),later)
    assert reconcile(store,later)==6 and reconcile(store,later)==0
    result=summary(store,later)
    for n in (1,2,3):
        r=result['formats'][n]
        assert r['correct']==1 and r['settled']==2 and r['pending']==1 and r['accuracy']==50.
        assert r['Experimental']['accuracy']==50. and r['Validated']['accuracy'] is None
    # A repeated pregame refresh is a preserved version, not another decision.
    changed=deepcopy(predictions[0]);changed.update(probability=.61,forecast_at=(NOW+timedelta(minutes=1)).isoformat())
    record(store,[changed],NOW+timedelta(minutes=1))
    assert summary(store,later)['formats'][1]['settled']==2
    with store.connect() as db:
        assert db.execute('SELECT count(*) FROM statistics_forecasts').fetchone()[0]==10
        with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM statistics_forecasts')


def test_display_uses_the_original_saved_probability_and_never_records_on_browse(store):
    _,rs=prepare(store);shown=saved_for_display(store,rs,NOW)
    assert len(shown)==9 and all(r['record_id'] and r['recorded_at']==NOW.isoformat() for r in shown)
    numerical=deepcopy(rs[0]);numerical['probability']+=1e-14
    assert saved_for_display(store,[numerical],NOW)[0]['probability']==rs[0]['probability']
    numerical['probability']+=.01
    assert not saved_for_display(store,[numerical],NOW)
    newer=deepcopy(rs[0]);newer['source_observed_at']=(NOW+timedelta(minutes=1)).isoformat()
    assert not saved_for_display(store,[newer],NOW+timedelta(minutes=1))
    assert not saved_for_display(store,rs,NOW+timedelta(days=10))
    with store.connect() as db:assert db.execute('SELECT count(*) FROM statistics_forecasts').fetchone()[0]==9


@pytest.mark.parametrize('kind',['void','unresolved','missing_provenance','backtest','postgame'])
def test_ineligible_outcomes_and_forecasts_do_not_enter_denominator(store,kind):
    _,rs=prepare(store);r=rs[0];ensure(store)
    with store.connect() as db:
        key=db.execute('SELECT id FROM statistics_forecasts WHERE payload LIKE ?',('%SYNTHETIC-accuracy-1%',)).fetchone()[0]
        out={'all_selections_won':True,'source':'SYNTHETIC-only','source_sha256':'a'*64,
            'source_observed_at':(NOW+timedelta(days=2)).isoformat()}
        if kind in ('void','unresolved'):out['settlement_status']=kind
        if kind=='missing_provenance':out.pop('source_sha256')
        if kind in ('backtest','postgame'):
            db.execute('DROP TRIGGER statistics_forecasts_no_update')
            if kind=='backtest':
                r['origin']='backtest';db.execute('UPDATE statistics_forecasts SET payload=? WHERE id=?',(json.dumps(r),key))
            else:db.execute('UPDATE statistics_forecasts SET at=kickoff WHERE id=?',(key,))
        db.execute('INSERT INTO statistics_outcomes VALUES(?,?,?)',(key,(NOW+timedelta(days=2)).isoformat(),json.dumps(out)))
    assert summary(store,NOW+timedelta(days=5))['formats'][1]['settled']==0


def test_committed_legacy_parlay_labels_are_accuracy_only_and_uncommitted_rows_excluded(store):
    from intelligence.publication_journal import ensure as journal
    journal(store)
    q={'market':'h2h','selection':'Synthetic Home','point':None,'participant':'',
        'commence_time':(NOW+timedelta(days=1)).isoformat()}
    source={'competition_id':'soccer:de:bundesliga','season':'2026-27','home_id':'synthetic-home','away_id':'synthetic-away'}
    p={'legs':[{'quote':q,'source_fixture':source,'estimate':{'model_version':'synthetic-model'}},
        {'quote':q|{'market':'btts','selection':'Yes'},'source_fixture':source,'estimate':{'model_version':'synthetic-model'}}]}
    end=NOW+timedelta(days=2)
    proof={'snapshot_sha256':'a'*64,'verified_result':{'observed_at':end.isoformat()}}
    label={'outcome':'loss','leg_fractions':[[1,0,0],[0,0,1]],'provenance':[proof,proof]}
    with store.connect() as db:
        for key in ('first','repeat','not-committed'):
            db.execute('INSERT INTO research_publications VALUES(?,?,?)',(key,NOW.isoformat(),json.dumps(p)))
            db.execute('INSERT INTO research_publication_labels VALUES(?,?,?)',(key,end.isoformat(),json.dumps(label)))
        db.execute('INSERT INTO shared_publication_receipts VALUES(?,?,?)',('first',NOW.isoformat(),2))
        db.execute('INSERT INTO shared_publication_receipts VALUES(?,?,?)',('repeat',(NOW+timedelta(minutes=1)).isoformat(),3))
    report=summary(store,end)
    assert report['unique_predictions']==1
    assert report['formats'][2]['settled']==1 and report['formats'][2]['correct']==0
    assert report['formats'][2]['accuracy']==0.
    assert all(k not in json.dumps(report).lower() for k in ('profit','roi','bankroll'))


def test_rescheduled_prediction_is_not_suppressed_by_unsettled_original_kickoff(store):
    _,rs=prepare(store);r=deepcopy(rs[0]);r['kickoff']=(NOW+timedelta(days=2)).isoformat()
    key=record(store,[r],NOW)[0];settled=NOW+timedelta(days=3)
    outcome={'all_selections_won':True,'source':'SYNTHETIC rescheduled final','source_sha256':'a'*64,'source_observed_at':settled.isoformat()}
    with store.connect() as db:db.execute('INSERT INTO statistics_outcomes VALUES(?,?,?)',(key,settled.isoformat(),json.dumps(outcome)))
    report=summary(store,settled)['formats'][1]
    assert report['settled']==1 and report['correct']==1 and report['pending']==3 and report['accuracy']==100.


def test_original_experimental_classification_is_not_rewritten_after_later_approval(store):
    _,rs=prepare(store);r=deepcopy(rs[0]);r['validated']=True
    # Serialized future-validation contract fixture only; production recorder
    # still rejects approved forecasts under the existing experimental protocol.
    with store.connect() as db:
        db.execute('INSERT INTO statistics_forecasts VALUES(?,?,?,?)',('later-approved-version',(NOW+timedelta(minutes=1)).isoformat(),r['kickoff'],json.dumps(r)))
        key=db.execute('SELECT id FROM statistics_forecasts WHERE payload LIKE ? ORDER BY at LIMIT 1',('%SYNTHETIC-accuracy-1%',)).fetchone()[0]
        settled=NOW+timedelta(days=2)
        o={'all_selections_won':True,'source':'SYNTHETIC','source_sha256':'a'*64,'source_observed_at':settled.isoformat()}
        db.execute('INSERT INTO statistics_outcomes VALUES(?,?,?)',(key,settled.isoformat(),json.dumps(o)))
    report=summary(store,settled)['formats'][1]
    assert report['Experimental']['settled']==1 and report['Validated']['settled']==0
