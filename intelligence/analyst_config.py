"""Server-only assistant settings. Reading configuration never contacts OpenAI."""
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import os
import re
from intelligence.chat_privacy import redact

# Published standard text rates checked 2026-10-16; recheck before activation.
MODEL_RATES = {
    'gpt-4.1-mini': ('0.40', '1.60'),
    'gpt-4.1-mini-2025-04-14': ('0.40', '1.60'),
}


@dataclass(frozen=True)
class AnalystConfig:
    approved: bool = False
    api_key: str = field(default='', repr=False)
    model: str = 'gpt-4.1-mini'
    max_daily_requests: int = 20
    max_monthly_requests: int = 100
    max_session_requests: int = 20
    max_input_chars: int = 2000
    max_input_tokens: int = 16000
    max_output_tokens: int = 800
    max_context_chars: int = 6000
    max_history_messages: int = 8
    max_session_messages: int = 24
    idle_minutes: int = 30
    monthly_usd: Decimal = Decimal('5')
    daily_usd: Decimal = Decimal('0.50')
    request_usd: Decimal = Decimal('0.02')
    input_rate: Decimal = Decimal('0.40')
    output_rate: Decimal = Decimal('1.60')
    timeout_seconds: int = 25
    errors: tuple[str, ...] = ()
    sensitive_values: tuple[str, ...] = field(default=(), repr=False)

    @property
    def paid_ready(self):
        return self.approved and bool(self.api_key) and not self.errors


def load_config(secret_getter=None):
    def get(name, default=''):
        value = os.getenv(name)
        if value is None and secret_getter:
            value = secret_getter(name)
        return default if value is None or value == '' else value

    errors = []
    def integer(name, default, lo, hi):
        try:
            raw = get(name, str(default))
            if isinstance(raw, bool):
                raise ValueError()
            value = int(str(raw))
            if not lo <= value <= hi:
                raise ValueError()
            return value
        except (ValueError, TypeError):
            errors.append(f'{name} must be an integer between {lo} and {hi}.')
            return default

    def money(name, default, maximum='1000'):
        try:
            value = Decimal(str(get(name, default)))
            if not value.is_finite() or not 0 <= value <= Decimal(maximum):
                raise ValueError()
            return value
        except (ValueError, InvalidOperation):
            errors.append(f'{name} must be a non-negative finite amount within the documented limit.')
            return Decimal(default)

    model = str(get('OPENAI_MODEL', 'gpt-4.1-mini'))
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}', model):
        errors.append('OPENAI_MODEL has an invalid format.')
        model = 'gpt-4.1-mini'
    known = MODEL_RATES.get(model)
    input_rate = money('ANALYST_INPUT_USD_PER_MILLION', known[0] if known else '0')
    output_rate = money('ANALYST_OUTPUT_USD_PER_MILLION', known[1] if known else '0')
    if input_rate <= 0 or output_rate <= 0:
        errors.append('Configure positive standard input/output token prices for this model before enabling requests.')
    if known:
        input_rate = max(input_rate, Decimal(known[0]))
        output_rate = max(output_rate, Decimal(known[1]))
    key = str(get('OPENAI_API_KEY', ''))
    sensitive = tuple(str(get(name)) for name in ('OPENAI_API_KEY', 'ODDS_API_KEY', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID', 'FOOTBALL_DATA_TOKEN') if get(name))
    if redact(model,sensitive)!=model:
        errors.append('OPENAI_MODEL appears to contain a credential; paid requests are blocked.')
        model = 'gpt-4.1-mini'
    return AnalystConfig(
        approved=str(get('PAID_ANALYST_APPROVED', '0')) == '1', api_key=key,
        model=model,
        max_daily_requests=integer('ANALYST_MAX_DAILY_REQUESTS',20,0,1000),
        max_monthly_requests=integer('ANALYST_MAX_MONTHLY_REQUESTS',100,0,10000),
        max_session_requests=integer('ANALYST_MAX_SESSION_REQUESTS',20,0,1000),
        max_input_chars=integer('ANALYST_MAX_INPUT_CHARS',2000,50,8000),
        max_input_tokens=integer('ANALYST_MAX_INPUT_TOKENS',16000,1000,64000),
        max_output_tokens=integer('ANALYST_MAX_OUTPUT_TOKENS',800,128,4096),
        max_context_chars=integer('ANALYST_MAX_CONTEXT_CHARS',6000,1500,16000),
        max_history_messages=integer('ANALYST_MAX_HISTORY_MESSAGES',8,0,20),
        max_session_messages=integer('ANALYST_MAX_SESSION_MESSAGES',24,4,60),
        idle_minutes=integer('ANALYST_IDLE_MINUTES',30,5,120),
        monthly_usd=money('ANALYST_MONTHLY_USD_CAP','5','100'),
        daily_usd=money('ANALYST_DAILY_USD_CAP','0.50','100'),
        request_usd=money('ANALYST_MAX_REQUEST_USD','0.02','1'),
        input_rate=input_rate,output_rate=output_rate,
        timeout_seconds=integer('ANALYST_TIMEOUT_SECONDS',25,5,60),
        errors=tuple(errors),sensitive_values=sensitive)
