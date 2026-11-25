"""Compact, team-independent overview components and event presentation."""
from html import escape
from io import BytesIO
import base64
import pandas as pd
import streamlit as st
from .data import clock_value, numeric


def text(value):
    return escape('—' if value is None or pd.isna(value) else str(value))


def number(value):
    if value is None or pd.isna(value):
        return '—'
    try:
        return f'{float(value):g}'
    except (ValueError,TypeError):
        return str(value)


def event_groups(events):
    """Group substitution batches, never infer player-for-player pairings.

    Group identity includes match, team and raw minute. Equal-minute ordering
    preserves source order; it is not a claim about within-minute chronology.
    """
    groups=[]; batches={}
    for index, row in events.reset_index(drop=True).iterrows():
        kind=str(row.Event)
        player={'name':row.Player, 'number':row.get('No'), 'position':row.get('Position')}
        raw=str(row.Minute)
        base=dict(minute=raw, order=clock_value(raw), team=row.Team,
                  source_order=index, kind=kind, players=[player], incoming=[], outgoing=[])
        if kind in {'Subbed on','Subbed off'}:
            identity=(row.get('Date'),row.get('Match'),row.Team,raw)
            if identity not in batches:
                base['kind']='Substitution';base['players']=[]
                batches[identity]=base;groups.append(base)
            batches[identity]['incoming' if kind=='Subbed on' else 'outgoing'].append(player)
        else:
            groups.append(base)
    return sorted(groups,key=lambda g:(float('inf') if pd.isna(g['order']) else g['order'],g['source_order']))


def avatar(name, image_bytes=None):
    """Optional caller-supplied verified raster bytes; no network image lookup."""
    if image_bytes:
        try:
            from PIL import Image
            with Image.open(BytesIO(image_bytes)) as image:
                image.thumbnail((64,64))
                output=BytesIO();image.convert('RGB').save(output,format='JPEG')
            encoded=base64.b64encode(output.getvalue()).decode()
            return f'<img class="oi-avatar" src="data:image/jpeg;base64,{encoded}" alt="{text(name)}" />'
        except (ValueError,OSError,TypeError):
            pass
    initials=''.join(word[0] for word in str(name).split() if word and word[0].isalnum())[:2].upper() or '?'
    return f'<span class="oi-avatar" aria-hidden="true">{text(initials)}</span>'


def events_html(groups, headshots=None):
    headshots=headshots or {}
    icons={'Goal':('⚽','goal'),'Yellow card':('▰','yellow'),'Red card':('▰','red'),
           'Substitution':('⇅','sub')}
    output=['<div class="oi-events" role="list" aria-label="Match events">']
    for group in groups:
        icon,style=icons.get(group['kind'],('•','other'))
        lines=[]
        sets=[('↑','On',group['incoming']),('↓','Off',group['outgoing'])] if group['kind']=='Substitution' else [('', '',group['players'])]
        for arrow,label,players in sets:
            if not players:
                lines.append(f'<div class="oi-missing">{arrow} No {label.lower()} player recorded</div>')
            for player in players:
                supplied=headshots.get((group['team'],player['number']))
                from ..identities import identity_html
                portrait=avatar(player['name'],supplied) if supplied else identity_html(group['team'],player['name'],24)
                lines.append(f'<div class="oi-player">{portrait}<span><b class="oi-direction" aria-label="{label}">{arrow}</b> {text(player["name"])}'
                             + (f' <small>{text(player.get("position"))}</small>' if label else '') + '</span></div>')
        output.append(f'<div class="oi-event" role="listitem"><div class="oi-minute">{text(group["minute"])}</div>'
                      f'<div class="oi-event-body"><div class="oi-event-title"><span class="oi-icon {style}">{icon}</span>'
                      f'<strong>{text(group["kind"])}</strong><span class="oi-team">{text(group["team"])}</span></div>'
                      + ''.join(lines) + '</div></div>')
    return ''.join(output)+'</div>'


def styles():
    from ..presentation import styles as shared_styles
    shared_styles()


def select_fixture(date):
    st.session_state['overview_match']=date


def fixture_strip(results, team):
    results=results.sort_values('Date',ascending=False)
    dates=results.Date.tolist()
    if st.session_state.get('overview_match') not in dates:
        st.session_state['overview_match']=dates[0]
    st.markdown('<div class="oi-section">Recent fixtures</div>', unsafe_allow_html=True)
    with st.container(key='overview_fixtures'):
        # Keep at most five cards in a row, then wrap larger report samples.
        for offset in range(0,len(results),5):
            block=results.iloc[offset:offset+5]
            for column,(_,row) in zip(st.columns(len(block),gap='small'),block.iterrows()):
                gf,ga=numeric(pd.Series([row[team],row['Opponent Goals']])).tolist()
                outcome='Unknown' if pd.isna(gf) or pd.isna(ga) else 'Win' if gf>ga else 'Draw' if gf==ga else 'Loss'
                date=pd.to_datetime(row.Date,errors='coerce')
                label=f"**{row.Opponent}**  \n{date.strftime('%d %b %Y') if pd.notna(date) else row.Date} · {row['Home/Away']}  \n**{number(gf)}–{number(ga)}** · {outcome}"
                from ..identities import identity_html
                column.html(identity_html(row.Opponent, size=28))
                column.button(label,key=f'overview_fixture_{row.Date}',width='stretch',
                    type='primary' if st.session_state['overview_match']==row.Date else 'secondary',
                    on_click=select_fixture,args=(row.Date,))
    return st.session_state['overview_match']


def formation_panel(result, forms, usage):
    if forms.empty or result.team not in forms:
        st.info('Formation-specific metrics are unavailable.')
        return
    from .data import exact_sum
    usage_column, comparison_column = st.columns([.35,.65], gap='large')
    with usage_column:
        st.markdown('**Formation usage**')
        bars=[]
        for _,row in usage.iterrows():
            value=numeric(pd.Series([row['Usage %']])).iloc[0]
            width=0 if pd.isna(value) else min(100,max(0,value))
            bars.append(f'<div class="oi-usage"><span class="oi-usage-label">{text(row.Formation)}</span><div class="oi-track"><span style="width:{width}%"></span></div><b>{number(value)}%</b></div>')
        st.html(''.join(bars))
        total=exact_sum(usage['Usage %'])
        if total is not None:
            st.html(f'<div class="oi-coverage">{total:g}% with reported KPIs · {max(0,100-total):g}% without comparable metrics.</div>')
    with comparison_column:
        side=st.segmented_control('Compare statistics for',[result.team,'Opponents'],default=result.team,key='formation_side')
    column=result.team if side!='Opponents' else 'Opponent'
    matrix=forms.pivot(index='Metric',columns='Formation',values=column)
    order=[key for key in ['xG','Goals','Possession %','Pass Accuracy %','PPDA','Match Tempo','Long Pass Share %'] if key in matrix.index]
    order+=sorted(set(matrix.index)-set(order))
    html='<table class="oi-matrix"><thead><tr><th>KPI</th>'+''.join(f'<th>{text(f)}</th>' for f in matrix.columns)+'</tr></thead><tbody>'
    for metric in order:
        html+='<tr><td>'+text(metric)+'</td>'+''.join('<td>'+text(number(matrix.loc[metric,f]))+('</td>') for f in matrix.columns)+'</tr>'
    comparison_column.html(html+'</tbody></table>')

