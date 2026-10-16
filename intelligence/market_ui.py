"""Explicit low-credit market searches and read-only stale-price inspection."""
from collections import Counter
from datetime import timedelta
import pandas as pd
import streamlit as st
from intelligence.domain import utcnow,parse_time
from intelligence.markets import FEATURED,CATALOG,catalog_for,selection_label,scope
from intelligence.providers import OddsAPI,LEAGUES,ProviderError
from intelligence.quota import quota_details,refresh_reason
from intelligence.registry import eligible_book
from intelligence.chat_privacy import redact
from intelligence.analyst_config import load_config


def quota_banner(store,settings):
    info=quota_details(store,settings.daily_limit)
    st.caption(f'Local odds reservations: {info["used"]}/{info["limit"]}; {info["remaining"]} remaining. '
        f'Next local reset {info["next_reset_toronto"]} · {info["next_reset_utc"]}. This is not the provider account reset.')
    if info['remaining']==0:
        st.info('The local odds budget is exhausted. Refresh is disabled; cached observations remain available for inspection. No spending cap is raised automatically.')
    return info


def render_markets(analysis,store,leagues,book_keys,key,settings,refresh_callback,secret_getter=None):
    sensitive=load_config(secret_getter).sensitive_values
    def safe(value):
        return redact(str(value),sensitive)
    st.info('Provider-documented markets are not a claim of Ontario availability. Only returned exact Ontario bookmaker keys supply observations. Stale prices are inspection-only and never enter current recommendations or the parlay selector.')
    league=st.selectbox('Search one competition',leagues or list(LEAGUES),key='market_league')
    sport=LEAGUES[league][0]
    quota=quota_details(store,settings.daily_limit)
    last=st.session_state.get('_market_request_at')
    cooldown=bool(last and (utcnow()-parse_time(last)).total_seconds()<60)
    selected=st.multiselect('Featured markets to retrieve',FEATURED,default=['spreads','totals'],
        format_func=lambda m:CATALOG[m].name,key='market_featured')
    from intelligence.research_refresh import featured_plan
    cost=sum(len(markets) for _,markets in featured_plan(analysis,[league],selected))
    reason=refresh_reason(key_configured=bool(key),selection_count=len(selected),cost=cost,quota=quota,cooldown=cooldown)
    st.caption('Featured requests cost up to one credit per selected market for the Canadian region. Current observations are reused. Retries also reserve credits. Choose just one market for a narrower search.')
    if st.button(f'Retrieve featured prices · up to {cost} local credits',key='market_fetch_featured',disabled=bool(reason)):
        st.session_state['_market_request_at']=utcnow().isoformat()
        try:
            with st.spinner('Retrieving only the selected featured markets…'):
                refresh_callback([league],markets=tuple(selected))
        except Exception:
            st.warning('The featured search did not complete. Check provider access and the local quota; no prices were invented.')
        else:
            st.rerun()
    if reason:
        st.caption(reason)
    events={q.event_id:(q.event,q.commence_time) for q in analysis.quotes
            if q.league==league and parse_time(q.commence_time)>utcnow()}
    cached=st.session_state.get('_listed_events',{}).get(league,{})
    events.update({id:row for id,row in cached.items() if parse_time(row[1])>utcnow()})
    st.subheader('Event markets and player props')
    st.caption('Event listing is documented as zero provider credits. Discovery costs one; event-odds queries reserve up to one per selected market. An observed market key does not prove a current price or sportsbook acceptance.')
    if st.button('Load upcoming event list · 0 provider credits',key='market_list_events',disabled=not key or cooldown):
        st.session_state['_market_request_at']=utcnow().isoformat()
        try:
            response=OddsAPI(key,store,daily_limit=settings.daily_limit,ttl=settings.cache_seconds).events(league)
            rows=response['data']
            if not isinstance(rows,list):
                raise ValueError()
            found={r['id']:(r['home_team']+' vs '+r['away_team'],r['commence_time']) for r in rows
                if r.get('sport_key')==LEAGUES[league][1] and parse_time(r['commence_time'])>utcnow()}
            st.session_state.setdefault('_listed_events',{})[league]=found
        except Exception:
            st.warning('The provider event list is unavailable. No events were substituted.')
        else:
            st.rerun()
    if events:
        event_id=st.selectbox('Event for additional markets',sorted(events),
            format_func=lambda id:safe(events[id][0]+' · '+events[id][1]),key='market_event')
        discovery_key=league+'/'+event_id
        discovery=st.session_state.get('_market_discovery',{}).get(discovery_key,{})
        if discovery and (utcnow()-parse_time(discovery['received_at'])).total_seconds()>1800:
            discovery={}
        if st.button('Discover Ontario market keys · 1 local credit',key='market_discover',
                     disabled=not key or cooldown or quota['remaining']<1):
            st.session_state['_market_request_at']=utcnow().isoformat()
            try:
                response=OddsAPI(key,store,daily_limit=settings.daily_limit,ttl=settings.cache_seconds).event_markets(league,event_id)
                rows=response['data'].get('bookmakers',[])
                found=[{'bookmaker':book['key'],'market':market['key'],'source_update':market.get('last_update')}
                    for book in rows if eligible_book(book.get('key')) for market in book.get('markets',[]) if isinstance(market.get('key'),str)]
                st.session_state.setdefault('_market_discovery',{})[discovery_key]={'received_at':response['received_at'],'rows':found}
            except Exception:
                st.warning('Event market discovery is unavailable for this provider/account/event. No Ontario coverage is assumed.')
            else:
                st.rerun()
        seen={r['market'] for r in discovery.get('rows',[])}
        choices=[m.key for m in catalog_for(sport) if m.key not in FEATURED and (m.documented or m.key in seen)]
        default='player_points' if sport=='NBA' else 'pitcher_strikeouts' if sport=='MLB' else 'btts'
        event_markets=st.multiselect('Event markets to retrieve',choices,
            default=[default] if default in choices else [],format_func=lambda m:CATALOG[m].name,key='market_event_keys_'+sport)
        reason=refresh_reason(key_configured=bool(key),selection_count=len(event_markets),cost=len(event_markets),quota=quota,cooldown=cooldown)
        if st.button(f'Retrieve event prices · up to {len(event_markets)} local credits',key='market_fetch_event',disabled=bool(reason)):
            st.session_state['_market_request_at']=utcnow().isoformat()
            try:
                with st.spinner('Checking this event’s actual Canadian feed…'):
                    refresh_callback([league],markets=tuple(event_markets),event_id=event_id,discovered=tuple(seen))
            except ProviderError as exc:
                st.warning(str(exc))
            except Exception:
                st.warning('Event prices are unavailable. No US/global prices or simulated props were substituted.')
            else:
                st.rerun()
        if reason:
            st.caption(reason)
        if discovery:
            st.caption('Keys seen in Ontario-mapped provider records at '+discovery['received_at']+'; no price or acceptance claim:')
            st.dataframe(pd.DataFrame(discovery['rows']),hide_index=True,use_container_width=True)
        if sport=='Soccer':
            st.caption('Asian-style handicaps use returned spread lines; quarter-line settlement remains unverified. Corners are offered for requests only if an exact reviewed key is discovered; the current published catalog does not establish Ontario corners coverage.')
    else:
        st.info('No upcoming event IDs are cached for this competition. Load the zero-credit event list to choose one; player props are never invented.')
    st.subheader('Observed selections')
    mode=st.radio('Prices to inspect',['Current only','Include stale / historical'],index=1,horizontal=True,key='market_inspect_mode')
    @st.fragment(run_every='60s')
    def inspect():
        now=utcnow(); rows=[]
        for q in analysis.quotes:
            if q.league!=league or q.bookmaker not in book_keys:
                continue
            status=q.status(now)
            if mode=='Current only' and status!='current':
                continue
            rows.append({'Event':safe(q.event),'Event start (UTC)':q.commence_time,
                'Selection in English':safe(selection_label(q)),'Market key':q.market,'Player / team':safe(q.participant or q.selection),
                'Line':q.point,'Direction':q.selection,'Observed decimal odds':q.odds,'Sportsbook':safe(q.bookmaker_name),
                'Source timestamp':q.source_updated_at,'Received':q.received_at,'Status':status,
                'Use':'current research observation; execution unverified' if status=='current' else 'historical inspection only; never actionable',
                'Settlement scope':scope(q)})
        if rows:
            st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
        else:
            st.info('No observed selections match this view. This is not evidence that every sportsbook lacks the market.')
        st.caption('Old source timestamps are retained exactly; requesting or reopening a cache never makes a price current. Settlement, overtime/extra-time and player-start rules must be verified at the operator.')
    inspect()
