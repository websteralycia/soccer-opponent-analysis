"""Opponent-scouting workspaces: source evidence first, analyst judgement later."""
import base64
import pandas as pd
import streamlit as st
from .data import table,numeric,success_rate,formation_usage,exact_sum,filter_table,overview
from .catalog import table_info
from .overview_ui import text
from .tactical_style import format_value,table_config,prepare_table,PAIRS
from .spatial import spatial_maps
from .standouts import table_standouts
from .tactical_models import FOCUSES,CONTROL_KEYS,SOURCES,total,filename,scoped_frame,scope_text,team_actions,focus_items,manual_seed,metric_label,formation_ppda_frame,crossing_options
from . import tactical_charts as plots
from . import player_charts
from ..workflow.evidence import seed_from_standout
from ..workflow.ui import draft_action,evidence_navigation

SHORT_UNITS={
 'final_third_recoveries':'Recoveries near the opponent’s goal; shot and goal markers refer to the analyzed team. Shirt numbers identify players.',
 'crosses':'Source crossing actions: successful/unsuccessful · high/ground delivery paths.',
 'final_third_dribbles':'Successful attacking-third dribbles; shot and goal markers refer to the analyzed team.',
 'recoveries':'Zone %: share of all team recoveries · smaller figures: recoveries per match.',
 'losses':'Zone %: share of all team possession losses · smaller figures: losses per match.',
 'fouls':'Zone %: share of all team fouls · smaller figures: fouls per match.',
 'dribbles':'Zone %: share of all attempts. Inner green/salmon %: success/failure within the zone. Blue/red: better/worse than league average.',
 'defensive_duels':'Own-third source markers: defensive-duel wins, interceptions and sliding tackles · shirt numbers identify players.',
 'lost_duels':'Own-third lost-duel markers and subsequent-shot/foul/card annotations · shirt numbers identify players.',
}


def retain_selection(key,value):
    if st.session_state.get(key) is None:st.session_state[key]=value


def selector(label,options,key):
    if st.session_state.get(key) not in options:st.session_state.pop(key,None)
    return st.segmented_control(label,options,default=options[0],key=key,
        on_change=retain_selection,args=(key,st.session_state.get(key) or options[0])) or options[0]


def focus_asset(result,fingerprint,category,spec):
    if spec.map_key is None:return None
    return next((a for a in spatial_maps(result,fingerprint,category) if a['key']==spec.map_key),None)


def card_strip(items):
    for col,(label,value,scope) in zip(st.columns(len(items),gap='small'),items):
        col.html(f'<div class="oi-kpi"><div class="oi-kpi-label">{text(label)}</div>'
                 f'<div class="oi-kpi-value oi-tactical-value">{text(value)}</div><div class="oi-kpi-note">{text(scope)}</div></div>')


def ratio_summary(result,key,attempts,successful):
    attempted=total(result,key,attempts);good=total(result,key,successful)
    rate=success_rate(pd.Series([good]),pd.Series([attempted])).iloc[0]
    return f'{format_value(good)} / {format_value(attempted)} · {format_value(rate,"percent")}'


