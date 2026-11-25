"""Visual-first player workspaces. No other page's presentation is changed."""
import pandas as pd
import streamlit as st
from .data import available_metrics, player_frame, table, numeric
from .overview_ui import text
from .tactical_style import format_value
from .page_analysis import comparison_frame, player_column_config
from .player_models import FOCUS, reported_position, reported_roles, extra_value, action_rows, scatter_population, observation_data
from . import player_charts as plots
from ..identities import identity_html


def keep_selection(key, default):
    if st.session_state.get(key) is None:
        st.session_state[key]=default


def chart(fig, key):
    if fig is None:
        st.info('Chart unavailable. Supporting statistics remain available below.')
    else:
        with st.container(border=True,key='player_chart_'+key):
            st.plotly_chart(fig,width='stretch',theme=None,key=key,
                config={'displaylogo':False,'displayModeBar':'hover','scrollZoom':False,'responsive':True})


def choose(label, options, key, default=None):
    if st.session_state.get(key) not in options: st.session_state.pop(key,None)
    return st.selectbox(label, options, index=options.index(default) if default in options else 0, key=key)


def choose_many(label, options, key, default=()):
    if key in st.session_state:
        st.session_state[key]=[name for name in st.session_state[key] if name in options]
        return st.multiselect(label, options, key=key)
    return st.multiselect(label, options, default=[v for v in default if v in options],key=key)


def identity(result, row, prominent=False):
    position=reported_position(result,row.Player,row.No)
    st.html(f'<div class="oi-profile oi-player-identity">{identity_html(result.team,row.Player,56 if prominent else 48)}'
            f'<div><strong>{text(row.Player)}</strong><div class="oi-player-meta">'
            f'<span>Reported position: {text(position)}</span><span>{text(format_value(row.Minutes))} minutes</span></div></div></div>')


def cards(items):
    for column,(label,value,unit) in zip(st.columns(len(items),gap='small'),items):
        column.html(f'<div class="oi-kpi"><div class="oi-kpi-label">{text(label)}</div>'
                    f'<div class="oi-kpi-value">{text(format_value(value,unit))}</div></div>')


def output_indicator(row,assists,normalize):
    suffix=' /90' if normalize else ''
    actual_unit='rate' if normalize else 'count'
    st.html('<div class="oi-shot-summary"><strong>Attacking output'+(' /90' if normalize else '')+'</strong>'
            f'<div class="oi-output-line"><span>Goals</span><b>{text(format_value(row.get("Goals"+suffix),actual_unit))}</b>'
            f'<span>xG</span><b>{text(format_value(row.get("xG"+suffix),"decimal"))}</b></div>'
            f'<div class="oi-output-line"><span>Assists</span><b>{text(format_value(assists,actual_unit))}</b>'
            f'<span>xA</span><b>{text(format_value(row.get("xA"+suffix),"decimal"))}</b></div></div>')


def shot_indicator(data):
    if data.empty:return
    row=data.iloc[0]
    known=pd.notna(row.Rate)
    bar=(f'<div class="oi-track"><span style="width:{min(100,max(0,row.Rate))}%"></span></div>' if known else '')
    st.html('<div class="oi-shot-summary"><strong>Shot outcomes</strong>'
            f'<div class="oi-shot-value">{text(format_value(row.Successful))} / {text(format_value(row.Attempts))} on target</div>'
            +bar+f'<div class="oi-shot-rate">Accuracy {text(format_value(row.Rate,"percent"))}</div></div>')


