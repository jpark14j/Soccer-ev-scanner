"""Numerical/software fixtures, not sportsbook data or model accuracy evidence."""
from copy import deepcopy
from dataclasses import replace
from datetime import date,timedelta
from pathlib import Path
import json,math
import numpy as np
import pytest
from conftest import NOW
from intelligence.domain import digest
from intelligence.score_distribution import score_distribution,marginals,settlement,joint_outcomes
from intelligence.quant_models import fit_poisson,goal_rates,fit_rho
from intelligence.quant_decision import decide,selection_format
from intelligence.pipeline import Analysis
from intelligence.parlays import CombinedPrice,JointEstimate


def test_score_mass_marginals_and_tail_have_one_coherent_distribution():
    d=score_distribution(1.8,1.1,-.1)
    assert d.mass.shape==(41,41) and np.all(d.mass>=0) and d.mass.sum()==pytest.approx(1.)
    m=marginals(d)
    assert m['home_win']+m['draw']+m['away_win']==pytest.approx(1.) and d.omitted_mass_bound<1e-8
    plain=marginals(score_distribution(1.8,1.1))
    assert plain['btts']==pytest.approx((1-math.exp(-1.8))*(1-math.exp(-1.1)))
    assert m['btts']!=plain['btts'] and not d.validated
    assert d.mass.sum()==pytest.approx(score_distribution(1.8,1.1,-.1,1.15).mass.sum())


@pytest.mark.parametrize('arguments',[(0.,1.),(float('nan'),1.),(1.,9.),(8.,8.,1.),(1.,1.,0.,.1)])
def test_invalid_distribution_parameters_never_produce_a_probability(arguments):
    with pytest.raises(ValueError):score_distribution(*arguments)


@pytest.mark.parametrize('market,selection,line,h,a,expected',[
    ('totals','Over',2.25,1,1,(0.,.5,.5)),('totals','Under',2.25,1,1,(.5,.5,0.)),
    ('totals','Over',2.,1,1,(0.,1.,0.)),('totals','Over',2.5,2,1,(1.,0.,0.)),
    ('spreads','H',-.25,1,1,(0.,.5,.5)),('spreads','H',.25,1,1,(.5,.5,0.)),
    ('spreads','A',.75,1,0,(0.,.5,.5)),('spreads','H',-1.,2,1,(0.,1.,0.)),
    ('btts','Yes',None,1,1,(1.,0.,0.)),('h2h','Draw',None,1,1,(1.,0.,0.))])
def test_quarter_half_integer_and_binary_score_settlement(market,selection,line,h,a,expected):
    assert settlement(market,selection,line,'H','A',h,a)==expected


def soccer_quotes(q):
    q=replace(q,sport='Soccer',league='Premier League',market='btts',selection='Yes',point=None)
    return q,replace(q,market='totals',selection='Over',point=2.5)


def test_same_game_outcomes_are_enumerated_not_multiplied(quote):
    btts,total=soccer_quotes(quote);d=score_distribution(1.8,1.1,-.1)
    joint=joint_outcomes(d,[btts,total]);m=marginals(d)
    assert joint['all_full_win']!=pytest.approx(m['btts']*m['totals_2.5'])
    assert sum(s['probability'] for s in joint['states'])==pytest.approx(1.)
    assert not joint['joint_validated'] and joint['parlay_ev'] is None and joint['combined_odds'] is None
    impossible=joint_outcomes(d,[btts,replace(total,selection='Under',point=1.5)])
    assert impossible['all_full_win']==0
    fractions=joint_outcomes(d,[btts,replace(total,point=2.25)])
    assert any('half-loss' in s['leg_outcomes'] for s in fractions['states'])
    with pytest.raises(ValueError):joint_outcomes(d,[btts,replace(total,commence_time='2026-10-18T01:00:00+00:00')])
    with pytest.raises(ValueError):joint_outcomes(d,[btts,btts])
    with pytest.raises(ValueError):joint_outcomes(d,[quote,replace(quote,selection=quote.away)])


def test_reviewed_alias_orientation_does_not_swap_home_away_score(quote):
    btts,total=soccer_quotes(quote)
    q=replace(btts,home='Arsenal',away='Chelsea',market='h2h',selection='Arsenal')
    alias=replace(total,home='Arsenal FC',away='Chelsea FC')
    normal=replace(total,home='Arsenal',away='Chelsea')
    d=score_distribution(2.,.5)
    assert joint_outcomes(d,[q,alias])['all_full_win']==pytest.approx(joint_outcomes(d,[q,normal])['all_full_win'])


