"""Streamlit presentation. Scope boundaries are local to each section."""
import pandas as pd
import streamlit as st
from . import charts
from .catalog import table_info
from .data import (table, overview, formation_usage, available_metrics, player_frame,
                   match_events, filter_table, quality_notes, exact_sum)


def chart(fig):
    if fig is not None:
        st.plotly_chart(fig, width='stretch', theme=None, config={'displaylogo':False})


def display(value):
    return '—' if value is None or pd.isna(value) else f'{value:g}'


def metadata(result, name):
    info = table_info(name[:2], result.matches)
    st.caption(f'{info.scope} · {info.coverage}')
    with st.expander('Table source and scope details'):
        st.caption(f'Source: {name} · PDF page(s) {info.page}')
        if info.note: st.caption(info.note)


def overview_view(result):
    from .overview_ui import styles, text, number
    styles()
    from ..identities import identity_html
    summary = overview(result)
    usage = formation_usage(result)
    missing_results = summary is None
    if missing_results:
        st.info('Match results are unavailable. Full-sample outcome totals cannot be calculated.')
        summary = dict(start=pd.NaT, end=pd.NaT, matches=result.matches, wins=None, draws=None, losses=None,
                       goals_for=None, goals_against=None, unknown=0)
    start = summary['start'].strftime('%d %b %Y') if pd.notna(summary['start']) else 'unknown'
    end = summary['end'].strftime('%d %b %Y') if pd.notna(summary['end']) else 'unknown'
    st.html(f'<div class="oi-header"><div class="oi-brand">{identity_html(result.team,size=52)}<div><div class="oi-label">Opponent report</div><h2>{text(result.team)}</h2>'
            f'<p>{start} – {end} · {summary["matches"]} matches</p></div></div><span class="oi-label">Full sample</span></div>')
    primary='—'
    if not usage.empty:
        eligible=usage.assign(value=pd.to_numeric(usage['Usage %'],errors='coerce')).dropna(subset=['value'])
        if not eligible.empty:
            row=eligible.sort_values('value',ascending=False).iloc[0]
            primary=f'{row.Formation} · {number(row.value)}%'
    with st.container(key='overview_kpis'):
        for col,label,value in zip(st.columns(4,gap='small'),['W–D–L','Goals scored','Goals conceded','Primary reported formation'],
                ["—" if missing_results else f"{summary['wins']}–{summary['draws']}–{summary['losses']}",display(summary['goals_for']),display(summary['goals_against']),primary]):
            col.metric(label,value)
    if summary['unknown']:
        st.warning('Some match scores are missing; W–D–L excludes those matches and goals remain unknown.')
    from .overview_workspace import matches_view, formations_view, observations_view
    selected_view = st.segmented_control('Team Overview view', ['Matches', 'Formations', 'Statistical Observations'],
                                         default='Matches', key='overview_primary') or 'Matches'
    {'Matches': matches_view, 'Formations': formations_view,
     'Statistical Observations': observations_view}[selected_view](result)


def player_view(result):
    from .player_workspace import player_view as render_players
    render_players(result)


def explorer_view(result):
    st.subheader('Data explorer')
    if not result.tables:
        st.info('No extracted tables are available.')
        return
    selected = st.selectbox('Extracted table',list(result.tables),key='explorer_table')
    metadata(result,selected)
    frame = result.tables[selected]
    query = st.text_input('Search all columns',key=f'explorer_search_{selected}',placeholder='Player, opponent, date or value')
    column = st.selectbox('Filter column',['No column filter']+list(frame.columns),key=f'explorer_column_{selected}')
    chosen = None
    if column != 'No column filter':
        choices = sorted(frame[column].dropna().astype('string').unique().tolist())
        chosen = st.multiselect('Include values',choices,key=f'explorer_values_{selected}_{column}')
        st.caption('An empty selection includes all values. Missing cells remain in the unfiltered table.')
    filtered = filter_table(frame,query,None if column=='No column filter' else column,chosen)
    st.caption(f'{len(filtered)} of {len(frame)} rows · raw source values')
    st.dataframe(filtered,hide_index=True,width='stretch')
    # Keep the original complete CSV download; filtering never alters source exports.
    st.download_button('Download selected CSV',result.csv_bytes(selected),file_name=selected,mime='text/csv',key='explorer_download')
    if len(filtered) != len(frame):
        st.download_button('Download filtered CSV',filtered.to_csv(index=False).encode('utf-8-sig'),
                           file_name='filtered_'+selected,mime='text/csv',key='explorer_filtered_download')
    from ..workflow.ui import draft_action
    from ..workflow.evidence import reference
    draft_action(result,dict(title='Review '+selected,source_refs=[reference(result,selected,column if column!='No column filter' else '',filtered.head(5).to_csv(index=False),'Snapshot of first five rows in the current filtered preview; not a team total.')]),'explorer')
    glossary=table(result,'34')
    if not glossary.empty:
        with st.expander('Report metric definitions'):
            st.dataframe(glossary,hide_index=True,width='stretch')


def render_dashboard(result):
    if charts.go is None:
        st.info('Interactive charts need Plotly. Launch with .venv/bin/python -m streamlit run app.py, or install requirements.txt in your active environment. Tables and extraction remain available.')
    from .tactical import tactical_view
    from ..workflow.ui import findings_view,coach_view
    overview_tab,player_tab,tactical_tab,explorer_tab,findings_tab,coach_tab = st.tabs(['Team Overview','Player Analysis','Tactical Analysis','Data Explorer','Scouting Findings','Coach Report'],key='workflow_navigation',on_change='rerun')
    with overview_tab:
        overview_view(result)
    with tactical_tab:
        tactical_view(result,st.session_state.get('source_id'))
    with player_tab:
        player_view(result)
    with explorer_tab:
        explorer_view(result)
    with findings_tab:
        findings_view(result)
    with coach_tab:
        coach_view(result)
    with st.expander('Data Quality & Sample Limits',expanded=bool(result.errors)):
        for note in quality_notes(result):
            st.write('• '+note)
        if st.session_state.get('workflow_navigation')=='Tactical Analysis':
            from .tactical import methodology
            methodology(result,st.session_state.get('source_id'))
