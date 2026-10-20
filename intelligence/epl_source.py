"""Strict public-domain EPL result contract. No accounts, odds or player data."""
from datetime import date
from hashlib import sha256
import json

REVISION = 'e6744429ee395bc86f247348c6184bb08d4eb361'
ROOT = 'https://raw.githubusercontent.com/openfootball/football.json/'
SEASONS = tuple(f'{year}-{str(year+1)[-2:]}' for year in range(2020, 2027))
SOURCE = 'openfootball/football.json; publisher CC0-1.0 public-domain dedication'
LICENSE_URL = ROOT + REVISION + '/LICENSE.md'

_NAMES = {
 'AFC Bournemouth':'Bournemouth', 'Brighton & Hove Albion FC':'Brighton',
 'Hull City AFC':'Hull', 'Sunderland AFC':'Sunderland',
 'Wolverhampton Wanderers FC':'Wolves', 'Tottenham Hotspur FC':'Tottenham',
 'Manchester United FC':'Manchester United', 'Manchester City FC':'Manchester City',
 'Nottingham Forest FC':'Nottingham Forest', 'West Bromwich Albion FC':'West Brom',
}
for _name in ('Arsenal','Aston Villa','Brentford','Burnley','Chelsea','Coventry City',
              'Crystal Palace','Everton','Fulham','Ipswich Town','Leeds United',
              'Leicester City','Liverpool','Luton Town','Newcastle United','Norwich City',
              'Sheffield United','Southampton','Watford','West Ham United'):
    _NAMES[_name+' FC'] = _name
ALIASES = dict(_NAMES)
ALIASES.update({name:name for name in _NAMES.values()})
ALIASES.update({'Brighton & Hove Albion':'Brighton','Brighton and Hove Albion':'Brighton',
                'Wolverhampton Wanderers':'Wolves','Tottenham Hotspur':'Tottenham',
                'West Bromwich Albion':'West Brom','Hull City':'Hull','Coventry':'Coventry City'})


def team(name):
    return ALIASES.get(name)


def identity(row):
    # EPL: each home/away pairing occurs once per season; rescheduling changes date.
    return '|'.join((row['season'], row['home'], row['away']))


def decode(raw, season):
    if season not in SEASONS or len(raw)>2_000_000:
        raise ValueError('Unsupported season or oversized public result file')
    payload=json.loads(raw)
    matches=payload.get('matches') if isinstance(payload,dict) else None
    if not isinstance(matches,list) or not 1<=len(matches)<=400:
        raise ValueError('Public result schema changed')
    rows=[];fixtures=[];seen=set()
    for match in matches:
        if not isinstance(match,dict):
            raise ValueError('Malformed public fixture record')
        home,away=team(match.get('team1')),team(match.get('team2'))
        day=date.fromisoformat(match['date']).isoformat()
        year=int(season[:4])
        if not home or not away or home==away or not f'{year}-07-01'<=day<=f'{year+1}-06-30':
            raise ValueError('Unrecognized team or date in public result file')
        row={'season':season,'date':day,'home':home,'away':away}
        key=identity(row)
        if key in seen:
            raise ValueError('Duplicate seasonal fixture')
        seen.add(key)
        score=match.get('score')
        full=score.get('ft') if isinstance(score,dict) else None
        if full is None:
            fixtures.append(row)
            continue
        if not isinstance(full,list) or len(full)!=2 or any(type(v) is not int or not 0<=v<=30 for v in full):
            raise ValueError('Invalid full-time result')
        rows.append(row|{'hg':full[0],'ag':full[1]})
    return sorted(rows,key=lambda r:(r['date'],identity(r))),fixtures


def source_record(raw, season):
    rows,fixtures=decode(raw,season)
    return {'season':season,'url':ROOT+REVISION+'/'+season+'/en.1.json',
            'sha256':sha256(raw).hexdigest(),'completed':len(rows),'unscored':len(fixtures),
            'latest_result':max((r['date'] for r in rows),default=None)}
