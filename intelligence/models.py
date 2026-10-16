"""Sport-specific research candidates. None is validated merely by existing."""
import math
from statistics import NormalDist
import pandas as pd
from intelligence.domain import parse_time
from intelligence.soccer import independent_prediction, match_team, poisson_1x2

VERSIONS = {'Soccer': 'soccer-poisson-2', 'NBA': 'nba-margin-normal-1', 'MLB': 'mlb-runs-poisson-1'}


def predict(history, sport, home, away, kickoff):
    if history.empty:
        return None
    cutoff = pd.Timestamp(parse_time(kickoff)).tz_localize(None).normalize()
    past = history[history.date < cutoff]
    if sport == 'Soccer':
        result = independent_prediction(history, home, away, kickoff)
        return result['probabilities'] if result else None
    if sport not in ('NBA', 'MLB'):
        return None
    home = match_team(home, set(past.HomeTeam) | set(past.AwayTeam))
    away = match_team(away, set(past.HomeTeam) | set(past.AwayTeam))
    if home is None or away is None or len(past) < 100:
        return None
    home_games = past[(past.HomeTeam == home) | (past.AwayTeam == home)].tail(30)
    away_games = past[(past.HomeTeam == away) | (past.AwayTeam == away)].tail(30)
    if min(len(home_games), len(away_games)) < 12:
        return None
    if sport == 'NBA':
        # Expected point margin, with home advantage from earlier league results.
        # Team net rating here is points/game, not pace-adjusted efficiency.
        def net(games, team):
            margin = games.FTHG - games.FTAG
            return float(margin.where(games.HomeTeam == team, -margin).mean()) * len(games) / (len(games) + 15)
        league = past.tail(1200)
        advantage = float((league.FTHG - league.FTAG).mean())
        mean = net(home_games, home) - net(away_games, away) + advantage
        scale = float((league.FTHG - league.FTAG).std(ddof=1))
        if scale <= 0 or not math.isfinite(scale):
            return None
        p = NormalDist(mean, scale).cdf(0)
        return [1 - p, p]
    # MLB uses run-count distributions rather than a basketball margin model.
    # Regulation ties are split by an explicitly unvalidated 50/50 extra-inning
    # assumption; promotion needs evidence against market. No F5 reuse.
    def runs(games, team, scored):
        at_home = games.HomeTeam == team
        first, second = ('FTHG','FTAG') if scored else ('FTAG','FTHG')
        return float(games[first].where(at_home, games[second]).mean())
    base = float((past.FTHG.mean() + past.FTAG.mean()) / 2)
    if base <= 0:
        return None
    h = (runs(home_games, home, True) + 15 * base / len(home_games)) / (1 + 15 / len(home_games))
    a = (runs(away_games, away, True) + 15 * base / len(away_games)) / (1 + 15 / len(away_games))
    h *= runs(away_games, away, False) / base
    a *= runs(home_games, home, False) / base
    hw, tie, aw = poisson_1x2(h, a, max_goals=40)
    return [hw + tie / 2, aw + tie / 2]


def poisson_count_over(rate, line):
    """P(count > line) for non-negative Poisson counts; integer lines can push.

    Research utility only: fitted/validated rate and push handling are required
    before pricing a count prop. It is not appropriate for all prop distributions.
    """
    if not math.isfinite(rate) or rate < 0 or not math.isfinite(line) or not 0 <= line < 1000 or rate > 500:
        raise ValueError('Invalid count rate/line')
    term = math.exp(-rate)
    cumulative = term
    for k in range(1,math.floor(line)+1):
        term *= rate/k
        cumulative += term
    return max(0.,min(1.,1-cumulative))
