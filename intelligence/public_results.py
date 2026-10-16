"""Separate hard-capped public-result requests, never the odds credit budget."""
from hashlib import sha256
import json
import uuid
import requests
from intelligence.domain import utcnow,digest
from intelligence.data_adapters import ROOT,SOURCE_ROOT,SOURCE_LICENSE,SEASONS,openfootball
from intelligence.competitions import COMPETITIONS
from intelligence.event_data import ingest,coverage

DAILY_LIMIT=6  # License plus up to five league files; failures count, no retries.


def reserve_public(store,now):
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS public_result_budget(day TEXT PRIMARY KEY,used INTEGER NOT NULL)')
        db.commit();db.execute('BEGIN IMMEDIATE')
        day=now.date().isoformat();row=db.execute('SELECT used FROM public_result_budget WHERE day=?',(day,)).fetchone()
        used=row['used'] if row else 0
        if used>=DAILY_LIMIT:return False
        db.execute('INSERT OR REPLACE INTO public_result_budget VALUES(?,?)',(day,used+1))
    return True


def get_public(store,path,now=None,session=None):
    now=now or utcnow()
    allowed={'LICENSE.md',*(SEASONS[-1]+'/'+c.source_file+'.json' for c in COMPETITIONS.values() if c.source_file)}
    if path not in allowed:raise ValueError('Unreviewed public endpoint')
    key='public-results-v1-'+digest(path);cached=store.cached(key,86400,now)
    if cached is not None:return cached
    owner=uuid.uuid4().hex
    if not store.claim_fetch(key,owner,now):return {'ok':False,'problem':'Public refresh already in progress'}
    value={'ok':False,'problem':'Public result source unavailable','checked_at':now.isoformat()}
    owned=session is None;session=session or requests.Session()
    try:
        if not reserve_public(store,now):
            return value|{'problem':'Separate six-request public-results daily limit reached'}
        store.cache(key,value,now)
        response=session.get(SOURCE_ROOT+'master/'+path,timeout=(5,10),stream=True,allow_redirects=False)
        try:
            if response.status_code!=200:raise ValueError('Public HTTP failure')
            raw=bytearray()
            for chunk in response.iter_content(65536):
                raw.extend(chunk)
                if len(raw)>2_000_000:raise ValueError('Oversized public response')
            value={'ok':True,'raw':bytes(raw).decode('utf-8'),'sha256':sha256(raw).hexdigest(),
                'checked_at':now.isoformat(),'url':SOURCE_ROOT+'master/'+path}
        finally:response.close()
        store.cache(key,value,now)
    except (requests.RequestException,ValueError,UnicodeError,OSError):store.cache(key,value,now)
    finally:
        if owned:session.close()
        store.release_fetch(key,owner)
    return value


def current(store,league,now=None,session=None):
    now=now or utcnow();c=COMPETITIONS[league]
    if not c.source_file:
        return [],{'ok':False,'problem':'Competition is a discovery target; no reviewed public result adapter'}
    manifest=json.loads((ROOT/'config/multi_source_snapshot.json').read_text())
    license_result=get_public(store,'LICENSE.md',now,session)
    if not license_result['ok']:return [],license_result
    if license_result['sha256']!=manifest['license_sha256']:
        return [],{'ok':False,'problem':'Publisher license changed; human review required'}
    response=get_public(store,SEASONS[-1]+'/'+c.source_file+'.json',now,session)
    if not response['ok']:return [],response
    try:
        events=openfootball(response['raw'].encode(),league,SEASONS[-1],response['checked_at'],now)
        meta=coverage(events,c,SEASONS[-1],now)|{'source':'openfootball','url':response['url'],
            'sha256':response['sha256'],'license_reference':SOURCE_LICENSE,'checked_at':response['checked_at'],'ok':True}
        ingest(store,events,meta,now)
        return events,meta
    except (ValueError,KeyError,TypeError):
        return [],{'ok':False,'problem':'Public fixture contract or aliases changed; no input inferred'}
