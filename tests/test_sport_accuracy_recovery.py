"""SYNTHETIC settlement and transport failures; not live performance evidence."""
from copy import deepcopy
from datetime import timedelta
import json
from unittest.mock import patch
import pytest
from conftest import NOW
from intelligence.domain import parse_time
from intelligence.statistics_forward import record
from intelligence.prediction_accuracy import summary,sport_classification
from test_prediction_accuracy import prepare


def settled_sports(store):
    _,templates=prepare(store)
    # Reuse contract shapes, never scores or claimed real forecasts.
    rows=[]
    for sport in ('Soccer','NBA','MLB','Mixed sports'):
        for n in (1,2,3):
            if sport=='Mixed sports' and n==1:continue
            r=deepcopy(templates[n-1]);r.update(sport=sport,fixture_id='synthetic-'+sport+str(n),
                model_version='synthetic-sport-accuracy-'+sport+str(n))
            if sport=='Mixed sports':
                for i,leg in enumerate(r['legs']):
                    leg.update(sport=('NBA','Soccer','MLB')[i],fixture_id='synthetic-leg-'+str(i),kickoff=r['kickoff'])
            key=record(store,[r],NOW)[0];rows.append((sport,n,r))
            end=NOW+timedelta(days=2)
            o={'all_selections_won':sport=='MLB' or sport=='Soccer' and n!=2 or sport=='Mixed sports' and n==2,
                'source':'SYNTHETIC fixture only','source_sha256':'a'*64,'source_observed_at':end.isoformat()}
            with store.connect() as db:db.execute('INSERT INTO statistics_outcomes VALUES(?,?,?)',(key,end.isoformat(),json.dumps(o)))
    return rows


def test_accuracy_is_sport_specific_with_mixed_parlays_separate_and_no_refresh_inflation(store):
    rows=settled_sports(store);later=NOW+timedelta(days=3)
    for sport in ('Soccer','NBA','MLB','Mixed sports'):
        report=summary(store,later,sport=sport)
        for n in (1,2,3):
            item=report['formats'][n]
            if sport=='Mixed sports' and n==1:
                assert item['settled']==0 and item['accuracy'] is None;continue
            assert item['settled']==1
            expected=100. if sport=='MLB' or sport=='Soccer' and n!=2 or sport=='Mixed sports' and n==2 else 0.
            assert item['accuracy']==expected and item['Experimental']['accuracy']==expected
            assert item['Validated']['settled']==0
    old=summary(store,later,sport='NBA')
    r=deepcopy(next(r for sport,n,r in rows if sport=='NBA' and n==1));r['probability']=.61
    r['forecast_at']=(NOW+timedelta(minutes=1)).isoformat()
    record(store,[r],NOW+timedelta(minutes=1))
    assert summary(store,later,sport='NBA')==old
    assert sport_classification({'sport':'NBA','legs':[{'sport':'NBA'},{'sport':'MLB'}]})=='Mixed sports'
    assert sport_classification({'sport':'NBA','legs':[{'sport':None}]})=='Unclassified'
    with pytest.raises(ValueError):summary(store,later,sport='guessed-sport')


def test_partial_worker_continues_other_sports_and_settlements_without_redating_failed_source(store):
    from intelligence.free_statistics_worker import update
    from intelligence.openliga import current
    from test_current_statistics import season
    raw=json.dumps(season(NOW)).encode()
    with patch('intelligence.fixture_research.collect',return_value={'forecasts':[]}),patch('intelligence.current_score_research.candidates',return_value=[]):
        update(store,NOW,lambda:(raw,NOW.isoformat()))
        original=current(store,'Bundesliga',NOW)
        later=NOW+timedelta(hours=3,minutes=1)
        def failed():raise ValueError('synthetic confidential transport detail')
        with patch('intelligence.free_results.refresh',return_value={'sources':{'NBA':{'ok':True}},'public_results_requests':1}) as other,\
             patch('intelligence.statistics_forward.reconcile',return_value=0) as settlement:
            result,_=update(store,later,failed,extra_fetch=lambda url:None)
            other.assert_called_once();settlement.assert_called_once()
        assert result['state']=='Partial free-statistics update' and result['public_results_requests']==2
        assert result['source_observed_at']==NOW.isoformat() and current(store,'Bundesliga',later)==original
        assert 'confidential' not in str(result)
        # A persisted failure limits retry attempts, including after cache expiry.
        expired=NOW+timedelta(hours=6,seconds=1)
        with patch('intelligence.free_results.refresh',return_value={'sources':{},'public_results_requests':0}):
            expired_report,_=update(store,expired,failed,extra_fetch=lambda url:None)
        assert not expired_report['bundesliga_source_status']['cached_inputs_valid']
        assert expired_report['source_observed_at'] is None and expired_report['public_results_requests']==0
        recovered=NOW+timedelta(hours=6,minutes=2)
        fresh=json.dumps(season(recovered)).encode()
        result,_=update(store,recovered,lambda:(fresh,recovered.isoformat()))
        assert result['bundesliga_source_status']['cached_inputs_valid']
        assert result['source_observed_at']==recovered.isoformat() and result['public_results_requests']==1


def test_accuracy_sport_selector_keeps_exactly_three_metrics(tmp_path):
    from streamlit.testing.v1 import AppTest
    from intelligence.storage import Store
    path=tmp_path/'accuracy.sqlite3';store=Store(path);settled_sports(store)
    # All synthetic outcomes are already past at the actual UI test clock.
    script=f'''from types import SimpleNamespace
from intelligence.storage import Store
from intelligence.consumer_ui import render_performance
render_performance(SimpleNamespace(store=Store({str(path)!r})))'''
    app=AppTest.from_string(script).run()
    for sport in ('NBA','MLB','Mixed sports','Soccer'):
        app.radio[0].set_value(sport).run()
        assert not app.exception and len(app.metric)==3
        assert [m.label for m in app.metric]==['Singles Accuracy (%)','2-Leg Parlay Accuracy (%)','3-Leg Parlay Accuracy (%)']
        assert any('1/1 correct' in c.value or '0/1 correct' in c.value for c in app.caption)
        if sport=='NBA':assert all(m.value=='0.0%' for m in app.metric)
        if sport=='MLB':assert all(m.value=='100.0%' for m in app.metric)
