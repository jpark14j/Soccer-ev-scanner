"""Read-only evidence supplied to either assistant mode; no tools or raw DB access."""
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import json
import re
from intelligence.chat_privacy import redact
from intelligence.domain import utcnow, digest
from intelligence.ev import qualify
from intelligence.registry import eligible_book


@dataclass(frozen=True)
class Fact:
    id: str
    kind: str
    sport: str
    text: str


@dataclass(frozen=True)
class Context:
    facts: tuple[Fact, ...]
    as_of: str

    def by_id(self):
        return {f.id:f for f in self.facts}


FOLLOW_UPS = {
    'best': "What opportunities currently qualify?",
    'prices': "Which sportsbook has the best current Ontario price?",
    'freshness': "Which prices are stale or unavailable?",
    'models': "Why are the prediction models still unvalidated?",
    'ev': "How is expected value calculated?",
    'performance': "How has forward-recorded performance been measured?",
    'nba': "What NBA information is available?",
    'soccer': "What soccer information is available?",
    'mlb': "What MLB information is available?",
    'risks': "What are the biggest data and model risks?",
    'parlays': "Find the best-supported two-leg and three-leg research candidates.",
    'props': "Which observed player props have sufficient statistical evidence?",
    'bankroll': "Why is Kelly unavailable for unvalidated parlay research?",
}


def model_evaluations(directory='docs/evidence'):
    result = []
    for sport, filename in (('NBA','nba-research.json'),('Soccer','premier-league-research.json'),('MLB','mlb-research.json')):
        try:
            report = json.loads((Path(directory)/filename).read_text())
            if report.get('evidence_id') != digest({k:v for k,v in report.items() if k!='evidence_id'}):
                continue
            if report.get('sport') == sport:
                result.append(report)
        except (OSError, ValueError, TypeError):
            continue
    return result


