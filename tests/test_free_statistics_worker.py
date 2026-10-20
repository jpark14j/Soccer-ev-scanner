"""Public collector bounds, fencing, preserved budgets and failed refreshes."""
from datetime import timedelta
from unittest.mock import patch
import json
import pytest
from intelligence.domain import utcnow
from intelligence.free_statistics_worker import download,update,URL,MAX_BYTES
from intelligence.openliga import current
from intelligence.statistics_import import protected_counts
from test_current_statistics import season


class Response:
    status_code=200
    def __init__(self,body):self.body=body;self.closed=False
    def iter_content(self,size):yield self.body
    def close(self):self.closed=True


def test_public_download_has_one_fixed_url_no_key_no_retry_no_redirect():
    class Session:
        def __init__(self,body):self.response=Response(body);self.calls=[]
        def get(self,*args,**kwargs):self.calls.append((args,kwargs));return self.response
    s=Session(b'[]');raw,at=download(s)
    assert raw==b'[]' and s.response.closed and len(s.calls)==1
    args,kwargs=s.calls[0];assert args==(URL,) and not kwargs['allow_redirects']
    assert 'Authorization' not in kwargs['headers'] and 'params' not in kwargs
    s=Session(b'x'*(MAX_BYTES+1))
    with pytest.raises(ValueError):download(s)
    assert s.response.closed


def test_refresh_preserves_hold_budgets_and_successful_cache_after_failure(store):
    from conftest import NOW
    now=NOW;raw=json.dumps(season(now)).encode();before=protected_counts(store)
    with patch('intelligence.fixture_research.collect',return_value={'forecasts':[]}),patch('intelligence.current_score_research.candidates',return_value=[]):
        report,rows=update(store,now,lambda:(raw,now.isoformat()))
    assert report['public_results_requests']==1 and report['odds_api_credits']==0 and not rows
    assert before==protected_counts(store)
    first=current(store,'Bundesliga',now)
    def blocked():raise AssertionError('No repeated collection inside interval')
    assert update(store,now+timedelta(hours=1),blocked)[0]['public_results_requests']==0
    later=now+timedelta(hours=4)
    failed,rows=update(store,later,lambda:(b'[]',later.isoformat()))
    assert failed['state']=='Partial free-statistics update' and failed['source_observed_at']==first[1]['checked_at']
    assert not rows and failed['bundesliga_source_status']['problem']
    assert current(store,'Bundesliga',later)[0]==first[0]
    assert protected_counts(store)==before


def test_source_is_refreshed_across_utc_midnight_even_inside_cache_interval(store):
    from datetime import datetime,timezone
    now=datetime(2026,10,18,23,30,tzinfo=timezone.utc);later=now+timedelta(hours=1)
    raw=json.dumps(season(now)).encode();calls=[]
    with patch('intelligence.fixture_research.collect',return_value={'forecasts':[]}),patch('intelligence.current_score_research.candidates',return_value=[]):
        update(store,now,lambda:(raw,now.isoformat()))
        def fetch():calls.append(True);return raw,later.isoformat()
        result,_=update(store,later,fetch)
    assert calls==[True] and result['public_results_requests']==1
    assert current(store,'Bundesliga',later)[1]['checked_at']==later.isoformat()


def test_failed_transport_cannot_overwrite_results_or_mark_refresh_success(store):
    def unavailable():raise ValueError('No response')
    report,rows=update(store,fetch=unavailable)
    assert report['state']=='Partial free-statistics update' and not rows
    assert report['source_observed_at'] is None and not report['bundesliga_source_status']['cached_inputs_valid']
    assert report['new_pregame_records']==0 and report['new_verified_outcomes']==0
    assert store.cached('free-statistics-last-success',86400) is None


def test_public_worker_code_never_reads_sports_credentials_or_reserves_credits():
    from pathlib import Path
    text=Path('intelligence/free_statistics_worker.py').read_text()
    assert all(word not in text for word in ('ODDS_API_KEY','FOOTBALL_DATA_TOKEN','OPENAI_API_KEY','.reserve(',"'release'",'held=false'))


def test_free_schedule_is_separate_private_and_preserves_disabled_held_worker():
    from pathlib import Path
    import yaml
    source=Path('deploy/free_statistics_worker.yml').read_text();w=yaml.safe_load(source)
    trigger=w.get('on',w.get(True));job=w['jobs']['statistics'];env=job['steps'][-1]['env']
    assert trigger['schedule']==[{'cron':'17 */4 * * *'}]
    assert 'sports-ai-private-recovery' in job['if'] and 'repository.private == true' in job['if']
    assert w['permissions']=={'contents':'read'} and w['concurrency']['group']=='development-research-authority'
    assert job['steps'][0]['with']['persist-credentials'] is False
    assert env['ODDS_API_KEY']==env['OPENAI_API_KEY']==env['FOOTBALL_DATA_TOKEN']==''
    assert env['RESEARCH_WORKER_ENABLED']==env['RESEARCH_SCHEDULE_ENABLED']==env['PAID_ANALYST_APPROVED']=='0'
    assert env['ODDS_DAILY_CREDITS']=='9' and 'SERVICE_KEY' not in job['steps'][0].get('env',{})
