"""Saved-only Home with synthetic prices; private dispatch must be unreachable."""
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
import pytest
from intelligence.domain import utcnow
from intelligence.pipeline import Analysis
from intelligence.manual_research import IDENTITY
from test_manual_research import TOKEN,COMMIT,CODE as ACCESS_CODE


@pytest.fixture
def home(tmp_path,monkeypatch,quote):
    from streamlit.testing.v1 import AppTest
    from intelligence.storage import Store
    now=utcnow();store=Store(tmp_path/'manual-home.sqlite3',read_replica=True)
    with store.connect() as db:db.execute('UPDATE store_identity SET instance=?',(IDENTITY,))
    store.shared_status={'manifest':{'store_instance':IDENTITY},'verified_at':now.isoformat(),
        'envelope':{'generation':2,'held':False,'heartbeat':{}}}
    for k,v in {'INTELLIGENCE_DB':store.path,'ODDS_API_KEY':'synthetic-provider-key',
        'RESEARCH_MANUAL_ENABLED':'1','RESEARCH_MANUAL_GITHUB_TOKEN':TOKEN,
        'RESEARCH_MANUAL_OWNER_HASH':sha256(ACCESS_CODE.encode()).hexdigest(),'RESEARCH_MANUAL_APP_COMMIT':COMMIT,
        'PAID_ANALYST_APPROVED':'0','RESEARCH_SHARED_STATE_ENABLED':'0',
        'PREDICTION_LEDGER_DIR':str(tmp_path/'empty-ledger')}.items():monkeypatch.setenv(k,v)
    qs=[replace(quote,sport=sport,league=league,event_id='synthetic-'+sport,
        source_updated_at=now.isoformat(),received_at=now.isoformat(),commence_time=(now+timedelta(days=1)).isoformat())
        for sport,league in [('NBA','NBA'),('MLB','MLB'),('Soccer','Premier League')]]
    analysis=Analysis(quotes=qs)
    class Private:
        def __init__(self):self.dispatched=[];self.polls=0
        def dispatch(self,rid):self.dispatched.append(rid)
        def status(self,rid):self.polls+=1;return {'phase':'running'}
    client=Private()
    with patch('intelligence.pipeline.configured_store',return_value=store),\
         patch('intelligence.pipeline.run_analysis',return_value=analysis) as scans,\
         patch('intelligence.manual_research.DispatchClient',return_value=client),\
         patch('openai.OpenAI',side_effect=AssertionError('Paid AI disabled')):
        app=AppTest.from_file(Path('app.py').resolve(),default_timeout=40).run()
        assert not app.exception
        yield app,store,analysis,client,scans


def test_home_passwordless_saved_refresh_cannot_dispatch_even_with_old_owner_configuration(home):
    app,store,_,client,scans=home
    button=next(b for b in app.button if b.key=='find_best_bets')
    assert not button.disabled and not app.text_input
    assert not any('private research access'==e.label.lower() for e in app.expander)
    button.click().run()
    assert not app.exception and app.sidebar.radio[0].value=='Best Picks & Parlays'
    assert not client.dispatched and client.polls==0
    assert ACCESS_CODE not in str(app.main.proto) and TOKEN not in str(app.main.proto)
    assert any('Showing saved predictions' in x.value for x in app.caption)
    assert scans.call_count<=2
    with store.connect() as db:assert db.execute('SELECT count(*) FROM budget').fetchone()[0]==0


def test_fresh_unmodeled_prices_show_experimental_two_and_three_leg_research(home):
    app,store,_,client,_=home
    from intelligence.positive_ev import EMPTY
    assert any(i.value==EMPTY for i in app.info)
    assert not any('price-only research' in x.value for x in app.markdown)
    app.sidebar.radio[0].set_value('Best Picks & Parlays').run()
    assert any(e.label=='Experimental market research · model evidence incomplete' for e in app.expander)
    assert any('2-leg price-only research' in x.value for x in app.markdown)
    assert any('3-leg price-only research' in x.value for x in app.markdown)
    assert any('Model probability and EV unavailable' in x.value for x in app.caption)
    assert not any('Estimated chance:' in x.value for x in app.markdown)
    assert all(sport in ' '.join(t.value for t in app.text) for sport in ('NBA','Soccer','MLB'))
    assert not client.dispatched and not store.records()


def test_stale_prices_cannot_become_home_candidates(home):
    app,_,analysis,client,_=home
    analysis.quotes=[replace(q,source_updated_at=(utcnow()-timedelta(minutes=6)).isoformat()) for q in analysis.quotes]
    app.run()
    assert not app.exception
    assert not any('price-only research' in x.value for x in app.markdown)
    from intelligence.positive_ev import EMPTY
    assert any(x.value==EMPTY for x in app.info) and not client.dispatched
    app.sidebar.radio[0].set_value('Best Picks & Parlays').run()
    assert not any('price-only research' in x.value for x in app.markdown)


def test_ambiguous_duplicate_observations_cannot_be_shown_as_price_research(home):
    app,_,analysis,_,_=home
    analysis.quotes=analysis.quotes+[analysis.quotes[0]]
    app.sidebar.radio[0].set_value('Best Picks & Parlays').run()
    assert not app.exception
    assert not any('3-leg price-only research' in x.value for x in app.markdown)
    assert any('2-leg price-only research' in x.value for x in app.markdown)
