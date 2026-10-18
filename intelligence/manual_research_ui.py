"""Private owner controls on Home; no sports calls or authoritative writes."""
import streamlit as st
from intelligence.manual_research import configuration,unlock,authorized,preflight,request_research,poll,ManualError

STATE='_manual_research_control'
CODE='_manual_research_owner_code'


def render(w):
    config=configuration(w.secret);state=st.session_state.setdefault(STATE,{})
    def login():
        code=st.session_state.pop(CODE,'')
        ok=unlock(state,code,configuration(w.secret))
        state['login_message']='Private access unlocked for ten minutes.' if ok else 'Private access could not be verified.'
    ready=authorized(state,config)
    reason=preflight(config,state,w.store)
    if state.get('request_message'):st.caption(state['request_message'])
    if st.button('Find Best Bets Now',key='find_best_bets',disabled=bool(reason),type='primary'):
        try:
            with st.spinner('Sending your private research request…'):request_research(config,state,w.store)
            state['request_message']='Research requested. The private worker will recheck permissions, holds and remaining allowance.'
        except ManualError as error:state['request_message']=str(error)
        except Exception:state['request_message']='Research could not be confirmed. No automatic retry was made.'
        st.rerun()
    if reason:st.caption(reason)
    pending=state.get('pending')
    if pending:
        if ready and pending['phase'] not in ('synced','failed'):
            try:
                phase=poll(config,state,w.store)
                # A completed request gets a fresh reader sync immediately,
                # rather than letting five-minute-old odds expire in the cache.
                if phase=='awaiting_saved_results' and not pending.get('sync_requested') and w.sync_saved:
                    pending['sync_requested']=True;w.sync_saved();st.rerun()
            except ManualError:st.caption('Private run status is temporarily unavailable. No additional research request was sent.')
            except Exception:st.caption('Private status is unavailable. No additional request was sent.')
        phase=pending['phase']
        messages={'unconfirmed':'Request delivery is uncertain. Check status; do not send a duplicate.',
            'queued':'Research requested; waiting for the private worker.',
            'running':'Research is running. Existing saved results remain visible.',
            'failed':'Research was blocked or failed. No new recommendations are claimed; the owner can inspect the private worker.',
            'awaiting_saved_results':'The private run finished. Waiting for its verified saved results.',
            'synced':'This request’s verified saved results are loaded. Only eligible current research is shown below.'}
        st.info(messages.get(phase,'Research status unavailable.'))
        if ready and phase not in ('synced','failed') and st.button('Check research status',key='manual_research_status'):
            try:poll(config,state,w.store)
            except ManualError as error:st.info(str(error))
            except Exception:st.info('Research status is unavailable. No new request was sent.')
            st.rerun()
        # Detect a committed result locally, without a GitHub request or retry.
        e=getattr(w.store,'shared_status',{}).get('envelope',{})
        if (ready and e.get('generation',0)>pending['baseline_generation']
            and e.get('heartbeat',{}).get('summary',{}).get('manual_request_id')==pending['id']):
            pending['phase']='synced'
    with st.expander('Private research access',expanded=False):
        st.caption('Only the owner can request new data. Browsing stays free of sports-provider requests. Never enter API keys here.')
        st.text_input('Private owner access code',type='password',key=CODE,max_chars=64)
        st.button('Unlock research',key='manual_research_unlock',on_click=login)
        if state.get('login_message'):st.caption(state['login_message'])
        if ready and st.button('Lock research',key='manual_research_lock'):
            state.pop('authorized_until',None);state.pop('auth_scope',None);st.rerun()
