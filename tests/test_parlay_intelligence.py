"""Synthetic software fixtures only; no real forecasts, odds or model evidence."""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
import math
import pytest
from conftest import NOW
from intelligence.domain import utcnow
from intelligence.pipeline import Analysis,evaluate_quotes
from intelligence.parlay_intelligence import (selection_groups,generate,binary_market,
    physical_game,explain_leg)
from intelligence.research_ranking import rank_research,RANKINGS,evidence_problem
from test_readiness_ranking import research_analysis,enable,cached_source


def opposed(analysis):
    """Add complementary synthetic model estimates and actual test quote objects."""
    a=replace(analysis,quotes=list(analysis.quotes),estimates=dict(analysis.estimates),
        advanced_estimates=dict(analysis.advanced_estimates),advanced_details=dict(analysis.advanced_details),research=list(analysis.research))
    for q in analysis.quotes:
        e=analysis.estimates[q.id]
        other=replace(q,selection=q.away if q.market=='h2h' else 'No' if q.market=='btts' else 'Under',odds=4.)
        oe=replace(e,probability=1-e.probability,lower=1-e.upper,upper=1-e.lower)
        a.quotes.append(other);a.estimates[other.id]=oe;a.advanced_estimates[other.id]=oe
        d={**analysis.advanced_details[q.id],'quote_id':other.id};a.advanced_details[other.id]=d;a.research.append(d)
    return a


def add_quote(a, original, **changes):
    q=replace(original,**changes);e=a.estimates[original.id]
    a.quotes.append(q);a.estimates[q.id]=e;a.advanced_estimates[q.id]=e
    d={**a.advanced_details[original.id],'quote_id':q.id};a.advanced_details[q.id]=d;a.research.append(d)
    return q


def test_favored_side_is_model_based_not_high_payout_or_implied_probability(quote):
    a=opposed(research_analysis(quote,[(.7,.6,.8,1.3,100)]))
    groups,_=selection_groups(a,now=NOW)
    assert len(groups)==1 and groups[0].preferred.quote.selection==a.quotes[0].home
    assert len(groups[0].offers)==2 and groups[0].research_eligible
    assert groups[0].preferred.estimate.probability==.7
    # The .3 opposing side has a positive raw model-price difference at 4.0;
    # default favorites/value views must not promote both sides of one market.
    report=rank_research(a,now=NOW)
    assert len(report['rankings'][RANKINGS[1]])==1
    assert not report['rankings'][RANKINGS[2]]


def test_equivalent_books_group_and_cross_book_maximum_prices_never_form_a_ticket(quote):
    a=opposed(research_analysis(quote,[(.7,.6,.8,1.7,100),(.65,.55,.75,1.6,100)]))
    better=add_quote(a,a.quotes[0],bookmaker='pointsbetca',bookmaker_name='PointsBet',odds=2.)
    report=generate(a,now=NOW)
    first=next(g for g in report.groups if g.preferred and g.preferred.quote.event_id==a.quotes[0].event_id)
    assert first.preferred.quote==better and len(first.offers)==3
    assert report.two_leg and all(l.quote.bookmaker==quote.bookmaker for l in report.two_leg[0].research.legs)
    assert report.two_leg[0].research.theoretical_odds==pytest.approx(1.7*1.6)
    assert not report.two_leg[0].research.executable


@pytest.mark.parametrize('kind',['tie','missing_favorite','wide','bin','uncalibrated'])
def test_no_favorite_or_weak_evidence_never_forces_a_candidate(quote,kind):
    p=.5 if kind=='tie' else .3 if kind=='missing_favorite' else .9
    lo,hi=(0.,1.) if kind=='wide' else (p-.1,p+.1)
    a=research_analysis(quote,[(p,lo,hi,2.,49 if kind=='bin' else 100)])
    if kind=='uncalibrated':a.advanced_details[a.quotes[0].id]['calibrated']=False
    report=generate(a,now=NOW)
    assert not report.favored and not report.two_leg and not report.three_leg
    assert report.exclusions and report.groups[0].problem


@pytest.mark.parametrize('failure',['sum','envelope','same_side','version','snapshot'])
def test_conflicting_equivalent_or_opposing_model_evidence_fails_closed(quote,failure):
    a=opposed(research_analysis(quote,[(.7,.6,.8,1.8,100)]));q=a.quotes[1]
    if failure=='same_side':q=add_quote(a,a.quotes[0],bookmaker='pointsbetca',odds=2.)
    e=a.estimates[q.id]
    if failure=='sum':e=replace(e,probability=.4)
    if failure=='envelope':e=replace(e,lower=.1,upper=.5)  # sums can match while complements do not
    if failure=='same_side':e=replace(e,probability=.65)
    if failure=='version':e=replace(e,model_version='another-model')
    if failure=='snapshot':a.advanced_details[q.id]['data_sha256']='different-snapshot'
    a.estimates[q.id]=e;a.advanced_estimates[q.id]=e
    report=generate(a,now=NOW)
    assert not report.favored and report.groups[0].problem