def context_cards(result,category,label):
    if category=='Defensive organization':
        if label=='Formation PPDA':return
        if label in {'Own-third wins','Own-third losses'}:
            # These source lists are incomplete; never pool them as team totals.
            spec=FOCUSES[category][label]
            items=[]
            for item in focus_items(result,spec)[:2]:
                who=item.names[0] if len(item.names)==1 else f'{len(item.names)} players tied'
                items.append((item.label,format_value(item.value,item.unit),who+' · selected players'))
            if not items:return
        elif label=='Foul locations':
            items=[('Fouls committed',format_value(total(result,'03','Fouls')),'All reported outfield players')]
        elif label=='All-area duels':
            items=[('Defensive duels · won / attempts',ratio_summary(result,'03','Defensive Duels','Defensive Duels Won'),'All reported outfield players'),
                   ('Aerial duels · won / attempts',ratio_summary(result,'03','Aerial Duels','Aerial Duels Won'),'All reported outfield players')]
        else:return
    elif category=='Transitions':
        if label=='All-area recoveries':
            items=[('Recoveries · all areas',format_value(total(result,'02','Recoveries')),'All reported outfield players')]
        elif label=='Possession losses':
            items=[('Possession losses · all areas',format_value(total(result,'02','Losses')),'All reported outfield players')]
        elif label=='Own-third lost duels':
            # Associated shots in this shortlist are not a unique team-shot total.
            comparisons=focus_items(result,FOCUSES[category][label])
            item=next((item for item in comparisons if item.metric=='Opponent Shots After'),None)
            if item is None:return
            who=item.names[0] if len(item.names)==1 else f'{len(item.names)} players tied'
            items=[('Most opponent shots following lost duels',format_value(item.value,item.unit),who+' · selected players')]
        else:return  # Attacking-third recoveries has no complete team total.
    elif category=='Buildup and progression':
        items=[('Progressive passes · completed / attempted',ratio_summary(result,'04','Progressive Passes','Progressive Passes Accurate'),'Complete outfield passing page'),
               ('Final-third passes · completed / attempted',ratio_summary(result,'04','Passes to Final Third','Passes to Final Third Accurate'),'Complete outfield passing page')]
    else:
        if category=='Attacking patterns' and label in {'Final-third dribbles','All-pitch dribbling'}:return
        summary=table(result,'20')
        kind='After set pieces' if category=='Set pieces' else 'After crosses' if label=='Crossing' else 'Total'
        rows=summary[summary['Shot Type'].eq(kind)] if 'Shot Type' in summary else pd.DataFrame()
        row=rows.iloc[0] if len(rows) else {}
        scope='Team finishing · '+('all set-piece types' if category=='Set pieces' else 'after crosses' if kind=='After crosses' else 'full sample')
        goals=row.get('Goals');goal_scope=scope
        if kind=='Total':
            summary=overview(result)
            goals=summary['goals_for'] if summary else None
            goal_scope='Match results · full sample'
        items=[('Shots',format_value(row.get('Shots')),scope),('xG',format_value(row.get('xG'),'decimal'),scope),('Goals',format_value(goals),goal_scope)]
    card_strip(items)


def plot(fig,key):
    if fig is None:st.info('This comparison is unavailable; original fields remain accessible in Statistics & Source Data.')
    else:
        with st.container(border=True,key='tactical_chart_'+key):
            st.plotly_chart(fig,width='stretch',theme=None,key='tactical_plot_'+key,
                config={'displaylogo':False,'displayModeBar':'hover','scrollZoom':False,'responsive':True})


def image_content(asset,result):
    context=asset.get('context',{})
    st.markdown(f'**Source-specific image · {result.matches}-match aggregate · PDF p.{asset["page"]}**')
    if asset.get('header_path'):
        images=[]
        for path,label in [(asset['header_path'],asset['label']+' — original title and legend'),
                           (asset.get('display_path') or asset['path'],asset['label']+' — source pitch map')]:
            encoded=base64.b64encode(path.read_bytes()).decode()
            images.append(f'<img src="data:image/png;base64,{encoded}" alt="{text(label)}">')
        st.html('<div class="oi-source-composite">'+''.join(images)+'</div>')
    else:
        st.image(str(asset.get('display_path') or asset['path']),width='stretch')
    st.markdown(SHORT_UNITS.get(asset['key'],context.get('units','Source units unavailable.')))


@st.dialog('Source pitch map',width='large')
def enlarged_map(asset,result):
    image_content(asset,result)
    st.write(asset.get('context',{}).get('legend','Original source legend retained.'))


def map_view(asset,result,key):
    with st.container(border=True,key='tactical_map_card_'+key):
        image_content(asset,result)
        if st.button('Enlarge source map',key='tactical_enlarge_'+key):enlarged_map(asset,result)


def contributor_view(result,key,fields,widget_key,passer=None,title='Supporting player contributions'):
    frame=scoped_frame(result,key,passer)
    options=[field for field in fields if field in frame]
    if frame.empty or not options:
        st.info('Reported contributor data unavailable for this evidence.');return
    field=options[0]
    if len(options)>1:
        if st.session_state.get(widget_key) not in options:st.session_state.pop(widget_key,None)
        field=st.selectbox('Comparison metric',options,format_func=lambda field:metric_label(key,field),key=widget_key,
            help='All-area defensive duels lost = reported attempts minus reported wins. Missing or inconsistent inputs are unavailable.' if key=='03' else None)
    if key=='03' and field=='Defensive Duels Won %':
        frame[field]=success_rate(frame['Defensive Duels Won'],frame['Defensive Duels'])
        frame=frame[numeric(frame['Defensive Duels']).ge(10)].copy()
        st.markdown('**Success-rate comparison · ≥10 raw attempts**')
    if key=='03' and field=='Defensive Duels Lost' and numeric(frame[field]).isna().any():
        st.info('Some losses are unavailable because reported attempts or wins are missing or inconsistent.')
    known=numeric(frame[field]);valid=known.notna() & known.ge(0)
    if (frame[field].notna() & ~valid).any():st.info('Unknown, bounded or invalid values are omitted from this chart; source values are preserved below.')
    frame=frame[valid].copy()
    population='Outfield players' if key in {'02','03','04'} else 'Selected links' if key=='15' else 'Selected players'
    if key=='16':population='Selected cross takers'
    elif key=='17':population='Selected cross receivers'
    if key=='15' and passer:population+=' · '+passer
    st.markdown(f'{population} · {min(8,len(frame))}/{len(frame)} shown')
    label_column='Receiver' if key=='15' else 'Player'
    if key=='19':st.markdown('**'+result.team+' shots following recoveries in the attacking third.**')
    plot(plots.contributors(frame,[field],metric_label(key,field),label_column,
        metric_labels={field:metric_label(key,field)}),widget_key)
    return frame


