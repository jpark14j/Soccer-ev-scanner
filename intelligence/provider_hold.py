"""Read-only operator hold review. No release, reservation or provider request.

The existing SQL-editor operator procedure remains the only release path.
This module can prepare a disabled-by-default, conservative SQL proposal, but
has no SQL execution endpoint and never calls a write RPC.
"""
from contextlib import closing
import json,os,re,sqlite3,tempfile
from intelligence.domain import parse_time
from intelligence.shared_state import Client,configuration,StateError
from intelligence.hosted_checks import inspect,SavedFile,expected_store

CAPS={'odds':9,'results':6,'discovery':12}


def stored_results(saved,league,now):
    """Receipt metadata only; avoid ingestion/normalization routines with DDL."""
    from intelligence.current_results import cache_key,season_at,TTL
    from intelligence.results_journal import latest
    try:
        accepted=latest(saved,league,season_at(now))
        with closing(saved.connect()) as db:
            row=db.execute('SELECT payload FROM cache WHERE key=?',(cache_key(league,season_at(now)),)).fetchone()
        attempt=json.loads(row['payload']) if row else None
        snapshot=accepted or (attempt if attempt and attempt.get('ok') is True else None)
        at=parse_time(snapshot['checked_at']) if snapshot else None
        fresh=bool(at and 0<=(now-at).total_seconds()<TTL)
        code=(attempt or {}).get('failure_code')
        allowed={'missing_snapshot','expired_verification','future_verification','reconciliation','schema',
            'schema_identity','schema_coverage','transport_timeout','transport_tls','transport','http','storage'}
        if code is not None and code not in allowed:code='unclassified_failure'
        return {'available':bool(snapshot),'fresh':fresh,'accepted_journal_snapshot':bool(accepted),
            'last_attempt_ok':attempt.get('ok') is True if attempt else None,
            'failure_code':code or ('expired_verification' if snapshot and not fresh else 'missing_snapshot' if not snapshot else None),
            'scope':'Saved receipt metadata only; no provider, fixture-reconciliation or model approval inferred'}
    except (ValueError,KeyError,TypeError,sqlite3.Error,OSError):
        return {'available':False,'fresh':False,'failure_code':'storage_integrity',
            'scope':'Saved results metadata unavailable; no readiness inferred'}


def worker_configuration():
    flag=lambda name:os.getenv(name,'0')=='1'
    present=lambda name:os.getenv(name,'false').lower()=='true'
    return {'manual_enabled':flag('RESEARCH_MANUAL_ENABLED'),
        'data_rights_reviewed':flag('RESEARCH_DATA_RIGHTS_VERIFIED'),
        'account_scope_reviewed':flag('RESEARCH_BUDGET_SCOPE_REVIEWED'),
        'actions_usage_reviewed':flag('RESEARCH_ACTIONS_FREE_TIER_REVIEWED'),
        'automatic_worker_enabled':flag('RESEARCH_CONFIG_WORKER_ENABLED'),
        'schedule_enabled':flag('RESEARCH_CONFIG_SCHEDULE_ENABLED'),
        'paid_ai_enabled':os.getenv('PAID_ANALYST_APPROVED','0')!='0',
        'odds_secret_present':present('RESEARCH_ODDS_KEY_CONFIGURED'),
        'results_secret_present':present('RESEARCH_RESULTS_TOKEN_CONFIGURED'),
        'results_enabled':flag('RESEARCH_RESULTS_ENABLED_CONFIGURED'),
        'results_use_reviewed':flag('RESEARCH_RESULTS_USE_REVIEWED')}


def release_proposal(report):
    """SQL text only. Approval must be supplied by the operator after review."""
    if not report['conservative_proposal_available']:return None
    g=report['generation'];identity=report['store_instance'];checksum=report['snapshot_sha256']
    at=report['server_at'];day=report['utc_day']
    if (type(g) is not int or g<1 or not re.fullmatch('[a-f0-9]{32}',identity)
        or not re.fullmatch('[a-f0-9]{64}',checksum)):raise StateError('Invalid release proposal identity')
    parse_time(at)
    if day!=parse_time(at).date().isoformat():raise StateError('Invalid release proposal day')
    return f'''-- PROPOSAL ONLY: do not run without explicit operator approval.
-- No forecast, snapshot, reservation or result record is changed.
-- Full current-day caps are preserved/reserved, so research must wait until
-- the next UTC day AND external account credits must still be sufficient.
BEGIN;
DO $review$
DECLARE
  release_approved boolean := false; -- remains false until explicitly approved
  c public.research_control_state;
  t timestamptz;
BEGIN
  IF NOT release_approved THEN RAISE EXCEPTION 'Operator release approval required'; END IF;
  SELECT * INTO STRICT c FROM public.research_control_state WHERE id FOR UPDATE;
  t := clock_timestamp();
  IF (t AT TIME ZONE 'UTC')::date <> DATE '{day}' OR
     t < TIMESTAMPTZ '{at}' OR t > TIMESTAMPTZ '{at}' + interval '30 minutes' THEN
    RAISE EXCEPTION 'Review day or freshness changed; prepare a fresh review';
  END IF;
  IF NOT c.held OR c.generation <> {g} OR
     (c.owner IS NOT NULL AND c.lease_until > t) THEN
    RAISE EXCEPTION 'Hold, generation or active writer changed';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM public.research_state_snapshots
    WHERE generation=c.generation AND manifest->>'store_instance'='{identity}'
      AND manifest->>'sha256'='{checksum}') THEN
    RAISE EXCEPTION 'Reviewed snapshot identity changed';
  END IF;
  IF EXISTS (SELECT 1 FROM public.research_reservations WHERE actual IS NULL) THEN
    RAISE EXCEPTION 'Unreconciled provider charges require separate operator review';
  END IF;
  INSERT INTO public.research_provider_budget(day,provider,used) VALUES
    (DATE '{day}','odds',9), (DATE '{day}','results',6), (DATE '{day}','discovery',12)
  ON CONFLICT(day,provider) DO UPDATE
    SET used=GREATEST(research_provider_budget.used,excluded.used);
  INSERT INTO public.research_control_audit(action,details) VALUES
    ('operator_budget_review',jsonb_build_object('scope_reviewed',true,
      'policy','full current-day caps reserved; no refunds',
      'reviewed_generation',{g},'reviewed_snapshot_sha256','{checksum}'));
  UPDATE public.research_control_state SET held=false,updated_at=t WHERE id;
END;
$review$;
COMMIT;
'''


