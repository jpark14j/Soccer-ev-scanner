"""Typed provenance and eligibility contracts. All times are timezone aware."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math


def utcnow():
    return datetime.now(timezone.utc)


def parse_time(value):
    value = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('Timestamp must include timezone')
    return value.astimezone(timezone.utc)


def finite(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class Quote:
    provider: str
    sport: str
    league: str
    event_id: str
    event: str
    home: str
    away: str
    commence_time: str
    bookmaker: str
    bookmaker_name: str
    market: str
    selection: str
    point: float | None
    participant: str
    odds: float
    source_updated_at: str
    received_at: str
    jurisdiction: str = 'unverified'
    suspended: bool = False

    @property
    def key(self):
        # Provider event IDs are not assumed interchangeable across providers.
        return (self.provider, self.event_id, self.market, self.selection, self.point, self.participant)

    @property
    def id(self):
        return digest((*self.key, self.bookmaker))

    def status(self, now=None, max_age=300):
        now = now or utcnow()
        try:
            source, received, start = map(parse_time, (self.source_updated_at, self.received_at, self.commence_time))
        except (TypeError, ValueError):
            return 'invalid timestamp'
        if not finite(self.odds) or self.odds <= 1:
            return 'invalid price'
        if self.suspended:
            return 'suspended'
        if source > received or received > now or source > now:
            return 'future timestamp'
        if (now - source).total_seconds() > max_age or (now - received).total_seconds() > max_age:
            return 'stale'
        if start <= now:
            return 'in-play: live model unavailable'
        return 'current'


@dataclass(frozen=True)
class Estimate:
    probability: float
    lower: float
    upper: float
    model_version: str
    training_end: str
    evidence_id: str
    validated: bool = False
    risk_factors: tuple[str, ...] = ()
    sport: str = ''
    league: str = ''
    market: str = 'h2h'

    def valid(self):
        return all(finite(x) for x in (self.probability, self.lower, self.upper)) and 0 <= self.lower <= self.probability <= self.upper <= 1


@dataclass(frozen=True)
class Opportunity:
    quote: Quote
    estimate: Estimate
    ev: float
    conservative_ev: float
    implied_probability: float
    score: float

    def to_dict(self):
        return asdict(self)
