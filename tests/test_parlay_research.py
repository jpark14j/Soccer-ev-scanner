"""Synthetic software fixtures, never app recommendations or performance claims."""
from dataclasses import replace
from datetime import timedelta
import math
from unittest.mock import patch
import pytest
from conftest import NOW
from intelligence.domain import Estimate,utcnow
from intelligence.parlay_research import (select_candidates,pair_review,contradictory_scores,
                                          research_category,quote_problem)
from intelligence.parlays import CATEGORIES
from intelligence.pipeline import Analysis,run_analysis
from intelligence.providers import ProviderError
from intelligence.research_refresh import refresh_research
from intelligence.team_codes import history_name


def game(quote,n=0,sport='NBA',**changes):
    fields=dict(sport=sport,league=sport if sport!='Soccer' else 'Premier League',
        event_id=f'event-{n}',event=f'Home {n} vs Away {n}',home=f'Home {n}',away=f'Away {n}',selection=f'Home {n}')
    return replace(quote,**(fields|changes))


def games(quote):
    return [game(quote,n,sport) for n,sport in enumerate(('NBA','Soccer','MLB','NBA','MLB'))]


def test_selects_current_same_book_candidates_without_validated_models(quote):
    result=select_candidates(Analysis(quotes=games(quote)),now=NOW)
    assert len(result.candidates)==3 and result.eligible_quotes==5
    assert len({tuple(sorted(l.quote.event_id for l in c.legs)) for c in result.candidates})==3
    for c in result.candidates:
        assert c.status=='research only' and not c.executable and c.parlay_ev is None
        assert c.combined_odds is None and c.joint_probability is None and c.probability_bounds is None
        assert c.theoretical_odds==pytest.approx(math.prod(l.quote.odds for l in c.legs))
        assert 'theoretical' in c.combined_price_status and len({l.quote.bookmaker for l in c.legs})==1
        assert any('joint probability' in b for b in c.blockers)
        assert any('combined parlay price' in b for b in c.blockers)
        assert any('independence' in w for w in c.warnings)
        assert all(l.implied_probability==pytest.approx(1/l.quote.odds) for l in c.legs)


def test_three_leg_mixed_sport_candidate_and_filters(quote):
    qs=games(quote)[:3]
    result=select_candidates(Analysis(quotes=qs),leg_counts=(3,),now=NOW)
    assert len(result.candidates)==1 and {l.quote.sport for l in result.candidates[0].legs}=={'NBA','Soccer','MLB'}
    assert not select_candidates(Analysis(quotes=qs),sports=('NBA',),now=NOW).candidates
    assert not select_candidates(Analysis(quotes=qs),bookmakers=[],now=NOW).candidates
    assert not select_candidates(Analysis(quotes=qs),leg_counts=[],now=NOW).candidates
    assert not select_candidates(Analysis(quotes=qs),categories=[],now=NOW).candidates


def test_never_mix_prices_from_different_sportsbooks(quote):
    a=game(quote,1)
    b=game(quote,2,bookmaker='betrivers_ca_on')
    assert not select_candidates(Analysis(quotes=[a,b]),now=NOW).candidates


@pytest.mark.parametrize('changes',[
    {'source_updated_at':(NOW-timedelta(minutes=6)).isoformat()},
    {'received_at':(NOW+timedelta(seconds=1)).isoformat()},
    {'source_updated_at':'missing'}, {'suspended':True},
    {'commence_time':(NOW-timedelta(minutes=1)).isoformat()},
    {'bookmaker':'betmgm_us'}, {'jurisdiction':'unverified'},
    {'provider':'unverified-source'}, {'odds':1.0}, {'odds':float('nan')}])
def test_stale_live_suspended_unverified_and_invalid_prices_excluded(quote,changes):
    result=select_candidates(Analysis(quotes=[game(quote,1),game(quote,2,**changes)]),now=NOW)
    assert not result.candidates and result.exclusions


def test_registry_expiry_excludes_even_fresh_quotes(quote):
    now=NOW+timedelta(days=40)
    q=replace(quote,source_updated_at=now.isoformat(),received_at=now.isoformat(),commence_time=(now+timedelta(days=1)).isoformat())
    assert 'registry expired' in quote_problem(q,now)


def test_ambiguous_duplicate_quote_rejected(quote):
    a,b=game(quote,1),game(quote,2)
    result=select_candidates(Analysis(quotes=[a,replace(a,odds=2.1),b]),now=NOW)
    assert not result.candidates and result.exclusions['Ambiguous duplicate provider quote']==2


