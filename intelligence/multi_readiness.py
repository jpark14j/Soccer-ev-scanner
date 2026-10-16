"""Multi-competition diagnostics and private paper labels, without new odds calls."""
import json
from intelligence.domain import utcnow,parse_time
from intelligence.competitions import COMPETITIONS
from intelligence.data_adapters import ROOT,team_identity
from intelligence.expanded_models import load,policy


def readiness(analysis=None,store=None,now=None):
    now=now or utcnow()
    try:audit=json.loads((ROOT/'research_assets/source_coverage.json').read_text())
    except (ValueError,OSError):audit={}
    rows=[]
    for c in COMPETITIONS.values():
        coverage=audit.get(c.name,{})
        bundle=load(c.name) if c.name in policy()['targets'] else None
        prepared=getattr(analysis,'expanded_models',{}).get(c.name,{}) if analysis else {}
        if c.name=='Premier League' and analysis:
            prepared=getattr(analysis,'focused_model',{}) or {}
        current=next((s for s in coverage.get('coverage',[]) if s['season']=='2026-27'),{})
        latest=prepared.get('state',{}).get('latest') or current.get('latest_completed')
        missing=(prepared.get('results_coverage',{}).get('unresolved_past') if prepared.get('results_provider')=='football-data.org'
            else sum(e['status']!='completed' and e['event_date']<now.date().isoformat() for e in prepared.get('fixtures',[])) if prepared.get('fixtures') and c.name!='Premier League' else current.get('unresolved_past'))
        problem=prepared.get('problem')
        if latest and (now.date()-parse_time(latest+'T00:00:00+00:00').date()).days>21:
            problem=problem or 'Current results exceed the 21-day freshness limit'
        if missing:problem=problem or 'Unresolved earlier source fixtures'
        if c.sport in ('NBA','MLB'):
            coverage=audit.get(c.name,{})
            problem='Current-season context/history insufficient; player/availability features unverified'
            latest=coverage.get('data_through');missing=None
        rows.append({'competition':c.name,'competition_id':c.id,'sport':c.sport,
            'coverage':'Verified historical snapshot; raw files need private import' if coverage else 'Discovery target; no dataset integrated',
            'historical_completed':coverage.get('completed',coverage.get('rows',0)),
            'latest_result':latest,'past_unresolved':missing,
            'model':bundle['model_version'] if bundle else 'Frozen EPL research model' if c.name=='Premier League' else 'No expanded model',
            'model_status':'Research model' if bundle or c.name=='Premier League' else 'Unavailable',
            'current_forecast':'Blocked: '+problem if problem else 'Input gates still require an exact current quote' if bundle else 'Not implemented',
            'source_check':prepared.get('results_observed_at') or prepared.get('source_checked_at') or coverage.get('checked_at'),
            'current_source':prepared.get('results_provider','OpenFootball' if coverage and c.sport=='Soccer' else 'No current source verified'),
            'validation':'Not approved','betting_edge':'Not approved'})
    return rows


def process_expanded_paper(store,analysis,now=None):
    """Label an exact normalized source target, never bookmaker settlement/returns."""
    from intelligence.processing import ensure_processing
    from intelligence.current_soccer import prepare_expanded as prepare
    now=now or utcnow();ensure_processing(store);n=0
    for league in analysis.processing.get('pending_expanded_leagues',[]):
        if league not in analysis.expanded_models:analysis.expanded_models[league]=prepare(league,store,now)
    with store.connect() as db:
        records=db.execute('SELECT f.* FROM shadow_forecasts f LEFT JOIN shadow_outcomes o ON f.id=o.id WHERE o.id IS NULL').fetchall()
        for record in records:
            payload=json.loads(record['payload']);q=payload['quote']
            if payload.get('target_scope')!='expanded_source_ft':continue
            bundle=analysis.expanded_models.get(q['league'],{})
            if not bundle or bundle.get('problem') or not parse_time(record['at'])<parse_time(q['commence_time'])<now:continue
            from intelligence.current_soccer import paper_result_matches
            if not paper_result_matches(q,bundle):continue
            try:h,_=team_identity(COMPETITIONS[q['league']],q['home']);a,_=team_identity(COMPETITIONS[q['league']],q['away'])
            except ValueError:continue
            result=next((r for r in bundle['current_rows'] if (r['home'],r['away'],r['date'])==(h,a,q['commence_time'][:10])),None)
            if not result or result['date']>=now.date().isoformat():continue
            positive=result['hg']>0 and result['ag']>0 if q['market']=='btts' else result['hg']+result['ag']>2.5
            hit=positive==(q['selection'].lower() in ('yes','over'))
            n+=db.execute('INSERT OR IGNORE INTO shadow_outcomes VALUES(?,?,?,?)',(record['id'],now.isoformat(),
                'hit' if hit else 'miss',bundle.get('results_provider','OpenFootball')+' source-reported full-time target; '+bundle['data_sha256']+'; not operator settlement')).rowcount
    return n
