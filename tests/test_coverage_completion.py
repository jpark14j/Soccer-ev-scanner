"""Synthetic deterministic workflows, never live predictions or accuracy proof."""
from copy import deepcopy
from dataclasses import asdict,replace
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
import pytest
from intelligence.domain import digest
from intelligence.fixture_research import combinations_for,daily_combinations,forward_combinations
from intelligence.statistics_forward import record,reconcile,monitoring
from intelligence.prediction_accuracy import saved_for_display,summary
from intelligence.statistics_learning import source_rows
from test_free_results import NOW,save_fixture_cache,day_response,receipt


def nba_rows(store):
    from intelligence.nba_current import forecasts
    save_fixture_cache(store)
    return [r for r in forecasts(store,NOW)[0] if r['research_eligible']]


def test_recorded_legs_remain_usable_after_five_minutes_but_not_expired(store):
    rs=nba_rows(store)[:100];record(store,rs,NOW)
    later=NOW+timedelta(minutes=20)
    from intelligence.nba_current import forecasts
    originals=saved_for_display(store,forecasts(store,later)[0],later)
    assert originals and all(r['forecast_at']==NOW.isoformat() for r in originals)
    assert combinations_for(originals,2,now=later)
    assert combinations_for(originals,3,now=later)
    assert not combinations_for(originals,2,now=NOW+timedelta(hours=6))


def test_bounded_candidates_preserve_exact_legs_and_no_joint_point(store):
    rs=nba_rows(store);cs=forward_combinations(rs,NOW)
    assert {len(c['legs']) for c in cs}=={2,3}
    assert len(record(store,cs,NOW))==2
    assert record(store,cs,NOW)==[]
    later=NOW+timedelta(minutes=10)
    from intelligence.nba_current import forecasts
    fresh=forward_combinations(forecasts(store,later)[0],later)
    shown=saved_for_display(store,fresh,later)
    assert len(shown)==2 and all(c['forecast_at']==NOW.isoformat() for c in shown)
    assert record(store,fresh,later)==[]  # Clock alone creates no extra version.
    assert all(c['joint_probability'] is None and not c['independence_assumed'] for c in shown)
    assert source_rows(store)==[]  # A bound cannot become a calibration label.
    forged=deepcopy(cs[0]);forged['logical_probability_bounds'][0]+=.01
    with pytest.raises(ValueError):record(store,[forged],NOW)
    assert not saved_for_display(store,[forged],NOW)
    forged=deepcopy(cs[0]);forged['joint_probability']=.5
    with pytest.raises(ValueError):record(store,[forged],NOW)


def test_each_cross_game_leg_needs_its_own_exact_final_and_never_duplicate_accuracy(store):
    rs=nba_rows(store);cs=forward_combinations(rs,NOW);record(store,cs,NOW)
    c=next(c for c in cs if len(c['legs'])==3)
    later=datetime(2026,10,23,12,tzinfo=timezone.utc)
    from intelligence.nba_current import current
    es,meta=current(store,NOW);by_id={e.fixture_id:e for e in es}
    finals=[]
    for r in c['legs']:
        e=by_id[r['fixture_id']]
        hg,ag=(110,105) if r['selection']==e.home_name else (105,110)
        finals.append(replace(e,status='completed',home_score=hg,away_score=ag,
            observed_at=later.isoformat(),score_scope='sportscore_final'))
    def put(events):
        store.cache('nba-current',{'events':[asdict(e) for e in events],
            'meta':meta|{'checked_at':later.isoformat()}},later)
    put(finals[:2]);reconcile(store,later)
    assert summary(store,later)['formats'][3]['settled']==0
    changed=replace(finals[2],kickoff=(datetime.fromisoformat(finals[2].kickoff)+timedelta(hours=1)).isoformat())
    put(finals[:2]+[changed]);reconcile(store,later)
    assert summary(store,later)['formats'][3]['settled']==0
    put(finals);assert reconcile(store,later)>=1
    assert reconcile(store,later)==0
    result=summary(store,later)['formats'][3]
    assert result['settled']==1 and result['correct']==1 and result['accuracy']==100.
    report=monitoring(store)
    assert all(g['brier'] is None and g['log_loss'] is None for g in report['groups'])
    assert all(g['point_probability_labels']==0 for g in report['groups'])
    assert source_rows(store)==[]


def test_mixed_and_per_sport_research_is_not_crowded_out_by_nba(store):
    nba=nba_rows(store);soccer=[]
    for i,r in enumerate(nba[:4]):
        soccer.append(r|{'sport':'Soccer','league':'SYNTHETIC soccer only','fixture_id':'soccer'+str(i),
            'home_id':'synthetic-h'+str(i),'away_id':'synthetic-a'+str(i)})
    for size in (2,3):
        cs=daily_combinations(nba+soccer,size,NOW)
        scopes={tuple(sorted({r['sport'] for r in c['legs']})) for c in cs}
        assert scopes=={('NBA',),('Soccer',),('NBA','Soccer')}
        assert all(len({r['fixture_id'] for r in c['legs']})==size for c in cs)