def test_rejects_opposite_winners_and_duplicate_physical_games(quote):
    a=game(quote,1)
    b=replace(a,selection=a.away)
    assert 'Contradictory' in pair_review(a,b)[0]
    assert not select_candidates(Analysis(quotes=[a,b]),now=NOW).candidates
    duplicate=replace(a,event_id='other-feed-id')
    assert 'Duplicate' in pair_review(a,duplicate)[0]
    assert not select_candidates(Analysis(quotes=[a,duplicate]),now=NOW).candidates


def test_shared_team_doubleheader_is_flagged_without_assuming_independence(quote):
    a=game(quote,1,sport='MLB')
    b=replace(a,event_id='doubleheader-two',commence_time='2026-10-17T06:00:00Z')
    c=select_candidates(Analysis(quotes=[a,b]),now=NOW).candidates[0]
    assert any('Shared team' in w for w in c.warnings)
    assert c.joint_probability is None and c.parlay_ev is None


@pytest.mark.parametrize('over,under,contradiction',[(2.5,2.5,True),(2.5,3,True),(2.5,3.5,False)])
def test_total_contradictions_respect_integer_score_semantics(quote,over,under,contradiction):
    a=game(quote,1,sport='Soccer',market='totals',point=over,selection='Over')
    b=replace(a,point=under,selection='Under')
    assert bool(pair_review(a,b)[0]) is contradiction
    result=select_candidates(Analysis(quotes=[a,b]),now=NOW)
    assert bool(result.candidates) is not contradiction
    if not contradiction:
        assert any('Same event' in w for w in result.candidates[0].warnings)


@pytest.mark.parametrize('home_line,away_line,rejected',[(-2.5,2.5,True),(-2.5,3.5,False)])
def test_spread_conflicts_and_middles(quote,home_line,away_line,rejected):
    a=game(quote,1,market='spreads',point=home_line)
    b=replace(a,point=away_line,selection=a.away)
    assert bool(pair_review(a,b)[0]) is rejected


def test_three_leg_score_constraints_reject_joint_impossibility(quote):
    # Home -1.5 and Away +3.5 require a home margin of 2 or 3.
    # Under 2.5 limits total to 2, so margin=2,total=2 is possible.
    a=game(quote,1,market='spreads',point=-1.5)
    b=replace(a,selection=a.away,point=3.5)
    total=replace(a,market='totals',selection='Under',point=2.5)
    assert not contradictory_scores([a,b,total])
    # An additional constraint forcing an odd margin with total exactly 2
    # is impossible; simpler total-under-1.5 also rejects the three-leg set.
    assert contradictory_scores([a,b,replace(total,point=1.5)])
    result=select_candidates(Analysis(quotes=[a,b,replace(total,point=1.5)]),leg_counts=(3,),now=NOW)
    assert not result.candidates


def test_soccer_draw_and_negative_spread_cannot_both_win(quote):
    a=game(quote,1,sport='Soccer',selection='Draw')
    b=replace(a,market='spreads',selection=a.home,point=-.5)
    assert contradictory_scores([a,b])
    assert not select_candidates(Analysis(quotes=[a,b]),now=NOW).candidates


def test_integer_push_warning_and_invalid_line_handling(quote):
    a=game(quote,1,market='totals',selection='Over',point=200.)
    b=game(quote,2)
    c=select_candidates(Analysis(quotes=[a,b]),now=NOW).candidates[0]
    assert any('pushes/voids' in w for w in c.warnings)
    assert quote_problem(replace(a,point=float('nan')),NOW)


def test_risk_categories_are_deterministic_price_proxies(quote):
    qs=[replace(q,odds=1.6) for q in games(quote)[:2]]
    assert research_category(qs,2.56)=='Lower-variance'
    assert research_category([replace(q,odds=2.) for q in qs],4.)=='Balanced'
    assert research_category([replace(q,odds=3.) for q in qs],9.)=='Higher-variance'
    result=select_candidates(Analysis(quotes=qs),categories=('Higher-variance',),now=NOW)
    assert not result.candidates


