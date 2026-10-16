import streamlit as st
from intelligence.persistence import storage_status
from intelligence.lifecycle import registry_status


def render_operations(analysis,store):
    st.subheader('Research Operations')
    storage=storage_status(store);registry=registry_status(store)
    a,b,c=st.columns(3)
    a.metric('Private shadow forecasts',storage['shadow_forecasts'])
    b.metric('Candidate model artifacts',registry['candidate_artifacts'])
    c.metric('Reviewed model actions',registry['reviewed_actions'])
    st.info('Automatic on-open research is active within the existing cap. Streamlit is not an always-running scheduler. Scheduled collection/retraining and off-host persistence are not configured.')
    st.write(storage['note'])
    st.write('Final results are collected automatically for ended pending publications/shadow events when two existing credits are available. Settlement stays pending without exact verified results and reviewed operator rules. Player props, voids and quarter-line settlement are not inferred.')
    st.write('Shadow forecasts are immutable pregame research records. Provider-declared completed NBA/MLB finals can score their explicit full-final targets; soccer period scope remains blocked. These labels are not operator settlements, recommended bets, accepted tickets or a forward ROI track record.')
    with st.expander('Processing, durability and model audit'):
        st.json({'storage':storage,'model_lifecycle':registry,'latest_processing':analysis.processing})
    st.caption('Manual offline worker checks and private SQLite backups are available through the documented CLI. Retraining creates candidates only; activation/rollback requires reviewed fresh evidence. No chat action can train, promote, purchase or place a wager.')
