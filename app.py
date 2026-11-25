"""Run with: streamlit run app.py"""
import hashlib
import pandas as pd
import streamlit as st
from opponent_intelligence import extract_report
from opponent_intelligence.dashboard.views import render_dashboard

st.set_page_config(page_title='Opponent Analysis Dashboard', layout='wide')
from opponent_intelligence.presentation import styles
styles()
if st.session_state.get('result') is None:
    st.title('Opponent Analysis Dashboard')
    st.write('Upload a text-based Hudl Wyscout team report to extract structured CSVs.')
with st.expander('Report upload & extraction', expanded=st.session_state.get('result') is None):
    st.caption('Text-based Hudl Wyscout team reports · PDFs up to 30 MB.')
    upload = st.file_uploader('Wyscout PDF', type=['pdf'])
    data = upload.getvalue() if upload is not None else None
    fingerprint = hashlib.sha256(data).hexdigest() if data else None
    if st.session_state.get('source_id') != fingerprint:
        st.session_state.pop('result', None)
        for key in list(st.session_state):
            if key.startswith(('overview_', 'formation_', 'player_', 'explorer_', 'tactical_', 'workflow_')):
                del st.session_state[key]
        st.session_state['source_id'] = fingerprint
    if st.button('Process', disabled=upload is None):
        with st.spinner('Extracting and validating tables…'):
            st.session_state['result'] = extract_report(data)
        st.rerun()
    result = st.session_state.get('result')
    if result is not None:
        if result.successful:
            st.success(f'{result.team}: all 36 tables extracted and passed consistency checks ({result.matches} matches).')
        elif result.tables:
            st.warning(f'Partial extraction: {len(result.tables)}/36 tables available. Review failures below.')
        else:
            st.error('Extraction failed. Review the table errors below.')
        with st.expander('Extraction status', expanded=bool(result.errors)):
            st.dataframe(pd.DataFrame(result.status()), hide_index=True, width='stretch')
        with st.expander('Data conventions and limitations', expanded=bool(result.errors)):
            for warning in result.warnings:
                st.write(f'• {warning}')
        if result.tables:
            st.download_button('Download available CSVs and status report (ZIP)', result.zip_bytes(),
                               file_name='wyscout_extraction.zip', mime='application/zip')
if result is not None and result.tables:
    render_dashboard(result)
