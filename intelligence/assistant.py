"""Local grounded analyst. Paid generative API deliberately disabled.

Answers are rendered from the same verified records as the UI. A generative
adapter needs explicit cost approval, context controls and output validation.
"""
from intelligence.ev import qualify
from intelligence.parlays import NO_PARLAYS
from intelligence.domain import utcnow


def answer(question, analysis, performance=None, now=None):
    now = now or utcnow()
    question = question.lower()
    if any(k in question for k in ('injur','lineup','weather','pitcher','prop')):
        return 'Verified player statistics, injuries, lineups and fitted prop models are not connected. No qualifying player-prop recommendation can be supported.'
    if 'parlay' in question:
        return NO_PARLAYS + ' A validated joint model and actual sportsbook combined price are required.'
    if any(k in question for k in ('perform','histor','profit','roi')):
        n = (performance or {}).get('settled',0)
        return f'The forward ledger contains {n} settled predictions. Review the Performance Tracker for source-backed results; no profitability claim is supported by an empty or small record.'
    if any(k in question for k in ('change','changed')):
        return 'A verified previous analysis comparison is not recorded yet. No change in injuries, odds or probabilities can be asserted.'
    opportunities = [o for o in analysis.opportunities if qualify(o.quote,o.estimate,now)[0]]
    for sport in ('nba','mlb','soccer'):
        if sport in question:
            opportunities = [o for o in opportunities if o.quote.sport.lower()==sport]
    if not opportunities:
        errors = ' Data collection is incomplete; see provider errors.' if analysis.errors else ''
        return 'No current opportunities pass the Ontario quote, model validation, freshness and uncertainty-adjusted EV checks.' + errors
    lines = []
    for o in opportunities[:3]:
        q,e = o.quote,o.estimate
        lines.append(f'{q.event}: {q.selection} at {q.bookmaker_name}, provider-observed decimal odds {q.odds:.2f} (updated {q.source_updated_at}). Model {e.model_version}: {e.probability:.1%}, estimated EV {o.ev:+.1%}, uncertainty-adjusted EV {o.conservative_ev:+.1%}. Risks: ' + '; '.join(e.risk_factors))
    return '\n\n'.join(lines)
