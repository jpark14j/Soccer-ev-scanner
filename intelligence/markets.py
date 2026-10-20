"""Reviewed market contracts, English labels and explicit settlement limitations.

Catalog presence means provider-documented, not Ontario-book/account availability.
Unlisted markets may be inspected after discovery; they cannot enter the selector.
"""
from dataclasses import dataclass
from intelligence.domain import finite

DOCS='https://the-odds-api.com/sports-odds-data/betting-markets.html'
FEATURED=('h2h','spreads','totals')


@dataclass(frozen=True)
class Market:
    key: str
    name: str
    sports: tuple
    kind: str
    units: str
    documented: bool=True
    model_available: bool=False


CATALOG={m.key:m for m in (
    Market('h2h','Match winner / moneyline',('NBA','Soccer','MLB'),'winner','',model_available=True),
    Market('spreads','Point spread / handicap / run line',('NBA','Soccer','MLB'),'spread','score',model_available=True),
    Market('totals','Game total',('NBA','Soccer','MLB'),'total','score',model_available=True),
    Market('player_points','Player points',('NBA',),'player','points'),
    Market('player_rebounds','Player rebounds',('NBA',),'player','rebounds'),
    Market('player_assists','Player assists',('NBA',),'player','assists'),
    Market('player_threes','Player three-pointers',('NBA',),'player','three-pointers made'),
    Market('btts','Both teams to score',('Soccer',),'yes_no','goals',model_available=True),
    Market('pitcher_strikeouts','Pitcher strikeouts',('MLB',),'player','strikeouts'),
    Market('batter_hits','Batter hits',('MLB',),'player','hits'),
    Market('batter_total_bases','Batter total bases',('MLB',),'player','total bases'),
    Market('batter_home_runs','Batter home runs',('MLB',),'player','home runs'),
    Market('batter_rbis','Batter runs batted in',('MLB',),'player','RBIs'),
    # Not documented on the current reviewed market page. Only enable an event
    # query after these exact keys were returned by authorized event discovery.
    Market('totals_corners','Total corners',('Soccer',),'corners','corners',False),
    Market('alternate_totals_corners','Alternate total corners',('Soccer',),'corners','corners',False),
)}


def catalog_for(sport):
    return [m for m in CATALOG.values() if sport in m.sports]


def market_problem(q):
    m=CATALOG.get(q.market)
    if m is None or q.sport not in m.sports:
        return 'Market needs a reviewed settlement and correlation adapter'
    if m.kind=='winner':
        if q.participant or q.point is not None or q.selection not in ([q.home,'Draw',q.away] if q.sport=='Soccer' else [q.home,q.away]):
            return 'Unsupported match-winner selection'
    elif m.kind=='spread':
        if q.participant or not finite(q.point) or q.selection not in (q.home,q.away):
            return 'Spread line or team is missing or invalid'
    elif m.kind in ('total','player','corners'):
        if not finite(q.point) or (m.kind!='spread' and q.point<0):
            return 'Spread/total line is missing or invalid'
        if q.selection.lower() not in ('over','under'):
            return 'Over/under direction is missing'
        if m.kind=='player' and (not isinstance(q.participant,str) or not q.participant.strip()):
            return 'Player identity is missing'
        if m.kind!='player' and q.participant:
            return 'Unexpected participant on a team/event market'
    elif q.selection.lower() not in ('yes','no') or q.point is not None or q.participant:
        return 'Yes/no selection is malformed'
    return ''


def scope(q):
    # No provider response field verifies operator overtime, extra innings,
    # retirement/abandonment or player-start rules. Never imply these are known.
    if q.market=='btts':
        base='Event BTTS market'
    elif q.participant:
        base='Event player market'
    else:
        base='Event market'
    detail='; period, overtime/extra-time, participation, push/void rules unverified'
    if q.market=='spreads' and finite(q.point) and q.point%0.5!=0:
        detail+='; quarter-line/Asian split settlement unverified'
    return base+detail


def selection_label(q):
    m=CATALOG.get(q.market)
    if m is None:
        return f'{q.participant+" · " if q.participant else ""}{q.selection} · {q.market}'+(f' line {q.point:g}' if finite(q.point) else '')
    if m.kind=='winner':
        return f'{q.selection} — '+('match winner' if q.sport=='Soccer' else 'moneyline')
    if m.kind=='spread':
        name='run line' if q.sport=='MLB' else 'handicap' if q.sport=='Soccer' else 'point spread'
        return f'{q.selection} {q.point:+g} — {name}' if finite(q.point) else f'{q.selection} — {name}, line unavailable'
    if m.kind=='yes_no':
        return f'Both teams to score — {q.selection.title()}'
    unit=m.units if m.units!='score' else {'NBA':'points','Soccer':'goals','MLB':'runs'}[q.sport]
    who=q.participant or 'Game'
    return f'{who} — {q.selection.title()} {q.point:g} {unit}' if finite(q.point) else f'{who} — {m.name}, line unavailable'


def is_half_line(line):
    return finite(line) and abs(line*2-round(line*2))<1e-9 and abs(line-round(line))>.1