def build_context(analysis, performance=None, evaluations=(), now=None, sensitive=(),focus_sport='all',store=None):
    now = now or utcnow()
    facts = []
    def add(id,kind,sport,text):
        facts.append(Fact(id,kind,sport,redact(text,sensitive)))
    if store is not None:
        from intelligence.model_reliability import scorecards
        import sqlite3
        try:
            forward=scorecards(store,now)
            add('forward_evaluation','performance','all',f"Prospective contract evaluation: {forward['recorded']} first pregame contract/model/protocol records, {forward['labeled']} verified target labels, {forward['quarantined']} quarantined. Books and opposing sides are deduplicated. Source-target scoring, legacy paper logs and published betting records are separate; counts must not be added. No accepted-ticket ROI or proven profitability is established.")
            for index,card in enumerate(forward['groups'][:6]):
                scope=card['scope'];scores=card['scores'];text=f"{scope['league']} {scope['market']} {scope['model_version']}: {card['state']}; {scores['n']} scored prospective contracts. "
                if scores['metrics']:text+=f"Binary Brier {scores['metrics']['binary_brier']['value']:.6f}; log loss {scores['metrics']['log_loss']['value']:.6f}. "
                text+='Missing review evidence: '+'; '.join(card['review_blockers'])+'. No automatic model or betting approval.'
                add('reliability_'+str(index),'models',scope['sport'],text)
        except (sqlite3.Error,OSError,ValueError,KeyError,TypeError):add('forward_evaluation','performance','all','Forward evaluation storage/protocol proof is unavailable. No score or reliability is inferred.')
    from intelligence.book_optimizer import best_by_game,optimize_by_book
    games=best_by_game(analysis,now=now)
    add('slate_summary','coverage','all',f'{len(games)} upcoming games discovered or observed in the configured slate; '
        f'{sum(g["observations_evaluated"]>0 for g in games)} have current eligible observations evaluated; '
        'coverage is partial, not every game/market was scanned. Quota, stale prices and missing data constrain analysis. '
        'Game cards rank at most two selections by qualified value, model evidence and freshness, not payout; ties have no demonstrated statistical superiority.')
    for index in range(0,min(len(games),30),5):
        text='; '.join(f"{g['event']['sport']} {g['event']['event']} starts {g['event']['start']}: {g['observations_evaluated']} current observations evaluated; {g['qualified']} shortlisted qualified singles" for g in games[index:index+5])
        add('games_'+str(index),'coverage','all',text+'. More games, when present, are available in Best Picks & Parlays → Singles.')
    eligible = [o for o in analysis.opportunities if qualify(o.quote,o.estimate,now)[0]]
    add('availability','availability','all',
        f'{len(eligible)} current opportunities pass the Ontario, freshness, model-validation and uncertainty-adjusted EV gates. '
        + ('Data collection is incomplete; some provider requests failed. ' if analysis.errors else '')
        + ('No current opportunities meet the minimum analytical requirements.' if not eligible else 'Only these evidence-gated opportunities qualify.'))
    add('limits','limitations','all','Player statistics, injuries, lineups, weather and validated player-prop models are not connected. '
        'Live prediction is unavailable without verified score/clock/state/latency and suspension data. '
        'No qualifying parlay opportunities identified today. Best Picks & Parlays → Parlays (Daily Parlay Research) can display current-price research candidates without validated models; these are not recommendations. A validated joint model and actual sportsbook combined quote are required to qualify.')
    add('actions','capabilities','all','This assistant can explain application records. It cannot place bets, make purchases, '
        'send notifications, run code, execute SQL, alter data or access other accounts. Positive estimated EV never guarantees a win.')
    add('ev_formula','ev','all','For a market without a push, EV = estimated win probability × decimal odds − 1. '
        'Qualification additionally requires current Ontario quotes, validated model evidence and a positive uncertainty-adjusted EV threshold. '
        'Market-implied probability is a comparison baseline, not an independently verified true probability.')
    for sport in ('NBA','Soccer','MLB'):
        quotes = [q for q in analysis.quotes if q.sport==sport]
        ontario = [q for q in quotes if eligible_book(q.bookmaker,now)]
        statuses = Counter(q.status(now) for q in ontario)
        add('coverage_'+sport.lower(),'coverage',sport,
            f'{sport}: {len(ontario)} provider-observed Ontario-key quotes; {statuses.get("current",0)} current. '
            f'{sum(n for status,n in statuses.items() if status!="current")} stale, in-play, suspended or otherwise ineligible. '
            f'{len(quotes)-len(ontario)} quotes have unverified Ontario eligibility. '
            'Absence in this feed does not establish that a sportsbook lacks a market.')
    if performance is not None:
        text = (f'Published betting ledger: {performance.get("published",0)} published, {performance.get("settled",0)} settled, '
                f'{performance.get("pending",0)} pending predictions. ')
        if performance.get('settled',0):
            for label,key in [('one-unit ROI','roi'),('P&L in hypothetical units','pnl_units'),
                              ('win rate','win_rate'),('binary Brier score','brier'),('log loss','log_loss'),
                              ('maximum drawdown in units','max_drawdown_units'),('recorded closing-price value','closing_line_value')]:
                value = performance.get(key)
                if value is not None:
                    text += f'{label}: {float(value):.4f}. '
            text += 'All recorded losses are included. This record is not proof of future profitability.'
        else:
            text += 'No settled forward track record or profitability claim is supported.'
        add('performance','performance','all',text)
    for report in evaluations:
        sport = report.get('sport')
        if sport not in ('NBA','Soccer','MLB'):
            continue
        text = (f'{sport} recorded historical evaluation: {report.get("model_version","unknown version")}; '
                f'data through {report.get("data_end","unknown")}; {report.get("test_n",0)} test events; '
                f'status {report.get("status","unverified")}. ')
        score = report.get('metrics',{})
        text += 'Diagnostic scores: ' + ', '.join(f'{name} {float(score[name]):.6f}' for name in ('brier','log_loss') if isinstance(score.get(name),(float,int))) + '. '
        text += 'Publication blockers: ' + '; '.join(str(s) for s in report.get('promotion_blockers',[])) + '. '
        text += 'Historical research diagnostics are separate from live forward performance and are not current event probabilities.'
        add('model_'+sport.lower(),'models',sport,text)
    from intelligence.market_validation import load_reports
    from intelligence.expanded_models import load as load_expanded,policy as expanded_policy
    for league in expanded_policy()['targets']:
        model=load_expanded(league)
        if model:
            m=model['periods']['final_test']['model']
            add('expanded_'+model['competition_id'],'models','Soccer',
                f"{league} {model['target']}, {model['model_version']}: research model, calibration n={model['calibration_n']}, final test n={m['n']}, binary Brier={m['binary_brier']['value']:.6f}, log loss={m['log_loss']['value']:.6f}. "
                'Independently fitted competition parameters; no approved forecasting or betting edge, no validated joint parlay model. Current source results through '+model['state']['latest']+'; freshness/missing-fixture gates still apply.')
    from intelligence.epl_forecasts import load_artifact
    focused=load_artifact()
    if focused:
        parts=[]
        for market,task in focused['tasks'].items():
            m=task['periods']['held_out']['model'];base=task['periods']['held_out']['constant_baseline']
            parts.append(f"{market}: calibration n={task['calibration_n']}; test n={m['n']}; binary Brier {m['binary_brier']['value']:.6f} versus constant baseline {base['binary_brier']['value']:.6f}; log loss {m['log_loss']['value']:.6f}; classification accuracy {m['classification_accuracy']['value']:.1%}")
        add('focused_epl','models','Soccer',focused['model_version']+': research only. '+'; '.join(parts)+
            '. No independent confirmation, approved champion or market-beating evidence. No betting profitability or parlay joint-model claim. Source: '+focused['source']+
            '; bundled results through '+focused['state']['latest']+'. Current forecasts additionally require complete recent results and fresh Ontario prices.')
        from intelligence.epl_forecasts import supported
        for q in [q for q in analysis.quotes if supported(q) and q.status(now)=='current'][:3]:
            d=analysis.advanced_details.get(q.id,{})
            e=analysis.estimates.get(q.id)
            text=f'{q.event} / {q.market} / {q.selection}: source odds {q.odds:.2f}, updated {q.source_updated_at}; sportsbook break-even {1/q.odds:.1%}. '
            if e:
                text+=f'Research estimate {e.probability:.1%}, frequency envelope {e.lower:.1%}–{e.upper:.1%}; model {e.model_version}, prediction {d.get("prediction_at","unavailable")}, calibration n={d.get("calibration_n",0)}, test n={d.get("test_n",0)}. Not an approved probability or betting EV. '
            else:
                text+='No current probability or betting EV is supported. '
            text+='Missing requirements: '+'; '.join(d.get('blockers',['Current model evidence is unavailable']))
            add('focused_quote_'+q.id[:16],'models','Soccer',text)
    for report in load_reports():
        parts=[f"{task['market']} fixed diagnostic line {task['fixed_diagnostic_line']}: test n={task['test_n']}, two-class Brier={task['metrics']['brier']:.6f}, log loss={task['metrics']['log_loss']:.6f}, classification accuracy={task['classification_accuracy']:.1%}, simple-baseline accuracy={task['baseline_classification_accuracy']:.1%}" for task in report['tasks']]
        add('advanced_'+report['sport'].lower(),'models',report['sport'],
            f"{report['model_version']}: research only; genuine archive through {report['data_end']}. "+'; '.join(parts)+
            '. These are held-out fixed-threshold forecast diagnostics, not observed betting win rates or ROI. No validated live-line or joint-market advantage is established.')
    from intelligence.markets import CATALOG,selection_label
    for sport in ('NBA','Soccer','MLB'):
        props=[q for q in analysis.quotes if q.sport==sport and q.market in CATALOG and CATALOG[q.market].kind=='player' and q.jurisdiction=='CA-ON' and eligible_book(q.bookmaker,now)]
        current=[q for q in props if q.status(now)=='current']
        text=f'{sport}: {len(props)} observed player-prop quotes, {len(current)} current. No licensed player logs, expected minutes/innings, reliable availability, injuries or fitted/calibrated prop forecasts are connected. No prop currently has sufficient statistical evidence for a recommendation. '
        for q in current[:2]:
            text+=f'{selection_label(q)} at {q.bookmaker_name}, observed decimal {q.odds:.2f}; source {q.source_updated_at}, received {q.received_at}. Price research only. '
        add('props_'+sport.lower(),'props',sport,text)
    from intelligence.parlay_research import select_candidates
    selected=select_candidates(analysis,sports=(focus_sport,) if focus_sport in ('NBA','Soccer','MLB') else ('NBA','Soccer','MLB'),now=now)
    add('parlay_summary','parlays',focus_sport,
        f'{len(selected.candidates)} current research candidates selected from {selected.eligible_quotes} eligible Ontario single quotes. No qualifying parlay opportunities identified today. '
        'Ranking considers actual single-price freshness, model evidence, interval width and dependence warnings, not high payouts. No validated joint probability or authorized combined quote is connected; parlay EV is unavailable. Candidate-specific settled performance is not recorded, and cannot be inferred from historical model diagnostics.')
    for index,candidate in enumerate(selected.candidates,1):
        description='; '.join(f"{leg.quote.sport} {leg.quote.event}: {selection_label(leg.quote)}, observed decimal {leg.quote.odds:.2f}, source {leg.quote.source_updated_at}, received {leg.quote.received_at}, model status {leg.model_status}" for leg in candidate.legs)
        add('parlay_'+candidate.id[:16],'parlays',focus_sport,
            f'Research candidate {index}, {len(candidate.legs)} legs at {candidate.legs[0].quote.bookmaker_name}: '+description+
            f'. Theoretical all-win price product {candidate.theoretical_odds:.2f}, not a sportsbook offer. '+
            'Missing: validated joint calibration, actual combined pricing and sportsbook acceptance/settlement restrictions. '+candidate.rank_explanation)
    from dataclasses import replace
    focused=replace(analysis,quotes=[q for q in analysis.quotes if focus_sport=='all' or q.sport==focus_sport])
    for row in optimize_by_book(focused,leg_counts=(2,3),now=now):
        candidate=row['research']
        text=f"{row['name']}: {row['qualification_status']}; {row['eligible_singles_scored']} eligible singles across {row['events_considered']} events. {row['search_method']}. "
        if candidate:
            text+='Unvalidated research candidate: '+'; '.join(f'{leg.quote.event}: {selection_label(leg.quote)}, individual decimal {leg.quote.odds:.2f}, source {leg.quote.source_updated_at}' for leg in candidate.legs)
            text+=f'. Theoretical price product {candidate.theoretical_odds:.2f}, not an executable quote. '+candidate.rank_explanation
        text+=' Validated joint probability, actual combined pricing, verified restrictions and candidate-specific betting performance are unavailable.'
        add('book_'+row['bookmaker'],'parlays',focus_sport,text)
    add('bankroll','bankroll','all','Hypothetical loss tables are available in Best Picks & Parlays → Parlays. The 0.5% per-bet and 2% portfolio caps are chosen exposure assumptions, not profitable stake promises. Fractional Kelly is blocked for research parlays without validated probabilities, uncertainty and actual prices. Overlapping tickets can concentrate losses.')
    quota=getattr(analysis,'quota',{})
    if quota:
        add('quota','freshness','all',f"Local odds quota: {quota['used']}/{quota['limit']}; next local reset {quota['next_reset_toronto']} ({quota['next_reset_utc']}). This does not establish the provider's account reset. No cap was automatically raised; stale snapshots remain inspection-only.")
    for o in eligible[:4]:
        q,e = o.quote,o.estimate
        add('opportunity_'+q.id[:16],'opportunity',q.sport,
            f'{q.event} / {q.market} / {q.selection}: {q.bookmaker_name} ({q.bookmaker}); '
            f'provider {q.provider}, observed decimal odds {q.odds:.2f}, source update {q.source_updated_at}, received {q.received_at}. '
            f'Model estimate {e.probability:.1%}, empirical interval {e.lower:.1%}–{e.upper:.1%}; '
            f'estimated EV {o.ev:+.1%}, conservative EV {o.conservative_ev:+.1%}; model {e.model_version}. '
            'Prices are observations, not an execution guarantee. Risks: '+ '; '.join(e.risk_factors))
    # Best observed price for each equivalent selection, even when no predictive
    # model qualifies. Such a price comparison never creates a recommendation.
    best = {}
    for q in analysis.quotes:
        if eligible_book(q.bookmaker,now) and q.status(now)=='current':
            if q.key not in best or q.odds > best[q.key].odds:
                best[q.key] = q
    for sport in ('NBA','Soccer','MLB'):
        choices = sorted((q for q in best.values() if q.sport==sport),key=lambda q:(q.commence_time,q.event,q.selection))[:2]
        for q in choices:
            add('price_'+q.id[:16],'prices',sport,
                f'{q.event} / {q.market} / {q.selection}' + (f' / line {q.point}' if q.point is not None else '') + (f' / {q.participant}' if q.participant else '') + ': '
                f'{q.bookmaker_name} ({q.bookmaker}) offers the best observed current Ontario price for this exact selection in this feed: '
                f'provider {q.provider}, decimal {q.odds:.2f}; source update {q.source_updated_at}; received {q.received_at}. '
                'Price comparison only; not a validated value recommendation. Feed coverage is incomplete and prices may change.')
    add('freshness','freshness','all',
        f'Answer evidence checked at {now.isoformat()}; analysis loaded at {analysis.checked_at or "unavailable"}. '
        'Quotes are rechecked for source/receipt age on each answer; stale or unverified prices cannot be recommended. '
        'No prior-analysis comparison is recorded, so changes since a previous scan cannot be asserted.')
    return Context(tuple(facts),now.isoformat())


