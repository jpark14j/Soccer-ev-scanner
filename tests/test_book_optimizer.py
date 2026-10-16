from dataclasses import replace
from conftest import NOW
from intelligence.pipeline import Analysis
from intelligence.book_optimizer import best_by_game,optimize_by_book
from intelligence.parlays import CombinedPrice,JointEstimate


def game(q,n,book=None):
    return replace(q,event_id=f'optimizer-{n}',home=f'Home {n}',away=f'Away {n}',
        event=f'Home {n} vs Away {n}',selection=f'Home {n}',bookmaker=book or q.bookmaker)


def test_one_research_shortlist_per_book_never_an_executable_offer(quote):
    quotes=[game(quote,n,book) for book in ('betmgm_ca_on','pointsbetca') for n in range(4)]
    rows=optimize_by_book(Analysis(quotes=quotes),leg_counts=(2,3),now=NOW)
    assert len(rows)==2
    for row in rows:
        assert row['qualification_status']=='No Qualifying Parlay' and not row['qualified']
        assert row['research'] and row['research'].combined_odds is None and row['research'].parlay_ev is None
        assert all(l.quote.bookmaker==row['bookmaker'] for l in row['research'].legs)


def test_large_slate_scores_all_games_beyond_old_24_leg_limit(quote):
    rows=optimize_by_book(Analysis(quotes=[game(quote,n) for n in range(40)]),now=NOW,beam_width=4)
    assert rows[0]['eligible_singles_scored']==40 and rows[0]['events_considered']==40
    assert 'not exhaustive' in rows[0]['search_method']
    assert rows[0]['combinations_evaluated']>40


def test_qualified_shortlist_requires_exact_genuine_combined_and_joint_evidence(quote,estimate):
    a,b=game(quote,1),game(quote,2);ids=tuple(sorted((a.id,b.id)))
    analysis=Analysis(quotes=[a,b],estimates={a.id:estimate,b.id:estimate})
    price=CombinedPrice(quote.bookmaker,ids,3.8,quote.source_updated_at,True,'https://example.test/authorized-quote')
    joint=JointEstimate(.44,.40,.48,ids,'synthetic-joint-validation',True)
    assert optimize_by_book(analysis,now=NOW,combined_prices=[price])[0]['qualified'] is None
    row=optimize_by_book(analysis,now=NOW,combined_prices=[price],joint_estimates=[joint])[0]
    assert row['qualification_status']=='Qualified' and row['qualified'][0]['odds']==3.8
    unverified=replace(price,restrictions_verified=False)
    assert optimize_by_book(analysis,now=NOW,combined_prices=[unverified],joint_estimates=[joint])[0]['qualified'] is None


def test_top_game_selections_compare_equivalent_prices_and_keep_few_markets(quote):
    first=game(quote,1)
    better=replace(first,bookmaker='pointsbetca',odds=2.)
    total=replace(first,market='totals',selection='Over',point=220.5)
    rows=best_by_game(Analysis(quotes=[first,better,total]),now=NOW)
    assert len(rows)==1 and len(rows[0]['selections'])==2
    assert next(l for l in rows[0]['selections'] if l.quote.market=='h2h').quote.bookmaker=='pointsbetca'
    assert rows[0]['qualified']==0 and 'price-only choices do not establish statistical superiority' in rows[0]['reason']


def test_stale_and_contradictory_legs_cannot_fill_book_shortlist(quote):
    opposing=replace(quote,selection=quote.away)
    row=optimize_by_book(Analysis(quotes=[quote,opposing]),now=NOW)[0]
    assert row['research'] is None and row['rejections']
    row=optimize_by_book(Analysis(quotes=[replace(quote,suspended=True)]),now=NOW)[0]
    assert row['eligible_singles_scored']==0 and row['research'] is None
