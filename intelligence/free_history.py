"""Explicit imports of published free historical snapshots, never current feeds.

Publisher licences were reviewed; source/attribution and raw-content hashes travel
with the normalized local files. No raw dataset is committed or redistributed by
this importer. Pinned revisions make research reproducible, not up to date.
"""
from hashlib import sha256
import json
from pathlib import Path
import io
import pandas as pd
import requests
from intelligence.history import clean_history
from intelligence.domain import utcnow

NBA_REV='4c1ff5e3aef1816ae04af63218015066e186c147'
RETRO_REV='118094bb3fc2ca292c25fccf54e7541762887bf6'
NBA_URL=f'https://raw.githubusercontent.com/fivethirtyeight/data/{NBA_REV}/nba-elo/nbaallelo.csv'
RETRO_FILES={2023:'GL2023.TXT',2024:'gl2024.txt',2025:'GL2025.TXT'}
RETRO_ATTRIBUTION='The information used here was obtained free of charge from and is copyrighted by Retrosheet. Interested parties may contact Retrosheet at "www.retrosheet.org".'


def download(url, cache_dir='data/research/downloads', session=None):
    path=Path(cache_dir)/(sha256(url.encode()).hexdigest()+'.csv')
    if path.exists():
        return path.read_bytes()
    client=session or requests.Session()
    try:
        response=client.get(url,timeout=(5,30),stream=True)
        if response.status_code!=200:
            raise ValueError(f'Published history download returned HTTP {response.status_code}')
        content=bytearray()
        for chunk in response.iter_content(65536):
            content.extend(chunk)
            if len(content)>25*1024*1024:
                raise ValueError('Published history exceeds allowed download size')
    except requests.RequestException:
        raise ValueError('Published history connection failed') from None
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(content)
    return bytes(content)


def parse_nba(content):
    frame=pd.read_csv(io.BytesIO(content))
    required={'game_id','date_game','game_location','lg_id','year_id','team_id','opp_id','pts','opp_pts'}
    if not required<=set(frame):
        raise ValueError('Unexpected FiveThirtyEight NBA schema')
    # One home row per game; neutral-site games need a separate model.
    frame=frame[(frame.game_location=='H') & (frame.lg_id=='NBA')]
    frame=frame[frame.year_id>=frame.year_id.max()-2]
    normalized=pd.DataFrame({'game_id':frame.game_id,
        'Date':pd.to_datetime(frame.date_game,format='%m/%d/%Y').dt.strftime('%d/%m/%Y'),
        'HomeTeam':frame.team_id,'AwayTeam':frame.opp_id,'FTHG':frame.pts,'FTAG':frame.opp_pts})
    return clean_history(normalized,'NBA')


def parse_retrosheet(content):
    frame=pd.read_csv(io.BytesIO(content),header=None,dtype=str,keep_default_na=False)
    if frame.shape[1]<14:
        raise ValueError('Unexpected Retrosheet game-log schema')
    # Completion metadata means the original date cannot establish final-score
    # availability. Exclude suspended/resumed games rather than leak later results.
    frame=frame[frame[13]=='']
    normalized=pd.DataFrame({'game_id':frame[0]+'-'+frame[6]+'-'+frame[3]+'-'+frame[1],
        'Date':pd.to_datetime(frame[0],format='%Y%m%d').dt.strftime('%d/%m/%Y'),
        'HomeTeam':frame[6],'AwayTeam':frame[3],'FTHG':frame[10],'FTAG':frame[9]})
    return clean_history(normalized,'MLB')


def import_snapshot(sport,directory='data/history',session=None):
    if sport=='NBA':
        urls=[NBA_URL]
        frames=[parse_nba(download(urls[0],session=session))]
        license_ref='https://github.com/fivethirtyeight/data/blob/'+NBA_REV+'/LICENSE'
        attribution='FiveThirtyEight, Historical NBA Elo dataset, CC BY 4.0. Game information credited by publisher to Basketball-Reference. Modified: retain home games and final scores from last three archived seasons; omit Elo forecasts.'
    elif sport=='MLB':
        urls=[f'https://raw.githubusercontent.com/chadwickbureau/retrosheet/{RETRO_REV}/seasons/{year}/{name}' for year,name in RETRO_FILES.items()]
        frames=[parse_retrosheet(download(url,session=session)) for url in urls]
        license_ref='https://www.retrosheet.org/notice.txt'
        attribution=RETRO_ATTRIBUTION
    else:
        raise ValueError('Free archive importer supports NBA and MLB')
    frame=clean_history(pd.concat(frames,ignore_index=True),sport)
    directory=Path(directory); directory.mkdir(parents=True,exist_ok=True)
    path=directory/(sport.lower()+'.csv')
    # Never overwrite an existing operator dataset implicitly.
    if path.exists():
        raise ValueError('Historical dataset already exists; choose a separate directory')
    raw=frame.drop(columns=['date']).to_csv(index=False).encode()
    path.write_bytes(raw)
    manifest={'source':urls,'license_reference':license_ref,'commercial_use':True,
              'license_scope':'Publisher permission only; no league endorsement or third-party rights clearance',
              'attribution':attribution,'snapshot_only':True,'imported_at':utcnow().isoformat(),
              'data_through':frame.date.max().isoformat(),'normalized_sha256':sha256(raw).hexdigest()}
    path.with_suffix('.source.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return {'sport':sport,'rows':len(frame),'data_through':manifest['data_through'],'path':str(path),'source':urls}
