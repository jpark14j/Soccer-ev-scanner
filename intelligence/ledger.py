"""Append-only, reviewable derived prediction archive for durable GitHub history.

SQLite is the query index; JSONL archives are the source of durable publications
and evidence-backed settlements. Never store credentials or user identifiers here.
A private persistent database is preferred once subscribers/users are introduced.
"""
import json
from pathlib import Path
from intelligence.domain import digest


def restore(store, directory):
    path=Path(directory)
    publications=path/'predictions.jsonl'
    settlements=path/'settlements.jsonl'
    with store.connect() as db:
        for name in (publications,settlements):
            if not name.exists():
                continue
            for line in name.read_text().splitlines():
                if not line.strip():
                    continue
                row=json.loads(line)
                if name==publications:
                    if digest((row['payload'],row['origin']))!=row['id']:
                        raise ValueError('Archived prediction differs from its content hash')
                    values=(row['id'],row['at'],row['origin'],json.dumps(row['payload'],allow_nan=False))
                    existing=db.execute('SELECT * FROM publications WHERE id=?',(row['id'],)).fetchone()
                    if existing and (existing['at']!=row['at'] or existing['origin']!=row['origin'] or json.loads(existing['payload'])!=row['payload']):
                        raise ValueError('Archived prediction differs from immutable ledger')
                    db.execute('INSERT OR IGNORE INTO publications VALUES(?,?,?,?)',values)
                else:
                    values=tuple(row[k] for k in ('publication_id','at','outcome','result','source','closing_odds','closing_source','closing_observed_at'))
                    existing=db.execute('SELECT * FROM settlements WHERE publication_id=?',(row['publication_id'],)).fetchone()
                    if existing and tuple(existing)!=values:
                        raise ValueError('Archived settlement differs from immutable ledger')
                    db.execute('INSERT OR IGNORE INTO settlements VALUES(?,?,?,?,?,?,?,?)',values)


def archive(store, directory):
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    with store.connect() as db:
        for table,file,key in [('publications','predictions.jsonl','id'),('settlements','settlements.jsonl','publication_id')]:
            rows=[dict(r) for r in db.execute('SELECT * FROM '+table+' ORDER BY at')]
            if table=='publications':
                for row in rows: row['payload']=json.loads(row['payload'])
            path=directory/file
            known={}
            if path.exists():
                known={json.loads(line)[key]:json.loads(line) for line in path.read_text().splitlines() if line.strip()}
            new=[]
            for row in rows:
                if row[key] in known:
                    if known[row[key]]!=row:
                        raise ValueError('Archive alteration detected; refusing to rewrite history')
                else:
                    new.append(row)
            if new:
                with path.open('a') as output:
                    for row in new: output.write(json.dumps(row,sort_keys=True,allow_nan=False)+'\n')
                    output.flush()
                    import os
                    os.fsync(output.fileno())
