"""Multi-competition diagnostics and private paper labels, without new odds calls."""
import json
from intelligence.domain import utcnow,parse_time
from intelligence.competitions import COMPETITIONS
from intelligence.data_adapters import team_identity


def readiness(analysis=None,store=None,now=None):
    from intelligence.diagnostics import competition_diagnostics
    return competition_diagnostics(analysis,store,now)


def process_expanded_paper(store,analysis,now=None,allow_results_fetch=True):
    """Label an exact normalized source target, never bookmaker settlement/returns."""
    from intelligence.processing import ensure_processing
    from intelligence.current_soccer import prepare_expanded as prepare
    now=now or utcnow();ensure_processing(store);n=0
    for league in analysis.processing.get('pending_expanded_leagues',[]):
        if league not in analysis.expanded_models:
            analysis.expanded_models[league]=(prepare(league,store,now) if allow_results_fetch else prepare(league,store,now,allow_fetch=False))
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
