from datetime import datetime, timedelta
from dataclasses import replace
from zoneinfo import ZoneInfo
import sqlite3
import pytest
import requests
from conftest import NOW
from intelligence.pipeline import Analysis, publish_current
from intelligence.performance import metrics, breakdown
from intelligence.notifications import format_digest, send_telegram
from intelligence.assistant import answer
import telegram_alerts


def test_immutable_forward_ledger_settlement_and_losing_results(store,opportunity):
    first=store.publish(opportunity,now=NOW)
    assert store.publish(opportunity,now=NOW)==first
    second=store.publish(replace(opportunity,quote=replace(opportunity.quote,event_id='second')),now=NOW)
    assert len(store.records())==2
    store.settle(first,'win','Home 100–90','https://test.example/result',1.8,NOW+timedelta(days=2),closing_source='https://test.example/closing',closing_observed_at=NOW.isoformat())
    store.settle(second,'loss','Home 90–100','https://test.example/result',None,NOW+timedelta(days=2))
    with store.connect() as db:
        with pytest.raises(sqlite3.IntegrityError): db.execute('DELETE FROM publications')
        with pytest.raises(sqlite3.IntegrityError): db.execute("UPDATE publications SET at='bad'")
        with pytest.raises(sqlite3.IntegrityError): db.execute('DELETE FROM settlements')
    with pytest.raises(sqlite3.IntegrityError): store.settle(first,'loss','new result','test',now=NOW+timedelta(days=2))
    summary=metrics(store.records())
    assert summary['win_rate']==.5
    assert summary['pnl_units']==pytest.approx(-.1)
    assert summary['roi']==pytest.approx(-.05)
    assert summary['max_drawdown_units']>=1.
    assert summary['closing_line_value']==pytest.approx(1.9/1.8-1)
    assert summary['brier'] is not None and summary['log_loss'] is not None
    assert 'NBA' in breakdown(store.records(),'sport')
    assert store.records('backtest')==[]


def test_no_invented_metrics(store):
    result=metrics(store.records())
    assert result['win_rate'] is None and result['roi'] is None and result['pnl_units'] is None


def test_settlement_requires_source_and_existing_prediction(store,opportunity):
    with pytest.raises(ValueError): store.settle('missing','win','result','')
    with pytest.raises(ValueError): store.settle('missing','win','result','test-source')


def test_budget_and_delivery_claim_are_durable(tmp_path):
    from intelligence.storage import Store
    store=Store(tmp_path/'durable.sqlite3')
    assert store.reserve(2,3,NOW)
    other=Store(tmp_path/'durable.sqlite3')
    assert not other.reserve(2,3,NOW)
    assert store.claim_delivery('2026-10-15',NOW)
    assert not other.claim_delivery('2026-10-15',NOW)


def test_digest_uses_current_qualified_evidence_only(opportunity):
    analysis=Analysis(opportunities=[opportunity])
    text=format_digest(analysis,'2026-10-15',now=NOW)
    assert 'decimal 1.90' in text
    assert 'estimated EV' in text and 'Last provider update' in text
    assert 'No qualifying parlay opportunities identified today.' in text
    assert 'Soccer singles' in text and 'MLB singles' in text
    assert len(text)<4096
    stale=replace(opportunity,quote=replace(opportunity.quote,suspended=True))
    assert 'decimal 1.90' not in format_digest(Analysis(opportunities=[stale]),'2026-10-15',now=NOW)


def test_telegram_transport_redacts_token_on_failure():
    class Session:
        def post(self,*args,**kwargs): raise requests.Timeout('botTEST_SECRET')
    with pytest.raises(RuntimeError,match='uncertain') as e: send_telegram('TEST_SECRET','test','text',Session())
    assert 'TEST_SECRET' not in str(e.value)


def test_no_llm_calls_and_grounded_answers(opportunity):
    assert 'No current opportunities' in answer('Best picks?',Analysis(),now=NOW)
    assert '1.90' in answer('best NBA picks',Analysis(opportunities=[opportunity]),now=NOW)
    assert 'not connected' in answer('NBA props and injuries',Analysis(),now=NOW)
    assert 'No qualifying parlay' in answer('parlays?',Analysis(),now=NOW)


def test_toronto_schedule_and_pending_send_survive_restart(tmp_path,monkeypatch):
    monkeypatch.setattr(telegram_alerts,'STATE_PATH',tmp_path/'state.json')
    monkeypatch.delenv('GITHUB_EVENT_NAME',raising=False)
    toronto=ZoneInfo('America/Toronto')
    assert not telegram_alerts.reserve(datetime(2026,10,15,8,tzinfo=toronto))
    assert telegram_alerts.reserve(datetime(2026,10,15,9,tzinfo=toronto))
    assert not telegram_alerts.reserve(datetime(2026,10,15,10,tzinfo=toronto))
    assert not telegram_alerts.reserve(datetime(2026,10,16,9,tzinfo=toronto))
    telegram_alerts.write_state({'last_sent_date':'2026-10-15'})
    assert telegram_alerts.reserve(datetime(2026,10,16,9,tzinfo=toronto))
    telegram_alerts.STATE_PATH.write_text('malformed')
    with pytest.raises(RuntimeError): telegram_alerts.reserve(datetime(2026,10,17,9,tzinfo=toronto))


def test_expiry_rechecked_at_publication(store,opportunity):
    from datetime import timedelta
    assert publish_current(Analysis(opportunities=[opportunity]),store,NOW+timedelta(minutes=10))==[]
    assert store.records()==[]


def test_archived_ledger_restores_across_fresh_runners(tmp_path,store,opportunity):
    from intelligence.ledger import archive,restore
    from intelligence.storage import Store
    identifier=store.publish(opportunity,now=NOW)
    store.settle(identifier,'loss','Verified final result','https://test.example/result',now=NOW+timedelta(days=2))
    archive(store,tmp_path/'archive')
    archive(store,tmp_path/'archive')
    assert len((tmp_path/'archive'/'predictions.jsonl').read_text().splitlines())==1
    other=Store(tmp_path/'fresh.sqlite3')
    restore(other,tmp_path/'archive')
    assert other.records()[0]['outcome']=='loss'
    assert len(other.records())==1


def test_archive_tampering_is_detected(tmp_path,store,opportunity):
    import json
    from intelligence.ledger import archive,restore
    store.publish(opportunity,now=NOW)
    archive(store,tmp_path/'archive')
    path=tmp_path/'archive'/'predictions.jsonl'
    row=json.loads(path.read_text())
    row['payload']['quote']['odds']=99.
    path.write_text(json.dumps(row)+'\n')
    with pytest.raises(ValueError,match='alteration'): archive(store,tmp_path/'archive')
    with pytest.raises(ValueError,match='differs'): restore(store,tmp_path/'archive')


def test_unvalidated_forward_publication_is_rejected(store,opportunity):
    with pytest.raises(ValueError,match='qualifying'):
        store.publish(replace(opportunity,estimate=replace(opportunity.estimate,validated=False)),now=NOW)


def test_future_event_cannot_be_marked_won(store,opportunity):
    identifier=store.publish(opportunity,now=NOW)
    with pytest.raises(ValueError,match='before the event'): store.settle(identifier,'win','asserted score','test-source',now=NOW)