def attacking_summary(row, assists, action_data, normalize):
    suffix=' /90' if normalize else ''
    count_unit='rate' if normalize else 'count'
    def metric(label,value,unit,definition=''):
        return (f'<div class="oi-attack-metric" title="{text(definition)}"><span>{text(label)}</span>'
                f'<strong>{text(format_value(value,unit))}</strong></div>')
    shot=action_data.iloc[0] if not action_data.empty else None
    attempted=shot.Total if shot is not None else None
    on_target=shot.Good if shot is not None else None
    rate=shot.Rate if shot is not None else None
    shooting,finishing,creation=st.columns([1,1,1.35],gap='medium')
    with shooting:
        bar=(f'<div class="oi-track"><span style="width:{rate}%"></span></div>' if rate is not None and pd.notna(rate) else '')
        raw=(f'<div class="oi-attack-foot">Sample: {text(format_value(shot.Successful))} / {text(format_value(shot.Attempts))} on target</div>' if normalize and shot is not None else '')
        st.html('<div class="oi-attack-card"><b>Shooting</b><div class="oi-attack-values">'
            +metric('Shots'+suffix,attempted,count_unit)+metric('On target'+suffix,on_target,count_unit)+'</div>'
            +bar+f'<div class="oi-attack-foot">On-target rate <b>{text(format_value(rate,"percent"))}</b></div>'+raw+'</div>')
    with finishing:
        st.html('<div class="oi-attack-card"><b>Goals and xG</b><div class="oi-attack-values">'
            +metric('Goals · actual'+suffix,row.get('Goals'+suffix),count_unit)
            +metric('xG · expected'+suffix,row.get('xG'+suffix),'decimal','Reported expected goals; not a goal count.')+'</div></div>')
    with creation:
        st.html('<div class="oi-attack-card"><b>Chance creation</b><div class="oi-attack-values">'
            +metric('Shot assists'+suffix,row.get('Shot assists'+suffix),count_unit,'Passing-page Shot Assists: passes leading to shots. Separate from passing-page Key Passes and actual goal assists.')
            +metric('Assists · actual'+suffix,assists,count_unit,'Reported goal assists from the general player table; not interchangeable with shot assists.')
            +metric('xA · expected'+suffix,row.get('xA'+suffix),'decimal','Reported expected assists; not actual assists.')+'</div></div>')


def missing_actions(data):
    if data.empty:
        st.info('These action fields are unavailable in this report.')
    elif data[['Attempts','Successful']].isna().any().any():
        st.info('Some action counts or outcomes are missing/invalid. Unknown outcomes are not shown as failures.')


def statistics(result, frame, metrics, names, normalize):
    with st.expander('Statistics & source data'):
        st.markdown('**All eligible outfield players · sortable statistics**')
        if 'Reported position' in frame:
            st.caption('Position labels/groups: report squad table (01); Attackers are labelled Forwards. '
                       'Unreported or conflicting fields remain unknown. The filter selects players, while their '
                       'statistics cover the full report sample, including any roles played—not actions isolated '
                       'to a position or match. Findings retain the selected comparison group.')
        st.dataframe(frame.sort_values('Minutes',ascending=False),hide_index=True,width='stretch',
                     column_config=player_column_config(frame))
        files=[name for name in result.tables if name.startswith(('02_','03_','04_'))]
        if files:
            name=st.selectbox('Player source table',files,key='player_source')
            data=result.tables[name]
            selected=data[data.Player.isin(names)] if 'Player' in data else data
            st.markdown('**Selected players · original source fields**')
            st.dataframe(selected,hide_index=True,width='stretch')
        st.dataframe(pd.DataFrame([dict(Metric=m.label,Source=next((n for n in result.tables if n.startswith(m.key+'_')),m.key),
                     Columns=m.attempts+(f' / {m.successful}' if m.successful else ''),Definition=m.definition) for m in metrics]),
                     hide_index=True,width='stretch')