def test_totals_and_handicap_opposites_share_exact_market_identity(quote):
    a=replace(quote,market='totals',point=2.5,selection='Over')
    assert binary_market(a)[0]==binary_market(replace(a,selection='Under'))[0]
    assert binary_market(a)[0]!=binary_market(replace(a,point=3.5))[0]
    h=replace(quote,market='spreads',point=-3.5)
    aw=replace(h,selection=h.away,point=3.5)
    assert binary_market(h)[0]==binary_market(aw)[0] and binary_market(h)[1]!=binary_market(aw)[1]
    assert binary_market(replace(h,point=-3.25))==(None,None)
    assert binary_market(replace(a,point=3.))==(None,None)
    assert binary_market(replace(quote,sport='Soccer',league='Premier League'))==(None,None)


@pytest.mark.parametrize('failure',['stale','future','suspended','live','wrong_book','wrong_jurisdiction','duplicate'])
def test_existing_current_ontario_and_duplicate_gates_are_preserved(quote,failure):
    a=research_analysis(quote,[(.7,.6,.8,1.8,100),(.65,.55,.75,1.8,100)])
    q=a.quotes[0]
    if failure=='stale':q=replace(q,source_updated_at=(NOW-timedelta(minutes=6)).isoformat())
    if failure=='future':q=replace(q,received_at=(NOW+timedelta(seconds=1)).isoformat())
    if failure=='suspended':q=replace(q,suspended=True)
    if failure=='live':q=replace(q,commence_time=(NOW-timedelta(seconds=1)).isoformat())
    if failure=='wrong_book':q=replace(q,bookmaker='betmgm_us')
    if failure=='wrong_jurisdiction':q=replace(q,jurisdiction='US')
    a.quotes[0]=q
    if failure=='duplicate':a.quotes.append(q)
    assert not generate(a,now=NOW).two_leg


def test_invalid_quote_or_window_cannot_crash_or_activate_research(quote):
    a=research_analysis(quote,[(.7,.6,.8,1.8,100)]*2)
    a.quotes.extend([replace(quote,point=float('nan')),replace(quote,commence_time='invalid')])
    report=generate(a,now=NOW)
    assert report.two_leg and report.exclusions
    a.slate={'window_end':'invalid'}
    assert not generate(a,now=NOW).two_leg
    a.slate={'window_end':(NOW+timedelta(minutes=1)).isoformat()}
    assert not generate(a,now=NOW).favored


def test_equivalent_physical_offers_do_not_consume_the_bounded_pool(quote):
    a=research_analysis(quote,[(.7,.6,.8,1.8,100)]*3)
    better=add_quote(a,a.quotes[0],event_id='another-id-for-the-same-game',odds=2.)
    report=generate(a,now=NOW,pool_limit=3)
    assert len(report.groups)==3 and report.searched_model_groups==3
    assert report.examined_combinations==4 and report.three_leg
    assert better in [l.quote for l in report.three_leg[0].research.legs]


def test_price_only_candidates_are_not_promoted_to_model_intelligence(quote):
    from intelligence.parlay_research import select_candidates
    a=research_analysis(quote,[(.7,.6,.8,1.8,100),(.65,.55,.75,1.8,100)])
    raw=Analysis(quotes=a.quotes)
    assert select_candidates(raw,now=NOW).candidates
    report=generate(raw,now=NOW)
    assert not report.two_leg and not report.favored and report.groups


def test_two_and_three_leg_mixed_sport_candidates_use_genuine_supplied_estimates_only(quote):
    a=opposed(research_analysis(quote,[(.7,.6,.8,1.8,100)]*3))
    # Supplied fixture estimates remain explicitly synthetic, not coverage claims.
    for i,sport in enumerate(('NBA','Soccer','MLB')):
        q=a.quotes[i]
        if sport=='Soccer':q=replace(q,sport=sport,league='Premier League',market='btts',selection='Yes')
        if sport=='MLB':q=replace(q,sport=sport,league='MLB')
        old=a.quotes[i];a.quotes[i]=q
        e=replace(a.estimates.pop(old.id),sport=q.sport,league=q.league,market=q.market)
        a.estimates[q.id]=e;a.advanced_estimates[q.id]=e
        a.advanced_details[q.id]={**a.advanced_details[old.id],'quote_id':q.id}
    report=generate(a,now=NOW)
    assert report.two_leg and report.three_leg
    assert {l.quote.sport for l in report.three_leg[0].research.legs}=={'NBA','Soccer','MLB'}
    for item in report.two_leg+report.three_leg:
        assert all(l.estimate and l.estimate.probability>.5 for l in item.research.legs)
        assert item.research.joint_probability is None and item.research.parlay_ev is None
        assert item.research.combined_odds is None and not item.research.executable
        assert 'do not prove independence' in item.dependence['note']