def training_rows():
    rows=[]
    # Deterministic synthetic league, not imported results or scientific metrics.
    for i in range(480):
        h,a=(str(i%4),str((i%4+1+(i//4)%3)%4))
        rows.append({'date':(date(2020,7,1)+timedelta(days=i)).isoformat(),'home':h,'away':a,'hg':i%4,'ag':(i//3)%3})
    return rows


def test_poisson_and_rho_ignore_future_outcomes_and_unknown_teams():
    from intelligence.quant_evaluation import POLICY
    p=json.loads(POLICY.read_text());rows=training_rows()
    model=fit_poisson(rows,p);rho=fit_rho(model,rows,p)
    future={'date':'2024-10-01','home':'0','away':'1','hg':999,'ag':999}
    other=fit_poisson(rows+[future],p)
    assert model==other and fit_rho(other,rows+[future],p)==rho
    assert goal_rates(model,future)==goal_rates(model,{k:v for k,v in future.items() if k not in ('hg','ag')})
    assert goal_rates(model,dict(future,home='unknown')) is None
    with pytest.raises(ValueError):goal_rates(model,dict(future,date='2022-01-01'))
    assert np.all(np.isfinite(model['coefficients']))


def test_real_research_report_is_integrity_bound_and_never_a_promoted_model():
    from intelligence.quant_evaluation import DESTINATION,POLICY
    r=json.loads(DESTINATION.read_text());checksum=r.pop('sha256')
    assert checksum==digest(r) and r['policy_sha256']==digest(json.loads(POLICY.read_text()))
    assert not r['independent_confirmation'] and r['historical_market_benchmark'] is None
    for league,v in r['leagues'].items():
        assert not v['approved'] and not v['live_dispatch']
        if league in ('La Liga','Serie A'):assert v['blocked'];continue
        assert v['common_test_n']>=100 and not v['joint_score_diagnostics']['joint_validated']
        for task in v['markets'].values():
            for method in ('poisson','dixon_coles','coherent_temperature'):
                lo,hi=task['methods'][method]['minus_frozen']['binary_brier']['interval']
                assert lo<=0<=hi  # Observed evidence, not an improvement claim.
        assert all(not s['validated'] for s in v['joint_event_research'].values())


def test_high_probability_unapproved_or_stale_never_triggers_best_bet(quote,estimate):
    a=Analysis(quotes=[quote],estimates={quote.id:replace(estimate,probability=.95,upper=.99,validated=False)})
    assert decide(a,now=NOW)['status']=='NO QUALIFYING BET'
    a.estimates[quote.id]=estimate
    assert decide(a,now=NOW)['best']['format']=='Single'
    assert decide(a,now=NOW+timedelta(minutes=10))['best'] is None
    a.estimates[quote.id]=replace(estimate,lower=.4)
    assert decide(a,now=NOW)['best'] is None


def test_format_neutral_ticket_comparison_requires_actual_joint_and_price_evidence(quote,estimate):
    second=replace(quote,event_id='another-game',home='Another H',away='Another A',selection='Another H')
    a=Analysis(quotes=[quote,second],estimates={quote.id:estimate,second.id:estimate})
    ids=tuple(sorted(q.id for q in a.quotes));price=CombinedPrice(quote.bookmaker,ids,3.,quote.source_updated_at,True,'https://example.test/synthetic-ticket')
    joint=JointEstimate(.5,.4,.6,ids,'synthetic-validated-only',True)
    assert decide(a,now=NOW)['best']['format']=='Single'
    result=decide(a,now=NOW,combined_prices=[price],joint_estimates=[joint])
    assert result['best']['format']=='Multi-game parlay'
    assert decide(a,now=NOW,combined_prices=[price],joint_estimates=[replace(joint,validated=False)])['best']['format']=='Single'
    btts,total=soccer_quotes(quote)
    assert selection_format([btts,total])=='Same-game parlay'
    assert selection_format([btts,total,replace(total,event_id='another',home='Other',away='Club',commence_time='2026-10-18T01:00:00+00:00')])=='Mixed parlay'
    assert result['qualified_by_format']['Same-game parlay']==0


def test_preview_best_bet_and_offline_report_keep_four_pages_and_no_requests(tmp_path,monkeypatch):
    from unittest.mock import patch
    from streamlit.testing.v1 import AppTest
    from ui_navigation import navigate
    monkeypatch.setenv('INTELLIGENCE_DB',str(tmp_path/'preview.sqlite3'))
    monkeypatch.setenv('ODDS_API_KEY','synthetic-preview-only')
    monkeypatch.setenv('PAID_ANALYST_APPROVED','0')
    monkeypatch.setenv('PREDICTION_LEDGER_DIR',str(tmp_path/'empty-ledger'))
    with patch('intelligence.pipeline.run_analysis',return_value=Analysis()) as scan,patch('openai.OpenAI',side_effect=AssertionError('Paid disabled')):
        app=AppTest.from_file(Path('app.py').resolve(),default_timeout=40).run()
        navigate(app,'AI Dashboard')
        assert any(s.value=="Today's Best-Supported Bet" for s in app.subheader)
        assert any('NO QUALIFYING BET' in i.value for i in app.info)
        navigate(app,'Best Picks & Parlays')
        assert len(app.sidebar.radio[0].options)==5 and [t.label for t in app.tabs]==['Singles','Parlays']
        navigate(app,'Model & Data Diagnostics')
        assert any(e.label.startswith('Quantitative model challengers') and not e.proto.expanded for e in app.expander)
        assert any('Method' in t.value.columns and 'dixon_coles' in set(t.value['Method']) for t in app.dataframe)
        assert not app.exception and scan.call_count==1


def test_offline_comparison_reproduces_metrics_without_promoting_or_changing_assets(tmp_path):
    from intelligence.quant_evaluation import build,DESTINATION
    source=Path('work/phase2/source')
    if not source.exists():
        # CI has no private archive download. Contract tests above remain active;
        # reproduce actual public-archive metrics locally, with no network fetch.
        pytest.skip('Pinned raw archive is local/private, not bundled with CI')
    original=DESTINATION.read_bytes();r=build(source,tmp_path/'evaluation.json')
    old=json.loads(original)
    for league in ('Premier League','Bundesliga','Ligue 1'):
        for market,task in r['leagues'][league]['markets'].items():
            for method,metrics in task['methods'].items():
                assert metrics['metrics']['binary_brier']['value']==pytest.approx(old['leagues'][league]['markets'][market]['methods'][method]['metrics']['binary_brier']['value'],abs=1e-12)
    assert DESTINATION.read_bytes()==original and not r['independent_confirmation']
