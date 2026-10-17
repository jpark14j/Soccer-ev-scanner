"""Stable competition registry. Targets explicitly differ from ingested coverage."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Competition:
    id: str
    name: str
    sport: str
    kind: str
    timezone: str
    source_file: str | None = None
    odds_name: str | None = None


_SPECS=(
 ('soccer:eng:pl','Premier League','Europe/London','en.1'),
 ('soccer:de:bundesliga','Bundesliga','Europe/Berlin','de.1'),
 ('soccer:es:laliga','La Liga','Europe/Madrid','es.1'),
 ('soccer:it:seriea','Serie A','Europe/Rome','it.1'),
 ('soccer:fr:ligue1','Ligue 1','Europe/Paris','fr.1'),
)
COMPETITIONS={name:Competition(cid,name,'Soccer','domestic',tz,key,name) for cid,name,tz,key in _SPECS}
for cid,name,kind in (
 ('soccer:pt:primeira','Primeira Liga','domestic'),('soccer:nl:eredivisie','Eredivisie','domestic'),
 ('soccer:us:mls','MLS','domestic'),('soccer:uefa:cl','Champions League','club_cup'),
 ('soccer:uefa:el','Europa League','club_cup'),('soccer:uefa:conference','Conference League','club_cup'),
 ('soccer:fifa:wc','World Cup','national'),('soccer:fifa:wcq','World Cup qualifiers','national'),
 ('soccer:uefa:euro','European Championship','national'),('soccer:uefa:nations','Nations League','national'),
 ('soccer:conmebol:copa','Copa América','national'),('soccer:caf:afcon','Africa Cup of Nations','national')):
    COMPETITIONS[name]=Competition(cid,name,'Soccer',kind,'UTC',None,name if name in ('MLS','Champions League') else None)
COMPETITIONS['NBA']=Competition('basketball:nba','NBA','NBA','professional','America/New_York',None,'NBA')
COMPETITIONS['MLB']=Competition('baseball:mlb','MLB','MLB','professional','America/New_York',None,'MLB')
BY_ID={v.id:v for v in COMPETITIONS.values()}


def expected_games(competition,season):
    if not competition.source_file:
        return None
    teams=18 if competition.name=='Bundesliga' or competition.name=='Ligue 1' and season>='2023-24' else 20
    return teams*(teams-1)
