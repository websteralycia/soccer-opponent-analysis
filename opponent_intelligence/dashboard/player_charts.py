"""Interactive player charts. Every axis uses explicit units and source scope."""
from html import escape
import pandas as pd
from . import charts
from .charts import values
from .data import numeric
from .tactical_style import format_value
from ..presentation import ACCENT, TEXT, MUTED, BORDER, SURFACE

PALETTE = [ACCENT, '#96a9c8', '#d5b67a', '#a99bc4', '#7da4b4', '#bc9997']


def padded_bounds(series):
    """Display padding only: never alter the plotted measurements."""
    known=numeric(pd.Series(series)).dropna()
    peak=max(0,float(known.max())) if len(known) else 0
    span=max(peak,.05)
    return [-.07*span,peak+.14*span]


def finish(fig, title, xlabel, height=225):
    fig.update_layout(title=dict(text=title,x=0,y=.99,xanchor='left',yanchor='top',font=dict(size=15)),height=height,
        paper_bgcolor=SURFACE,plot_bgcolor='rgba(0,0,0,0)',font=dict(color=TEXT,family='Arial',size=13),
        margin=dict(l=12,r=42,t=64,b=42),barmode='stack',bargap=.55,barcornerradius=6,
        legend=dict(orientation='h',y=1.02,x=0,yanchor='bottom',font=dict(size=12),traceorder='normal'),
        hovermode='closest',hoverlabel=dict(bgcolor='#253145',bordercolor=BORDER,font=dict(color=TEXT,size=13)))
    fig.update_xaxes(title=dict(text=xlabel,font=dict(size=12)),gridcolor='rgba(148,163,184,.10)',
                     nticks=5,showline=False,zeroline=False,automargin=True)
    fig.update_yaxes(showgrid=False,showline=False,zeroline=False,automargin=True,autorange='reversed',ticklabelstandoff=14)
    return fig


def action_chart(data, normalize=False, title='Attempts and outcomes', shot=False):
    if charts.go is None or data.empty: return None
    go=charts.go; fig=go.Figure()
    raw = [[format_value(r.Successful), format_value(r.Attempts), format_value(r.Rate,'percent')] for r in data.itertuples()]
    labels = [f'{a}/{b} · {rate}' for a,b,rate in raw]
    y=[escape(str(v)) for v in data.Metric]
    for name, field, color in [('On target' if shot else 'Successful','Good',ACCENT),
                               ('Other shots' if shot else 'Unsuccessful','Other','#52657e')]:
        fig.add_bar(name=name,x=values(data[field]),y=y,orientation='h',marker_color=color,
            customdata=raw, text=labels if field=='Other' else None, textposition='outside', cliponaxis=False,
            hovertemplate='%{y}<br>Raw successes/on target: %{customdata[0]} / %{customdata[1]}<br>Raw rate: %{customdata[2]}<br>Displayed count: %{x:.1f}<extra>%{fullData.name}</extra>')
    unknown=data.Good.isna()
    if unknown.any():
        fig.add_bar(name='Attempts · outcome unavailable', x=values(data.Total.where(unknown)),y=y,
                    orientation='h',marker=dict(color=MUTED,pattern_shape='/'))
    fig.update_layout(margin=dict(r=120))
    fig=finish(fig,title,'Shots /90' if shot and normalize else 'Shots · sample total' if shot else 'Actions /90' if normalize else 'Actions · sample total',height=160+max(0,len(data)-1)*38)
    fig.update_layout(margin=dict(r=112))
    maximum=numeric(data.Total).max()
    fig.update_xaxes(range=[0,max(1,float(maximum)*1.06)] if pd.notna(maximum) else [0,1])
    fig.update_traces(width=.3,constraintext='none',textfont=dict(size=12),selector=dict(type='bar'))
    return fig


