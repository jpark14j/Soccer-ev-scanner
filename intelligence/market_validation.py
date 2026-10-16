"""Chronological research diagnostics, never invented historical sportsbook bets."""
from pathlib import Path
from types import SimpleNamespace
import json,math
from intelligence.domain import digest,utcnow
from intelligence.advanced_models import make_context,probability,VERSIONS
from intelligence.evaluation import calibrate,scores,wilson

# Predeclared diagnostic tasks; these are NOT historical sportsbook lines/prices.
TASKS={'NBA':(('spreads','Home',-5.5),('totals','Over',220.5)),
       'MLB':(('spreads','Home',-1.5),('totals','Over',8.5)),
       'Soccer':(('totals','Over',2.5),('btts','Yes',None))}


def code_hash():
    root=Path(__file__).parent
    return digest({name:(root/name).read_text() for name in ('advanced_models.py','market_validation.py','team_codes.py','soccer.py')})


def evaluate(history,sport,source):
    if sport not in TASKS or len(history)<500 or not source:
        raise ValueError('At least 500 genuine historical games with source provenance are required')
    days=sorted(history.date.unique())
    cal_start,test_start=days[int(len(days)*.6)],days[int(len(days)*.8)]
    buckets={str(task):{'cal':[],'test':[]} for task in TASKS[sport]}
    for index,row in history[history.date>=cal_start].iterrows():
        kickoff=row.date.isoformat()+'+00:00'
        context=make_context(history,sport,row.HomeTeam,row.AwayTeam,kickoff,as_of=row.date.tz_localize('UTC'))
        if context is None:
            continue
        for market,side,line in TASKS[sport]:
            # A diagnostic target carries no sportsbook, price or fabricated quote.
            q=SimpleNamespace(sport=sport,home=row.HomeTeam,away=row.AwayTeam,commence_time=kickoff,
                market=market,selection=row.HomeTeam if side=='Home' else side,point=line,participant='')
            p=probability(context,q)
            if p is None:
                continue
            y=int(row.FTHG+line>row.FTAG) if market=='spreads' else int(row.FTHG+row.FTAG>line) if market=='totals' else int(row.FTHG>0 and row.FTAG>0)
            buckets[str((market,side,line))]['cal' if row.date<test_start else 'test'].append((p,y))
    tasks=[]
    for market,side,line in TASKS[sport]:
        cal,test=(buckets[str((market,side,line))][name] for name in ('cal','test'))
        if len(cal)<30 or len(test)<30:
            continue
        temperatures=[.5+i*.05 for i in range(31)]
        temp=min(temperatures,key=lambda t:sum(-math.log(max(1e-12,calibrate([p,1-p],t)[0 if y else 1])) for p,y in cal)/len(cal))
        test_p=[calibrate([p,1-p],temp)[0] for p,_ in test]
        y=[y for _,y in test]
        correct=sum(int(p>=.5)==target for p,target in zip(test_p,y))
        cal_bins=[]
        gap=0.
        for i in range(10):
            vals=[(p,target) for p,target in zip(test_p,y) if min(9,int(p*10))==i]
            if vals:
                n=len(vals); positives=sum(target for _,target in vals)
                mean=sum(p for p,_ in vals)/n
                gap+=abs(mean-positives/n)*n/len(test)
                cal_bins.append({'bin':i,'n':n,'mean_forecast':mean,'observed':positives/n,
                                 'observed_frequency_interval':wilson(positives,n)})
        baseline=(sum(y for _,y in cal)+1)/(len(cal)+2)
        tasks.append({'market':market,'selection_rule':side,'fixed_diagnostic_line':line,
            'calibration_n':len(cal),'test_n':len(test),'temperature':temp,
            'metrics':scores([[p,1-p] for p in test_p],[0 if target else 1 for target in y]),
            'simple_baseline_metrics':scores([[baseline,1-baseline]]*len(test),[0 if target else 1 for target in y]),
            'classification_accuracy':correct/len(test),'accuracy_interval':wilson(correct,len(test)),
            'baseline_classification_accuracy':sum(int(baseline>=.5)==target for target in y)/len(test),
            'test_positive_rate':sum(y)/len(y),
            'calibration_gap':gap,'calibration_bins':cal_bins,
            'betting_win_rate':None,'roi':None,'pnl_units':None,
            'limitation':'Fixed threshold forecast diagnostic, not observed historical markets or a betting strategy'})
    if not tasks:
        raise ValueError('No adequately sized chronological task evaluation was possible')
    report={'schema':1,'sport':sport,'model_version':VERSIONS[sport],'status':'research',
        'data_source':source,'data_sha256':digest(history.to_json(orient='records',date_format='iso')),
        'code_sha256':code_hash(),'data_end':history.date.max().isoformat()+'+00:00',
        'generated_at':utcnow().isoformat(),'calibration_start':str(cal_start),'test_start':str(test_start),
        'tasks':tasks,'score_convention':'Brier sums both class errors; binary Brier is half this value',
        'interval_assumptions':'Wilson diagnostic intervals assume independent classification outcomes; shared-team/same-day dependence can invalidate nominal coverage',
        'promotion_blockers':['No timestamped historical sportsbook lines/prices or accepted-parlay restrictions',
            'Predeclared fixed thresholds do not validate every live market line',
            'No held-out joint-market calibration or independently verified forward record',
            'Injuries, confirmed lineups and player-level inputs are missing',
            'Archive recency and distribution shift require review before current publication'],
        'roi':None,'profitable_edge_established':False}
    report['evidence_id']=digest(report)
    return report


def load_reports(directory='docs/evidence'):
    result=[]
    for sport in TASKS:
        try:
            report=json.loads((Path(directory)/(sport.lower()+'-advanced-research.json')).read_text())
            if report.get('evidence_id')!=digest({k:v for k,v in report.items() if k!='evidence_id'}):
                continue
            if report.get('code_sha256')!=code_hash() or report.get('model_version')!=VERSIONS[sport]:
                continue
            result.append(report)
        except (OSError,ValueError,TypeError,KeyError):
            continue
    return result
