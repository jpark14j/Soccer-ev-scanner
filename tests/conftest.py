"""Synthetic fixtures for software tests only; never production recommendations."""
from datetime import datetime, timezone
from dataclasses import replace
import pytest
import requests
import httpx
from intelligence.domain import Quote, Estimate
from intelligence.ev import qualify
from intelligence.storage import Store

NOW = datetime(2026,10,16,2,0,tzinfo=timezone.utc)
OPENAI_TEST_KEY = 'sk-test-NEVER-A-REAL-KEY'


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args,**kwargs):
        raise AssertionError('Unit/integration tests must not call external networks')
    monkeypatch.setattr(requests.sessions.Session,'request',blocked)
    monkeypatch.setattr(httpx.HTTPTransport,'handle_request',blocked)
    monkeypatch.setattr(httpx.AsyncHTTPTransport,'handle_async_request',blocked)


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path/'test.sqlite3')


@pytest.fixture
def quote():
    return Quote('the-odds-api','NBA','NBA','fixture-event','Home vs Away','Home','Away',
                 '2026-10-17T01:00:00+00:00','betmgm_ca_on','BetMGM (CA - ON)','h2h','Home',
                 None,'',1.9,'2026-10-16T01:59:00+00:00','2026-10-16T01:59:01+00:00','CA-ON')


@pytest.fixture
def estimate():
    return Estimate(.65,.60,.70,'nba-margin-normal-1','2026-10-14T00:00:00+00:00',
                    'synthetic-test-evidence',True,('Test risk',),'NBA','NBA','h2h')


@pytest.fixture
def opportunity(quote,estimate):
    return qualify(quote,estimate,NOW)[0]