def output_chart(row, assists, normalize):
    if charts.go is None:return None
    go=charts.go;fig=go.Figure()
    suffix=' /90' if normalize else ''
    actual=[row.get('Goals'+suffix),assists]
    expected=[row.get('xG'+suffix),row.get('xA'+suffix)]
    for name,x,color,symbol in [('Actual',actual,ACCENT,'circle'),('Expected',expected,'#c4af84','diamond-open')]:
        fig.add_trace(go.Scatter(name=name,x=values(pd.Series(x)),y=['Goals / xG','Assists / xA'],
              mode='markers+text',text=[format_value(v,'rate' if normalize else 'decimal' if name=='Expected' else 'count') for v in x],
              textposition='bottom center' if name=='Actual' else 'top center',marker=dict(size=9 if name=='Actual' else 11,color=color,symbol=symbol),
              hovertemplate='%{y}<br>%{x:.2f}<extra>%{fullData.name}</extra>'))
    fig=finish(fig,'Actual vs expected output','Output /90' if normalize else 'Output · sample total',height=220)
    fig.update_xaxes(range=padded_bounds(actual+expected))
    fig.update_traces(cliponaxis=False)
    fig.update_yaxes(range=[1.6,-.6],autorange=False)
    if not numeric(pd.Series(actual+expected)).gt(0).any():fig.update_xaxes(tickvals=[0])
    return fig


def count_chart(labels, counts, normalize, title):
    if charts.go is None:return None
    fig=charts.go.Figure(charts.go.Bar(x=values(pd.Series(counts)),y=labels,orientation='h',marker_color=ACCENT,
        text=[format_value(v,'rate' if normalize else 'count') for v in counts],textposition='outside',cliponaxis=False,
        hovertemplate='%{y}<br>%{x:.1f}<extra></extra>'))
    fig=finish(fig,title,'Actions /90' if normalize else 'Actions · sample total',height=205)
    maximum=numeric(pd.Series(counts)).max()
    fig.update_xaxes(range=[0,max(1,float(maximum)*1.2)] if pd.notna(maximum) else [0,1])
    fig.update_traces(width=.3,constraintext='none',textfont=dict(size=12))
    return fig


def comparison_chart(frame, names, metric, normalize, percent=False):
    if charts.go is None:return None
    go=charts.go; fig=go.Figure(); data=frame.set_index('Player').loc[names]
    y=[escape(n) for n in names]; suffix=' /90' if normalize else ''
    fields=[('Success %',metric.label+' success %',ACCENT)] if percent else [('Attempts' if metric.successful else metric.label,metric.label+suffix,'#52657e')]
    if metric.successful and not percent:fields.append(('Successful',metric.label+' successful'+suffix,ACCENT))
    for name,column,color in fields:
        shown=numeric(data[column])
        if metric.successful and name=='Successful':
            good=numeric(data[metric.label+' successful']);attempts=numeric(data[metric.label])
            shown=shown.where(good.ge(0) & good.le(attempts))
        if not percent:shown=shown.where(shown.ge(0))
        raw=[]
        for player,row in data.iterrows():
            raw.append([format_value(row.Minutes),format_value(row.get(metric.label)),format_value(row.get(metric.label+' successful')),format_value(row.get(metric.label+' success %'),'percent')])
        fig.add_bar(name=name,x=values(shown),y=y,orientation='h',marker_color=color,
                    text=[format_value(v,'percent' if percent else 'rate' if normalize else 'decimal' if metric.attempts in {'xG','xA'} else 'count') for v in shown],
                    textposition='outside',cliponaxis=False,customdata=raw,
                    hovertemplate='%{y}<br>Value: %{x}<br>Minutes: %{customdata[0]}<br>Raw actions: %{customdata[1]}<br>Raw successes: %{customdata[2]}<br>Raw success %: %{customdata[3]}<extra>%{fullData.name}</extra>')
    title=metric.label+(' · success rate' if percent else '')
    fig=finish(fig,title,'Success %' if percent else 'Actions /90' if normalize else 'Sample total',max(230,130+len(names)*42))
    fig.update_layout(barmode='group',bargap=.3,bargroupgap=.18)
    fig.update_traces(constraintext='none',textfont=dict(size=12))
    if percent:
        fig.update_xaxes(range=[0,118],tickvals=[0,25,50,75,100])
        fig.update_layout(showlegend=False,margin=dict(t=42))
    else:
        maximum=max((max([float(v) for v in trace.x if v is not None],default=0) for trace in fig.data),default=0)
        fig.update_xaxes(range=[0,max(1,maximum*1.16)])
    return fig


