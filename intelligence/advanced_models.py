"""Sport-specific score research. Never validated merely because forecasts exist.

NBA uses paired empirical score residuals (retaining observed score dependence).
Soccer uses goal Poisson strengths; MLB uses run Poisson strengths conditioned on
non-tie final scores. These assumptions require empirical validation and cannot
supply a tradable advantage, player context or known sportsbook settlement rules.
"""
from dataclasses import dataclass
import math
import numpy as np
import pandas as pd
from intelligence.domain import utcnow,parse_time
from intelligence.markets import is_half_line,market_problem
from intelligence.soccer import independent_prediction,canonical
from intelligence.team_codes import history_name

VERSIONS={'NBA':'nba-paired-score-research-1','Soccer':'soccer-goal-grid-research-1','MLB':'mlb-run-grid-research-1'}


@dataclass
class ScoreContext:
    sport: str
    home: str
    away: str
    kickoff: str
    training_end: str
    history_n: int
    home_scores: np.ndarray
    away_scores: np.ndarray
    weights: np.ndarray
    method: str

    @property
    def version(self):
        return VERSIONS[self.sport]


def make_context(history,sport,home,away,kickoff,as_of=None):
    if history is None or history.empty or sport not in VERSIONS:
        return None
    event=pd.Timestamp(parse_time(kickoff)).tz_localize(None).normalize()
    observed=pd.Timestamp(as_of or utcnow()).tz_localize(None).normalize()
    past=history[history.date<min(event,observed)]
    if len(past)<200:
        return None
    options=set(past.HomeTeam)|set(past.AwayTeam)
    hname,aname=history_name(sport,home,options),history_name(sport,away,options)
    if not hname or not aname or hname==aname:
        return None
    hgames=past[(past.HomeTeam==hname)|(past.AwayTeam==hname)].tail(30)
    agames=past[(past.HomeTeam==aname)|(past.AwayTeam==aname)].tail(30)
    if min(len(hgames),len(agames))<12:
        return None
    league=past.tail(1200)
    def average(games,team,scored):
        a,b=('FTHG','FTAG') if scored else ('FTAG','FTHG')
        return float(games[a].where(games.HomeTeam==team,games[b]).mean())
    base=float((league.FTHG.mean()+league.FTAG.mean())/2)
    if not math.isfinite(base) or base<=0:
        return None
    def shrink(games,team,scored):
        return (average(games,team,scored)*len(games)+15*base)/(len(games)+15)
    if sport=='NBA':
        advantage=float((league.FTHG-league.FTAG).mean())
        hmean=(shrink(hgames,hname,True)+shrink(agames,aname,False))/2+advantage/2
        amean=(shrink(agames,aname,True)+shrink(hgames,hname,False))/2-advantage/2
        # Move paired residuals together. Never independently resample home/away.
        hs=np.maximum(0,np.rint(league.FTHG.to_numpy()-league.FTHG.mean()+hmean))
        ass=np.maximum(0,np.rint(league.FTAG.to_numpy()-league.FTAG.mean()+amean))
        keep=hs!=ass
        hs,ass=hs[keep],ass[keep]
        if len(hs)<100:
            return None
        weights=np.ones(len(hs))/len(hs)
        method='Paired historical score-residual scenarios; final non-tie scores; not pace/player/injury adjusted'
    else:
        if sport=='Soccer':
            fit=independent_prediction(past,home,away,kickoff)
            # Explicit archive aliases may have resolved names differently.
            if fit is None:
                fit=independent_prediction(past,hname,aname,kickoff)
            if fit is None:
                return None
            hmean,amean=fit['home_goal_rate'],fit['away_goal_rate']
        else:
            hmean=shrink(hgames,hname,True)*average(agames,aname,False)/base
            amean=shrink(agames,aname,True)*average(hgames,hname,False)/base
        maximum=24 if sport=='Soccer' else 45
        if not all(math.isfinite(v) and 0<v<20 for v in (hmean,amean)):
            return None
        def pmf(rate):
            values=[math.exp(-rate)]
            for n in range(1,maximum+1):
                values.append(values[-1]*rate/n)
            return np.array(values)
        hp,ap=pmf(hmean),pmf(amean)
        if 1-hp.sum()*ap.sum()>1e-6:
            return None
        hgrid,agrid=np.meshgrid(np.arange(maximum+1),np.arange(maximum+1),indexing='ij')
        hs,ass=hgrid.ravel(),agrid.ravel()
        weights=np.outer(hp,ap).ravel()
        if sport=='MLB':
            keep=hs!=ass
            hs,ass,weights=hs[keep],ass[keep],weights[keep]
        weights=weights/weights.sum()
        method=('Independent Poisson goal strengths; team-score independence is an unvalidated modeling assumption' if sport=='Soccer'
                else 'Independent Poisson run strengths conditioned on a non-tie final; no extra-innings, pitcher, bullpen or weather model')
    return ScoreContext(sport,home,away,kickoff,past.date.max().isoformat()+'+00:00',len(past),hs,ass,weights,method)


def forecast_problem(q):
    problem=market_problem(q)
    if problem:
        return problem
    if q.market not in ('h2h','spreads','totals','btts'):
        return 'No licensed player/corners history, availability inputs or fitted market-specific model is connected'
    if q.market in ('spreads','totals') and not is_half_line(q.point):
        return 'Integer/quarter lines require verified push/half-win/half-loss settlement modeling; no probability is supplied'
    return ''


def win_mask(context,q):
    if forecast_problem(q) or q.sport!=context.sport or (canonical(q.home),canonical(q.away))!=(canonical(context.home),canonical(context.away)) or parse_time(q.commence_time)!=parse_time(context.kickoff):
        return None
    h,a=context.home_scores,context.away_scores
    if q.market=='h2h':
        return h==a if q.selection=='Draw' else h>a if canonical(q.selection)==canonical(q.home) else a>h
    if q.market=='spreads':
        return h+q.point>a if canonical(q.selection)==canonical(q.home) else a+q.point>h
    if q.market=='totals':
        return h+a>q.point if q.selection.lower()=='over' else h+a<q.point
    yes=(h>0)&(a>0)
    return yes if q.selection.lower()=='yes' else ~yes


def probability(context,q):
    mask=win_mask(context,q)
    return float(context.weights[mask].sum()) if mask is not None else None


def research_joint(context,quotes):
    if not 2<=len(quotes)<=3:
        return None
    masks=[win_mask(context,q) for q in quotes]
    if any(mask is None for mask in masks):
        return None
    mask=np.logical_and.reduce(masks)
    return {'probability':float(context.weights[mask].sum()),'validated':False,
            'model_version':context.version,'training_end':context.training_end,'history_n':context.history_n,
            'method':context.method,'scope':'Assumed same full-event score target; operator settlement rules remain unverified',
            'ev':None,'reason':'Conditional score-model scenario only; no held-out joint-market validation or actual combined quote'}
