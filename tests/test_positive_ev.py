"""Synthetic publication/price safety tests; not evidence of real bets."""
from dataclasses import replace
from datetime import timedelta
from copy import deepcopy
import pytest
from conftest import NOW
from intelligence.pipeline import Analysis
from intelligence.positive_ev import shortlist,EMPTY
from intelligence.manual_odds import save_price,compare,target_id


def row():
    return {'fixture_id':'synthetic-game','event':'Synthetic fixture','league':'Bundesliga',
        'market':'btts','selection':'Yes','point':None,'model_version':'synthetic-model','evidence_id':'synthetic-evidence',
        'probability':.65,'lower':.5,'upper':.8,'kickoff':(NOW+timedelta(days=1)).isoformat(),
        'source_observed_at':NOW.isoformat(),'research_eligible':True,'approved':False}


def test_only_current_approved_value_survives_main_gate(store,quote,estimate):
    a=Analysis(quotes=[quote],estimates={quote.id:estimate})
    result=shortlist(a,store,{quote.bookmaker},['NBA'],NOW)
    assert result['qualified']==1 and result['winners'][1]['ev']>0
    assert result['winners'][2] is result['winners'][3] is None
    a.estimates[quote.id]=replace(estimate,validated=False)
    assert shortlist(a,store,{quote.bookmaker},['NBA'],NOW)['qualified']==0


@pytest.mark.parametrize('failure',['stale','negative','lower','duplicate','wrong_league','incomplete','old_history'])
def test_main_rejects_unsupported_or_uncertain_positive_point_values(store,quote,estimate,failure):
    q,e=quote,estimate;details={}
    if failure=='stale':q=replace(q,source_updated_at=(NOW-timedelta(minutes=6)).isoformat())
    if failure=='negative':e=replace(e,probability=.4,lower=.3,upper=.5)
    if failure=='lower':e=replace(e,lower=.45)
    if failure=='wrong_league':e=replace(e,league='MLB')
    if failure=='old_history':e=replace(e,training_end=(NOW-timedelta(days=100)).isoformat())
    if failure=='incomplete':details={'quote_id':q.id,'inputs_complete':False}
    a=Analysis(quotes=[q,q] if failure=='duplicate' else [q],estimates={q.id:e},research=[details] if details else [])
    assert shortlist(a,store,{q.bookmaker},['NBA'],NOW)['qualified']==0


def test_manual_price_is_timestamped_and_cannot_publish_experimental_ev():
    r=row();p=save_price(r,'betmgm_ca_on',2.,NOW.isoformat(),attested=True,now=NOW)
    result=compare(r,p,NOW)
    assert p['independently_verified'] is p['restrictions_verified'] is False
    assert result['point_estimate_ev']==pytest.approx(.3) and not result['qualifies']
    assert result['conservative_ev'] is None and any('experimental' in b for b in result['blockers'])
    assert p['recorded_at']==NOW.isoformat()
    assert not any(k in p for k in ('source','token','secret','payload','estimate','approved','probability'))


@pytest.mark.parametrize('bad',[0,1,float('nan'),float('inf'),True,1001])
def test_manual_invalid_odds_rejected(bad):
    with pytest.raises(ValueError):save_price(row(),'betmgm_ca_on',bad,NOW.isoformat(),attested=True,now=NOW)


def test_manual_stale_missing_attestation_wrong_fixture_and_true_combined_input():
    r=row()
    for attested,at in [(False,NOW),(True,NOW-timedelta(minutes=6)),(True,NOW+timedelta(seconds=1))]:
        with pytest.raises(ValueError):save_price(r,'betmgm_ca_on',2.,at.isoformat(),attested=attested,now=NOW)
    r['legs']=[{'market':'h2h','selection':'Home','point':None,'probability':.6},
               {'market':'totals','selection':'Over','point':2.5,'probability':.6}]
    r['joint_probability']=.4;r['lower']=.25;r['upper']=.55;r['joint_validated']=False
    p=save_price(r,'betmgm_ca_on',3.5,NOW.isoformat(),attested=True,now=NOW)
    assert p['decimal_odds']==3.5 and 'combined' in p['kind']  # No individual odds to multiply.
    assert not compare(r,p,NOW)['qualifies']
    wrong=deepcopy(r);wrong['fixture_id']='different'
    assert compare(wrong,p,NOW)['point_estimate_ev'] is None
    assert compare(r,p,NOW+timedelta(minutes=6))['point_estimate_ev'] is None


def test_manual_quote_cannot_be_reinterpreted_as_a_verified_provider_quote(store,quote,estimate):
    q=replace(quote,provider='user-reported')
    a=Analysis(quotes=[q],estimates={q.id:estimate})
    assert shortlist(a,store,{q.bookmaker},['NBA'],NOW)['qualified']==0


def test_two_three_leg_slots_need_real_ticket_and_validated_joint_contract(store,quote,estimate):
    from intelligence.parlays import CombinedPrice,JointEstimate
    quotes=[replace(quote,event_id=f'synthetic-{i}',home=f'Home{i}',away=f'Away{i}',selection=f'Home{i}') for i in range(3)]
    analysis=Analysis(quotes=quotes,estimates={q.id:estimate for q in quotes})
    prices=[];joints=[]
    for n,p,lower,odds in [(2,.4,.3,3.6),(3,.28,.2,5.2)]:
        ids=tuple(q.id for q in quotes[:n])
        prices.append(CombinedPrice(quote.bookmaker,ids,odds,NOW.isoformat(),True,'synthetic actual ticket evidence'))
        joints.append(JointEstimate(p,lower,p+.1,ids,'synthetic independently validated joint evidence',True))
    result=shortlist(analysis,store,{quote.bookmaker},['NBA'],NOW,prices,joints)
    assert result['qualified']==3
    assert result['winners'][2]['odds']==3.6 and result['winners'][3]['odds']==5.2
    missing=shortlist(analysis,store,{quote.bookmaker},['NBA'],NOW,prices,[])
    assert missing['winners'][2] is missing['winners'][3] is None


def test_extreme_apparent_edge_is_withheld_for_review(store,quote,estimate):
    q=replace(quote,odds=100.)
    assert shortlist(Analysis(quotes=[q],estimates={q.id:estimate}),store,{q.bookmaker},['NBA'],NOW)['qualified']==0
