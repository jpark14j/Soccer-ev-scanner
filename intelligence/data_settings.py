"""Interactive data controls honor Secrets/environment without raising any cap."""
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class DataSettings:
    daily_limit: int=9
    cache_seconds: int=1800
    collect_results: bool=False
    errors: tuple=()
    window_hours: int=48


def load_settings(secret_getter=None):
    def get(name,default):
        value=os.getenv(name)
        if value is None and secret_getter:
            value=secret_getter(name)
        return default if value is None or value=='' else value
    errors=[]
    def integer(name,default,lo,hi):
        try:
            value=int(str(get(name,default)))
            if not lo<=value<=hi:
                raise ValueError()
            return value
        except (TypeError,ValueError):
            errors.append(f'{name} is invalid; interactive data requests are blocked.')
            return default
    cap=integer('ODDS_DAILY_CREDITS',9,0,9)
    ttl=integer('ODDS_CACHE_SECONDS',1800,60,86400)
    window=integer('SLATE_WINDOW_HOURS',48,1,168)
    return DataSettings(0 if errors else cap,ttl,str(get('COLLECT_RESULTS','0'))=='1',tuple(errors),window)
