"""Timestamped, user-reported price comparisons, isolated from provider quotes.

This module cannot approve models, verify Ontario inventory, publish picks, place
wagers, write the shared replica or contact any external service. Fair odds and
multiplied leg prices are never accepted as an observed combined ticket.
"""
from intelligence.domain import digest,finite,parse_time,utcnow
from intelligence.ev import expected_value
from intelligence.registry import eligible_book

MAX_AGE=300


def target_id(row):
    return digest({k:row.get(k) for k in ('fixture_id','market','selection','point','legs','model_version','evidence_id','kickoff')})


def save_price(row,bookmaker,odds,observed_at,*,attested=False,now=None):
    now=now or utcnow()
    if (not eligible_book(bookmaker,now) or not finite(odds) or not 1<odds<=1000
        or not attested or not row.get('fixture_id') or not row.get('evidence_id')
        or not now<parse_time(row['kickoff']) or not 0<=(now-parse_time(observed_at)).total_seconds()<=MAX_AGE):
        raise ValueError('A current, personally observed sportsbook price and an upcoming exact selection are required')
    legs=row.get('legs') or [row]
    if not 1<=len(legs)<=3:raise ValueError('One, two or three exact selections required')
    # Only explicit fields are saved: never source objects, user prose or secrets.
    value={'schema':1,'target_id':target_id(row),'fixture_id':row['fixture_id'],
        'bookmaker':bookmaker,'decimal_odds':float(odds),'observed_at':parse_time(observed_at).isoformat(),
        'recorded_at':now.isoformat(),'kind':'individual price' if len(legs)==1 else 'actual combined price reported by user',
        'provenance':'User-reported, not independently verified by a sportsbook/provider',
        'independently_verified':False,'restrictions_verified':False}
    value['id']=digest(value);return value


def compare(row,price,now=None):
    now=now or utcnow();reasons=[]
    if price.get('target_id')!=target_id(row):reasons.append('The price belongs to a different selection, fixture or model version')
    try:
        if not 0<=(now-parse_time(price['observed_at'])).total_seconds()<=MAX_AGE:reasons.append('The entered price is stale or future dated')
        if not now<parse_time(row['kickoff']):reasons.append('The game has started')
        if not 0<=(now-parse_time(row['source_observed_at'])).total_seconds()<21600:reasons.append('Model inputs have expired')
    except (KeyError,TypeError,ValueError):reasons.append('Required timestamps are missing or invalid')
    if not eligible_book(price.get('bookmaker'),now):reasons.append('Ontario operator review expired or unsupported operator')
    odds=price.get('decimal_odds');p=row.get('joint_probability',row.get('probability'))
    lo,hi=row.get('lower'),row.get('upper')
    valid=(all(finite(v) for v in (odds,p,lo,hi)) and 1<odds<=1000 and 0<=lo<=p<=hi<=1)
    if not valid:reasons.append('A complete probability estimate and valid decimal price are required')
    if not row.get('research_eligible'):reasons.append('The candidate does not pass the research evidence checks')
    research_ev=expected_value(p,odds) if valid and not reasons else None
    # Even a large user-entered price must not create an approval or evidence ID.
    reasons.append('The entered price and sportsbook ticket restrictions have not been independently verified')
    if not row.get('approved'):reasons.append('This model is experimental and has no publication approval')
    if row.get('legs') and not row.get('joint_validated'):reasons.append('Joint probability has not passed independent parlay validation')
    return {'status':'Research comparison only','qualifies':False,'point_estimate_ev':research_ev,
        'conservative_ev':None,'implied_probability':1/odds if finite(odds) and odds>1 else None,
        'probability':p if valid else None,'blockers':reasons,
        'note':'Mathematical comparison conditional on an experimental model and a user-reported price; not a verified edge or recommendation. The calibration range is not an event-specific confidence interval.'}