@pytest.mark.parametrize('link',['game','team','player'])
def test_known_links_are_explicit_alternatives_only(quote,link):
    a=research_analysis(quote,[(.7,.6,.8,1.8,100)]*2)
    original=a.quotes[1]
    if link=='game':q=replace(original,event_id=a.quotes[0].event_id,home=a.quotes[0].home,away=a.quotes[0].away,market='totals',point=200.5,selection='Over')
    elif link=='team':q=replace(original,home=a.quotes[0].home,selection=a.quotes[0].home)
    else:
        first=replace(a.quotes[0],market='player_points',point=20.5,participant='Synthetic Player',selection='Over')
        q=replace(original,market='player_points',point=20.5,participant='Synthetic Player',selection='Over')
        old=a.quotes[0];a.quotes[0]=first
        e=replace(a.estimates[old.id],market=first.market)
        a.estimates[first.id]=e;a.advanced_estimates[first.id]=e;a.advanced_details[first.id]={**a.advanced_details[old.id],'quote_id':first.id}
    a.quotes[1]=q;e=replace(a.estimates[original.id],market=q.market)
    a.estimates[q.id]=e;a.advanced_estimates[q.id]=e;a.advanced_details[q.id]={**a.advanced_details[original.id],'quote_id':q.id}
    assert not generate(a,now=NOW).two_leg
    allowed=generate(a,now=NOW,include_linked=True)
    assert not allowed.two_leg and allowed.alternatives
    assert allowed.alternatives[0].dependence['shared_'+link+'_pairs']>=1


def test_incompatible_model_favorites_are_rejected_even_with_linked_research_enabled(quote):
    a=research_analysis(quote,[(.7,.6,.8,1.8,100)]*2)
    first,old=a.quotes
    q=replace(old,event_id=first.event_id,home=first.home,away=first.away,
        selection=first.away,market='spreads',point=-3.5)
    a.quotes[1]=q;e=replace(a.estimates[old.id],market='spreads')
    a.estimates[q.id]=e;a.advanced_estimates[q.id]=e;a.advanced_details[q.id]={**a.advanced_details[old.id],'quote_id':q.id}
    result=generate(a,now=NOW,include_linked=True)
    assert len(result.favored)==2 and not result.two_leg and not result.alternatives
    assert any('Contradictory' in reason for reason in result.exclusions)


def test_opaque_feed_ids_and_reviewed_aliases_do_not_duplicate_a_physical_game(quote):
    a=research_analysis(quote,[(.7,.6,.8,1.8,100)])
    old=a.quotes[0]
    q=replace(old,sport='Soccer',league='Premier League',home='Arsenal',away='Chelsea',market='btts',selection='Yes')
    e=replace(a.estimates[old.id],sport='Soccer',league='Premier League',market='btts')
    a=Analysis(quotes=[q],estimates={q.id:e},advanced_estimates={q.id:e},advanced_details={q.id:a.advanced_details[old.id]})
    other=add_quote(a,q,event_id='another-feed-id',home='Arsenal FC',away='Chelsea FC',bookmaker='pointsbetca')
    assert physical_game(q)==physical_game(other)
    report=generate(a,now=NOW)
    assert len(report.groups)==1 and not report.two_leg


def test_rank_is_not_theoretical_payout_maximization_and_search_is_bounded(quote):
    a=research_analysis(quote,[(.8,.7,.9,1.2,100),(.7,.6,.8,4.,100),(.6,.5,.7,6.,100)])
    report=generate(a,now=NOW,max_per_size=1)
    assert {l.estimate.probability for l in report.two_leg[0].research.legs}=={.8,.7}
    assert report.two_leg[0].research.theoretical_odds==pytest.approx(4.8)
    many=research_analysis(quote,[(.7,.6,.8,1.8,100)]*30)
    bounded=generate(many,now=NOW,pool_limit=6)
    assert bounded.eligible_model_groups==30 and bounded.searched_model_groups==6
    assert bounded.examined_combinations==math.comb(6,2)+math.comb(6,3)


def test_leg_explanations_only_describe_available_model_evidence(quote):
    a=research_analysis(quote,[(.7,.4,.85,1.8,100)])
    e=a.estimates[a.quotes[0].id]
    from intelligence.parlay_research import leg_evidence
    leg=leg_evidence(a.quotes[0],a,NOW);lines=explain_leg(leg)
    assert any('70.0%' in line for line in lines) and any('reverse' in line for line in lines)
    assert any('experimental' in line for line in lines)
    assert not any('injured' in line or 'guaranteed' in line for line in lines)