def test_regular_season_continues_beyond_opening_with_real_prior_results_only(store):
    from intelligence.nba_current import forecasts
    es,meta=save_fixture_cache(store)
    now=datetime(2026,11,4,12,tzinfo=timezone.utc)
    # Deterministic source contracts simulate all earlier completed games.
    completed=[replace(e,status='completed',home_score=110,away_score=105,
        observed_at=now.isoformat(),score_scope='sportscore_final') if e.event_date<now.date().isoformat() else e for e in es]
    meta=meta|{'checked_at':now.isoformat()}
    def put(events):store.cache('nba-current',{'events':[asdict(e) for e in events],'meta':meta},now)
    put(completed);rows,problem=forecasts(store,now)
    assert rows and not problem
    assert all('regular-season forecast' in r['status'] and not r['validated'] for r in rows)
    assert all(r['training_end']<r['kickoff'][:10] for r in rows)
    first=next(e for e in completed if e.status=='completed')
    put([replace(e,status='unresolved',home_score=None,away_score=None) if e==first else e for e in completed])
    assert forecasts(store,now)[0]==[]
    # Postponement is explicit non-play, not an invented result or missing final.
    put([replace(e,status='unresolved',home_score=None,away_score=None,score_scope='source_postponed') if e==first else e for e in completed])
    assert forecasts(store,now)[0]
    # No current season results: do not extend prior-year ratings indefinitely.
    put([e for e in es if e.event_date>=now.date().isoformat()])
    assert forecasts(store,now)[0]==[]


def test_nonplayed_soccer_statuses_are_retained_but_never_features_or_picks(store):
    from intelligence.free_results import parse_day,model_inputs
    data=day_response();data['matches'][0]['status']='postponed'
    e=parse_day(receipt(data),'Premier League','2026-10-18',NOW)[0]
    assert e.score_scope=='source_postponed' and e.status=='unresolved' and e.home_score is None
    meta={'ok':True,'provider':'sportscore','checked_at':NOW.isoformat(),'coverage':{'unresolved_past':1}}
    store.cache('public-results-current-Premier League',{'events':[asdict(e)],'meta':meta},NOW)
    events,model_meta=model_inputs(store,'Premier League',NOW)
    assert not events and model_meta['coverage']['unresolved_past']==0 and model_meta['explicitly_unplayed']==1
    # Suspended or unknown games keep the old blocking behavior.
    e=replace(e,score_scope='source_suspended')
    store.cache('public-results-current-Premier League',{'events':[asdict(e)],'meta':meta},NOW)
    assert model_inputs(store,'Premier League',NOW)[1]['coverage']['unresolved_past']==1


def test_new_cached_research_records_without_resetting_refresh_clock_or_source_requests(store):
    from intelligence.free_statistics_worker import update
    from test_current_statistics import season
    import json
    rows=nba_rows(store)[::3][:3]
    raw=json.dumps(season(NOW)).encode()
    with patch('intelligence.fixture_research.collect',return_value={'forecasts':[]}),patch('intelligence.current_score_research.candidates',return_value=[]):
        update(store,NOW,lambda:(raw,NOW.isoformat()))
    later=NOW+timedelta(minutes=10)
    rows=[r|{'forecast_at':later.isoformat()} for r in rows]
    def blocked():raise AssertionError('No external source requests in cooldown')
    with patch('intelligence.fixture_research.collect',return_value={'forecasts':rows}),patch('intelligence.current_score_research.candidates',return_value=[]):
        report,_=update(store,later,blocked)
    assert report['public_results_requests']==0 and report['source_observed_at']==NOW.isoformat()
    assert report['new_pregame_records']>3 and report['experimental_cross_game_bounds']=={'2':1,'3':1}
    assert summary(store,later)['formats'][2]['pending']==1


@pytest.mark.parametrize('status',['postponed','cancelled'])
def test_nba_source_explicit_nonplay_is_never_a_prediction(status):
    from intelligence.nba_current import fixtures
    from test_free_results import schedule
    data=schedule();data['events'][0]['status']=status
    e=fixtures(receipt(data),NOW)[0]
    assert e.status=='unresolved' and e.score_scope=='source_'+status and e.home_score is None


def test_disappearing_nba_fixture_is_not_silently_rebound_or_predicted(store):
    from intelligence.nba_current import save,forecasts
    from test_free_results import schedule
    es,_=save_fixture_cache(store);data=schedule()
    data['events'][0]['time_utc']='22:00'  # Same date/team identity, changed tipoff.
    class C:
        now=NOW
        def __init__(self):self.store=store
        def get(self,*args):return receipt(data)
        def day(self,*args):raise AssertionError('Season has not started')
    save(C());current=__import__('intelligence.nba_current',fromlist=['current']).current(store,NOW)[0]
    old=es[0];new=next(e for e in current if e.fixture_id==old.fixture_id)
    assert new.kickoff!=old.kickoff  # Earlier records retain original kickoff.
    data['events'][0]['date_utc']='2026-11-25'  # Cannot bind a repeated pairing across dates.
    meta=save(C())
    assert old.fixture_id in meta['removed_unreconciled_fixtures']
    rows,reason=forecasts(store,NOW)
    assert not rows and 'source binding' in reason


