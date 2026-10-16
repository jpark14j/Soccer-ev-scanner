"""Append-only normalized event observations, exact reconciliation and coverage."""
from dataclasses import dataclass,asdict
from datetime import date
import json
from intelligence.domain import digest,parse_time,utcnow
from intelligence.competitions import BY_ID


@dataclass(frozen=True)
class EventObservation:
    competition_id: str
    season: str
    source: str
    source_event_id: str
    home_id: str
    away_id: str
    home_name: str
    away_name: str
    event_date: str
    status: str
    home_score: int | None
    away_score: int | None
    observed_at: str
    source_updated_at: str | None
    license_reference: str
    score_scope: str
    kickoff: str | None = None
    historical_timing_verified: bool = False

    def validate(self,now=None):
        now=now or utcnow()
        if self.competition_id not in BY_ID or not self.home_id or not self.away_id or self.home_id==self.away_id:
            raise ValueError('Unknown competition or invalid team identity')
        date.fromisoformat(self.event_date)
        if not self.source or not self.source_event_id or not self.license_reference.startswith('https://'):
            raise ValueError('Result provenance and reviewed rights reference required')
        if parse_time(self.observed_at)>now or self.source_updated_at and parse_time(self.source_updated_at)>parse_time(self.observed_at):
            raise ValueError('Future source observation')
        if self.kickoff and parse_time(self.kickoff)>now and self.status=='completed':
            raise ValueError('Completed fixture has future kickoff')
        if self.status not in ('completed','scheduled','unresolved'):
            raise ValueError('Unknown result status')
        if self.status=='completed':
            timed_final=bool(self.kickoff and self.source_updated_at and parse_time(self.kickoff)<parse_time(self.source_updated_at)<=parse_time(self.observed_at))
            if (self.event_date>now.date().isoformat() or self.event_date==now.date().isoformat() and not timed_final
                or any(type(x) is not int or not 0<=x<=250 for x in (self.home_score,self.away_score))):
                raise ValueError('Unverified same/future-day or invalid completed score')
        elif self.home_score is not None or self.away_score is not None:
            raise ValueError('Uncompleted fixtures must not contain inferred scores')
        return self

    @property
    def fixture_id(self):
        c=BY_ID[self.competition_id]
        # Domestic soccer has one home pairing per season. Other sports/cups need
        # exact source IDs until an explicit cross-provider event binding exists.
        identity=(self.competition_id,self.season,self.home_id,self.away_id)
        return digest(identity if c.sport=='Soccer' and c.kind=='domestic' else (*identity,self.source,self.source_event_id))