def profile(result,frame,metrics,normalize):
    names=frame.Player.tolist()
    with st.container(border=True,key='player_profile_header'):
        select_column,identity_column=st.columns([.28,.72],gap='small',vertical_alignment='center')
        with select_column:name=choose('Player',names,'player_profile')
        row=frame[frame.Player.eq(name)].iloc[0]
        with identity_column:identity(result,row,True)
    focus_column,kpi_column=st.columns([.4,.6],gap='medium',vertical_alignment='center')
    with focus_column:
        focus=st.segmented_control('Analysis focus',list(FOCUS),default='Progression',key='player_focus',on_change=keep_selection,args=('player_focus',st.session_state.get('player_focus') or 'Progression')) or 'Progression'
    lookup={m.label:m for m in metrics};suffix=' /90' if normalize else ''
    relevant=[lookup[label] for label in FOCUS[focus] if label in lookup]
    count_unit='rate' if normalize else 'count'
    if focus=='Progression':
        paired=[m for m in relevant if m.successful]
        data=action_rows(row,paired,normalize);missing_actions(data)
        chart(plots.action_chart(data,normalize,'Progression · attempts and completions'),'player_profile_progression')
    elif focus=='Attacking':
        shot=lookup.get('Shots')
        data=action_rows(row,[shot] if shot else [],normalize)
        assists=extra_value(result,row,'Assists',normalize)
        fields=[row.get(k+suffix) for k in ['Goals','xG','xA','Shot assists']]+[assists]
        if any(v is None or pd.isna(v) for v in fields):st.info('Some attacking fields are unavailable (—).')
        missing_actions(data)
        attacking_summary(row,assists,data,normalize)
        with st.expander('Detailed attacking charts'):
            main,support=st.columns([.58,.42],gap='medium')
            with main:chart(plots.output_chart(row,assists,normalize),'player_profile_output')
            with support:chart(plots.action_chart(data,normalize,'Shot outcomes',shot=True),'player_profile_shots')
    else:
        main,support=st.columns([.5,.5],gap='medium')
        with main:
            data=action_rows(row,[m for m in relevant if m.successful],normalize);missing_actions(data)
            chart(plots.duel_success_chart(data,normalize),'player_profile_duels')
        with support:
            counts=[row.get('Recoveries'+suffix),extra_value(result,row,'Recoveries Opponent Half',normalize),row.get('Interceptions'+suffix)]
            if any(v is None or pd.isna(v) for v in counts):st.info('Some recovery/interception fields are unavailable.')
            if counts[0] is not None and counts[1] is not None and pd.notna(counts[0]) and pd.notna(counts[1]) and counts[1]>counts[0]:
                st.info('The reported opponent-half subset exceeds total recoveries; its marker is omitted.')
            chart(plots.recovery_dot_chart(counts,normalize),'player_profile_recoveries')
    statistics(result,frame,metrics,[name],normalize)


def comparisons(result,frame,metrics,normalize):
    names=frame.Player.tolist()
    selected=choose_many('Compare players',names,'player_comparison_players',names[:2])
    if not selected:
        st.info('Select players to compare.');statistics(result,frame,metrics,[],normalize);return
    for offset in range(0,len(selected),3):
        block=selected[offset:offset+3]
        for col,name in zip(st.columns(len(block)),block):
            with col:identity(result,frame[frame.Player.eq(name)].iloc[0])
    lookup={m.label:m for m in metrics}
    defaults=[v for v in ['Progressive passes','Defensive duels','Dribbles','Shot assists'] if v in lookup]
    labels=[label for label in st.session_state.get('player_families',defaults or list(lookup)[:3]) if label in lookup]
    chosen=[lookup[label] for label in labels]
    mode_column,metric_column=st.columns([.55,.45],gap='medium')
    with mode_column:
        mode=st.segmented_control('Comparison chart',['Action comparison','Attacking contribution'],default='Action comparison',key='player_comparison_chart',on_change=keep_selection,args=('player_comparison_chart',st.session_state.get('player_comparison_chart') or 'Action comparison')) or 'Action comparison'
    if mode=='Attacking contribution':
        population=scatter_population(frame)
        st.markdown(f'**{len(population)} eligible outfield players · xG/90 versus xA/90**')
        if len(population)<len(frame):st.info(f'{len(frame)-len(population)} players omitted: positive minutes and known non-negative xG/xA are required.')
        chart(plots.contribution_chart(population,selected),'player_contribution')
    elif chosen:
        with metric_column:label=choose('Comparison metric',labels,'player_comparison_metric')
        metric=lookup[label]
        selected_frame=frame[frame.Player.isin(selected)]
        required=[metric.label]+([metric.label+' successful'] if metric.successful else [])
        if selected_frame[required].isna().any().any():st.info('Some selected-player values are missing. Chart gaps remain unknown.')
        if metric.successful and ((selected_frame[metric.label+' successful']>selected_frame[metric.label]) | selected_frame[metric.label+' successful'].lt(0)).any():
            st.info('Some success counts are inconsistent with attempts; invalid success bars are omitted.')
        if metric.successful:
            left,right=st.columns([.6,.4],gap='medium')
            with left:chart(plots.comparison_chart(frame,selected,metric,normalize),'player_comparison_actions')
            with right:
                if numeric(selected_frame[metric.label]).lt(10).any():st.info('Success rates include small samples (<10 attempts); no accuracy leader is assigned here.')
                chart(plots.comparison_chart(frame,selected,metric,False,percent=True),'player_comparison_success')
        else:chart(plots.comparison_chart(frame,selected,metric,normalize),'player_comparison_actions')
    else:st.info('Choose KPI families in Customize metrics to compare actions.')
    with st.expander('Customize metrics'):
        choose_many('KPI families',list(lookup),'player_families',defaults or list(lookup)[:3])
    with st.expander('Complete comparison table'):
        if chosen:st.dataframe(comparison_frame(frame,selected,chosen,normalize),hide_index=True,width='stretch')
        else:st.info('No KPI families selected.')
    statistics(result,frame,metrics,selected,normalize)


