"""One daily Toronto-morning Telegram digest; does not place bets."""
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import scanner_core as core

STATE_PATH = Path('.daily_digest_state.json')
LEAGUES = ['Premier League', 'La Liga', 'Bundesliga', 'Serie A']
SITE = os.getenv('STREAMLIT_APP_URL', 'https://soccer-ev-scanner-jp.streamlit.app')
TORONTO = ZoneInfo('America/Toronto')


def main():
    now = datetime.now(TORONTO)
    if os.getenv("GITHUB_EVENT_NAME") != "workflow_dispatch" and not (9 <= now.hour < 12):
        print(f"Outside Toronto morning delivery window: {now.isoformat()}")
        return
    today = now.date().isoformat()
    try:
        state = json.loads(STATE_PATH.read_text())
    except (FileNotFoundError, ValueError):
        state = {}
    if state.get('last_sent_date') == today:
        print(f'Digest already sent for {today}')
        return

    token = os.environ['TELEGRAM_BOT_TOKEN']
    chat_id = os.environ['TELEGRAM_CHAT_ID']
    core.KEY = os.environ['ODDS_API_KEY']
    rows, errors, timestamp = core.scan(LEAGUES)
    if errors:
        raise RuntimeError('Odds scan incomplete; no potentially misleading digest sent: ' + '; '.join(map(str, errors)))

    histories = {league: core.load_history(league) for league in {r['league'] for r in rows}}
    predictions = {}
    for row in rows:
        key = (row['event_id'], row['league'])
        if key not in predictions:
            predictions[key] = core.independent_prediction(
                histories[row['league']], row['home'], row['away'], row['kickoff']
            )
        model = predictions[key]
        if model:
            index = 0 if row['selection'] == row['home'] else 1 if row['selection'] == 'Draw' else 2
            row['model_prob'] = model['probabilities'][index]
            row['prob'] = min(row['prob'], row['model_prob'])
            row['edge'] = row['prob'] * row['odds'] - 1
        else:
            row['model_prob'] = None

    picks = core.shortlist(rows)[:3]
    lines = [f'⚽ Soccer Picks — Morning Digest ({now:%b %d})',
             f'Checked {len(rows)} selections across four leagues.']
    if not picks:
        lines += ['', 'No strong picks today. Nothing passed the current checks.']
    else:
        for i, pick in enumerate(picks, 1):
            lines += ['', f'{i}. {pick["kind"]}']
            for leg in pick['legs']:
                lines.append(f'• {leg["match"]}: {leg["selection"]}')
                lines.append(f'  Kickoff (UTC): {leg["kickoff"]}')
            lines += [f'BetMGM odds at scan: {pick["odds"]:.2f}',
                      f'Experimental estimated chance: {pick["prob"]:.1%}']
    lines += ['', f'Review current prices: {SITE}',
              'Experimental, unvalidated estimates. Odds can change. No bets are placed.']
    response = requests.post(
        f'https://api.telegram.org/bot{token}/sendMessage',
        json={'chat_id': chat_id, 'text': '\n'.join(lines), 'disable_web_page_preview': True},
        timeout=20,
    )
    response.raise_for_status()
    if not response.json().get('ok'):
        raise RuntimeError('Telegram did not accept the digest')
    STATE_PATH.write_text(json.dumps({'last_sent_date': today}, indent=2) + '\n')
    print(f'Sent one morning digest for {today} with {len(picks)} picks.')


if __name__ == '__main__':
    main()
