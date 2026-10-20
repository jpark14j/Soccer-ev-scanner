"""Atomic, conservative admission limits. Never stores prompts or credentials."""
from datetime import timedelta
from decimal import Decimal, ROUND_CEILING
from intelligence.domain import utcnow


class UsageLimit(ValueError):
    pass


def reservation_cost(config, input_bound):
    # Rates are USD per million tokens; one microdollar is 1/1,000,000 USD.
    return int((Decimal(input_bound)*config.input_rate +
                Decimal(config.max_output_tokens)*config.output_rate).to_integral_value(rounding=ROUND_CEILING))


class UsageLedger:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS analyst_calls(
                request_id TEXT PRIMARY KEY, day TEXT NOT NULL, month TEXT NOT NULL,
                reserved_microusd INTEGER NOT NULL, input_bound INTEGER NOT NULL,
                output_cap INTEGER NOT NULL, input_tokens INTEGER, output_tokens INTEGER)''')

    def snapshot(self, now=None):
        now = now or utcnow()
        day, month = now.date().isoformat(), now.strftime('%Y-%m')
        with self.store.connect() as db:
            rows = db.execute('''SELECT COUNT(*) AS n, COALESCE(SUM(reserved_microusd),0) AS cost,
                COALESCE(SUM(CASE WHEN day=? THEN 1 ELSE 0 END),0) AS daily_n,
                COALESCE(SUM(CASE WHEN day=? THEN reserved_microusd ELSE 0 END),0) AS daily_cost
                FROM analyst_calls WHERE month=?''',(day,day,month)).fetchone()
            legacy = 0
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='llm_budget'").fetchone():
                previous = db.execute('SELECT reserved_cents FROM llm_budget WHERE month=?',(month,)).fetchone()
                legacy = previous['reserved_cents']*10_000 if previous else 0
        return {'month_requests':rows['n'],'day_requests':rows['daily_n'],
                'month_reserved_usd':(rows['cost']+legacy)/1_000_000,'day_reserved_usd':rows['daily_cost']/1_000_000}

    def reserve(self, request_id, config, input_bound, session_requests=0, now=None):
        now = now or utcnow()
        if not isinstance(request_id,str) or not 16 <= len(request_id) <= 64 or not request_id.isalnum():
            raise UsageLimit('Invalid request identifier; no request was sent.')
        if not 0 < input_bound <= config.max_input_tokens:
            raise UsageLimit('The input token safeguard was reached. Shorten the question or clear the conversation.')
        if session_requests >= config.max_session_requests:
            raise UsageLimit('The browser-session request limit was reached.')
        cost = reservation_cost(config,input_bound)
        if cost > config.request_usd*1_000_000:
            raise UsageLimit('The per-request budget safeguard was reached.')
        day, month = now.date().isoformat(), now.strftime('%Y-%m')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM analyst_calls WHERE request_id=?',(request_id,)).fetchone():
                raise UsageLimit('This request was already attempted; automatic resubmission is blocked.')
            rows = db.execute('SELECT day, reserved_microusd FROM analyst_calls WHERE month=?',(month,)).fetchall()
            daily = [r for r in rows if r['day']==day]
            if len(rows) >= config.max_monthly_requests or len(daily) >= config.max_daily_requests:
                raise UsageLimit('The daily or monthly request limit was reached.')
            # Retain reservations made by the previous adapter during migration.
            legacy = 0
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='llm_budget'").fetchone():
                previous = db.execute('SELECT reserved_cents FROM llm_budget WHERE month=?',(month,)).fetchone()
                legacy = previous['reserved_cents']*10_000 if previous else 0
            if sum(r['reserved_microusd'] for r in rows)+legacy+cost > config.monthly_usd*1_000_000:
                raise UsageLimit('The monthly budget safeguard was reached.')
            if sum(r['reserved_microusd'] for r in daily)+cost > config.daily_usd*1_000_000:
                raise UsageLimit('The daily budget safeguard was reached.')
            db.execute('INSERT INTO analyst_calls VALUES(?,?,?,?,?,?,NULL,NULL)',
                       (request_id,day,month,cost,input_bound,config.max_output_tokens))
            db.execute('DELETE FROM analyst_calls WHERE day<?',((now-timedelta(days=90)).date().isoformat(),))
        return cost

    def record_tokens(self, request_id, input_tokens, output_tokens):
        # Actual provider token counts are diagnostics, never refunds. Retaining
        # the full reservation makes failures and ambiguous retries conservative.
        if all(type(n) is int and n>=0 for n in (input_tokens,output_tokens)):
            with self.store.connect() as db:
                db.execute('UPDATE analyst_calls SET input_tokens=?,output_tokens=? WHERE request_id=?',
                           (input_tokens,output_tokens,request_id))
