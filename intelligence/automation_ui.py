"""Saved automation/publication status only. No training or provider requests."""
import json,os,sqlite3
import streamlit as st
from intelligence.domain import utcnow,parse_time
from intelligence.shared_state import configuration


def health(store,secret=None):
    c=configuration(secret);p=getattr(store,'shared_status',{})
    envelope=p.get('envelope',{});heartbeat=envelope.get('heartbeat',{})
    running=heartbeat.get('status')=='running'
    expired=bool(running and envelope.get('lease_until') and parse_time(envelope['lease_until'])<=utcnow())
    return {'shared_mode_configured':c.problem() is None,'problem':c.problem() or p.get('problem'),
        'reader_mode':getattr(store,'read_replica',False),'saved_generation':envelope.get('generation'),
        'last_replica_sync':p.get('verified_at'),'heartbeat':heartbeat,
        'last_success':heartbeat.get('last_success_at'),'last_error':heartbeat.get('last_error_code'),
        'coverage_status':heartbeat.get('summary',{}).get('coverage_status') if isinstance(heartbeat.get('summary'),dict) else None,
        'missed_or_interrupted_run':expired,'provider_budget_hold':envelope.get('held'),
        'worker_enabled_here':os.getenv('RESEARCH_WORKER_ENABLED','0')=='1',
        'scheduled_operation_verified':False,'next_expected_run':None,
        'remote_redeploy_persistence_verified':False,
        'schedule_note':'A configured external schedule is required. GitHub default-branch cron is not changed; no recurring operation is inferred from credentials or a single saved run.',
        'durability_note':'Fenced single-writer snapshots with separate Postgres write-ahead budgets; not concurrent multi-writer SQLite. Real hosted readback/redeploy requires user verification.'}


def render_health(store,secret=None):
    h=health(store,secret)
    st.subheader('Automation Health')
    st.write('Background research · '+('Saved worker run available' if h['last_success'] else 'Needs configuration / no saved successful run'))
    st.write('Durable shared state · '+('Saved committed replica' if h['saved_generation'] else 'Not verified operating'))
    st.caption('Last successful run: '+str(h['last_success'] or 'not recorded')+' · last error: '+str(h['last_error'] or 'none recorded'))
    if h['coverage_status']:st.caption('Saved run coverage: '+h['coverage_status'])
    if h['missed_or_interrupted_run']:st.warning('The saved running lease expired. A run may have been interrupted; the previous committed state and reserved budgets remain authoritative.')
    if h['problem']:st.info(h['problem'])
    st.caption(h['schedule_note'])
    with st.expander('Advanced Details · automation, commit identity and budget authority'):st.json(h)


def render_published(store):
    from intelligence.publication_journal import performance,records
    from intelligence.learning import status
    st.subheader('Published Research & Paper Performance')
    try:report=performance(store);rows=records(store);learning=status(store)
    except (ValueError,OSError,sqlite3.Error,KeyError):
        st.info('Saved publication or learning evidence unavailable. Inspect storage; no performance inferred.');return
    from intelligence.analyst_config import load_config
    from intelligence.current_results import secret
    from intelligence.chat_privacy import redact_data
    sensitive=load_config(secret).sensitive_values
    report=redact_data(report,sensitive);rows=redact_data(rows,sensitive);learning=redact_data(learning,sensitive)
    a,b,c=st.columns(3)
    a.metric('Committed pregame picks',report['published_committed_pregame']);b.metric('Research wins',report['wins']);c.metric('Research losses',report['losses'])
    a,b,c=st.columns(3)
    a.metric('Pending',report['pending']);b.metric('Paper single units',f"{report['paper_net_units']:+.2f}" if report['paper_net_units'] is not None else 'Unavailable')
    c.metric('Paper single ROI',f"{report['paper_roi']:.1%}" if report['paper_roi'] is not None else 'Unavailable')
    st.caption('Win rate: '+(f"{report['win_rate']:.1%}" if report['win_rate'] is not None else 'unavailable')+'. '+report['note'])
    if not report['published_committed_pregame']:st.info('No genuine remotely committed pregame publications are available in this store. Local prepared research and old paper logs are separate; no winning history is simulated.')
    for r in rows[-5:][::-1]:
        p=r['payload']
        with st.expander(p['kind']+' · '+('Quarantined' if r['quarantined'] else r['label']['outcome'] if r['label'] else 'Pending')+' · '+p['prepared_at']):
            for leg in p['legs']:
                q=leg['quote'];st.text(q['league']+' · '+q['event']+' · '+q['market']+' '+q['selection']+' '+str(q['point'] if q['point'] is not None else ''))
                st.caption(q['bookmaker_name']+f" · original observed decimal {q['odds']:.2f} · source {q['source_updated_at']} · receipt {q['received_at']}")
                e=leg['estimate'];st.caption(f"Original model estimate {e['probability']:.1%}, range {e['lower']:.1%}–{e['upper']:.1%} · {e['model_version']} · kickoff {q['commence_time']}")
            st.caption('Committed publication: '+str(r['committed_at'] or 'not remotely verified')+' · '+p['status'])
            st.caption('Original prices are historical observations, not current offers. Parlay combined quote and joint probability remain unavailable.')
    st.subheader('AI Learning Status')
    st.write(learning['state']);st.caption(learning['frozen_champions'])
    st.caption(f"Challengers: {len(learning['challengers'])} · prospective challenger forecasts: {learning['test_forecasts']} · last evaluation: {learning['last_evaluation'] or 'not yet available'}")
    st.caption('No improvement or automatic model promotion is established. Historical models remain intact; the independent worker fits challengers only after the locked evidence requirements pass.')
    with st.expander('Advanced Details · paper accounting, model evaluation and review evidence'):
        st.json(report);st.json(learning)
        st.download_button('Download published research audit',json.dumps({'records':rows,'performance':report,'learning':learning},indent=2),file_name='published-research-audit.json',mime='application/json')
