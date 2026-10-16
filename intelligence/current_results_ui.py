"""Explicit, results-only preview diagnostic; never requests sportsbook prices."""
import streamlit as st
from intelligence.current_results import configuration, status, current, CODES


def render(w):
    config = configuration(w.secret)
    st.subheader('Current soccer results')
    st.caption('Optional football-data.org delayed results. A configured account is not proof of current coverage. No live in-game forecasts are enabled here.')
    st.json(status(w.store, config))
    st.caption('Existing OpenFootball data remains the default. Set FOOTBALL_DATA_ENABLED and FOOTBALL_DATA_USE_REVIEWED only after reviewing the account terms; store FOOTBALL_DATA_TOKEN in preview Secrets. Never paste tokens into chat.')
    leagues = st.multiselect('Results competitions', list(CODES), default=list(CODES)[:3], key='current_results_leagues')
    if st.button('Refresh soccer results only', disabled=bool(config.problem), help='At most one cached results request per selected league; six/day/store. Does not fetch odds.'):
        with st.spinner('Checking full-season results, identities and coverage…'):
            for league in leagues:
                _, meta = current(w.store, league, config=config)
                st.write(league)
                st.json({k: v for k, v in meta.items() if k in ('ok', 'problem', 'checked_at', 'coverage', 'sha256', 'source_url')})
        st.info('Results cache updated. The next Refresh analysis uses this cache; existing odds limits still apply. No new odds were requested by this results check.')
    st.link_button('Results setup and verification guide', 'https://github.com/jpark14j/Soccer-ev-scanner/blob/development/verified-sports-intelligence/docs/PHASE3A_CURRENT_RESULTS.md')
    if config.enabled:
        st.caption('Football data provided by the Football-Data.org API')
    st.subheader('Forward research backup')
    from intelligence.persistence import storage_status, paper_export
    from intelligence.analyst_config import load_config
    from intelligence.chat_privacy import redact_data
    import json
    st.json(storage_status(w.store))
    st.caption('Community Cloud does not guarantee local file persistence. Download paper records to your own device before a reboot/redeploy; this is an inspection export, not an automated database restore or permanent hosted ledger.')
    if st.button('Prepare paper research export'):
        try:
            data = redact_data(paper_export(w.store), load_config(w.secret).sensitive_values)
            st.download_button('Download paper research JSON', json.dumps(data, indent=2),
                               file_name='prospective-paper-research.json', mime='application/json')
        except ValueError:
            st.warning('Export exceeds the bounded UI size. Use the documented private SQLite backup instead.')
