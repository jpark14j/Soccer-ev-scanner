"""Compatibility facade for the existing soccer scanner and Telegram entry point.

The shared intelligence package now owns model, ingestion and eligibility logic.
Research models no longer publish recommendations without validation evidence.
"""
from intelligence.soccer import ALIASES, canonical, match_team, poisson_1x2, independent_prediction
from intelligence.history import HISTORY_LEAGUES, load_soccer
from intelligence.providers import LEAGUES
from intelligence.pipeline import configured_store, run_analysis
from intelligence.ev import qualify

SPORTS = {name:key for name,(sport,key) in LEAGUES.items() if sport=='Soccer'}
KEY = ''
MIN_EDGE = .02
MIN_PEERS = 3


def load_history(league):
    return load_soccer(league,configured_store())


def scan(leagues):
    result = run_analysis(KEY,leagues)
    rows = [{'event_id':q.event_id,'league':q.league,'match':q.event,'kickoff':q.commence_time,
             'selection':q.selection,'odds':q.odds,'bookmaker':q.bookmaker_name,
             'last_update':q.source_updated_at,'home':q.home,'away':q.away,
             'opportunity':next((o for o in result.opportunities if o.quote.id==q.id),None)}
             for q in result.quotes]
    return rows,result.errors,result.checked_at


def shortlist(rows):
    choices = []
    for row in rows:
        o = row.get('opportunity')
        if o and qualify(o.quote,o.estimate)[0]:
            choices.append({'kind':'Single','legs':[row],'prob':o.estimate.probability,
                            'odds':o.quote.odds,'edge':o.ev,'score':o.score})
    return sorted(choices,key=lambda c:c['score'],reverse=True)[:3]
