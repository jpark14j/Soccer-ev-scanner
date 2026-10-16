"""Streamlit conversation UI; credentials and API clients remain server-side."""
import uuid
from dataclasses import asdict
import streamlit as st
from intelligence.analyst_config import load_config
from intelligence.analyst_context import FOLLOW_UPS
from intelligence.analyst_usage import UsageLedger
from intelligence.chat_privacy import InvalidChatInput, append_message, conversation, validate_input
from intelligence.llm import PaidAnalyst, ChatReply
from intelligence.performance import metrics

STATE = '_analyst_conversation_v2'
COUNT = '_analyst_session_requests'
CONSENT = '_analyst_provider_consent'


def clear_conversation():
    st.session_state.pop(STATE,None)
    st.session_state[CONSENT] = False


def display_message(message):
    with st.chat_message(message['role']):
        if message['role']=='assistant':
            st.caption(message.get('mode','Local · rule-based'))
            if message.get('warning'):
                st.warning(message['warning'])
        # Plain text prevents user/source Markdown from embedding remote images
        # or masquerading as system UI. Static controls use Streamlit components.
        st.text(message['content'])
        if message.get('sources'):
            with st.expander('Evidence used for this answer'):
                for source in message['sources']:
                    st.caption(f'{source["id"]} · {source["sport"]} · {source["kind"]}')
                    st.text(source['text'])


def render_assistant(analysis, store, secret_getter):
    config = load_config(secret_getter)
    st.session_state.pop('analyst_history',None)  # discard the old unbounded format
    state, expired = conversation(st.session_state.get(STATE),config)
    st.session_state[STATE] = state
    if expired:
        st.session_state[CONSENT] = False
        st.info('The inactive conversation was cleared. Start a new question.')
    st.session_state.setdefault(COUNT,0)
    if config.paid_ready:
        st.info(f'OpenAI integration configured · {config.model}. Requests require your session consent below. Local answers remain available.')
    else:
        st.info('Local mode · rule-based answers from application records. Paid OpenAI requests are disabled or unconfigured; no question is sent to OpenAI.')
    for error in config.errors:
        st.warning(error+' Paid requests are blocked.')
    with st.expander('Privacy, usage limits and capabilities'):
        st.write('Ask about NBA, soccer, MLB, observed Ontario odds, model evaluations, expected value and forward performance. Missing evidence stays unavailable. This assistant cannot place wagers, make purchases, execute code or change application records.')
        st.write(f'Conversation history stays in this Streamlit session: at most {config.max_session_messages} messages, cleared on the next interaction after {config.idle_minutes} inactive minutes. Clear it at any time. Prior answers are historical snapshots; check their timestamps.')
        st.write('If you later enable OpenAI and consent, the bounded question, recent conversation topics/questions and selected verified analytical records are sent to OpenAI. Do not enter personal, financial or account information. Credential-like messages are rejected; detection cannot recognize every secret.')
        st.write('Requests use store=False and no remote conversation storage. This does not eliminate provider abuse-monitoring retention or infrastructure logs. Consult the provider data policy before consenting. Chat text is not written to the application database or reports; minimal request-count/token/budget records are retained for up to 90 days, purged when another request is admitted.')
        st.link_button('OpenAI API data controls','https://developers.openai.com/api/docs/guides/your-data')
        st.write(f'Limits: {config.max_daily_requests}/day, {config.max_monthly_requests}/month, {config.max_session_requests}/browser session; input bound {config.max_input_tokens} tokens; output cap {config.max_output_tokens}. USD safeguards: ${config.request_usd}/request, ${config.daily_usd}/day, ${config.monthly_usd}/month. No automatic API retries.')
        st.caption('Reservations are conservative estimates using configured token prices, shared by this database. These limits do not replace provider billing controls, durable storage or authentication; separate deployments have separate counters. Clear chat does not reset the counters.')
        try:
            st.write(UsageLedger(store).snapshot())
        except Exception:
            st.warning('Usage counters are unavailable; paid requests will be blocked.')
    consent = False
    if config.paid_ready:
        consent = st.checkbox('I consent to sending this session’s bounded questions and verified analytical context to OpenAI.',key=CONSENT,value=False)
        st.caption('Approval and API keys are configured by the operator in secrets; this checkbox does not activate a disabled integration.')
    else:
        st.session_state[CONSENT] = False
    st.button('Clear conversation',key='analyst_clear',on_click=clear_conversation)
    for message in state['messages']:
        display_message(message)
    if not state['messages']:
        st.subheader('Explore the evidence')
        st.caption('Ask a question or start with one below. Local mode uses rules and templates; it is not a generative AI model.')
    last = next((m for m in reversed(state['messages']) if m['role']=='assistant'),{})
    suggestions = last.get('followups') or [FOLLOW_UPS[k] for k in ('best','models','performance')]
    suggestion = None
    columns = st.columns(min(len(suggestions),3))
    for index,text in enumerate(suggestions[:3]):
        if columns[index].button(text,key=f'analyst_suggestion_{index}',use_container_width=True):
            suggestion = text
    question = st.chat_input('Ask about verified sports data, odds, models or performance',
                             max_chars=config.max_input_chars,key='analyst_chat_input')
    question = suggestion or question
    if not question:
        # A prior interrupted execution must not silently cause a second call.
        if state.pop('pending',None):
            st.warning('The previous response was interrupted. It will not be automatically resubmitted. You can ask again; an earlier provider attempt may still count toward usage.')
        return
    try:
        question = validate_input(question,config)
    except InvalidChatInput as exc:
        st.error(str(exc))
        return
    prior = list(state['messages'])
    append_message(state,{'role':'user','content':question},config)
    display_message(state['messages'][-1])
    request_id = uuid.uuid4().hex
    state['pending'] = request_id
    # Count before starting: an interrupted request cannot evade the session cap.
    previous_count = st.session_state[COUNT]
    may_attempt = config.paid_ready and consent
    if may_attempt:
        st.session_state[COUNT] += 1
    with st.spinner('Checking current evidence and preparing an answer…'):
        try:
            reply = PaidAnalyst(store,config).respond(question,analysis,metrics(store.records()),
                        history=prior,consent=consent,session_requests=previous_count,request_id=request_id)
        except Exception:
            # Do not let unexpected storage/context errors expose tracebacks or
            # inputs. Keep the session reservation if an attempt is uncertain.
            reply = ChatReply('Verified evidence is temporarily unavailable. Try again after checking the application data status.',
                'Local · rule-based','availability','all',[],[],
                'An answer could not be prepared. No unverified recommendation is shown.',may_attempt)
    if may_attempt and not reply.paid_attempted:
        st.session_state[COUNT] -= 1
    state.pop('pending',None)
    message = {'role':'assistant',**asdict(reply)}
    append_message(state,message,config)
    st.rerun()
