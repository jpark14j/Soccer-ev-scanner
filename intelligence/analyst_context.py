"""Read-only evidence supplied to either assistant mode; no tools or raw DB access."""
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import json
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


def build_context(analysis, performance=None, evaluations=(), now=None, sensitive=()):
    now = now or utcnow()
    facts = []
    def add(id,kind,sport,text):
        facts.append(Fact(id,kind,sport,redact(text,sensitive)))
    eligible = [o for o in analysis.opportunities if qualify(o.quote,o.estimate,now)[0]]
    add('availability','availability','all',
        f'{len(eligible)} current opportunities pass the Ontario, freshness, model-validation and uncertainty-adjusted EV gates. '
        + ('Data collection is incomplete; some provider requests failed. ' if analysis.errors else '')
        + ('No current opportunities meet the minimum analytical requirements.' if not eligible else 'Only these evidence-gated opportunities qualify.'))
    add('limits','limitations','all','Player statistics, injuries, lineups, weather and validated player-prop models are not connected. '
        'Live prediction is unavailable without verified score/clock/state/latency and suspension data. '
        'No qualifying parlay opportunities identified today. A validated joint model and actual sportsbook combined quote are required.')
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
        text = (f'Forward ledger: {performance.get("published",0)} published, {performance.get("settled",0)} settled, '
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


def select_local(question, context, history=()):
    lower = question.lower()
    sport = next((s for s in ('NBA','Soccer','MLB') if s.lower() in lower),None)
    if sport is None:
        sport = next((m.get('sport') for m in reversed(history) if m.get('sport') in ('NBA','Soccer','MLB')), 'all')
    if any(word in lower for word in ('place a bet','place bets','bet for me','execute','run code','run python',
                                      'drop table','purchase','buy credits','buy a subscription',
                                      'api key','credentials','system prompt','secrets')):
        kind = 'capabilities'
    elif any(word in lower for word in ('prop','injur','lineup','weather','parlay','live')):
        kind = 'limitations'
    elif any(word in lower for word in ('perform','profit','roi','win rate','results')):
        kind = 'performance'
    elif any(word in lower for word in ('model','validat','calibrat','backtest','historical','confidence','why')):
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
    if not chosen:
        chosen = ['availability','coverage_'+sport.lower()] if sport!='all' else ['availability']
    followups = ['prices','models','freshness'] if kind!='performance' else ['models','risks','best']
    return {'intent':kind,'sport':sport,'fact_ids':chosen[:4],'followups':followups}


def render_plan(plan,context):
    by_id = context.by_id()
    # These notices are always added by the server, not left to model discretion.
    ids = list(dict.fromkeys(['availability',*plan['fact_ids'],'freshness']))
    texts = [by_id[id].text for id in ids if id in by_id]
    return '\n\n'.join(texts), [by_id[id] for id in ids if id in by_id]