def primary_chart(result,label,spec,passer,key):
    source=spec.source
    if spec.kind=='team_progression':
        data=team_actions(result,'04',[('Progressive passes','Progressive Passes','Progressive Passes Accurate'),
                                      ('Passes to final third','Passes to Final Third','Passes to Final Third Accurate')])
        if data[['Attempts','Successful']].isna().any().any():st.info('Some complete-page totals are unavailable; missing actions are not zero.')
        st.markdown('**All reported outfield players · full-sample totals**')
        plot(player_charts.action_chart(data,title='Team progression · attempts and completions'),key)
    elif spec.kind=='team_duels':
        data=team_actions(result,'03',[('Defensive duels','Defensive Duels','Defensive Duels Won'),('Aerial duels','Aerial Duels','Aerial Duels Won')])
        if data[['Attempts','Successful']].isna().any().any():st.info('Some complete-page totals are unavailable; missing actions are not zero.')
        st.markdown('**All-area actions · all reported outfield players**')
        fig=player_charts.action_chart(data,title='All-area duels · separate action categories')
        if fig is not None:
            for trace in fig.data:
                if trace.name=='Successful':trace.name='Won'
                elif trace.name=='Unsuccessful':trace.name='Lost (calculated)'
        plot(fig,key)
    elif spec.kind=='formation':
        frame=formation_ppda_frame(result)
        st.markdown('**PPDA by formation · reported periods**')
        if frame.empty:st.info('Formation PPDA unavailable for this report.')
        else:st.dataframe(frame,hide_index=True,width='stretch',column_config={
            'Usage %':st.column_config.NumberColumn(format='%.1f%%'),
            'Team PPDA':st.column_config.NumberColumn(format='%.2f'),
            'Opponent PPDA':st.column_config.NumberColumn(format='%.2f')})
    elif spec.kind=='team_creation':
        st.markdown('**Passing-page fields · complete outfield totals · separate definitions**')
        plot(plots.team_creation(result),key)
    elif spec.source=='16':
        support_view(result,label,spec,passer,key)
    elif spec.kind in {'pairs','deliveries'}:
        frame=table(result,source)
        st.markdown('**'+scope_text(source,result.matches)+'**')
        plot(plots.contributors(frame,spec.fields,'Reported deliveries by side' if spec.kind=='deliveries' else 'Reported attempts and completions'),key)
    else:
        contributor_view(result,source,spec.fields,'tactical_primary_'+key,passer,title='Reported evidence')


def support_view(result,label,spec,passer,key):
    if spec.source=='16':
        options=crossing_options(result,spec)
        if not options:
            st.info('Crossing comparison data unavailable for this report.');return
        control_key='tactical_crossing_metric'
        if st.session_state.get(control_key) not in options:st.session_state.pop(control_key,None)
        source,field=st.selectbox('Comparison metric',options,format_func=lambda choice:metric_label(*choice),key=control_key)
        contributor_view(result,source,[field],'tactical_support_metric_'+key,passer)
        return
    source=spec.support_source or spec.source
    if spec.kind=='links':
        data=table(result,'14')
        row=data[data.Player.eq(passer)].iloc[0] if 'Player' in data and data.Player.eq(passer).any() else {}
        st.markdown('**Selected passer · reported buildup actions**')
        card_strip([('Attempts / completed',f'{format_value(row.get("Passes"))} / {format_value(row.get("Passes Accurate"))}',passer or 'Selected buildup passer')]);return
    if source=='15':
        frame=table(result,'15')
        choices=frame.Passer.dropna().unique().tolist() if 'Passer' in frame else []
        passer=choices[0] if choices else None
        title='Reported receiver links'+(' · '+passer if passer else '')
    else:title='Reported shot takers' if source in {'31','33'} else 'Supporting player contributions'
    contributor_view(result,source,spec.support_fields or spec.fields,'tactical_support_metric_'+key,passer,title)


