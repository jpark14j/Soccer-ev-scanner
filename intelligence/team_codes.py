"""Explicit current feed names to archive codes; no fuzzy or generative matching."""
from intelligence.soccer import canonical,match_team

NBA={
 'Atlanta Hawks':('ATL',),'Boston Celtics':('BOS',),'Brooklyn Nets':('BRK','BKN'),
 'Charlotte Hornets':('CHO','CHA'),'Chicago Bulls':('CHI',),'Cleveland Cavaliers':('CLE',),
 'Dallas Mavericks':('DAL',),'Denver Nuggets':('DEN',),'Detroit Pistons':('DET',),
 'Golden State Warriors':('GSW',),'Houston Rockets':('HOU',),'Indiana Pacers':('IND',),
 'LA Clippers':('LAC',),'Los Angeles Clippers':('LAC',),'Los Angeles Lakers':('LAL',),
 'Memphis Grizzlies':('MEM',),'Miami Heat':('MIA',),'Milwaukee Bucks':('MIL',),
 'Minnesota Timberwolves':('MIN',),'New Orleans Pelicans':('NOP',),'New York Knicks':('NYK',),
 'Oklahoma City Thunder':('OKC',),'Orlando Magic':('ORL',),'Philadelphia 76ers':('PHI',),
 'Phoenix Suns':('PHO','PHX'),'Portland Trail Blazers':('POR',),'Sacramento Kings':('SAC',),
 'San Antonio Spurs':('SAS',),'Toronto Raptors':('TOR',),'Utah Jazz':('UTA',),
 'Washington Wizards':('WAS',),
}
MLB={
 'Arizona Diamondbacks':('ARI',),'Atlanta Braves':('ATL',),'Baltimore Orioles':('BAL',),
 'Boston Red Sox':('BOS',),'Chicago Cubs':('CHN',),'Chicago White Sox':('CHA',),
 'Cincinnati Reds':('CIN',),'Cleveland Guardians':('CLE',),'Colorado Rockies':('COL',),
 'Detroit Tigers':('DET',),'Houston Astros':('HOU',),'Kansas City Royals':('KCA',),
 'Los Angeles Angels':('ANA',),'Los Angeles Dodgers':('LAN',),'Miami Marlins':('MIA',),
 'Milwaukee Brewers':('MIL',),'Minnesota Twins':('MIN',),'New York Mets':('NYN',),
 'New York Yankees':('NYA',),'Oakland Athletics':('OAK',),'Athletics':('OAK',),
 'Philadelphia Phillies':('PHI',),'Pittsburgh Pirates':('PIT',),'San Diego Padres':('SDN',),
 'San Francisco Giants':('SFN',),'Seattle Mariners':('SEA',),'St. Louis Cardinals':('SLN',),
 'Tampa Bay Rays':('TBA',),'Texas Rangers':('TEX',),'Toronto Blue Jays':('TOR',),
 'Washington Nationals':('WAS',),
}


def history_name(sport,name,options):
    exact=match_team(name,options)
    if exact:
        return exact
    aliases={canonical(n):codes for n,codes in (NBA if sport=='NBA' else MLB if sport=='MLB' else {}).items()}
    matches=[code for code in aliases.get(canonical(name),()) if code in options]
    # Ambiguous historical codes must be reconciled, never guessed.
    return matches[0] if len(matches)==1 else None