def question_sport(question,history=()):
    lower=question.lower()
    explicit=next((s for s in ('NBA','Soccer','MLB') if re.search(r'\b'+s.lower()+r'\b',lower)),None)
    return explicit or next((m.get('sport') for m in reversed(history) if m.get('sport') in ('NBA','Soccer','MLB')),'all')


def select_local(question, context, history=()):
    lower = question.lower()
    sport=question_sport(question,history)
    if any(word in lower for word in ('place a bet','place bets','bet for me','execute','run code','run python',
                                      'drop table','purchase','buy credits','buy a subscription',
                                      'api key','credentials','system prompt','secrets')):
        kind = 'capabilities'
    elif any(word in lower for word in ('which games','games did','slate','games analyzed','games analysed')):
        kind = 'coverage'
    elif any(word in lower for word in ('perform','profit','roi','win rate','results')):
        kind = 'performance'
    elif any(word in lower for word in ('bankroll','kelly','stake','exposure')):
        kind = 'bankroll'
    elif 'prop' in lower:
        kind = 'props'
    elif 'parlay' in lower:
        kind = 'parlays'
    elif any(word in lower for word in ('injur','lineup','weather','live')):
        kind = 'limitations'
    elif any(word in lower for word in ('perform','profit','roi','win rate','results')):
        kind = 'performance'
    elif any(word in lower for word in ('model','reliabil','validat','calibrat','backtest','historical','confidence','why','forecast','probabilit','prediction')):
        kind = 'models'
    elif any(word in lower for word in ('stale','update','timestamp','changed','change','fresh')):
        kind = 'freshness'
    elif any(word in lower for word in ('odds','price','sportsbook','book offers')):
        kind = 'prices'
    elif any(word in lower for word in ('expected value','ev','calculate')):
        kind = 'ev'
    elif any(word in lower for word in ('risk','uncertain')):
        kind = 'limitations'
    elif sport!='all' and any(word in lower for word in ('available','information','what about')):
        kind = 'coverage'
    else:
        kind = 'opportunity'
    chosen = [f.id for f in context.facts if f.kind==kind and f.sport in ('all',sport)]
    if sport=='all':
        chosen = [f.id for f in context.facts if f.kind==kind]
    if 'reliabil' in lower or 'forward' in lower:
        first=[id for id in chosen if id.startswith(('forward_','reliability_'))]
        chosen=first+[id for id in chosen if id not in first]
    if kind=='coverage' and any(word in lower for word in ('games','slate')):
        chosen=['slate_summary',*[f.id for f in context.facts if f.id.startswith('games_')]]
    if kind=='parlays':
        normalized=re.sub(r'[^a-z0-9]','',lower)
        matched=[f.id for f in context.facts if f.id.startswith('book_') and
            re.sub(r'[^a-z0-9]','',f.id[5:].split('_ca')[0]) in normalized]
        if matched:
            chosen=matched+['parlay_summary']
    if not chosen:
        chosen = ['availability','coverage_'+sport.lower()] if sport!='all' else ['availability']
    followups = ['prices','models','freshness'] if kind!='performance' else ['models','risks','best']
    return {'intent':kind,'sport':sport,'fact_ids':chosen[:4],'followups':followups}


def render_plan(plan,context):
    by_id = context.by_id()
    # These notices are always added by the server, not left to model discretion.
    ids = list(dict.fromkeys(['availability',*plan['fact_ids'],*(['limits'] if plan.get('intent') in ('props','parlays') else []),'freshness']))
    texts = [by_id[id].text for id in ids if id in by_id]
    return '\n\n'.join(texts), [by_id[id] for id in ids if id in by_id]