def review(*,client=None,expected_instance='',settings=None):
    """One authenticated state read plus a new temporary, query-only restore."""
    expected_instance=expected_instance or expected_store()
    client=client or Client(configuration(),writer=True)
    envelope=client.read()  # The only remote operation in this module.
    now=parse_time(envelope['server_at']);day=now.date().isoformat()
    settings=worker_configuration() if settings is None else settings
    with tempfile.TemporaryDirectory(prefix='provider-hold-review-') as folder:
        path,facts=inspect(envelope,folder,expected_instance)
        saved=SavedFile(path)
        with closing(saved.connect()) as db:
            from intelligence.request_guard import blocked
            local_hold=blocked(db)
            row=db.execute('SELECT used FROM budget WHERE day=?',(day,)).fetchone()
            local_odds=row['used'] if row else 0
            has_results=db.execute("SELECT 1 FROM sqlite_master WHERE name='football_data_requests'").fetchone()
            local_results=db.execute('SELECT count(*) FROM football_data_requests WHERE substr(at,1,10)=?',(day,)).fetchone()[0] if has_results else 0
            old=db.execute("SELECT payload FROM cache WHERE key='provider-quota-observation'").fetchone()
            observed_at=None
            if old:
                try:observed_at=parse_time(json.loads(old['payload'])['observed_at']).isoformat()
                except (ValueError,KeyError,TypeError):pass
        sources={league:stored_results(saved,league,now) for league in ('Premier League','Bundesliga','Ligue 1')}
    budgets={provider:0 for provider in CAPS};seen=set()
    for row in envelope.get('budgets',[]):
        if row['day']!=day:continue
        provider=row['provider'];used=row['used']
        if provider not in CAPS or provider in seen or type(used) is not int or used<0:raise StateError('Remote budget metadata invalid')
        budgets[provider]=used;seen.add(provider)
    active=bool(envelope.get('lease_until') and parse_time(envelope['lease_until'])>now)
    blockers=[]
    if envelope.get('held') is True:blockers.append('remote_provider_hold')
    elif envelope.get('held') is not False:blockers.append('remote_hold_unknown')
    if active:blockers.append('active_writer_lease')
    if local_hold:blockers.append('local_recovery_hold')
    for name in ('manual_enabled','data_rights_reviewed','account_scope_reviewed','actions_usage_reviewed','odds_secret_present'):
        if settings.get(name) is not True:blockers.append(name+'_not_confirmed')
    if any(settings.get(name) is not False for name in ('automatic_worker_enabled','schedule_enabled','paid_ai_enabled')):
        blockers.append('automatic_or_paid_flags_not_disabled')
    effective_odds=max(local_odds,budgets['odds'])
    if effective_odds>=9:blockers.append('current_day_odds_allowance_exhausted')
    from intelligence.manual_research import deployed_commit
    r={'status':'provider hold review - read-only','server_at':now.isoformat(),'utc_day':day,
        **facts,'app_checkout_commit':deployed_commit(),'writer_active':active,'local_recovery_hold':local_hold,
        'worker_configuration':settings,'worker_budget_reservations':{k:{'used':n,'cap':CAPS[k]} for k,n in budgets.items()},
        'saved_local_reservations':{'odds':local_odds,'results':local_results},
        'external_account_remaining':None,'last_provider_balance_observation_at':observed_at,
        'rotation_note':'Rotating a provider key does not reset this ledger or the external account allowance.',
        'current_results':sources,'manual_blockers':blockers,
        'remote_reservation_details':'Not exposed by the read RPC. The proposed operator transaction refuses unreconciled charges.',
        'hold_release_authorized':False,'sports_provider_requests':0,'paid_ai_requests':0,'remote_writes':0}
    review_flags=all(settings.get(n) is True for n in ('data_rights_reviewed','account_scope_reviewed','actions_usage_reviewed'))
    disabled_flags=all(settings.get(n) is False for n in ('automatic_worker_enabled','schedule_enabled','paid_ai_enabled'))
    r['conservative_proposal_available']=bool(envelope.get('held') is True and not active and not local_hold and review_flags and disabled_flags)
    r['release_assessment']='Explicit operator approval and reconciliation required; this review never releases a hold.'
    r['same_day_run_after_conservative_release']=False
    r['proposed_operator_sql']=release_proposal(r)
    return r
