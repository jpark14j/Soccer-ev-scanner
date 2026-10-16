"""Historical statistics ingestion; date-only results become usable next day."""
import io
import os
import json
from pathlib import Path
import pandas as pd
import requests
from intelligence.domain import utcnow

HISTORY_LEAGUES = {'Premier League': 'E0', 'La Liga': 'SP1', 'Bundesliga': 'D1', 'Serie A': 'I1', 'Ligue 1': 'F1'}


def seasons(now=None):
    now = now or utcnow()
    year = now.year if now.month >= 7 else now.year - 1
    return tuple(f'{y % 100:02d}{(y + 1) % 100:02d}' for y in range(year - 2, year + 1))


def clean_history(frame, sport='Soccer'):
    columns = {'Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG'}
    if not columns <= set(frame.columns):
        raise ValueError('History needs Date, HomeTeam, AwayTeam, FTHG, FTAG')
    frame = frame.copy()
    frame['date'] = pd.to_datetime(frame.Date, dayfirst=True, errors='coerce', format='mixed').dt.normalize()
    for c in ('FTHG', 'FTAG'):
        frame[c] = pd.to_numeric(frame[c], errors='coerce')
    frame = frame.dropna(subset=['date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG'])
    frame = frame[frame.HomeTeam.map(lambda n:isinstance(n,str) and bool(n.strip())) & frame.AwayTeam.map(lambda n:isinstance(n,str) and bool(n.strip()))]
    frame = frame[(frame.FTHG >= 0) & (frame.FTAG >= 0) & (frame.FTHG % 1 == 0) & (frame.FTAG % 1 == 0)]
    frame = frame[(frame.HomeTeam != frame.AwayTeam) & (frame.date < pd.Timestamp(utcnow()).tz_localize(None).normalize())]
    if sport in ('NBA', 'MLB'):
        frame = frame[frame.FTHG != frame.FTAG]
    identities = ['game_id'] if 'game_id' in frame else ['date', 'HomeTeam', 'AwayTeam']
    if 'game_id' in frame and (frame.game_id.isna().any() or frame.game_id.astype(str).str.strip().eq('').any()):
        raise ValueError('Missing historical game IDs')
    # Conflicting results cannot be silently used. Identical overlap is deduplicated.
    conflicts = frame.groupby(identities)[['date','HomeTeam','AwayTeam','FTHG','FTAG']].nunique().max(axis=1)
    if (conflicts > 1).any():
        raise ValueError('Conflicting historical results')
    return frame.drop_duplicates(identities).sort_values(['date']+[k for k in identities if k!='date']).reset_index(drop=True)


def load_soccer(league, store=None, session=None, allow_fetch=True):
    local = load_licensed(league, os.getenv('HISTORY_DIR', 'data/history'))
    if not local.empty:
        return local
    # This free source is restricted to personal research and light downloads.
    # Commercial use requires a separately licensed local dataset/provider.
    if os.getenv('FOOTBALL_DATA_PERSONAL_RESEARCH') != '1':
        return pd.DataFrame()
    code = HISTORY_LEAGUES.get(league)
    if not code:
        return pd.DataFrame()
    cache_key = 'history-v2-' + league + '-'.join(seasons())
    cached = store.cached(cache_key, 345600) if store else None
    if cached is not None:
        return clean_history(pd.DataFrame(cached))
    if not allow_fetch:
        return pd.DataFrame()
    if store is None:
        raise ValueError('Personal research downloads require a persistent cache')
    client = session or requests.Session()
    frames = []
    for season in seasons():
        try:
            response = client.get(f'https://www.football-data.co.uk/mmz4281/{season}/{code}.csv', timeout=(5, 15))
            if response.status_code == 200:
                df = pd.read_csv(io.BytesIO(response.content))
                if {'Date','HomeTeam','AwayTeam','FTHG','FTAG'} <= set(df):
                    keep = [c for c in ['Date','HomeTeam','AwayTeam','FTHG','FTAG','AvgH','AvgD','AvgA'] if c in df]
                    frames.append(df[keep])
        except (requests.RequestException, ValueError):
            continue
    if not frames:
        return pd.DataFrame()
    result = clean_history(pd.concat(frames, ignore_index=True))
    if store:
        raw = result.drop(columns=['date']).where(pd.notna(result.drop(columns=['date'])), None)
        # JSON round trip replaces NaN with null.
        import json
        store.cache(cache_key, json.loads(raw.to_json(orient='records')))
    return result


def load_local(league, directory='data/history'):
    """Import the operator's licensed NBA/MLB results; no guessed public endpoint.

    Use Date, HomeTeam, AwayTeam, FTHG (home points/runs), FTAG. Optional AvgH,
    AvgA are baseline odds only, never input predictors. See docs/DATA_CONTRACTS.md.
    """
    if league not in ('NBA', 'MLB'):
        raise ValueError('Local adapter only supports NBA/MLB')
    return load_licensed(league,directory)


def load_licensed(league, directory='data/history'):
    stem = league.lower().replace(' ', '_')
    path = Path(directory) / (stem + '.csv')
    if not path.exists():
        return pd.DataFrame()
    manifest = Path(directory) / (stem + '.source.json')
    if not manifest.exists():
        raise ValueError('Historical source/licence manifest required')
    source = json.loads(manifest.read_text())
    if not source.get('source') or not source.get('license_reference') or source.get('commercial_use') is not True:
        raise ValueError('Licensed historical data provenance required')
    if source.get('normalized_sha256'):
        from hashlib import sha256
        if sha256(path.read_bytes()).hexdigest()!=source['normalized_sha256']:
            raise ValueError('Historical dataset differs from its provenance hash')
    return clean_history(pd.read_csv(path), 'Soccer' if league not in ('NBA','MLB') else league)