def observations(result,frame,metrics,normalize,minimum):
    lookup={m.label:m for m in metrics}
    metric_column,measure_column=st.columns([.5,.5],gap='medium')
    with metric_column:label=choose('Statistical metric',list(lookup),'player_observation_metric')
    metric=lookup[label]
    modes=['Action volume']+(['Successful actions','Success rate'] if metric.successful else [])
    with measure_column:
        mode=st.segmented_control('Comparison measure',modes,default='Action volume',key='player_observation_measure',on_change=keep_selection,args=('player_observation_measure',st.session_state.get('player_observation_measure') or 'Action volume')) or 'Action volume' if len(modes)>1 else 'Action volume'
    frame=reported_roles(result,frame)
    available=frame['Position group'].unique().tolist()
    groups=['All positions']+[g for g in ['Forwards','Midfielders','Defenders'] if g in available]
    groups += sorted(g for g in available if g not in groups)
    group_column,highlight_column=st.columns([1,2],gap='medium')
    with group_column:group=choose('Position group',groups,'player_observation_group')
    if group!='All positions':frame=frame[frame['Position group'].eq(group)].copy()
    with highlight_column:
        selected=choose_many('Highlight players',frame.Player.tolist(),'player_observation_highlights',frame.Player.tolist()[:1])
    data,item,unit=observation_data(frame,metric,mode,normalize,minimum,group)
    population='outfield players' if group=='All positions' else group.lower()
    st.markdown(f'**{len(data)} eligible {population} · {mode.lower()}'+(' · ≥10 raw attempts**' if mode=='Success rate' else '**'))
    if len(data)<len(frame):st.info(f'{len(frame)-len(data)} players excluded from this comparison: unavailable values or unmet attempt threshold.')
    if item:
        summary_column,action_column=st.columns([.75,.25],vertical_alignment='center')
        with summary_column:
            st.html(f'<div class="oi-summary"><b>{text(", ".join(item.names))}</b> · {text(format_value(item.value,unit))}'
                    f' · {text(item.label)}</div>')
        with action_column:
            from ..workflow.evidence import seed_from_standout
            from ..workflow.ui import draft_action
            draft_action(result,seed_from_standout(result,item),'player',label='Add to Scouting Findings')
    elif not data.empty:st.info('No distinctive leader: a standout requires at least two players with differing known values and a positive maximum.')
    chart(plots.ranking_chart(data,selected,unit),'player_ranking')
    statistics(result,frame,metrics,selected,normalize)


def player_view(result):
    st.subheader('Player analysis')
    metrics=available_metrics(result)
    if table(result,'02').empty or not metrics:
        st.info('Complete player statistics are unavailable for this report.');return
    navigation,minutes_control,rate_control=st.columns([3.3,1,.65],gap='medium',vertical_alignment='bottom')
    with navigation:
        view=st.segmented_control('Player Analysis view',['Player Profile','Comparisons','Statistical Observations'],
                                  default='Player Profile',key='player_primary',label_visibility='collapsed',on_change=keep_selection,args=('player_primary',st.session_state.get('player_primary') or 'Player Profile')) or 'Player Profile'
    minimum=minutes_control.number_input('Minimum minutes',min_value=0,value=90,step=30,key='player_minimum')
    normalize=rate_control.toggle('Per 90',value=False,key='player_per90')
    frame=player_frame(result,metrics,normalize,minimum).sort_values('Minutes',ascending=False,kind='stable')
    if frame.empty:
        st.info('No players meet the minutes filter. Lower the minimum to inspect smaller samples.');return
    st.markdown(f'**{text(result.team)} · {result.matches}-match sample · {len(frame)} eligible outfield players**')
    if view=='Player Profile':profile(result,frame,metrics,normalize)
    elif view=='Comparisons':comparisons(result,frame,metrics,normalize)
    else:observations(result,frame,metrics,normalize,minimum)