def evidence_cards(result,category,label,spec,asset,passer):
    items=focus_items(result,spec,passer)
    st.markdown('#### Evidence worth investigating')
    if items:
        for index,(col,item) in enumerate(zip(st.columns(min(2,len(items)),gap='medium'),items[:2])):
            with col,st.container(border=True):
                st.html(f'<div class="oi-label">{text(item.label)}</div><div class="oi-observation-value">{text(format_value(item.value,item.unit))}</div>'
                        f'<b>{text(", ".join(item.names))}</b><div class="oi-tactical-population">{text(item.population)} · {item.eligible} eligible</div>')
                seed=dict(seed_from_standout(result,item),category=category,status='Draft',classification=None,
                          visual_key=asset['key'] if asset else '')
                draft_action(result,seed,'tactical_evidence_'+str(index),label='Add to Scouting Findings')
    draft_action(result,manual_seed(result,category,label,spec,asset,passer),'tactical_manual',label='Record an analyst observation')


def supporting_data(result,fingerprint,category,label,spec,passer):
    with st.expander('Statistics & Source Data'):
        mode=selector('Supporting view',['Tables','Source visuals','Statistical comparisons'],'tactical_data_view')
        if mode=='Tables':
            names=[name for name in result.tables if name[:2] in SOURCES[category]]
            if not names:st.info('No supporting source tables are available.');return
            if st.session_state.get('tactical_source_table') not in names:st.session_state.pop('tactical_source_table',None)
            name=st.selectbox('Source table',names,key='tactical_source_table')
            frame=result.tables[name]
            if name[:2] in PAIRS and st.checkbox('Calculated success rates',key='tactical_calculated_rates',help='Recalculate successful actions / attempts; zero or unknown attempts have no rate. Original source values remain in Data Explorer.'):
                frame=prepare_table(result,name[:2],list(frame.columns))
            query=st.text_input('Search source rows',key='tactical_source_search')
            shown=filter_table(frame,query)
            st.markdown(f'**{scope_text(name[:2],result.matches)} · {len(shown)} / {len(frame)} rows**')
            st.dataframe(shown,hide_index=True,width='stretch',column_config=table_config(shown))
            st.button('Open in Data Explorer',key='tactical_open_source',on_click=evidence_navigation,args=(name,))
        elif mode=='Source visuals':
            assets=spatial_maps(result,fingerprint,category)
            if not assets:st.info('Spatial map unavailable for this uploaded report/category.');return
            by_key={a['key']:a for a in assets}
            if st.session_state.get('tactical_original_image') not in by_key:st.session_state.pop('tactical_original_image',None)
            chosen=st.selectbox('Registered source image',list(by_key),format_func=lambda k:by_key[k]['label'],key='tactical_original_image')
            asset=by_key[chosen]
            st.image(str(asset['path']),width='stretch')
            if asset.get('support_path'):
                encoded=base64.b64encode(asset['support_path'].read_bytes()).decode()
                st.html(f'<div class="oi-source-dark"><img src="data:image/png;base64,{encoded}" alt="{text(asset["label"])}: original distribution chart"></div>')
                st.write('Original source-specific distribution chart: '+asset['support_original'])
        else:
            items=[]
            for key in SOURCES[category]:items.extend(table_standouts(result,key,'creation' if key=='04' and label=='Shot creation' else None))
            items+=focus_items(result,spec,passer)
            unique={ (i.source,i.label,i.names):i for i in items }
            items=list(unique.values())
            if not items:st.info('No supported statistical comparison is available.');return
            if st.session_state.get('tactical_more_comparisons') not in range(len(items)):st.session_state.pop('tactical_more_comparisons',None)
            index=st.selectbox('Comparison to review',range(len(items)),format_func=lambda i:items[i].label+' · source '+items[i].source,key='tactical_more_comparisons')
            item=items[index];st.write(', '.join(item.names)+' · '+format_value(item.value,item.unit))
            st.write(item.population+f' · {item.eligible} eligible')
            seed=dict(seed_from_standout(result,item),category=category,status='Draft',classification=None)
            draft_action(result,seed,'tactical_more',label='Add to Scouting Findings')


