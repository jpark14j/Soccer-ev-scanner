"""Input/privacy controls; no conversation persistence outside session memory."""
from datetime import timedelta
import re
import unicodedata
from intelligence.domain import utcnow, parse_time

PATTERNS = (
    r'\bsk-[A-Za-z0-9_-]{8,}',
    r'\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}',
    r'\b\d{6,}:[A-Za-z0-9_-]{15,}',
    r'(?i)\b(?:OPENAI_API_KEY|ODDS_API_KEY|TELEGRAM_BOT_TOKEN|TELEGRAM_CHAT_ID|RESEARCH_BACKUP_SERVICE_KEY|RESEARCH_STATE_SERVICE_KEY|RESEARCH_STATE_READER_KEY|RESEARCH_STATE_READ_TOKEN)\s*[=:]\s*[\"\']?[^\s\"\']+',
    r'(?i)\bBearer\s+[^\s,;\"\']+',
)


class InvalidChatInput(ValueError):
    pass


def redact(text, sensitive=()):
    text = str(text)
    for value in sensitive:
        if value and len(value) >= 4:
            text = text.replace(value, '[redacted]')
    for pattern in PATTERNS:
        text = re.sub(pattern, '[redacted]', text)
    return text


def redact_data(value,sensitive=()):
    """Preserve numeric evidence while redacting nested diagnostic display strings."""
    if isinstance(value,str):return redact(value,sensitive)
    if isinstance(value,dict):return {redact(str(k),sensitive):redact_data(v,sensitive) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [redact_data(v,sensitive) for v in value]
    return value


def validate_input(text, config):
    if not isinstance(text, str):
        raise InvalidChatInput('Enter a text question.')
    text = unicodedata.normalize('NFC', text).strip()
    if not text:
        raise InvalidChatInput('Enter a question before sending.')
    if len(text) > config.max_input_chars:
        raise InvalidChatInput(f'Keep questions within {config.max_input_chars} characters.')
    if any(unicodedata.category(c).startswith('C') and c not in '\n\t' for c in text):
        raise InvalidChatInput('Remove control characters from the question.')
    if redact(text, config.sensitive_values) != text:
        raise InvalidChatInput('This message appears to contain a credential. It was not sent or saved. Remove it and try again.')
    return text


def conversation(state, config, now=None):
    """Expire on the next app interaction; runtime reclaims disconnected sessions."""
    now = now or utcnow()
    expired = False
    if state:
        try:
            expired = now - parse_time(state['last_activity']) > timedelta(minutes=config.idle_minutes)
        except (KeyError, TypeError, ValueError):
            expired = True
    if not state or expired:
        state = {'messages': [], 'last_activity': now.isoformat()}
    # Recheck past messages after settings/key changes; a credential must not be
    # replayed to the browser or provider from an old session.
    state['messages'] = [m for m in state.get('messages', [])
                         if isinstance(m, dict) and redact(m.get('content',''),config.sensitive_values)==m.get('content','')][-config.max_session_messages:]
    return state, expired


def append_message(state, message, config, now=None):
    state['messages'].append(message)
    state['messages'] = state['messages'][-config.max_session_messages:]
    state['last_activity'] = (now or utcnow()).isoformat()