def test_unvalidated_estimates_have_no_ev_and_no_multiplied_joint_probability(quote,estimate):
    qs=games(quote)[:2]
    estimates={q.id:replace(estimate,sport=q.sport,league=q.league,validated=False) for q in qs}
    c=select_candidates(Analysis(quotes=qs,estimates=estimates),now=NOW).candidates[0]
    assert all(l.model_status=='research' and l.estimated_ev is None for l in c.legs)
    assert c.joint_probability is None and c.parlay_ev is None
    assert c.probability_bounds==pytest.approx((.3,.65))
    assert c.uncertainty_bounds==pytest.approx((.2,.7))


def test_marginal_ev_requires_validated_current_market_evidence(quote,estimate):
    qs=[game(quote,1),game(quote,2)]
    c=select_candidates(Analysis(quotes=qs,estimates={q.id:estimate for q in qs}),now=NOW).candidates[0]
    assert all(l.estimated_ev==pytest.approx(.65*1.9-1) for l in c.legs)
    assert c.parlay_ev is None and not c.executable
    stale=replace(estimate,training_end='2015-01-01T00:00:00Z')
    c=select_candidates(Analysis(quotes=qs,estimates={q.id:stale for q in qs}),now=NOW).candidates[0]
    assert all(l.estimated_ev is None for l in c.legs)


def test_mismatched_or_future_model_estimate_is_not_shown(quote,estimate):
    qs=games(quote)[:2]
    estimates={qs[0].id:replace(estimate,training_end=NOW.isoformat()),
               qs[1].id:replace(estimate,sport='NBA')}
    c=select_candidates(Analysis(quotes=qs,estimates=estimates),now=NOW).candidates[0]
    assert all(l.estimate is None for l in c.legs)


def test_ranking_rewards_evidence_not_theoretical_payout_and_search_is_bounded(quote,estimate):
    qs=[game(quote,i,odds=10. if i>=3 else 1.9) for i in range(12)]
    estimates={q.id:estimate for q in qs[:2]}
    result=select_candidates(Analysis(quotes=qs,estimates=estimates),pool_per_book=6,now=NOW)
    assert result.searched_quotes==6 and result.eligible_quotes==12
    assert {l.quote.event_id for l in result.candidates[0].legs}=={'event-0','event-1'}
    assert result.candidates[0].theoretical_odds==pytest.approx(3.61)


def test_candidates_expire_without_refreshing_timestamps(quote):
    analysis=Analysis(quotes=games(quote))
    assert select_candidates(analysis,now=NOW).candidates
    assert not select_candidates(analysis,now=NOW+timedelta(minutes=6)).candidates


def test_empty_and_invalid_filter_states(quote):
    assert not select_candidates(Analysis(),now=NOW).candidates
    with pytest.raises(ValueError):
        select_candidates(Analysis(),leg_counts=(4,),now=NOW)
    with pytest.raises(ValueError):
        select_candidates(Analysis(),pool_per_book=100,now=NOW)


def test_refresh_respects_budget_and_does_not_poll_scores(store,quote,monkeypatch):
    from intelligence.domain import utcnow
    store.reserve(1,9)
    monkeypatch.setenv('ODDS_DAILY_CREDITS','1')
    with patch('intelligence.research_refresh.run_analysis') as run:
        with pytest.raises(ProviderError,match='Not enough'):
            refresh_research(Analysis(),'fixture',['NBA'],store)
        run.assert_not_called()
    monkeypatch.setenv('ODDS_DAILY_CREDITS','9')
    a,b=game(quote,1),game(quote,2,sport='MLB')
    original=Analysis(quotes=[a,b],estimates={},errors=['NBA: old','MLB: retained'])
    fresh=Analysis(quotes=[replace(a,odds=2.)],errors=[],checked_at=NOW.isoformat())
    with patch('intelligence.research_refresh.run_analysis',return_value=fresh) as run:
        result=refresh_research(original,'fixture',['NBA'],store)
    assert run.call_args.kwargs['collect_results'] is False
    assert run.call_args.args[3].ttl==0
    assert result.quotes[-1].odds==2. and b in result.quotes and result.errors==['MLB: retained']
    assert original.quotes[0].odds==1.9


def test_archive_team_codes_are_explicit_and_ambiguous_codes_rejected():
    assert history_name('NBA','Boston Celtics',{'BOS','LAL'})=='BOS'
    assert history_name('MLB','New York Yankees',{'NYA','LAN'})=='NYA'
    assert history_name('NBA','Brooklyn Nets',{'BRK','BKN'}) is None
    assert history_name('MLB','Imaginary Team',{'NYA','LAN'}) is None
    assert history_name('Soccer','Manchester United',{'Man United'})=='Man United'


