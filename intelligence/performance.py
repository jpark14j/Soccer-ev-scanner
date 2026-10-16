"""All settled predictions, including losses; no simulated profitability."""
from collections import defaultdict
import math
import numpy as np
from intelligence.evaluation import wilson
from intelligence.domain import parse_time


def metrics(records):
    settled = sorted((r for r in records if r['outcome'] is not None), key=lambda r:(parse_time(r['settled_at']),r['id']))
    wins = losses = pushes = voids = 0
    blocks=defaultdict(lambda:[0.,0.])
    event_ids=[]
    pnl = stake = peak = max_drawdown = 0.
    briers, logs, clv, calibration = [], [], [], []
    for row in settled:
        q, e = row['payload']['quote'], row['payload']['estimate']
        outcome = row['outcome']
        pushes+=int(outcome=='push')
        voids+=int(outcome=='void')
        if outcome != 'void':
            stake += 1
        change = q['odds']-1 if outcome=='win' else -1 if outcome=='loss' else 0
        pnl += change
        day=parse_time(q.get('commence_time',row['at'])).date().isoformat()
        blocks[day][0]+=change
        blocks[day][1]+=int(outcome!='void')
        peak = max(peak,pnl)
        max_drawdown = max(max_drawdown,peak-pnl)
        if outcome in ('win','loss'):
            y = int(outcome=='win')
            event_ids.append((q.get('sport'),q.get('home'),q.get('away'),q.get('commence_time')))
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
                         'observed':sum(y for _,y in values)/len(values),
                         'frequency_interval_iid_assumption':wilson(sum(y for _,y in values),len(values))})
    mean = lambda values: sum(values)/len(values) if values else None
    roi_interval=None
    if len(blocks)>=30 and stake:
        data=np.array(list(blocks.values()))
        rng=np.random.default_rng(7321)
        draws=data[rng.integers(0,len(data),size=(500,len(data)))].sum(axis=1)
        ratios=draws[draws[:,1]>0,0]/draws[draws[:,1]>0,1]
        if len(ratios):
            roi_interval=tuple(float(v) for v in np.quantile(ratios,[.025,.975]))
    independent_sample=len(set(event_ids))==len(event_ids)
    return {'wins':wins,'losses':losses,'pushes':pushes,'voids':voids,
            'decisive_sample':wins+losses,'unique_events':len(set(event_ids)),'day_blocks':len(blocks),
            'win_rate_interval':wilson(wins,wins+losses) if wins+losses and independent_sample else None,
            'win_rate_interval_method':'Wilson 95%; assumes independent events; suppressed for shared-event decisions',
            'roi_interval':roi_interval,'roi_interval_method':'95% UTC-day block bootstrap, 500 resamples; minimum 30 days; stationarity/between-day independence unverified',
            'hypothetical_unit_stake':1.,'execution_assumption':'Publication observations, not confirmed placed/accepted tickets; slippage/tax/operator restrictions unverified',
            'published':len(records),'settled':len(settled),'pending':len(records)-len(settled),
            'win_rate':wins/(wins+losses) if wins+losses else None,
            'roi':pnl/stake if stake else None,'pnl_units':pnl if settled else None,
            'max_drawdown_units':max_drawdown if settled else None,
            'brier':mean(briers),'log_loss':mean(logs),'closing_line_value':mean(clv),'calibration':bins}


def breakdown(records, dimension):
    if dimension not in ('sport','market','model_version','parlay_size'):
        raise ValueError('Unsupported grouping')
    groups = defaultdict(list)
    for row in records:
        if dimension=='parlay_size':
            size=len(row['payload'].get('legs',[])) or 1
            groups[str(size)].append(row)
        else:
            source = row['payload']['estimate'] if dimension=='model_version' else row['payload']['quote']
            groups[source[dimension]].append(row)
    return {key:metrics(value) for key,value in groups.items()}
