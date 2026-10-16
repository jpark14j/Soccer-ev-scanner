"""Accumulate provider-observed completed game results without guessing outcomes.

This local dataset is not an independently verified settlement feed or a public
raw-data export. Keep persistent storage; a fresh runner cannot rebuild older than
three days of provider results. No score is silently revised: snapshots append.
"""
import json
import re
import pandas as pd
from intelligence.domain import digest,parse_time,utcnow
from intelligence.providers import LEAGUES,ProviderError
from intelligence.history import clean_history


def normalize_results(payload,league,received_at,now=None):
    now=now or utcnow()
    rows=[]
    if not isinstance(payload,list):
        raise ValueError('Completed-results response must be a list')
    for event in payload:
        try:
            if not isinstance(event,dict) or event.get('completed') is not True:
                continue
            if event['sport_key']!=LEAGUES[league][1] or not event['id']:
                continue
            updated,start,received=map(parse_time,(event['last_update'],event['commence_time'],received_at))
            if not start<updated<=received<=now:
                continue
            home,away=event['home_team'],event['away_team']
            scores=event['scores']
            if not isinstance(scores,list) or len(scores)!=2:
                continue
            values={r['name']:r['score'] for r in scores}
            if set(values)!={home,away} or not all(re.fullmatch(r'\d+',str(v)) for v in values.values()):
                continue
            row={'provider':'the-odds-api','league':league,'event_id':event['id'],
                 'home':home,'away':away,'home_score':int(values[home]),'away_score':int(values[away]),
                 'commence_time':event['commence_time'],'observed_at':event['last_update'],
                 'received_at':received_at}
            rows.append(row)
        except (ValueError,TypeError,KeyError):
            continue
    return rows


def ensure_table(store):
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS observed_results(id TEXT PRIMARY KEY, league TEXT NOT NULL, payload TEXT NOT NULL)')


def collect(provider,store,leagues=('NBA','MLB')):
    ensure_table(store)
    summary={}
    for league in leagues:
        cache_key='daily-completed-v1-'+league
        cached=store.cached(cache_key,86400)
        if cached is not None:
            summary[league]=cached
            continue
        response=provider.scores(league,days_from=3)
        rows=normalize_results(response['data'],league,response['received_at'])
        with store.connect() as db:
            for row in rows:
                db.execute('INSERT OR IGNORE INTO observed_results VALUES(?,?,?)',
                           (digest(row),league,json.dumps(row,allow_nan=False)))
        summary[league]={'completed_records':len(rows),'received_at':response['received_at']}
        store.cache(cache_key,summary[league])
    return summary


def history_from_results(league,store):
    ensure_table(store)
    with store.connect() as db:
        rows=[json.loads(r['payload']) for r in db.execute('SELECT payload FROM observed_results WHERE league=?',(league,))]
    if not rows:
        return pd.DataFrame()
    # A source correction becomes a new observation. Only latest known completed
    # score is used for current research; original snapshots remain in the store.
    latest={}
    for row in sorted(rows,key=lambda r:(r['observed_at'],r['received_at'])):
        latest[row['event_id']]=row
    records=[]
    for row in latest.values():
        # Use the first full day after observation as a conservative availability
        # date, not the scheduled start day of a potentially delayed/resumed game.
        records.append({'game_id':row['event_id'],'Date':parse_time(row['observed_at']).strftime('%d/%m/%Y'),
                        'HomeTeam':row['home'],'AwayTeam':row['away'],
                        'FTHG':row['home_score'],'FTAG':row['away_score']})
    return clean_history(pd.DataFrame(records),'Soccer' if league not in ('NBA','MLB') else league)
