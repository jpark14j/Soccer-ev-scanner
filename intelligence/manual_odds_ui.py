"""Small optional price form on the existing research page. No provider I/O."""
import json,sqlite3
import streamlit as st
from intelligence.domain import utcnow
from intelligence.manual_odds import save_price,compare,target_id
from intelligence.registry import load_registry,eligible_book

KEY='user_reported_research_prices_v1'


def render(w,safe):
    from intelligence.fixture_research import collect
    from intelligence.current_score_research import candidates
    from intelligence.consumer_ui import friendly_time
    now=utcnow()
    try:
        rows=collect(w.store,now,168,w.leagues)['forecasts']
        if 'Bundesliga' in w.leagues:rows+=candidates(w.store,now)
    except (OSError,sqlite3.Error,ValueError,KeyError,TypeError):rows=[]
    rows=[r for r in rows if r.get('research_eligible')]
    with st.expander('Compare a sportsbook price · optional research',expanded=False):
        st.caption('No API credits are used. Enter the exact individual price or the actual offered combined ticket price you see in your Ontario account. Never enter a fair price or a product of leg prices as a sportsbook ticket.')
        if not rows:
            st.info('No current source-backed research selection is available for price entry.');return
        books={b['odds_api_key']:b['name'] for b in load_registry()['books'] if eligible_book(b.get('odds_api_key'),now)}
        if not books:st.info('The Ontario sportsbook review must be current before comparing prices.');return
        with st.form('research_manual_price'):
            selected=st.selectbox('Exact selection',list(range(len(rows))),format_func=lambda i:rows[i]['event']+' · '+
                (' + '.join(str(l['selection'])+(f" {l['point']}" if l.get('point') is not None else '') for l in rows[i]['legs']) if rows[i].get('legs') else rows[i]['market']+' '+rows[i]['selection']))
            book=st.selectbox('Sportsbook',list(books),format_func=lambda b:books[b])
            odds=st.number_input('Actual offered decimal odds',min_value=1.01,max_value=1000.,value=2.,step=.01)
            attested=st.checkbox('I am viewing this exact selection or combined ticket in my Ontario sportsbook account now.')
            submitted=st.form_submit_button('Save price comparison')
        if submitted:
            try:
                row=rows[selected];price=save_price(row,book,odds,now.isoformat(),attested=attested,now=now)
                saved=list(st.session_state.get(KEY,[]));saved.append(price);st.session_state[KEY]=saved[-30:]
                st.success('Price comparison saved for this session. No bet was placed.')
            except ValueError:st.error('Confirm you personally see the exact current price before saving.')
        by_id={target_id(r):r for r in rows}
        for price in reversed(st.session_state.get(KEY,[])[-3:]):
            row=by_id.get(price['target_id'])
            if not row:st.caption('An earlier comparison is no longer supported by the current fixture/model inputs.');continue
            result=compare(row,price,now)
            st.text(safe(row['event']+' · '+books.get(price['bookmaker'],price['bookmaker'])))
            st.caption(f"User-reported decimal {price['decimal_odds']:.2f} · observed "+friendly_time(price['observed_at'])+' · not independently verified')
            if result['point_estimate_ev'] is not None:
                st.write(f"Conditional experimental model EV: {result['point_estimate_ev']:+.1%}. Research only; this cannot qualify for the Home page.")
            for reason in result['blockers']:st.caption(safe(reason))
        saved=st.session_state.get(KEY,[])
        if saved:
            st.download_button('Download entered price records',json.dumps(saved,indent=2,allow_nan=False),file_name='user-reported-price-records.json',mime='application/json')
            if st.button('Clear entered prices'):st.session_state.pop(KEY,None);st.rerun()
        st.caption('Stored only in this server session, up to 30 entries. A restart, disconnection or redeploy may erase them. Downloading preserves your copy; these are separate from permanent pregame forecasts and are not recorded wagers.')