def contribution_chart(data, selected):
    if charts.go is None or data.empty:return None
    go=charts.go;fig=go.Figure()
    for highlight in [False,True]:
        part=data[data.Player.isin(selected).eq(highlight)]
        if part.empty:continue
        raw=[[str(r.Player),r.Minutes,r.xG,r.xA] for r in part.itertuples()]
        fig.add_trace(go.Scatter(name='Selected players' if highlight else 'Other eligible players',
            x=values(part['xG /90']),y=values(part['xA /90']),customdata=raw,
            mode='markers',
            marker=dict(color=ACCENT if highlight else '#718399',size=11 if highlight else 7,
                        symbol='diamond' if highlight else 'circle',line=dict(width=1,color=TEXT)),
            hovertemplate='%{customdata[0]}<br>xG/90: %{x:.2f}<br>xA/90: %{y:.2f}<br>Minutes: %{customdata[1]}<br>Raw xG: %{customdata[2]}<br>Raw xA: %{customdata[3]}<extra></extra>'))
    fig=finish(fig,'Attacking contribution','xG /90',310)
    fig.update_xaxes(range=padded_bounds(data['xG /90']))
    fig.update_yaxes(title='xA /90',autorange=False,range=padded_bounds(data['xA /90']),
                     showgrid=True,gridcolor='rgba(148,163,184,.10)')
    if not data['xG /90'].gt(0).any():fig.update_xaxes(tickvals=[0])
    if not data['xA /90'].gt(0).any():fig.update_yaxes(tickvals=[0])
    return fig


def ranking_chart(data, selected, unit):
    if charts.go is None or data.empty:return None
    go=charts.go;fig=go.Figure()
    label_column='Player label' if 'Player label' in data else 'Player'
    styles=[('Selected + leader',data.Leader & data.Player.isin(selected),ACCENT,'/'),
            ('Leader',data.Leader & ~data.Player.isin(selected),ACCENT,''),
            ('Selected',~data.Leader & data.Player.isin(selected),'#96a9c8','/'),
            ('Other eligible players',~data.Leader & ~data.Player.isin(selected),'#52657e','')]
    for label,mask,color,pattern in styles:
        part=data[mask]
        if part.empty:continue
        fig.add_bar(name=label,x=values(part.Value),y=[escape(n) for n in part[label_column]],orientation='h',
                    text=[format_value(row.Value,unit)+(f' · {format_value(row["Raw successful"])}/{format_value(row["Raw attempts"])}' if unit=='percent' else '') for _,row in part.iterrows()],textposition='outside',cliponaxis=False,
                    customdata=[[row.Minutes,format_value(row['Raw attempts']),format_value(row['Raw successful'])] for _,row in part.iterrows()],marker=dict(color=color,pattern_shape=pattern),
                    hovertemplate='%{y}<br>Value: %{x}<br>Minutes: %{customdata[0]}<br>Raw attempts/actions: %{customdata[1]}<br>Raw successful actions: %{customdata[2]}<extra>%{fullData.name}</extra>')
    fig=finish(fig,'Reported player comparison','Success %' if unit=='percent' else 'Actions /90' if unit=='rate' else 'Sample total',max(260,115+len(data)*23))
    fig.update_layout(margin=dict(t=70))
    fig.update_traces(width=.5,constraintext='none',textfont=dict(size=12))
    if unit=='percent':fig.update_layout(margin=dict(r=135))
    fig.update_yaxes(categoryorder='array',categoryarray=[escape(n) for n in data[label_column]])
    return fig


