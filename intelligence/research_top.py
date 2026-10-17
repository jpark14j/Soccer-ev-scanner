"""Evidence-first experimental summaries. No requests, approval or joint model."""
from collections import Counter,defaultdict
from dataclasses import replace,asdict
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import json
import math
import sqlite3
from intelligence.domain import utcnow,parse_time,digest,Quote,Estimate
from intelligence.research_ranking import rank_research,RANKINGS,comparison,evidence_problem,count
from intelligence.parlay_intelligence import generate,binary_market,explain_leg
from intelligence.parlay_research import ResearchLeg,quote_problem


class SourceChecks:
    def __init__(self,store,now):self.store,self.now,self.cache=store,now,{}

    def check(self,leg,model_only=False):
        try:return self._check(leg,model_only)
        except (sqlite3.Error,OSError,ValueError,KeyError,TypeError):
            return 'Current source proof unavailable or malformed; inspect results and storage diagnostics'

    def _check(self,leg,model_only=False):
        d=leg.model_details;e=leg.estimate;q=leg.quote
        if d.get('inputs_complete') is False or d.get('input_gates_passed') is False:
            return 'Required current model inputs are incomplete'
        if d.get('results_provider')!='football-data.org':
            return 'Model-only replay requires the supported frozen soccer source' if model_only else None
        if self.store is None:return 'Current results store verification unavailable'
        if q.league not in self.cache:
            from intelligence.current_results import cached_status,configuration
            from intelligence.epl_forecasts import load_artifact
            from intelligence.expanded_models import load
            config=configuration();state=cached_status(self.store,q.league,self.now)
            artifact=load_artifact() if q.league=='Premier League' else load(q.league)
            self.cache[q.league]=(config,state,artifact)
        config,state,artifact=self.cache[q.league]
        if config.problem:return config.problem
        if not state.get('ok') or not state.get('fresh'):return state.get('problem') or 'Fresh verified results unavailable'
        coverage=state.get('coverage',{})
        if not coverage.get('complete_fixture_schedule') or coverage.get('unresolved_past'):
            return 'Current results coverage is incomplete or contains unresolved earlier fixtures'
        if not artifact or e.model_version!=artifact['model_version'] or e.evidence_id!=artifact['artifact_sha256']:
            return 'Prediction does not match the frozen model evidence'
        from intelligence.epl_forecasts import supported as epl_supported
        from intelligence.expanded_forecasts import supported as expanded_supported
        if not (epl_supported(q) or expanded_supported(q)):return 'Frozen model does not support this competition/market contract'
        adapter=digest({name:sha256(Path(__file__).with_name(name+'.py').read_bytes()).hexdigest() for name in ('current_results','current_soccer')})
        if (d.get('results_sha256')!=state.get('sha256') or d.get('results_adapter_sha256')!=adapter
            or d.get('model_code_sha256')!=artifact['code_sha256']
            or d.get('data_sha256')!=digest((artifact['data_sha256'],state['sha256'],adapter))):
            return 'Saved forecast inputs differ from the currently verified source/model; recheck saved research'
        if model_only:
            from intelligence.results_journal import latest
            from intelligence.current_results import season_at,cache_key
            from intelligence.competitions import COMPETITIONS
            from intelligence.data_adapters import team_identity
            saved=latest(self.store,q.league,season_at(self.now))
            if not saved:
                with self.store.connect() as db:row=db.execute('SELECT payload FROM cache WHERE key=?',(cache_key(q.league,season_at(self.now)),)).fetchone()
                saved=json.loads(row['payload']) if row else None
            if not saved or not saved.get('ok') or saved.get('sha256')!=state['sha256']:return 'Exact current fixture snapshot unavailable'
            h,_=team_identity(COMPETITIONS[q.league],q.home);a,_=team_identity(COMPETITIONS[q.league],q.away)
            matches=[r for r in saved['events'] if (r['home_id'],r['away_id'])==(h,a)]
            if (len(matches)!=1 or matches[0]['status']!='scheduled'
                or parse_time(matches[0]['kickoff'])!=parse_time(q.commence_time)):
                return 'Previously forecast fixture/kickoff is no longer exactly confirmed'
            if any(r['status']=='unresolved' for r in saved['events']):return 'Unresolved source fixtures block model-only research'
        return None


def risk_tags(leg):
    text=' '.join(map(str,leg.blockers)).lower()
    categories={'availability':('injur','lineup','availability'),'operator settlement':('settlement','operator'),
        'prospective confirmation':('confirmation','prospective'),'market baseline':('market baseline','market benchmark'),
        'calibration support':('fewer than','insufficient','calibration outcomes')}
    return tuple(k for k,words in categories.items() if any(w in text for w in words))


def research_key(leg,now,priced=True):
    e,d=leg.estimate,leg.model_details
    # Shared display gates already passed; lower key is preferred. Disagreement
    # is a late tie-break, never a substitute for calibrated evidence.
    grade=0 if d.get('results_provider')=='football-data.org' else 1 if d.get('data_source') else 2
    gap=comparison(leg) if priced else None
    return (grade,e.upper-e.lower,-count(d,'calibration_bin_n'),-count(d,'test_n'),-count(d,'calibration_n'),
        len(risk_tags(leg)),-e.lower,-gap['difference_envelope'][0] if gap else 0.,-e.probability,
        (now-parse_time(leg.quote.source_updated_at if priced else d['prediction_at'])).total_seconds(),leg.quote.id)


def value_status(leg):
    lo,hi=comparison(leg)['difference_envelope']
    return 'Positive model-versus-price difference; unvalidated' if lo>0 else 'Negative model-versus-price difference' if hi<0 else 'Inconclusive model-versus-price difference'