def test_chronological_calibration_is_applied_only_to_its_exact_dataset(store,quote,monkeypatch):
    import pandas as pd
    from intelligence.domain import digest
    from intelligence.evaluation import calibrate
    import intelligence.pipeline as pipeline
    history=pd.DataFrame({'date':pd.date_range('2026-04-01',periods=180),
                          'HomeTeam':['Home']*180,'AwayTeam':['Away']*180,'FTHG':[110]*180,'FTAG':[100]*180})
    report={'data_sha256':digest(history.to_json(orient='records',date_format='iso')),
            'temperature':1.25,'calibration_bins':[{'n':100,'interval':[.45,.75]}]*10,
            'evidence_id':'synthetic-evaluation','calibration_n':200,'test_n':201,'generated_at':NOW.isoformat(),
            'data_end':'2026-09-27T00:00:00Z','data_source':'synthetic-test-only','calibration_gap':.03,
            'metrics':{'brier':.4,'log_loss':.6}}
    class Provider:
        def odds(self,*args):
            return {'received_at':quote.received_at,'data':[{'id':quote.event_id,'sport_key':'basketball_nba',
                'commence_time':quote.commence_time,'home_team':'Home','away_team':'Away',
                'bookmakers':[{'key':quote.bookmaker,'title':quote.bookmaker_name,'last_update':quote.source_updated_at,
                    'markets':[{'key':'h2h','outcomes':[{'name':'Home','price':1.9}]}]}]}]}
    monkeypatch.setattr(pipeline,'utcnow',lambda:NOW)
    monkeypatch.setattr(pipeline,'load_local',lambda *a:history)
    monkeypatch.setattr(pipeline,'predict',lambda *a:[.6,.4])
    monkeypatch.setattr(pipeline,'load_report',lambda *a:report)
    result=run_analysis('fixture',['NBA'],store,Provider(),collect_results=False)
    assert result.research[0]['probability']==pytest.approx(calibrate([.6,.4],1.25)[0])
    assert result.research[0]['calibration_bin_n']==100 and result.research[0]['test_n']==201
    assert not result.research[0]['validated'] and not result.opportunities
    report['data_sha256']='mismatched-dataset'
    result=run_analysis('fixture',['NBA'],store,Provider(),collect_results=False)
    assert result.research[0]['probability']==.6 and result.research[0]['lower']==0 and result.research[0]['upper']==1
    assert result.warnings and result.research[0]['calibration_bin_n']==0


def test_score_contradiction_solver_matches_brute_force_small_markets(quote):
    from itertools import combinations
    for sport in ('Soccer','NBA'):
        q=game(quote,1,sport=sport)
        markets=[q,replace(q,selection=q.away),replace(q,market='spreads',point=-1.5),
            replace(q,market='spreads',point=3.5,selection=q.away),
            replace(q,market='totals',point=2.5,selection='Under'),
            replace(q,market='totals',point=4.,selection='Over')]
        if sport=='Soccer':
            markets.append(replace(q,selection='Draw'))
        def wins(leg,h,a):
            if leg.market=='h2h':
                return (h>a if leg.selection==q.home else h==a if leg.selection=='Draw' else a>h)
            if leg.market=='spreads':
                return h+leg.point>a if leg.selection==q.home else a+leg.point>h
            return h+a>leg.point if leg.selection=='Over' else h+a<leg.point
        for combo in combinations(markets,3):
            possible=any(all(wins(leg,h,a) for leg in combo) for h in range(10) for a in range(10)
                         if sport=='Soccer' or h!=a)
            assert contradictory_scores(combo) is not possible


def test_invalid_refresh_budget_fails_closed_without_echoing_config(store,monkeypatch):
    monkeypatch.setenv('ODDS_DAILY_CREDITS','credential-like-invalid-value')
    with patch('intelligence.research_refresh.run_analysis') as run:
        with pytest.raises(ProviderError) as error:
            refresh_research(Analysis(),'fixture',['NBA'],store)
        assert 'credential-like-invalid-value' not in str(error.value)
        run.assert_not_called()


def test_nonfinite_line_cannot_break_candidate_identity_or_entire_page(quote):
    bad=game(quote,1,market='totals',point=float('nan'),selection='Over')
    result=select_candidates(Analysis(quotes=[bad,game(quote,2)]),now=NOW)
    assert not result.candidates and result.exclusions['Spread/total line is missing or invalid']==1
