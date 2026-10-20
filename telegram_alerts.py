"""Existing Toronto daily entrypoint with durable reservation and publication phases."""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from intelligence.domain import Estimate, Opportunity, Quote, parse_time, utcnow
from intelligence.ledger import archive
from intelligence.notifications import format_digest, send_telegram
from intelligence.pipeline import Analysis, configured_store, run_analysis, publish_current
from intelligence.providers import LEAGUES

STATE_PATH = Path('.daily_digest_state.json')
PREPARED_PATH = Path('work/prepared-digest.json')
TORONTO = ZoneInfo('America/Toronto')


def read_state():
    try:
        state = json.loads(STATE_PATH.read_text())
        if not isinstance(state,dict):
            raise ValueError('Invalid digest state')
        return state
    except FileNotFoundError:
        return {}
    except (ValueError,OSError):
        raise RuntimeError('Digest state unreadable; sending blocked to avoid duplicates') from None


def write_state(state):
    temporary = STATE_PATH.with_suffix('.tmp')
    temporary.write_text(json.dumps(state,indent=2)+'\n')
    temporary.replace(STATE_PATH)


def reserve(now=None):
    now = now or datetime.now(TORONTO)
    today = now.date().isoformat()
    hour = int(os.getenv('DIGEST_HOUR_LOCAL','9'))
    if not 0 <= hour <= 21:
        raise ValueError('DIGEST_HOUR_LOCAL must be between 0 and 21')
    if os.getenv('GITHUB_EVENT_NAME') != 'workflow_dispatch' and not hour <= now.hour < hour+3:
        return False
    state = read_state()
    if state.get('last_sent_date')==today or state.get('pending_date'):
        return False
    write_state(state | {'pending_date':today})
    return True


def prepare(store):
    leagues = [s.strip() for s in (os.getenv('DIGEST_LEAGUES') or ','.join(LEAGUES)).split(',') if s.strip()]
    analysis = run_analysis(os.getenv('ODDS_API_KEY',''),leagues,store)
    if analysis.errors:
        raise RuntimeError('Daily scan incomplete; reconcile pending state after resolving data access')
    publish_current(analysis,store)
    archive(store,os.getenv('PREDICTION_LEDGER_DIR','ledger'))
    PREPARED_PATH.parent.mkdir(parents=True,exist_ok=True)
    PREPARED_PATH.write_text(json.dumps({'prepared_at':utcnow().isoformat(),
        'checked_at':analysis.checked_at,'opportunities':[o.to_dict() for o in analysis.opportunities]},allow_nan=False)+'\n')
    return analysis


def load_prepared():
    prepared = json.loads(PREPARED_PATH.read_text())
    age = (utcnow()-parse_time(prepared['prepared_at'])).total_seconds()
    if not 0<=age<=300:
        raise RuntimeError('Prepared report expired; no stale report sent')
    opportunities=[]
    for payload in prepared['opportunities']:
        payload['quote']=Quote(**payload['quote'])
        payload['estimate']=Estimate(**payload['estimate'])
        opportunities.append(Opportunity(**payload))
    return Analysis(opportunities=opportunities,checked_at=prepared['checked_at'])


def main():
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--reserve',action='store_true')
    group.add_argument('--prepare-reserved',action='store_true')
    group.add_argument('--send-reserved',action='store_true')
    group.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    if args.reserve:
        print('reserved='+str(reserve()).lower())
        return
    now=datetime.now(TORONTO)
    if not args.dry_run:
        if args.prepare_reserved or args.send_reserved:
            if read_state().get('pending_date')!=now.date().isoformat():
                raise RuntimeError('No current persisted delivery reservation')
        elif not reserve(now):
            print('Digest skipped: outside window, already sent, or reconciliation required')
            return
    store=configured_store()
    if args.send_reserved:
        analysis=load_prepared()
    else:
        analysis=prepare(store)
    if args.prepare_reserved:
        print('Prepared report and archived predictions; persist archive before sending')
        return
    message=format_digest(analysis,now.date().isoformat(),os.getenv('STREAMLIT_APP_URL','https://soccer-ev-scanner-jp.streamlit.app'))
    if args.dry_run:
        print(message)
        return
    token,chat_id=os.getenv('TELEGRAM_BOT_TOKEN',''),os.getenv('TELEGRAM_CHAT_ID','')
    if not token or not chat_id:
        raise RuntimeError('Telegram secrets missing; no message sent')
    if not store.claim_delivery(now.date().isoformat()):
        print('Digest delivery already pending or sent')
        return
    send_telegram(token,chat_id,message)
    store.delivery_sent(now.date().isoformat())
    write_state({'last_sent_date':now.date().isoformat()})
    print('Sent one daily report')


if __name__=='__main__':
    main()