def ensure_events(store):
    with store.connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS event_observations(id TEXT PRIMARY KEY,fixture_id TEXT NOT NULL,competition_id TEXT NOT NULL,at TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS data_snapshots(id TEXT PRIMARY KEY,at TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS event_no_update BEFORE UPDATE ON event_observations BEGIN SELECT RAISE(ABORT,'Immutable event observation'); END;
        CREATE TRIGGER IF NOT EXISTS event_no_delete BEFORE DELETE ON event_observations BEGIN SELECT RAISE(ABORT,'Immutable event observation'); END;
        CREATE TRIGGER IF NOT EXISTS snapshot_no_update BEFORE UPDATE ON data_snapshots BEGIN SELECT RAISE(ABORT,'Immutable data snapshot'); END;
        CREATE TRIGGER IF NOT EXISTS snapshot_no_delete BEFORE DELETE ON data_snapshots BEGIN SELECT RAISE(ABORT,'Immutable data snapshot'); END;
        ''')


def ingest(store,events,snapshot,now=None):
    now=now or utcnow();ensure_events(store);added=0
    events=[e.validate(now) for e in events]
    if len({e.fixture_id for e in events})!=len(events):
        raise ValueError('Duplicate fixture in one source snapshot; nothing imported')
    if not snapshot.get('sha256') or not snapshot.get('license_reference','').startswith('https://'):
        raise ValueError('Snapshot provenance/rights missing')
    with store.connect() as db:
        for e in events:
            payload=asdict(e)
            key=digest({k:v for k,v in payload.items() if k!='observed_at'})
            added+=db.execute('INSERT OR IGNORE INTO event_observations VALUES(?,?,?,?,?)',
                (key,e.fixture_id,e.competition_id,e.observed_at,json.dumps(payload,allow_nan=False))).rowcount
        db.execute('INSERT OR IGNORE INTO data_snapshots VALUES(?,?,?)',
            (digest(snapshot),now.isoformat(),json.dumps(snapshot,allow_nan=False)))
    return {'added_observations':added,'fixtures':len(events)}


def reconciled(store,competition_id,as_of=None):
    as_of=as_of or utcnow();ensure_events(store);groups={}
    with store.connect() as db:
        rows=db.execute('SELECT fixture_id,payload FROM event_observations WHERE competition_id=?',(competition_id,)).fetchall()
    for row in rows:
        value=json.loads(row['payload'])
        if parse_time(value['observed_at'])<=as_of:
            groups.setdefault(row['fixture_id'],[]).append(value)
    result=[]
    for key,versions in groups.items():
        latest=max(versions,key=lambda v:v['observed_at'])
        completed=[v for v in versions if v['status']=='completed']
        scores={(v['home_score'],v['away_score'],v['score_scope']) for v in completed}
        dates={v['event_date'] for v in versions}
        conflicts=[]
        if len(scores)>1:conflicts.append('Conflicting completed scores/scope; manual review required')
        if len(dates)>1:conflicts.append('Fixture date changed across observations; exact reconciliation required')
        if completed and any(v['status']!='completed' and v['observed_at']>=max(r['observed_at'] for r in completed) for v in versions):
            conflicts.append('Previously completed result was withdrawn; review required')
        result.append({'fixture_id':key,'observation':latest,'conflicts':conflicts,'versions':len(versions)})
    return result


def coverage(events,competition,season,now=None):
    from intelligence.competitions import expected_games
    now=now or utcnow();selected=[e for e in events if e.season==season]
    completed=[e for e in selected if e.status=='completed']
    expected=expected_games(competition,season)
    teams={t for e in selected for t in (e.home_id,e.away_id)}
    pairs={(e.home_id,e.away_id) for e in selected}
    balanced=bool(expected and len(teams)*(len(teams)-1)==expected and len(pairs)==len(selected)==expected)
    return {'season':season,'fixtures':len(selected),'completed':len(completed),'expected_season_games':expected,
        'observed_teams':len(teams),'complete_fixture_schedule':balanced,
        'complete_historical_season':bool(balanced and len(completed)==expected),
        'unresolved_past':sum(e.status!='completed' and e.event_date<now.date().isoformat() for e in selected),
        'latest_completed':max((e.event_date for e in completed),default=None),
        'date_precision':'calendar date; not a verified kickoff timestamp'}


def pregame_features(store,competition_id,team_id,as_of):
    """Only actually observed, unconflicted prior dates; no backdated archive use."""
    from datetime import datetime
    as_of=parse_time(as_of) if isinstance(as_of,str) else as_of
    observations=reconciled(store,competition_id,as_of)
    games=[];blockers=[]
    for row in observations:
        e=row['observation']
        if team_id not in (e['home_id'],e['away_id']) or e['event_date']>=as_of.date().isoformat():continue
        if row['conflicts']:blockers.extend(row['conflicts']);continue
        if e['status']!='completed':blockers.append('Unresolved earlier team fixture');continue
        home=e['home_id']==team_id
        games.append((e['event_date'],e['home_score'] if home else e['away_score'],e['away_score'] if home else e['home_score']))
    games.sort();recent=games[-5:]
    return {'prior_games':len(games),'last_result':games[-1][0] if games else None,
        'result_based_rest_days':(as_of.date()-date.fromisoformat(games[-1][0])).days if games else None,
        'recent_goals_or_points_for':sum(g[1] for g in recent)/len(recent) if recent else None,
        'recent_goals_or_points_against':sum(g[2] for g in recent)/len(recent) if recent else None,
        'recent_sample':len(recent),'unverified_features':['Player availability','Lineups','Pitcher/bullpen/park context','xG'],
        'blockers':list(dict.fromkeys(blockers)) or ([] if games else ['No previously observed team results']),
        'note':'Result-based form/rest proxies; not a fitted model effect or independently verified full schedule'}