def duel_success_chart(data, normalize=False):
    """Raw-count donut fractions, with raw denominators and optional /90 counts."""
    if charts.go is None or data.empty:return None
    go=charts.go;fig=go.Figure();n=len(data)
    for index,row in data.reset_index(drop=True).iterrows():
        center=(index+.5)/n
        domain=[index/n+.04,(index+1)/n-.04]
        valid=pd.notna(row.Rate) and pd.notna(row.Successful) and row.Attempts>0
        if valid:
            raw=[format_value(row.Successful),format_value(row.Attempts),format_value(row.Rate,'percent')]
            fig.add_trace(go.Pie(labels=['Won','Not won'],values=[row.Successful,row.Attempts-row.Successful],
                name=str(row.Metric),hole=.78,sort=False,direction='clockwise',showlegend=False,
                marker=dict(colors=[ACCENT,'#344459'],line=dict(width=0)),textinfo='none',
                domain=dict(x=domain,y=[.23,.81]),customdata=[raw,raw],
                hovertemplate='%{label}: %{value}<br>Won / attempts: %{customdata[0]} / %{customdata[1]}<br>Win rate: %{customdata[2]}<extra>%{fullData.name}</extra>'))
        fig.add_annotation(x=center,y=.96,xref='paper',yref='paper',text=escape(str(row.Metric)),showarrow=False,
                           font=dict(size=13,color=TEXT),xanchor='center',yanchor='middle')
        fig.add_annotation(x=center,y=.52,xref='paper',yref='paper',text=format_value(row.Rate,'percent'),showarrow=False,
                           font=dict(size=20,color=ACCENT),xanchor='center',yanchor='middle')
        counts=f'{format_value(row.Successful)} / {format_value(row.Attempts)} won'
        if normalize:counts+=f'<br>{format_value(row.Good,"rate")} / {format_value(row.Total,"rate")} per 90'
        fig.add_annotation(x=center,y=.07,xref='paper',yref='paper',text=counts,showarrow=False,
                           font=dict(size=12,color=TEXT),xanchor='center',yanchor='middle')
    fig=finish(fig,'Duel success','',height=245 if normalize else 220)
    fig.update_layout(margin=dict(l=5,r=5,t=30,b=8),showlegend=False)
    fig.update_xaxes(visible=False);fig.update_yaxes(visible=False)
    return fig


def recovery_dot_chart(counts, normalize=False):
    """Opponent-half recoveries share the recovery row: a subset, never additive."""
    if charts.go is None:return None
    go=charts.go;fig=go.Figure()
    total,subset,interceptions=numeric(pd.Series(counts)).tolist()
    unit='rate' if normalize else 'count'
    if pd.notna(subset) and (subset<0 or (pd.notna(total) and subset>total)):subset=float('nan')
    for value,y in [(total,0),(interceptions,1)]:
        if pd.notna(value) and value>=0:
            fig.add_trace(go.Scatter(x=[0,value],y=[y,y],mode='lines',line=dict(color='#46596f',width=2),showlegend=False,hoverinfo='skip'))
    fig.add_trace(go.Scatter(name='Total',x=values(pd.Series([total,interceptions])),y=[0,1],mode='markers+text',
        text=[format_value(v,unit) for v in [total,interceptions]],textposition='bottom right',
        marker=dict(size=10,color=ACCENT),cliponaxis=False,
        customdata=[['Recoveries · all areas'],['Interceptions · all areas']],
        hovertemplate='%{customdata[0]}<br>%{x:.1f}<extra></extra>'))
    fig.add_trace(go.Scatter(name='Opponent-half recovery subset',x=values(pd.Series([subset])),y=[0],mode='markers+text',
        text=[format_value(subset,unit)],textposition='top center',cliponaxis=False,
        marker=dict(size=13,symbol='diamond-open',color='#c4af84',line=dict(width=2)),
        hovertemplate='Opponent-half recoveries · subset of total recoveries<br>%{x:.1f}<extra></extra>'))
    fig=finish(fig,'Recoveries and interceptions','Actions /90' if normalize else 'Actions · sample total',height=230)
    fig.update_xaxes(range=padded_bounds([total,subset,interceptions]))
    fig.update_yaxes(tickvals=[0,1],ticktext=['Recoveries','Interceptions'],range=[1.45,-.55],autorange=False)
    if not numeric(pd.Series([total,subset,interceptions])).gt(0).any():fig.update_xaxes(tickvals=[0])
    return fig