def methodology(result,fingerprint=None):
    category=st.session_state.get('tactical_category') or 'Defensive organization'
    if category not in FOCUSES:return
    st.markdown('**Tactical evidence: scope and interpretation**')
    for note in [
        'Statistical patterns are evidence for investigation, not confirmed weaknesses, strengths or recurring tendencies. Recurrence requires match-level or video evidence; coaching recommendations are analyst-authored.',
        'All-area defensive duels (03), won own-third mixed defensive actions (11), and lost own-third duels (12) have different scopes. Their counts are not combined into a win rate.',
        'Recovery/loss maps can cover a different team population from pooled outfield totals. Player lists are incomplete where marked; missing players are not zero. Subsequent shots/xG are provider-associated team outcomes, not proof of individual causation or fault. The recovering player is not necessarily the shooter.',
        'All-area defensive duels lost are calculated per player from the report’s attempts minus wins (player-duels page). Missing, negative or inconsistent inputs remain unavailable. Own-third losses remain a separate selected-player source; no losses elsewhere on the pitch are inferred.',
        'Formation PPDA covers reported periods only. It does not establish block height, and missing formation coverage is not interpolated.',
        'Buildup receiver shares use the passer’s all accurate buildup passes, not the sum of displayed links. No complete passing network or spatial routes are inferred. Loss-location context is not buildup-specific.',
        'The all-pitch dribbling map covers all team attempts. The separate page-14 map covers successful final-third dribbles, with selected-player outcomes in table 18. These lists are not summed as complete team totals. Passing-page Key Passes and Shot Assists remain distinct from finishing-page fields.',
        'Team after-set-pieces summaries cover all reported set-piece types and are separate from selected corner/free-kick taker lists. Shot categories can overlap. Bounded xG values remain bounds, never exact zero.',
        'Charts show up to eight known contributors for readability. Complete source rows, all existing comparisons and original source visuals remain accessible in supporting data. Success-rate comparisons require at least ten raw attempts; ties are retained. No automatic classification or confirmation occurs.',
    ]:st.write('• '+note)
    if category=='Defensive organization':
        usage=formation_usage(result)
        coverage=exact_sum(usage['Usage %']) if not usage.empty else None
        st.write('Reported formation coverage: '+format_value(coverage,'percent')+'. Coverage may differ by metric; missing periods are not interpolated.')
    for key in SOURCES[category]:
        info=table_info(key,result.matches)
        st.write(f'{filename(result,key)} · PDF page(s) {info.page} · {info.scope} · {info.coverage}')
        if info.note:st.write(info.note)
    for asset in spatial_maps(result,fingerprint,category):
        context=asset.get('context',{})
        st.write(f'**{asset["label"]} · original PDF p.{asset["page"]}**')
        for field in ['measurement','units','legend','orientation','limit']:
            if context.get(field):st.write(context[field])
    glossary=table(result,'34')
    if not glossary.empty:st.dataframe(glossary,hide_index=True,width='stretch',height=220)


def tactical_view(result,fingerprint=None):
    st.subheader('Tactical analysis')
    summary=overview(result)
    period=f'{summary["start"].strftime("%d %b %Y")} – {summary["end"].strftime("%d %b %Y")}' if summary and pd.notna(summary['start']) and pd.notna(summary['end']) else 'Dates unavailable'
    st.markdown(f'**{text(result.team)} · {period} · {result.matches}-match report aggregate**')
    category=selector('Tactical category',list(FOCUSES),'tactical_category')
    label=selector('Evidence focus',list(FOCUSES[category]),CONTROL_KEYS[category])
    spec=FOCUSES[category][label];key=category+'_'+label
    asset=focus_asset(result,fingerprint,category,spec)
    passer=None
    if spec.kind=='links':
        links=table(result,'15');options=links.Passer.dropna().unique().tolist() if 'Passer' in links else []
        if options:
            if st.session_state.get('tactical_receiver_passer') not in options:st.session_state.pop('tactical_receiver_passer',None)
            passer=st.selectbox('Buildup passer',options,key='tactical_receiver_passer')
    context_cards(result,category,label)
    if asset:
        primary,support=st.columns([.64,.36],gap='large')
        with primary:map_view(asset,result,key)
        with support:
            support_view(result,label,spec,passer,key)
    elif spec.map_key:
        st.info('Spatial map unavailable for this uploaded report. Recorded statistics are shown below; no unrelated report image is used.')
        primary_chart(result,label,spec,passer,key)
    elif spec.kind=='formation':
        primary_chart(result,label,spec,passer,key)
    else:
        primary,support=st.columns([.64,.36],gap='large')
        with primary:primary_chart(result,label,spec,passer,key)
        with support:support_view(result,label,spec,passer,key)
    evidence_cards(result,category,label,spec,asset,passer)
    supporting_data(result,fingerprint,category,label,spec,passer)
