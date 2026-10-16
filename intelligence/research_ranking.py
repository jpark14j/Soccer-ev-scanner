"""Transparent marginal-model research rankings, never approval or betting EV."""
from intelligence.domain import utcnow, parse_time

RANKINGS = ('Most reliable model evidence','Highest estimated win probability',
            'Strongest model-versus-market difference')
MIN_CALIBRATION_BIN = 50
MIN_CALIBRATION = 100
MIN_TEST = 100
MAX_ENVELOPE_WIDTH = .50


def count(details, key):
    value = details.get(key,0)
    return value if type(value) is int and value>=0 else 0


def evidence_problem(leg, now=None):
    now = now or utcnow()
    e = leg.estimate
    d = leg.model_details
    if not e or not e.valid():
        return 'No valid market-specific model estimate'
    if d.get('calibrated') is not True:
        return 'Probability calibration has not been demonstrated'
    if count(d,'calibration_bin_n') < MIN_CALIBRATION_BIN:
        return 'Fewer than 50 historical calibration outcomes in this probability bucket'
    if count(d,'calibration_n') < MIN_CALIBRATION or count(d,'test_n') < MIN_TEST:
        return 'Fewer than 100 calibration or held-out test outcomes'
    if e.upper-e.lower > MAX_ENVELOPE_WIDTH:
        return 'Supplied probability envelope is wider than 50 percentage points'
    limit = 21 if leg.quote.sport=='Soccer' else 90
    age = (now-parse_time(e.training_end)).total_seconds()/86400
    if not 0 < age <= limit:
        return 'Model input history is outside the current research freshness limit'
    if d.get('results_provider')=='football-data.org':
        checked = d.get('source_checked_at')
        try:
            if not 0 <= (now-parse_time(checked)).total_seconds() < 21600:
                return 'Current-results verification is expired'
        except (ValueError,TypeError):
            return 'Current-results verification timestamp is unavailable'
    return None


def evidence_key(leg, now):
    e = leg.estimate
    d = leg.model_details
    # Stable IDs are last: probability complements with identical evidence must
    # not be ordered by an opaque hash before their probability is considered.
    return (e is None, evidence_problem(leg,now) is not None,
        e.upper-e.lower if e else 1.,
        -count(d,'calibration_bin_n'),-count(d,'test_n'),-count(d,'calibration_n'),
        -e.lower if e else 0.,-e.probability if e else 0.,
        (now-parse_time(leg.quote.source_updated_at)).total_seconds(),leg.quote.id)


def comparison(leg):
    e = leg.estimate
    if not e:
        return None
    implied = leg.implied_probability
    return {'model_probability':e.probability,'sportsbook_break_even':implied,
        'difference':e.probability-implied,
        'difference_envelope':[e.lower-implied,e.upper-implied],
        'envelope_entirely_above_break_even':e.lower>implied,
        'validated_edge':False,
        'note':'Unvalidated model minus margin-inclusive break-even, not de-vigged market probability or established value. Historical bin envelopes are not event-specific confidence intervals.'}


def rank_research(analysis, bookmakers=None, now=None):
    from intelligence.research_state import singles,EXPERIMENTAL,APPROVED
    now = now or utcnow()
    rows = singles(analysis,bookmakers,statuses=[EXPERIMENTAL,APPROVED],now=now)
    supported = []
    excluded = {}
    for state, leg in rows:
        problem = evidence_problem(leg,now)
        if problem:
            excluded[problem] = excluded.get(problem,0)+1
        else:
            supported.append((state,leg))
    result = {name:[] for name in RANKINGS}
    result[RANKINGS[0]] = sorted(supported,key=lambda row:evidence_key(row[1],now))
    result[RANKINGS[1]] = sorted(supported,key=lambda row:(-row[1].estimate.probability,*evidence_key(row[1],now)))
    positives = [row for row in supported if comparison(row[1])['difference']>0]
    result[RANKINGS[2]] = sorted(positives,key=lambda row:(-comparison(row[1])['difference'],*evidence_key(row[1],now)))
    return {'rankings':result,'exclusions':excluded,
        'requirements':'Calibrated estimates, calibration bucket n≥50, calibration/test n≥100 each, supplied envelope width≤50 percentage points, current model inputs and eligible Ontario prices. These are research-display requirements; they do not approve a model.',
        'descriptions':{RANKINGS[0]:'Narrower supplied envelopes, larger calibration/test samples, then stronger lower bounds and freshness. Historical evidence is not independent current-event validation.',
            RANKINGS[1]:'Highest marginal model probability first, with uncertainty and calibration requirements. A higher probability can still be below the sportsbook break-even price.',
            RANKINGS[2]:'Largest positive model-minus-break-even difference first. The envelope may cross zero; this is unvalidated disagreement, not an established betting edge or EV.'}}
