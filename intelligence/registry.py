"""Evidence-backed Ontario mapping; never substitute US or global book keys."""
import json
from pathlib import Path
from intelligence.domain import parse_time, utcnow

REGISTRY_PATH = Path(__file__).resolve().parents[1] / 'config' / 'ontario_books.json'


def load_registry(path=REGISTRY_PATH):
    return json.loads(Path(path).read_text())


def eligible_book(key, now=None, registry=None):
    registry = registry or load_registry()
    now = now or utcnow()
    if not parse_time(registry['reviewed_at']) <= now <= parse_time(registry['review_expires_at']):
        return False
    return any(b.get('odds_api_key') == key and b.get('legal_basis') in ('iGO directory', 'OLG')
               for b in registry['books'])
