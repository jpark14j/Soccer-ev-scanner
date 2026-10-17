from dataclasses import asdict,replace
from datetime import timedelta
import json,sqlite3
import pytest
from conftest import NOW
from intelligence.domain import digest
from intelligence.pipeline import Analysis
from intelligence.processing import (record_shadow_forecasts,process_cycle,outcome_for,shadow_statistics)
from intelligence.storage import Store
from intelligence.persistence import backup_store,storage_status
from intelligence.results import ensure_table


def final(q,now):
    return {'provider':q.provider,'league':q.league,'event_id':q.event_id,'home':q.home,'away':q.away,
        'commence_time':q.commence_time,'home_score':110,'away_score':100,
        'observed_at':now.isoformat(),'received_at':now.isoformat()}


def save_result(store,row):
    ensure_table(store)
    with store.connect() as db:
        db.execute('INSERT INTO observed_results VALUES(?,?,?)',(digest(row),row['league'],json.dumps(row)))


def test_shadow_forecasts_are_pregame_immutable_and_separate_from_bet_ledger(store,quote,estimate):
    analysis=Analysis(quotes=[quote],estimates={quote.id:replace(estimate,validated=False)})
    assert record_shadow_forecasts(analysis,store,NOW)==1
    assert record_shadow_forecasts(analysis,store,NOW)==0
    assert record_shadow_forecasts(analysis,store,NOW+timedelta(days=2))==0
    assert store.records()==[] and shadow_statistics(store)['betting_roi'] is None
    with store.connect() as db:
        with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM shadow_forecasts')


def test_completed_results_score_shadow_targets_but_not_unverified_operator_bets(store,quote,estimate,opportunity):
    record_shadow_forecasts(Analysis(quotes=[quote],estimates={quote.id:estimate}),store,NOW)
    store.publish(opportunity,now=NOW)
    later=NOW+timedelta(days=2);save_result(store,final(quote,later))
    class Provider:pass
    report=process_cycle(store,Provider(),['NBA'],0,now=later)
    assert report['settled']==0 and report['blocked']
    assert report['shadow_labels_recorded']==1 and store.records()[0]['outcome'] is None
    stats=shadow_statistics(store)
    assert stats['scored_forecast_labels']==1 and stats['binary_brier']==pytest.approx((1-.65)**2)
    assert stats['betting_roi'] is None


def test_reviewed_exact_operator_rules_allow_append_only_settlement(store,quote,opportunity,tmp_path):
    store.publish(opportunity,now=NOW);later=NOW+timedelta(days=2);save_result(store,final(quote,later))
    rules={'rules':[{'bookmaker':quote.bookmaker,'sport':'NBA','market':'h2h','verified':True,
        'score_scope':'full_event_final_including_extras','source':'https://example.test/rules',
        'provider_scope_source':'https://example.test/provider','reviewed_at':NOW.isoformat(),
        'expires_at':(later+timedelta(days=10)).isoformat()}]}
    path=tmp_path/'rules.json';path.write_text(json.dumps(rules))
    report=process_cycle(store,object(),['NBA'],0,now=later,rules_path=path)
    assert report['settled']==1 and store.records()[0]['outcome']=='win'
    assert process_cycle(store,object(),['NBA'],0,now=later,rules_path=path)['settled']==0


def test_conflicting_scores_and_unknown_soccer_scope_stay_unsettled(store,quote,estimate):
    later=NOW+timedelta(days=2)
    record_shadow_forecasts(Analysis(quotes=[quote],estimates={quote.id:estimate}),store,NOW)
    row=final(quote,later);save_result(store,row);save_result(store,{**row,'home_score':90})
    assert process_cycle(store,object(),['NBA'],0,now=later)['shadow_labels_recorded']==0
    q=replace(quote,sport='Soccer',league='Premier League')
    outcome,reason=outcome_for(asdict(q),final(q,later),{'score_scope':'regulation_90'})
    assert outcome is None and 'scope is unverified' in reason


def test_exact_scope_push_supported_quarter_and_player_settlement_blocked(quote):
    later=NOW+timedelta(days=2);row=final(quote,later);rule={'score_scope':'full_event_final_including_extras'}
    total=replace(quote,market='totals',selection='Over',point=210.)
    assert outcome_for(asdict(total),row,rule)[0]=='push'
    assert outcome_for(asdict(replace(total,point=210.25)),row,rule)[0] is None
    assert outcome_for(asdict(replace(total,market='player_points')),row,rule)[0] is None


def test_consistent_private_backup_preserves_ledger_quota_and_shadows(store,quote,estimate,opportunity,tmp_path):
    store.publish(opportunity,now=NOW);store.reserve(9,9,NOW)
    record_shadow_forecasts(Analysis(quotes=[quote],estimates={quote.id:estimate}),store,NOW)
    path=tmp_path/'backup.sqlite3';backup_store(store,path)
    restored=Store(path)
    assert len(restored.records())==1 and shadow_statistics(restored)['private_forecasts']==1
    assert not restored.reserve(1,9,NOW)
    assert storage_status(restored)['redeployment_persistence_verified'] is False
    with pytest.raises(ValueError):backup_store(store,path)


def test_pending_research_automatically_collects_final_scores_within_existing_cap(store,quote,estimate,monkeypatch):
    record_shadow_forecasts(Analysis(quotes=[quote],estimates={quote.id:estimate}),store,NOW)
    later=NOW+timedelta(days=2)
    monkeypatch.setattr('intelligence.results.utcnow',lambda:later)
    class Provider:
        calls=0
        def scores(self,league,days_from):
            self.calls+=1
            assert store.reserve(2,2,later)
            return {'received_at':later.isoformat(),'data':[{'id':quote.event_id,
                'sport_key':'basketball_nba','completed':True,'home_team':quote.home,'away_team':quote.away,
                'commence_time':quote.commence_time,'last_update':later.isoformat(),
                'scores':[{'name':quote.home,'score':'110'},{'name':quote.away,'score':'100'}]}]}
    provider=Provider()
    report=process_cycle(store,provider,['NBA'],2,now=later)
    assert provider.calls==1 and report['collection']['NBA']['completed_records']==1
    assert report['shadow_labels_recorded']==1 and not store.reserve(1,2,later)
