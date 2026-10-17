"""Read-only named odds snapshots. No provider, token or network capability."""
from dataclasses import asdict
from datetime import timedelta
import json
from intelligence.domain import parse_time,utcnow,digest
from intelligence.providers import LEAGUES,normalize


def rows(store):
    with store.connect() as db:
        return db.execute("SELECT key,at,payload FROM cache WHERE key LIKE 'last-success-%' OR key LIKE 'event-snapshot-%' ORDER BY at DESC,key LIMIT 1001").fetchall()


def scope(key):
    for league in LEAGUES:
        prefix='last-success-'+league
        if key==prefix:return league,None,('h2h',)
        if key.startswith(prefix+'-'):return league,None,tuple(key[len(prefix)+1:].split(','))
        prefix='event-snapshot-'+league+'-'
        if key.startswith(prefix):
            event,market=key[len(prefix):].rsplit('-',1)
            return league,event,(market,)
    raise ValueError('Unknown saved market scope')


def revision(store):
    values=rows(store)
    return digest([(r['key'],r['at'],digest(r['payload'])) for r in values])


def read(store,now=None):
    now=now or utcnow();records=rows(store);snapshots=[];bad=0
    for row in records[:1000]:
        try:
            league,event,markets=scope(row['key']);payload=json.loads(row['payload'])
            receipt=parse_time(payload['received_at']);saved=parse_time(row['at'])
            if receipt>now or saved>now:raise ValueError('Future saved observation')
            if not isinstance(payload['data'],(dict,list)):raise ValueError('Invalid event payload')
            quotes,rejected=normalize(payload['data'],league,payload['received_at'],now)
            snapshots.append({'league':league,'event':event,'markets':markets,'quotes':quotes,
                'received_at':receipt,'saved_at':saved,'within_retention':now-saved<=timedelta(days=7),
                'rejected':rejected,'key':row['key']})
        except (ValueError,TypeError,KeyError):bad+=1
    return snapshots,{'snapshot_rows':len(records),'malformed_snapshots':bad,'inspection_truncated':len(records)>1000}


def restore(analysis,store,leagues,now=None):
    now=now or utcnow();snapshots,facts=read(store,now)
    snapshots=[s for s in snapshots if s['league'] in leagues and s['within_retention']]
    originals={q.id:q for q in analysis.quotes};candidates=dict(originals)
    for s in snapshots:
        for q in s['quotes']:
            old=candidates.get(q.id)
            if old is None or (parse_time(q.received_at),parse_time(q.source_updated_at))>(parse_time(old.received_at),parse_time(old.source_updated_at)):
                candidates[q.id]=q
    output=[]
    for q in candidates.values():
        covering=[s for s in snapshots if s['league']==q.league and q.market in s['markets'] and (s['event'] is None or s['event']==q.event_id)]
        if covering:
            receipt=max(s['received_at'] for s in covering)
            if parse_time(q.received_at)<=receipt:
                latest=[s for s in covering if s['received_at']==receipt]
                offers=[[x for x in s['quotes'] if x.id==q.id] for s in latest]
                # A newer complete query withdraws missing outcomes. Conflicting
                # simultaneous snapshots cannot choose an arbitrary quote.
                if any(len(xs)!=1 for xs in offers):continue
                choices=[xs[0] for xs in offers]
                if len({digest(asdict(x)) for x in choices})!=1:continue
                q=choices[0]
        output.append(q)
        if originals.get(q.id)!=q:
            analysis.quote_origins[q.id]={'origin':'restored private cache','received_at':q.received_at}
        else:analysis.quote_origins.setdefault(q.id,{'origin':'analysis input','received_at':q.received_at})
    analysis.quotes=output
    if facts['malformed_snapshots']:analysis.warnings=list(dict.fromkeys([*analysis.warnings,'Malformed saved odds snapshots were excluded']))
    if facts['inspection_truncated']:analysis.warnings=list(dict.fromkeys([*analysis.warnings,'Saved odds inspection is bounded to the latest 1,000 snapshots']))
    return analysis
