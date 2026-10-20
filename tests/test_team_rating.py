"""Synthetic chronology/leakage tests, not historical accuracy evidence."""
import pandas as pd
import pytest
from intelligence.team_rating import replay, evaluate


def synthetic(sport):
    days=pd.date_range('2023-01-01',periods=300)
    return pd.DataFrame([{'date':day,'HomeTeam':h,'AwayTeam':a,'FTHG':110 if sport=='NBA' else 6,'FTAG':100 if sport=='NBA' else 3}
        for day in days for h,a in [('A','B'),('B','A')]])


@pytest.mark.parametrize('sport',['NBA','MLB'])
def test_same_day_order_and_later_outcomes_cannot_leak_into_earlier_predictions(sport):
    history=synthetic(sport); first, _=replay(history,sport)
    reversed_rows,_=replay(history.iloc[::-1],sport)
    by_key=lambda rows:{(r['date'],r['home'],r['away']):r['p'] for r in rows}
    assert by_key(first)==pytest.approx(by_key(reversed_rows))
    cutoff=history.date.iloc[400];history.loc[history.date>=cutoff,['FTHG','FTAG']]=[1,2]
    changed,_=replay(history,sport)
    assert by_key([r for r in first if r['date']<=cutoff.date().isoformat()])==pytest.approx(
        by_key([r for r in changed if r['date']<=cutoff.date().isoformat()]))


def test_calibration_is_unchanged_when_test_outcomes_change():
    history=synthetic('NBA');before=evaluate(history,'NBA','synthetic-only',resamples=10)
    history.loc[history.date>=pd.Timestamp(before['test_start']),['FTHG','FTAG']]=[1,2]
    after=evaluate(history,'NBA','synthetic-only',resamples=10)
    assert before['temperature']==after['temperature']
    assert before['calibration_start']<before['test_start']
    assert not before['approved'] and not before['replaces_incumbent']
