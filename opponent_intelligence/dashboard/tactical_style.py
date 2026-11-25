"""Display-only tactical formatting and scoped leader annotations."""
import pandas as pd
import streamlit as st
from ..presentation import ACCENT
from .data import table,numeric,success_rate
from .overview_ui import text
from .standouts import table_standouts,MIN_ATTEMPTS,RANKINGS

PAIRS={
 '03':[('Defensive Duels','Defensive Duels Won','Defensive Duels Won %')],
 '04':[('Progressive Passes','Progressive Passes Accurate','Progressive Passes Accurate %'),('Passes to Final Third','Passes to Final Third Accurate','Passes to Final Third Accurate %')],
 '14':[('Passes','Passes Accurate','Passes Accurate %')],
 '16':[('Crosses','Crosses Successful','Crosses Successful %')],
 '12':[('Opponent Shots After','Opponent Shots After On Target','Following shots on target %')],
 '19':[('Shots After','Shots After On Target','Following shots on target %')],
}


def format_value(value,unit='count'):
    if value is None or pd.isna(value):return '—'
    try:number=float(value)
    except (TypeError,ValueError):return str(value)
    if unit=='percent':return f'{number:.1f}%'
    if unit=='decimal':return f'{number:.2f}'
    if unit=='rate':return f'{number:.1f}'
    return f'{number:,.0f}'


def standout_panel(result,key,profile=None,extra_keys=()):
    items=table_standouts(result,key,profile)
    for other in extra_keys:items.extend(table_standouts(result,other))
    if not items:return
    # Keep the visual summary short; every retained comparison is explicit.
    items=items[:3]
    html='<div class="oi-summary"><b>Statistical standouts</b><span class="oi-muted"> · calculated comparisons</span>'
    shared=len({(item.source,item.population) for item in items})==1
    if shared:
        html+=f'<div class="oi-muted">{text(items[0].population)} · source {text(items[0].source)}</div>'
    for item in items:
        names=', '.join(item.names[:2])+(f' +{len(item.names)-2} tied' if len(item.names)>2 else '')
        label=('Tied: ' if len(item.names)>1 else '')+item.label
        counts=(' · '+item.detail.rsplit(' · ',1)[-1]) if item.metric=='_success_rate' else ''
        scope=f'{item.eligible} eligible with known values'
        if not shared:scope+=' · '+item.population+' · source '+item.source
        html+=f'<div class="oi-summary-line"><span class="oi-muted">{text(label)}</span> · <b>{text(names)} — {text(format_value(item.value,item.unit))}</b>{text(counts)} <small class="oi-muted">({text(scope)})</small></div>'
    st.html(html+'</div>')
    from ..workflow.ui import draft_action
    from ..workflow.evidence import seed_from_standout
    with st.expander('Record a standout as a finding'):
        index=st.selectbox('Standout to review',range(len(items)),format_func=lambda index:items[index].label,key='workflow_standout_'+key+'_'+str(profile))
        draft_action(result,seed_from_standout(result,items[index]),'tactical_'+key+'_'+str(profile))


def prepare_table(result,key,columns,profile=None):
    data=table(result,key)
    chosen=[c for c in columns if c in data]
    frame=data[chosen].copy()
    for attempts,successful,pct in PAIRS.get(key,[]):
        if {attempts,successful}.issubset(data) and any(c in frame for c in (attempts,successful)):
            position=min(frame.columns.get_loc(c) for c in (attempts,successful) if c in frame)
            for column in (attempts,successful,pct):
                if column in frame:frame=frame.drop(columns=column)
            frame.insert(position,attempts,data[attempts])
            frame.insert(position+1,successful,data[successful])
            frame.insert(position+2,pct,success_rate(data[successful],data[attempts]))
    items=table_standouts(result,key,profile)
    primary=next((column for _,column,_ in RANKINGS.get(profile or key,[]) if column in frame),None)
    if primary:
        frame=frame.assign(_sort=numeric(frame[primary])).sort_values('_sort',ascending=False,kind='stable').drop(columns='_sort')
    if 'Player' in frame and items:
        annotations={}
        for item in items:
            kind='Success ≥'+str(MIN_ATTEMPTS)+' attempts' if item.metric=='_success_rate' else ('Reported share' if item.unit=='percent' else 'Listed leader' if 'Selected' in item.population or 'Reported delivery' in item.population else 'Volume leader')
            for name in item.names:annotations.setdefault(name,[]).append(kind)
        frame.insert(0,'Standout',frame.Player.map(lambda p:' · '.join(dict.fromkeys(annotations.get(p,[])))))
    return frame


def table_config(frame):
    config={}
    for column in frame:
        if column in {'Standout','Player','Passer','Receiver','Foot','Shot Type'}:continue
        values=numeric(frame[column])
        if not values.notna().any():continue
        if (frame[column].notna() & values.isna()).any():
            config[column]=st.column_config.TextColumn(column,help='Source bounds such as <0.01 are preserved, not rounded to zero.')
        elif '%' in column or column=='Pct of All Accurate Passes':
            config[column]=st.column_config.NumberColumn(column,format='%.1f%%',help='Percentage points, not fractions. Success rates use raw attempts and successes.')
        elif column in {'xG','xA','Opponent xG After'}:
            config[column]=st.column_config.NumberColumn(column,format='%.2f')
        elif column=='Avg per 90':
            config[column]=st.column_config.NumberColumn(column,format='%.1f',help='Actions per 90 minutes; consider minutes alongside this rate.')
        elif column in {'Minutes','Minutes on Field','Height cm','No'}:
            config[column]=st.column_config.NumberColumn(column,format='%.0f')
        else:
            config[column]=st.column_config.ProgressColumn(column,format='%.0f',min_value=0,
                max_value=max(1,float(values.max())),color=ACCENT,help='Reported action count. Bar length is relative to the maximum in this displayed table.')
    return config


def styled_table(frame):
    def colors(data):
        style=pd.DataFrame('',index=data.index,columns=data.columns)
        if 'Standout' in data:
            for index in data.index[data.Standout.ne('')]:
                for column in ['Standout','Player']:
                    if column in style:style.loc[index,column]='background-color: #203733; color: #d9f3ed'
        return style
    return frame.style.apply(colors,axis=None)
