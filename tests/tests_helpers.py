def event_payload(q,market=None,participant='',point=None,selection=None):
    event={'id':q.event_id,'sport_key':{'NBA':'basketball_nba','MLB':'baseball_mlb','Soccer':'soccer_epl'}[q.sport],
        'home_team':q.home,'away_team':q.away,'commence_time':q.commence_time,
        'bookmakers':[{'key':q.bookmaker,'title':q.bookmaker_name,'last_update':q.source_updated_at,
        'markets':[{'key':market or q.market,'outcomes':[{'name':selection or q.selection,'description':participant,
                                                      'point':point,'price':q.odds}]}]}]}
    return {'received_at':q.received_at,'data':event}