def test_home_keeps_original_point_cards_and_falls_back_to_recorded_bounds_for_nba(store):
    from intelligence.prediction_accuracy import home_choices
    nba_rows(store)
    from intelligence.fixture_research import collect
    rs=[r for r in collect(store,NOW,168,['NBA'])['forecasts'] if r['research_eligible']][:94]
    cs=forward_combinations(rs,NOW)
    record(store,rs+cs,NOW)
    result=home_choices(store,['NBA'],NOW)
    assert result[1]['probability'] is not None
    assert all(result[n]['kind']=='bounded_cross_game' and result[n]['joint_probability'] is None for n in (2,3))
    for n in (2,3):assert len(result[n]['legs'])==n


def test_verified_same_day_final_does_not_block_nba_or_leak_into_ratings(store):
    from intelligence.nba_current import forecasts
    es,meta=save_fixture_cache(store)
    # Retain normal opening-season research while a different game has a
    # verified same-day finish whose numerical score is intentionally withheld.
    now=NOW.replace(day=21,hour=12)
    completed=[replace(e,status='completed',home_score=110,away_score=105,
        observed_at=now.isoformat(),score_scope='sportscore_final') if e.event_date<now.date().isoformat() else e for e in es]
    original=completed[0]
    held=replace(original,status='unresolved',home_score=None,away_score=None,
        event_date=now.date().isoformat(),kickoff=now.replace(hour=1).isoformat(),
        score_scope='same_day_final_withheld',observed_at=now.isoformat())
    def put(events,at=now):store.cache('nba-current',{'events':[asdict(e) for e in events],
        'meta':meta|{'checked_at':at.isoformat()}},at)
    put(completed[1:]+[held]);rows,problem=forecasts(store,now)
    assert rows and not problem and all(r['training_end']<now.date().isoformat() for r in rows)
    put(completed[1:]);without=forecasts(store,now)[0]
    assert [(r['fixture_id'],r['probability']) for r in rows]==[(r['fixture_id'],r['probability']) for r in without]
    put(completed[1:]+[replace(held,score_scope='source_reported_ft')])
    assert not forecasts(store,now)[0]  # Live or unknown score is still blocking.
    tomorrow=now+timedelta(days=1)
    put([held],tomorrow)
    assert not forecasts(store,tomorrow)[0]  # Yesterday's held score needs a new verified final.


def test_nba_fresh_fixture_receipt_does_not_extend_older_result_receipt_lifetime(store):
    from intelligence.nba_current import save,current
    from test_free_results import schedule
    now=NOW.replace(day=20,hour=22);older=now-timedelta(hours=2)
    data=schedule();data['generated']=now.isoformat()
    class C:
        def __init__(self):self.store=store;self.now=now
        def get(self,*args):return receipt(data,now)
        def day(self,league,day):return [],receipt(day_response('NBA',day),older)
    meta=save(C())
    assert meta['checked_at']==older.isoformat()
    assert current(store,now)[1]['ok']
    assert not current(store,now+timedelta(hours=4))[1]['ok']


def test_accuracy_contracts_normalize_legacy_implicit_and_explicit_leg_kickoffs():
    from intelligence.prediction_accuracy import decision
    start='2026-10-21T23:00:00+00:00'
    base={'fixture_id':'synthetic-game','kickoff':start,'model_version':'synthetic-model',
        'market':'h2h','selection':'Synthetic Home','point':None}
    legacy=base|{'legs':[{'market':'h2h','selection':'Synthetic Home','point':None}]}
    explicit=base|{'legs':[{'market':'h2h','selection':'Synthetic Home','point':None,
        'fixture_id':base['fixture_id'],'kickoff':'2026-10-21T19:00:00-04:00'}]}
    assert decision(base)==decision(legacy)==decision(explicit)
    changed=deepcopy(explicit);changed['legs'][0]['kickoff']='2026-10-22T23:00:00+00:00'
    assert decision(base)!=decision(changed)


def test_new_nba_result_conflict_retains_saved_success_but_blocks_cached_forecasts(store):
    from intelligence.nba_current import forecasts,current,NBAReconciliationError
    from intelligence.free_results import refresh
    nba_rows(store);before=current(store,NOW)
    later=NOW+timedelta(minutes=1)
    def unavailable(*args):raise ValueError('Synthetic source unavailable')
    with patch('intelligence.nba_current.save',side_effect=NBAReconciliationError('NBA final conflicts with a previously verified result')):
        report=refresh(store,later,unavailable)
    assert not report['sources']['NBA']['ok'] and report['sources']['NBA']['blocks_cached_inference']
    assert current(store,NOW)==before  # Original successful snapshot is untouched.
    assert not forecasts(store,later)[0]
    # A successful exact reconciliation clears this temporary inference block.
    with patch('intelligence.nba_current.save',return_value=before[1]):refresh(store,later,unavailable)
    assert forecasts(store,later)[0]
