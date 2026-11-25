"""Compact tactical comparisons with explicit, independent metric units."""
from html import escape
import pandas as pd
from . import charts
from .data import numeric
from .player_charts import finish,padded_bounds
from .tactical_style import format_value
from .tactical_models import unit
from ..presentation import ACCENT,MUTED


def contributors(frame,fields,title='Reported contributors',label_column='Player',metric_labels=None):
    if charts.go is None or frame.empty or label_column not in frame:return None
    fields=[c for c in fields if c in frame]
    if not fields:return None
    data=frame.copy()
    data['_sort']=numeric(data[fields[0]])
    data=data.sort_values('_sort',ascending=False,kind='stable').head(8)
    fig=charts.go.Figure()
    for index,column in enumerate(fields):
        numbers=numeric(data[column])
        details=[]
        for _,row in data.iterrows():
            parts=[]
            if {'Crosses','Crosses Successful'}.issubset(data):
                parts.append('Cross attempts: '+format_value(row.get('Crosses')))
                parts.append('Successful crosses: '+format_value(row.get('Crosses Successful')))
                parts.append('Reported success: '+format_value(row.get('Crosses Successful %'),'percent'))
            if 'Goals After' in data:parts.append('Team goals following action: '+escape(str(row.get('Goals After','—'))))
            if 'xG' in data:parts.append('Source xG: '+escape(str(row.get('xG','—'))))
            if 'Pct of All Accurate Passes' in data:parts.append('Receiver share: '+escape(str(row.get('Pct of All Accurate Passes','—')))+'%')
            details.append('<br>'.join(parts))
        fig.add_bar(name=(metric_labels or {}).get(column,column),x=numbers.astype(object).where(numbers.notna(),None).tolist(),
            y=[escape(str(v)) for v in data[label_column]],orientation='h',marker_color=[ACCENT,'#718399'][index%2],
            text=[format_value(v,unit(column)) for v in numbers],textposition='outside',cliponaxis=False,
            customdata=details,hovertemplate='%{y}<br>%{x}<br>%{customdata}<extra>%{fullData.name}</extra>')
    kind=unit(fields[0]);axis='Percentage (%)' if kind=='percent' else 'Actions /90' if kind=='rate' else 'Reported xG / xA' if kind=='decimal' else 'Reported action count'
    fig=finish(fig,title,axis,height=max(235,115+len(data)*28))
    fig.update_layout(barmode='group',bargap=.35,showlegend=len(fields)>1)
    if len(fields)==1:fig.update_layout(margin=dict(t=38))
    fig.update_traces(constraintext='none',textfont=dict(size=12))
    known=numeric(data[fields].stack()).dropna()
    maximum=float(known.max()) if len(known) else 0
    fig.update_xaxes(range=[0,max(1,maximum*1.22)])
    return fig


def formation_ppda(frame,team):
    if charts.go is None or frame.empty or not {'Formation',team,'Opponent'}.issubset(frame):return None
    fig=charts.go.Figure()
    for name,column,color in [(team,team,ACCENT),('Opponents','Opponent',MUTED)]:
        vals=numeric(frame[column]);raw=frame['Usage %'].astype(str).tolist()
        fig.add_trace(charts.go.Scatter(name=name,x=vals.astype(object).where(vals.notna(),None).tolist(),
            y=frame.Formation.astype(str).tolist(),mode='markers+text',text=[format_value(v,'decimal') for v in vals],
            textposition='top center',cliponaxis=False,marker=dict(size=11,color=color),customdata=raw,
            hovertemplate='%{y}<br>PPDA: %{x:.2f}<br>Reported usage: %{customdata}%<extra>%{fullData.name}</extra>'))
    fig=finish(fig,'PPDA by reported formation','PPDA · formation periods',height=245)
    fig.update_xaxes(range=padded_bounds(list(frame[team])+list(frame.Opponent)))
    fig.update_yaxes(range=[len(frame)-.5,-.5],autorange=False)
    return fig


def team_creation(result):
    from .tactical_models import total
    from .player_charts import count_chart
    columns=['Shot Assists','Deep Completions','Key Passes']
    return count_chart(['Shot assists','Deep completions','Key passes · passing page'],
                       [total(result,'04',c) for c in columns],False,'Passing-page creation · outfield totals')
