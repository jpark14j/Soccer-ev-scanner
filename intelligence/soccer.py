"""Existing shrinkage Poisson model, retained as a research candidate."""
import math
import pandas as pd
from intelligence.domain import parse_time

ALIASES = {"manchester united":"man united", "manchester city":"man city", "tottenham hotspur":"tottenham", "newcastle united":"newcastle", "west ham united":"west ham", "wolverhampton wanderers":"wolves", "brighton and hove albion":"brighton", "nottingham forest":"nottm forest", "internazionale":"inter", "inter milan":"inter", "ac milan":"milan", "atletico madrid":"ath madrid", "athletic club":"ath bilbao", "real betis":"betis", "bayern munich":"bayern munich", "borussia dortmund":"dortmund", "rb leipzig":"rb leipzig", "bayer leverkusen":"leverkusen", "paris saint germain":"paris sg", "olympique marseille":"marseille", "olympique lyonnais":"lyon", "as roma":"roma", "juventus turin":"juventus", "ssc napoli":"napoli", "hellas verona":"verona"}
def canonical(name):
    import re
    cleaned = re.sub(r"[^a-z0-9 ]", "", str(name).lower()).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return ALIASES.get(cleaned, cleaned)

def match_team(name, options):
    index = {canonical(option): option for option in options}
    key = canonical(name)
    if key in index:
        return index[key]
    return None


def poisson_1x2(home_xg, away_xg, max_goals=12):
    def pmf(rate):
        return [math.exp(-rate) * rate**k / math.factorial(k) for k in range(max_goals + 1)]
    h, a = pmf(home_xg), pmf(away_xg)
    home_win = sum(h[i] * a[j] for i in range(len(h)) for j in range(i))
    draw = sum(h[i] * a[i] for i in range(len(h)))
    away_win = sum(h[i] * a[j] for i in range(len(h)) for j in range(i + 1, len(h)))
    total = home_win + draw + away_win
    return [home_win / total, draw / total, away_win / total]

def independent_prediction(history, home_name, away_name, kickoff):
    """Simple shrinkage Poisson strength model; explicitly unvalidated."""
    if history.empty:
        return None
    try:
        cutoff = pd.Timestamp(parse_time(kickoff)).tz_localize(None).normalize()
    except (TypeError, ValueError):
        return None
    past = history[history.date < cutoff].copy()
    if len(past) < 80:
        return None
    teams = set(past.HomeTeam) | set(past.AwayTeam)
    home = match_team(home_name, teams)
    away = match_team(away_name, teams)
    if home is None or away is None or home == away:
        return None
    home_games = past[past.HomeTeam == home].tail(24)
    away_games = past[past.AwayTeam == away].tail(24)
    if len(home_games) < 8 or len(away_games) < 8:
        return None
    league_home = float(past.FTHG.tail(450).mean())
    league_away = float(past.FTAG.tail(450).mean())
    if min(league_home, league_away) <= 0:
        return None
    # Shrink toward league average to avoid overreacting to small samples.
    prior = 10
    home_scored = (home_games.FTHG.sum() + prior * league_home) / (len(home_games) + prior)
    home_allowed = (home_games.FTAG.sum() + prior * league_away) / (len(home_games) + prior)
    away_scored = (away_games.FTAG.sum() + prior * league_away) / (len(away_games) + prior)
    away_allowed = (away_games.FTHG.sum() + prior * league_home) / (len(away_games) + prior)
    expected_home = min(4.0, max(0.2, home_scored * away_allowed / league_home))
    expected_away = min(4.0, max(0.2, away_scored * home_allowed / league_away))
    probs = poisson_1x2(expected_home, expected_away)
    return {"probabilities": probs, "home_goal_rate": expected_home, "away_goal_rate": expected_away,
            "home_games": len(home_games), "away_games": len(away_games)}