def recorded_model_only(analysis,store,checks,now,books=None,leagues=None):
    """Only replay actually computed forecasts; never fabricate a fresh quote."""
    records=list(analysis.processing.get('previously_recorded_research_only',{}).values())
    for q in analysis.quotes:
        e=analysis.advanced_estimates.get(q.id) or analysis.estimates.get(q.id)
        if e:records.append({'quote':asdict(q),'estimate':asdict(e),'model_evidence':analysis.advanced_details.get(q.id,{})})
    if store:
        with store.connect() as db:
            table=db.execute("SELECT name FROM sqlite_master WHERE name='shadow_forecasts'").fetchone()
            if table:
                records.extend(json.loads(r['payload']) for r in db.execute('SELECT payload FROM shadow_forecasts WHERE at>=? ORDER BY at DESC,id LIMIT 1000',((now-timedelta(hours=6)).isoformat(),)))
    candidates={};excluded=Counter()
    for record in records:
        try:
            q=Quote(**record['quote']);e=Estimate(**record['estimate']);d=record.get('model_evidence',{})
            if books is not None and q.bookmaker not in books or leagues is not None and q.league not in leagues:continue
            if q.sport!='Soccer' or parse_time(q.commence_time)<=now:continue
            if q.provider!='the-odds-api' or q.jurisdiction!='CA-ON':continue
            # Only expired/absent prices trigger this view; suspended/unverified
            # market contracts do not become an alternative priced pick.
            if q.status(now) not in ('stale','current'):continue
            if not e.valid() or (e.sport,e.league,e.market)!=(q.sport,q.league,q.market):continue
            at=parse_time(d['prediction_at'])
            if not parse_time(e.training_end)<at<parse_time(q.commence_time) or not 0<=(now-at).total_seconds()<21600:continue
            if parse_time(q.received_at)>at or parse_time(d['source_checked_at'])>at:continue
            if e.probability<=.5 or binary_market(q)[0] is None:continue
            leg=ResearchLeg(q,1/q.odds,e,'research',d,tuple(d.get('blockers',[])))
            problem=evidence_problem(leg,now) or checks.check(leg,model_only=True)
            if problem:excluded[problem]+=1;continue
            key=binary_market(q)[0];old=candidates.get(key)
            if old and not math.isclose(old.estimate.probability,e.probability,abs_tol=1e-8):
                excluded['Conflicting recorded model-only outcomes']+=1;candidates[key]=None;continue
            if key in candidates and candidates[key] is None:continue
            if old is None or research_key(leg,now,False)<research_key(old,now,False):candidates[key]=leg
        except (ValueError,TypeError,KeyError):excluded['Recorded forecast lacks complete verified evidence']+=1
    ranked=sorted((l for l in candidates.values() if l is not None),key=lambda l:research_key(l,now,False))
    return ranked[0] if ranked else None,dict(excluded)


def select_top(analysis,store=None,books=None,now=None,leagues=None):
    now=now or utcnow();checks=SourceChecks(store,now)
    base=rank_research(analysis,books,now);excluded=Counter(base['exclusions']);eligible=[]
    for state,leg in base['rankings'][RANKINGS[0]]:
        from intelligence.research_state import APPROVED
        if state==APPROVED:continue
        problem=checks.check(leg)
        if problem:excluded[problem]+=1
        else:eligible.append(leg)
    eligible.sort(key=lambda leg:research_key(leg,now));pick=eligible[0] if eligible else None
    valid_rank_ids={leg.quote.id for leg in eligible}
    base['rankings']={name:[row for row in values if row[1].quote.id in valid_rank_ids] for name,values in base['rankings'].items()}
    # Keep all equivalent sportsbook offers for same-book parlay construction.
    valid_ids=set()
    for q in analysis.quotes:
        if books is not None and q.bookmaker not in books or quote_problem(q,now):continue
        from intelligence.parlay_research import leg_evidence
        leg=leg_evidence(q,analysis,now)
        if not evidence_problem(leg,now) and not checks.check(leg):valid_ids.add(q.id)
    report=generate(replace(analysis,quotes=[q for q in analysis.quotes if q.id in valid_ids]),books,now)
    parlays=report.two_leg+report.three_leg+report.alternatives
    parlays=[p for p in parlays if not any(p.dependence[k] for k in ('shared_game_pairs','shared_team_pairs','shared_player_pairs'))]
    parlay=min(parlays,key=lambda p:p.evidence_rank) if parlays else None
    try:model_only,model_exclusions=(None,{}) if pick else recorded_model_only(analysis,store,checks,now,books,leagues)
    except (sqlite3.Error,OSError,ValueError,TypeError):
        model_only,model_exclusions=None,{'Recorded model-only forecasts unavailable; inspect storage integrity':1}
    input_blockers=Counter()
    current_ids={q.id for q in analysis.quotes if (books is None or q.bookmaker in books) and not quote_problem(q,now)}
    modeled_ids=set(analysis.estimates)|set(analysis.advanced_estimates)
    for detail in analysis.research:
        if detail.get('quote_id') in current_ids-modeled_ids:
            input_blockers.update(detail.get('blockers',[]))
    return {'pick':pick,'parlay':parlay,'model_only':model_only,'exclusions':dict(excluded),
        'input_blockers':dict(input_blockers),
        'model_only_exclusions':model_exclusions,'shared_rankings':base,'parlay_exclusions':report.exclusions,
        'method':'Existing favored-side and research-display gates first. Default: verified input completeness; narrower supplied range; calibration bucket/test/calibration support; known risk categories; lower probability bound; lower model-minus-break-even difference; point probability; source freshness. No payout or approval score.',
        'parlay_method':'Compare weakest-leg evidence across eligible 2/3-leg candidates; no joint winning probability or format optimality is established.'}
