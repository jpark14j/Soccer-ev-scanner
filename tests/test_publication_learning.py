"""Synthetic research records test accounting/learning; never claimed live picks."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from copy import deepcopy
from pathlib import Path
import json,math,sqlite3
import pytest
from intelligence.domain import utcnow,parse_time,digest
from intelligence.publication_journal import prepare,records,reconcile,performance,combined_outcome,overall
from intelligence.shared_state import hydrate_budgets
from intelligence.forward_testing import records as forward_records
from intelligence.processing import record_shadow_forecasts
from intelligence.research_top import select_top
from test_master_workflow import research_slate
from test_forward_evaluation import save_final


def committed(store,created,at):
    hydrate_budgets(store,{'budgets':[],'publication_receipts':[{'id':r['id'],'at':at.isoformat(),'generation':2} for r in created]})


def test_published_choices_dedup_prices_preserve_originals_and_never_invent_joint_ev(store,quote,monkeypatch):
    a=research_slate(store,quote,monkeypatch);record_shadow_forecasts(a,store)
    top=select_top(a,store);result=overall(top)
    assert result['winner'] is None and result['single'] and result['parlay']
    created=prepare(a,store,top);before=records(store)
    assert len(created)>=2 and not prepare(a,store,top)
    assert all(r['payload']['combined_odds'] is r['payload']['joint_probability'] is r['payload']['parlay_ev'] is None for r in before)
    assert performance(store)['published_committed_pregame']==0
    committed(store,created,utcnow());assert performance(store)['published_committed_pregame']==len(created)
    a.quotes=[replace(q,odds=q.odds+.02) for q in a.quotes]
    assert not prepare(a,store,top) and records(store)[0]['payload']==before[0]['payload']
    with store.connect() as db:
        with pytest.raises(sqlite3.IntegrityError,match='Immutable'):db.execute("UPDATE research_publications SET payload='{}'")
        with pytest.raises(sqlite3.IntegrityError,match='Immutable'):db.execute('DELETE FROM research_publications')


def test_reconcile_actual_model_source_contracts_counts_losses_and_blocks_parlay_roi(store,quote,monkeypatch):
    a=research_slate(store,quote,monkeypatch);record_shadow_forecasts(a,store);created=prepare(a,store)
    committed(store,created,utcnow());before=records(store)
    assert performance(store)['pending']==len(created)
    single=next(r for r in before if r['payload']['kind']=='single')
    sq=single['payload']['legs'][0]['quote'];later=max(parse_time(q.commence_time) for q in a.quotes)+timedelta(days=1)
    for league in ('Premier League','Bundesliga'):
        q=next(q for q in a.quotes if q.league==league)
        # Explicitly cause the selected single to lose; these are test finals.
        if q.league==sq['league']:
            if sq['market']=='btts':goals=0 if sq['selection']=='Yes' else 2
            else:goals=0 if sq['selection']=='Over' else 2
        else:goals=1
        save_final(store,q,goals,goals,later)
    from intelligence.forward_testing import reconcile as label
    assert label(store,later)['labeled']==3
    assert reconcile(store,later)['labeled']==len(created) and reconcile(store,later)['labeled']==0
    after=records(store);assert [r['payload'] for r in after]==[r['payload'] for r in before]
    r=next(r for r in after if r['id']==single['id']);assert r['label']['outcome']=='loss' and r['label']['paper_net_units']==-1
    stats=performance(store);assert stats['paper_net_units']==stats['paper_roi']==-1 and stats['paper_max_drawdown_units']==1
    assert stats['losses']>=1 and stats['actual_betting_profit'] is None
    assert all(r['label']['paper_net_units'] is None for r in after if r['payload']['kind']!='single')


def test_contradiction_stale_prices_read_only_and_missing_models_never_publish(store,quote,monkeypatch):
    a=research_slate(store,quote,monkeypatch);record_shadow_forecasts(a,store)
    later=max(parse_time(q.commence_time) for q in a.quotes)+timedelta(minutes=1)
    assert not prepare(a,store,now=later)
    from intelligence.pipeline import Analysis
    assert not prepare(Analysis(quotes=[quote]),store)
    store.read_replica=True;assert not prepare(a,store)


@pytest.mark.parametrize('states,expected',[
    ([(1,0,0),(1,0,0)],'win'), ([(1,0,0),(0,0,1),(0,1,0)],'loss'),
    ([(0,1,0),(0,1,0)],'push'), ([(.5,.5,0),(1,0,0)],'partial'),
    ([(0,.5,.5),(0,1,0)],'partial'), ([(.5,.5,0),(0,0,1)],'loss')])
def test_parlay_settled_score_states_handle_pushes_and_partials_without_prices(states,expected):
    assert combined_outcome(states)==expected
    with pytest.raises(ValueError):combined_outcome(states+[(.2,.2,.2)])


def learning_rows(start,n,*,label=True,p=.72,offset=0,per_day=1):
    rows=[]
    for i in range(n):
        at=start+timedelta(days=i//per_day,minutes=10*(i%per_day));kick=at+timedelta(hours=12)
        rows.append({'id':digest(('synthetic-learning',offset+i)),'at':(at+timedelta(seconds=1)).isoformat(),'quarantined':False,
            'payload':{'forecast_at':at.isoformat(),'protocol_locked_before_forecast':True,
                'quote':{'commence_time':kick.isoformat()},'estimate':{'probability':p},
                'scope':{'sport':'Soccer','league':'Premier League','market':'btts','point':None,'model_version':'frozen-test','evidence_id':'synthetic','protocol_id':'test'},
                'baseline':{'probability':.5}},
            'label':{'outcome':'win' if i%2 else 'loss','verified_result':{'observed_at':(kick+timedelta(hours=2)).isoformat()}} if label else None})
    return rows


def test_learning_requires_post_lock_full_chronological_evidence_and_does_not_fit_on_pages(store,monkeypatch):
    from intelligence import learning
    locked=datetime(2023,1,1,tzinfo=timezone.utc);learning.lock_protocol(store,locked)
    rows=learning_rows(locked+timedelta(days=1),100)
    monkeypatch.setattr(learning,'records',lambda _:rows)
    monkeypatch.setattr(learning,'fit_calibrator',lambda *a:pytest.fail('Insufficient data must not fit'))
    report=learning.update(store,locked+timedelta(days=400));assert report['new_challengers']==0
    assert learning.status(store)['challengers']==[] and not learning.status(store)['automatic_promotion']
    # A missing earlier label blocks settled-only training rather than selecting hits.
    rows=learning_rows(locked+timedelta(days=1),550);rows[2]['label']=None
    assert learning.update(store,locked+timedelta(days=600))['new_challengers']==0


def test_challenger_fits_once_then_records_unseen_pregame_test_and_never_promotes(store,monkeypatch):
    from intelligence import learning
    locked=datetime(2023,1,1,tzinfo=timezone.utc);learning.lock_protocol(store,locked)
    rows=learning_rows(locked+timedelta(days=1),500)
    monkeypatch.setattr(learning,'records',lambda _:rows)
    at=locked+timedelta(days=510);report=learning.update(store,at)
    assert report['new_challengers']==1
    candidate=learning.status(store)['challengers'][0];a=candidate['payload']
    assert a['training_n']==300 and a['calibration_n']==200
    assert set(a['training_ids']).isdisjoint(a['calibration_ids']) and not a['automatic_promotion']
    assert learning.update(store,at)['new_challengers']==0
    future=learning_rows(parse_time(a['test_start']),200,label=False,offset=1000,per_day=2)
    rows.extend(future)
    for i in range(0,200,2):
        now=parse_time(future[i+1]['at'])+timedelta(seconds=1)
        learning.update(store,now)
    assert learning.status(store)['test_forecasts']==200
    # Only now provide actual-label test fixtures; candidate coefficients remain frozen.
    for i,r in enumerate(future):r['label']={'outcome':'win' if i%2 else 'loss','verified_result':{'observed_at':(parse_time(r['payload']['quote']['commence_time'])+timedelta(hours=2)).isoformat()}}
    end=parse_time(a['test_end'])+timedelta(days=4);report=learning.update(store,end)
    assert report['new_evaluations']==1 and learning.update(store,end)['new_evaluations']==0
    final=learning.status(store);evaluation=final['evaluations'][0]['payload']
    assert evaluation['test_n']==200 and evaluation['report'] and not evaluation['approved'] and not evaluation['automatic_promotion']
    assert final['challengers'][0]['payload']==a and final['improvement_verified'] is False
    with store.connect() as db:
        assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='model_actions'").fetchone()


def test_challenger_rejects_same_date_fit_overlap_and_protects_secrets(monkeypatch):
    from intelligence import learning
    rows=learning_rows(datetime(2025,1,1,tzinfo=timezone.utc),2)
    with pytest.raises(ValueError,match='Chronological'):learning.train_candidate(rows,rows,json.loads(learning.POLICY.read_text()))
    from intelligence.analyst_config import load_config
    from intelligence.chat_privacy import validate_input,InvalidChatInput,redact
    value='private_research_capability_0123456789abcdef'
    monkeypatch.setenv('RESEARCH_STATE_READ_TOKEN',value);c=load_config()
    assert value not in redact(value,c.sensitive_values)
    with pytest.raises(InvalidChatInput):validate_input('Here is '+value,c)


def test_local_assistant_reads_saved_learning_without_training_or_paid_requests(store,monkeypatch):
    from intelligence.llm import PaidAnalyst
    from intelligence.analyst_config import AnalystConfig
    from intelligence.pipeline import Analysis
    monkeypatch.setattr('intelligence.learning.train_candidate',lambda *args:pytest.fail('Chat cannot train'))
    response=PaidAnalyst(store,AnalystConfig()).respond('What is the AI learning status?',Analysis())
    assert '0 calibration challengers' in response.content and 'Independent improvement is not established' in response.content
    assert response.mode=='Local · rule-based' and not response.paid_attempted