def test_frozen_soccer_model_pipeline_can_supply_model_backed_candidates(store,quote,monkeypatch):
    enable(monkeypatch);now=utcnow();qs=[]
    # Use one instant throughout the synthetic pipeline, after the real frozen
    # artifacts' generation time. The provider fixture keeps TIMED games future.
    monkeypatch.setattr('intelligence.pipeline.utcnow',lambda:now)
    from intelligence.current_soccer import prepare_epl,prepare_expanded,forecast
    from intelligence.parlay_research import leg_evidence
    for league in ('Premier League','Bundesliga','Ligue 1'):
        events,_=cached_source(store,league,now)
        artifact=prepare_epl(store,now,allow_fetch=False) if league=='Premier League' else prepare_expanded(league,store,now,allow_fetch=False)
        for event in events:
            if event.status!='scheduled' or event.event_date<=now.date().isoformat():continue
            market='totals' if league=='Ligue 1' else 'btts'
            q=replace(quote,sport='Soccer',league=league,home=event.home_name,away=event.away_name,event_id=league+'-fixture',
                event=event.home_name+' vs '+event.away_name,commence_time=event.kickoff,market=market,point=2.5 if market=='totals' else None,
                selection='Over' if market=='totals' else 'Yes',source_updated_at=now.isoformat(),received_at=now.isoformat())
            for selection in (('Over','Under') if market=='totals' else ('Yes','No')):
                q=replace(q,selection=selection);e,d=forecast(q,artifact,now)
                if e and e.probability>.5:
                    test=Analysis(quotes=[q],estimates={q.id:e},advanced_estimates={q.id:e},advanced_details={q.id:d})
                    if evidence_problem(leg_evidence(q,test,now),now) is None:qs.append(q);break
            if len(qs) and qs[-1].league==league:break
    assert len(qs)==3
    a=evaluate_quotes(Analysis(quotes=qs),store,allow_results_fetch=False)
    result=generate(a,now=now)
    assert result.two_leg and result.three_leg and all(not e.validated for e in a.estimates.values())
    assert not a.opportunities


def test_preview_cards_keep_opponents_collapsed_and_filters_never_scan(tmp_path,quote,monkeypatch):
    from streamlit.testing.v1 import AppTest
    from ui_navigation import navigate
    now=utcnow();a=opposed(research_analysis(quote,[(.7,.6,.8,1.8,100)]*3,now))
    canary='sk-test-NEVER-A-REAL-UI-KEY'
    monkeypatch.setenv('OPENAI_API_KEY',canary)
    a.quotes=[replace(q,event=q.event+' '+canary) for q in a.quotes]
    for d in a.advanced_details.values():d['data_source']=canary
    monkeypatch.setenv('INTELLIGENCE_DB',str(tmp_path/'ui.sqlite3'));monkeypatch.setenv('ODDS_API_KEY','synthetic-ui-only')
    monkeypatch.setenv('PREDICTION_LEDGER_DIR',str(tmp_path/'empty-ledger'));monkeypatch.setenv('PAID_ANALYST_APPROVED','0')
    with patch('intelligence.pipeline.run_analysis',return_value=a) as scans,patch('openai.OpenAI',side_effect=AssertionError('No paid AI')):
        app=AppTest.from_file(Path('app.py').resolve(),default_timeout=40).run();navigate(app,'Best Picks & Parlays')
        assert not app.exception and len(app.sidebar.radio[0].options)==4
        assert [t.label for t in app.tabs]==['Singles','Parlays']
        assert any(s.value=='AI Parlay Intelligence' for s in app.subheader)
        assert all(any(s.value.startswith(str(i)+'.') for s in app.subheader) for i in (1,2,3))
        details=[e for e in app.expander if e.label=='Why this leg? Evidence, opposing outcomes and risks']
        assert details and all(not e.proto.expanded for e in details)
        assert any('Away' in t.value for e in details for t in e.text)
        assert any('Combined sportsbook ticket' in m.value and 'unverified' in m.value for m in app.markdown)
        assert canary not in str(app.main.proto)
        next(m for m in app.multiselect if m.key=='intelligence_sizes').set_value([3]).run()
        next(m for m in app.multiselect if m.key=='intelligence_sports').set_value(['MLB']).run()
        assert not app.exception and scans.call_count==1
        assert any('No model-backed parlay candidates' in i.value for i in app.info)
        assert any(e.label.startswith('Unsupported and price-only research') and not e.proto.expanded for e in app.expander)
