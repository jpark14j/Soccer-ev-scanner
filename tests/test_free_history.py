import pandas as pd
from intelligence.free_history import parse_nba,parse_retrosheet
from intelligence.history import clean_history


def test_nba_archive_keeps_one_home_record_per_game():
    frame=pd.DataFrame([
        {'game_id':'test1','date_game':'5/1/2015','game_location':'H','lg_id':'NBA','year_id':2015,'team_id':'CLE','opp_id':'GSW','pts':100,'opp_pts':90},
        {'game_id':'test1','date_game':'5/1/2015','game_location':'A','lg_id':'NBA','year_id':2015,'team_id':'GSW','opp_id':'CLE','pts':90,'opp_pts':100}])
    result=parse_nba(frame.to_csv(index=False).encode())
    assert len(result)==1 and result.FTHG.iloc[0]==100 and result.HomeTeam.iloc[0]=='CLE'


def test_retrosheet_doubleheaders_remain_distinct_and_resumed_games_excluded():
    # Synthetic Retrosheet-shaped records, not genuine match data.
    a=['20250901','1','Mon','NYA','AL','100','BOS','AL','100','2','3','54','D','']
    b=a.copy(); b[1]='2'; b[9]='4'; b[10]='1'
    resumed=a.copy(); resumed[1]='3'; resumed[13]='20250903,BOS01,1,2,3'
    result=parse_retrosheet(pd.DataFrame([a,b,resumed]).to_csv(index=False,header=False).encode())
    assert len(result)==2 and result.game_id.nunique()==2
    assert result.FTHG.tolist()==[3,1]


def test_arbitrary_game_ids_do_not_reorder_time():
    frame=pd.DataFrame({'game_id':['a','z'],'Date':['02/01/2024','01/01/2024'],
                        'HomeTeam':['Home','Home'],'AwayTeam':['Away','Away'],'FTHG':[2,1],'FTAG':[1,0]})
    result=clean_history(frame)
    assert result.game_id.tolist()==['z','a']
