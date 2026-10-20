"""Reload saved predictions only. No owner password or workflow dispatch."""
import streamlit as st
from intelligence.domain import utcnow


def refresh_saved(w):
    now=utcnow().timestamp();last=st.session_state.get('_saved_picks_refresh_at',0.)
    # A short session cooldown prevents repeat clicks clearing the shared-reader
    # cache; it is not a sports-provider allowance or authorization.
    if now-last>=30:
        if w.sync_saved:w.sync_saved()
        st.session_state.pop('_research_snapshot',None)
        st.session_state['_saved_picks_refresh_at']=now
    st.session_state.pop('_manual_research_owner_code',None)
    st.session_state.pop('_manual_research_control',None)
    # Callback runs before the sidebar radio is instantiated on the next run.
    st.session_state['workspace']='Best Picks & Parlays'
    st.session_state['_saved_picks_message']='Showing saved predictions. No sportsbook or paid AI request was made.'


def render(w):
    if st.button('Find Best Bets Now',key='find_best_bets',type='primary',on_click=refresh_saved,args=(w,)):
        st.rerun(scope='app')
    st.caption('Refresh saved singles and parlays. Background updates generate research; this button spends no sports-provider credits.')
