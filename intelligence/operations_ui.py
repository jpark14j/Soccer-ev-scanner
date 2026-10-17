import streamlit as st
from intelligence.persistence import storage_status
from intelligence.lifecycle import registry_status


def render_operations(analysis,store,secret=None):
    st.subheader('Research Operations')
    storage=storage_status(store);registry=registry_status(store)
    a,b,c=st.columns(3)
    a.metric('Private shadow forecasts',storage['shadow_forecasts'])
    b.metric('Candidate model artifacts',registry['candidate_artifacts'])
    c.metric('Reviewed model actions',registry['reviewed_actions'])
    st.info('Research loads on first open or an explicit refresh within the existing cap. Pages and filters reuse the session scan. Streamlit is not an always-running scheduler. Scheduled collection/retraining and off-host persistence are not configured.')
    st.write(storage['note'])
    st.write('Final results are collected automatically for ended pending publications/shadow events when two existing credits are available. Settlement stays pending without exact verified results and reviewed operator rules. Player props, voids and quarter-line settlement are not inferred.')
    st.write('Shadow forecasts are immutable pregame research records. Provider-declared NBA/MLB finals can score their full-final targets; focused EPL forecasts can receive public source-reported full-time target labels. Soccer operator settlement scope remains unverified. These are not accepted tickets or a forward betting ROI record.')
    with st.expander('Processing, durability and model audit'):
        st.json({'storage':storage,'model_lifecycle':registry,'latest_processing':analysis.processing})
    st.caption('Manual offline worker checks and private SQLite backups are available through the documented CLI. Retraining creates candidates only; activation/rollback requires reviewed fresh evidence. No chat action can train, promote, purchase or place a wager.')
    with st.expander('Optional private off-host backup · disabled until configured'):
        from intelligence.remote_backup import configuration,status,upload,BackupError
        from intelligence.analyst_config import load_config
        from intelligence.chat_privacy import redact_data
        config=configuration(secret);remote=status(store,config)
        st.json(redact_data(remote,load_config(secret).sensitive_values))
        st.caption('Manual snapshot only: at most one attempt per UTC day, 20 MiB, three requests for private-bucket check/upload/readback. No continuous persistence or shared-budget scheduler is enabled. Restore uses a new file with a provider-request hold.')
        if st.button('Create private off-host snapshot · explicit upload',disabled=not remote['configured'],key='explicit_remote_backup'):
            try:st.json(upload(store,config))
            except BackupError as error:st.info(str(error))
