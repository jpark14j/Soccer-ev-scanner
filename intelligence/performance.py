"""All settled predictions, including losses; no simulated profitability."""
from collections import defaultdict
import math


def metrics(records):
    settled = sorted((r for r in records if r['outcome'] is not None), key=lambda r:(r['settled_at'],r['id']))
    wins = losses = 0
    pnl = stake = peak = max_drawdown = 0.
    briers, logs, clv, calibration = [], [], [], []
    for row in settled:
        q, e = row['payload']['quote'], row['payload']['estimate']
        outcome = row['outcome']
        if outcome != 'void':
            stake += 1
        change = q['odds']-1 if outcome=='win' else -1 if outcome=='loss' else 0
        pnl += change
        peak = max(peak,pnl)
        max_drawdown = max(max_drawdown,peak-pnl)
        if outcome in ('win','loss'):
            y = int(outcome=='win')
            wins += y
            losses += 1-y
            p = min(1-1e-12,max(1e-12,e['probability']))
            briers.append((p-y)**2)
            logs.append(-y*math.log(p)-(1-y)*math.log(1-p))
            calibration.append((p,y))
        if row['closing_odds'] is not None:
            clv.append(q['odds']/row['closing_odds']-1)
    bins = []
    for i in range(10):
        values = [(p,y) for p,y in calibration if min(9,int(p*10))==i]
        if values:
            bins.append({'bin':f'{i/10:.1f}–{(i+1)/10:.1f}', 'n':len(values),
                         'forecast':sum(p for p,_ in values)/len(values),
                         'observed':sum(y for _,y in values)/len(values)})
    mean = lambda values: sum(values)/len(values) if values else None
    return {'published':len(records),'settled':len(settled),'pending':len(records)-len(settled),
            'win_rate':wins/(wins+losses) if wins+losses else None,
            'roi':pnl/stake if stake else None,'pnl_units':pnl if settled else None,
            'max_drawdown_units':max_drawdown if settled else None,
            'brier':mean(briers),'log_loss':mean(logs),'closing_line_value':mean(clv),'calibration':bins}


def breakdown(records, dimension):
    if dimension not in ('sport','market','model_version'):
        raise ValueError('Unsupported grouping')
    groups = defaultdict(list)
    for row in records:
        source = row['payload']['estimate'] if dimension=='model_version' else row['payload']['quote']
        groups[source[dimension]].append(row)
    return {key:metrics(value) for key,value in groups.items()}
