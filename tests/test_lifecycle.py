from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import pytest
from conftest import NOW
from intelligence.domain import digest
from intelligence.lifecycle import (register_artifact,active_champion,change_champion,
    promotion_blockers,drift_report,registry_status)
from intelligence.worker import run_cycle


def synthetic_report():
    report={'sport':'NBA','league':'NBA','market':'h2h','model_version':'synthetic-only',
        'test_n':250,'calibration_n':250,'data_source':'explicit synthetic test fixture',
        'baseline_timing_verified':True,'beats_market_with_uncertainty':True,'calibration_gap':.02,
        'generated_at':NOW.isoformat(),'expires_at':(NOW+timedelta(days=10)).isoformat(),
        'data_end':(NOW-timedelta(days=2)).isoformat(),'code_sha256':'synthetic-code','data_sha256':'synthetic-data'}
    report['evidence_id']=digest(report)
    return report


def test_candidate_registration_never_promotes_and_content_hash_is_required(store):
    report=synthetic_report();identifier=register_artifact(store,report)
    assert len(identifier)==64 and active_champion(store,'NBA','h2h') is None
    assert registry_status(store)['automatic_promotion'] is False
    report['test_n']=99999
    with pytest.raises(ValueError):register_artifact(store,report)


def test_promotion_requires_reviewed_fresh_evidence_and_rollback_history(store):
    report=synthetic_report();identifier=register_artifact(store,report)
    with pytest.raises(ValueError,match='Fresh independent'):
        change_champion(store,identifier,{},'https://example.test/review',now=NOW)
    evidence={'fresh_unseen_period_verified':True,'commercial_data_rights_verified':True,
        'operator_scope_verified':True,'forward_decisions':100,'paired_improvement_lower':.001,
        'verification_source':'https://example.test/independent-audit'}
    with pytest.raises(ValueError,match='previously approved'):
        change_champion(store,identifier,evidence,'https://example.test/review','rollback',NOW)
    change_champion(store,identifier,evidence,'https://example.test/review',now=NOW)
    assert active_champion(store,'NBA','h2h')['evidence_id']==report['evidence_id']
    assert promotion_blockers(report,evidence,NOW+timedelta(days=20))


def test_drift_uses_unique_forward_decisions_and_never_changes_models(opportunity):
    rows=[]
    for i in range(200):
        p=opportunity.to_dict();p['quote']['event_id']=str(i);p['estimate']['probability']=.9
        rows.append({'payload':p,'outcome':'win' if i<100 else 'loss',
            'at':(NOW+timedelta(minutes=i)).isoformat(),'settled_at':(NOW+timedelta(days=1,minutes=i)).isoformat()})
    report=drift_report(rows+rows)[0]
    assert report['unique_settled_events']==200 and report['status']=='review model drift'
    assert report['automatic_action']=='none'


def test_online_worker_requires_explicit_independent_configuration_before_network(store,monkeypatch):
    for name in ('RESEARCH_WORKER_ENABLED','RESEARCH_DURABLE_STORAGE_VERIFIED','RESEARCH_DATA_RIGHTS_VERIFIED'):
        monkeypatch.delenv(name,raising=False)
    with pytest.raises(ValueError,match='Online worker disabled'):
        run_cycle(store,['NBA'],offline=False)
    report=run_cycle(store,['NBA'],offline=True)
    assert report['mode']=='offline inspection' and report['paid_ai_requests']==0
    assert report['storage']['redeployment_persistence_verified'] is False


def test_manual_audit_workflow_cannot_run_on_main_or_make_data_calls():
    import yaml
    from pathlib import Path
    text=Path('.github/workflows/research_audit.yml').read_text();workflow=yaml.safe_load(text)
    assert 'development/verified-sports-intelligence' in workflow['jobs']['audit']['if']
    assert '--offline' in text and 'secrets.' not in text
    triggers=workflow.get('on',workflow.get(True))
    assert 'schedule' not in triggers


def test_champion_comparison_refuses_different_periods_or_sources():
    from intelligence.lifecycle import compare_challenger
    a={'sport':'NBA','league':'NBA','market':'h2h','data_sha256':'synthetic-a',
       'test_start':'2026-01-01','test_n':200,'metrics':{'brier':.4,'log_loss':.6}}
    b={**a,'data_sha256':'synthetic-b'}
    assert 'brier_change' not in compare_challenger(a,b)
    assert compare_challenger(a,a)['brier_change']==0
