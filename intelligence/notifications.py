"""Formatting and safe Telegram transport shared by the existing daily entrypoint."""
import requests
from intelligence.ev import qualify
from intelligence.parlays import CATEGORIES, NO_PARLAYS
from intelligence.domain import utcnow


def format_digest(analysis, date, site='', now=None):
    now = now or utcnow()
    opportunities = [o for o in analysis.opportunities if qualify(o.quote,o.estimate,now)[0]]
    lines = [f'Sports Intelligence — Ontario morning report ({date})']
    for sport in ('NBA','Soccer','MLB'):
        rows = [o for o in opportunities if o.quote.sport==sport][:1]
        lines.extend(['',sport+' singles'])
        if not rows:
            lines.append('No qualifying opportunities identified.')
        for o in rows:
            q,e = o.quote,o.estimate
            lines.extend([f'{q.event}: {q.selection} ({q.market})',
                          f'{q.bookmaker_name} · decimal {q.odds:.2f}',
                          f'Model probability {e.probability:.1%} · estimated EV {o.ev:+.1%}',
                          f'Conservative EV {o.conservative_ev:+.1%}; validated model + current Ontario quote.',
                          f'Last provider update: {q.source_updated_at}'])
    lines.extend(['',NO_PARLAYS])
    lines.append(' / '.join(CATEGORIES)+': none qualified.')
    if analysis.errors:
        lines.extend(['','Data collection incomplete. No claim that all markets were evaluated.'])
    if site:
        lines.extend(['',f'Dashboard: {site}'])
    lines.extend(['','19+ Ontario. Estimates are uncertain; prices can change. No guaranteed returns or wagers placed.'])
    message = '\n'.join(lines)
    # Keep a single message; never cut a recommendation mid-way.
    if len(message)>4000:
        raise ValueError('Report exceeds Telegram single-message limit; no partial report sent')
    return message


def send_telegram(token,chat_id,text,session=None):
    client = session or requests.Session()
    try:
        response = client.post(f'https://api.telegram.org/bot{token}/sendMessage',
            json={'chat_id':chat_id,'text':text,'disable_web_page_preview':True},timeout=(5,20))
        if response.status_code != 200 or not response.json().get('ok'):
            raise RuntimeError('Telegram rejected the daily report; inspect bot access securely')
    except (requests.RequestException,ValueError):
        # An ambiguous timeout must not be retried automatically: send may have succeeded.
        raise RuntimeError('Telegram delivery uncertain; automatic retry blocked to prevent duplicates') from None
