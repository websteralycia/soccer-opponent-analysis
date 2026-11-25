"""A small neutral chart library. Missing Plotly never breaks extraction."""
try:
    import plotly.graph_objects as go
except ModuleNotFoundError:
    go = None

from .data import numeric

from ..presentation import ACCENT, TEXT, BORDER, SURFACE
SECONDARY = '#94a3b8'


def finish(fig, title, ytitle=''):
    fig.update_layout(title=dict(text=title, font=dict(size=16)), height=350,
                      paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
                      font=dict(color=TEXT, family='Arial'),
                      margin=dict(l=20,r=20,t=55,b=35),
                      legend=dict(orientation='h', y=1.15), hovermode='closest',
                      yaxis_title=ytitle, barmode='group')
    fig.update_xaxes(gridcolor=BORDER, zeroline=False)
    fig.update_yaxes(gridcolor=BORDER, zeroline=False)
    return fig


def values(series):
    s = numeric(series)
    return s.astype(object).where(s.notna(), None).tolist()


def results_chart(results, team):
    if go is None:
        return None
    frame = results.sort_values('Date')
    labels = (frame.Date.astype(str) + ' · ' + frame.Opponent + ' (' + frame['Home/Away'] + ')').tolist()
    fig = go.Figure()
    for name, column, color in [(team, team, ACCENT), ('Opponent', 'Opponent Goals', SECONDARY)]:
        fig.add_bar(name=name, x=labels, y=values(frame[column]), marker_color=color,
                    hovertemplate='%{x}<br>' + name + ': %{y} goals<extra></extra>')
    return finish(fig, 'Match results', 'Goals')


def event_chart(events, team):
    if go is None or events.empty:
        return None
    fig = go.Figure()
    symbols = {'Goal':'circle', 'Yellow card':'square-open', 'Red card':'square',
               'Subbed on':'triangle-up', 'Subbed off':'triangle-down'}
    for name, frame in events.groupby('Team', sort=False):
        known = frame[frame['Minute order'].notna()]
        if known.empty:
            continue
        fig.add_trace(go.Scatter(x=known['Minute order'].tolist(),
            y=(known.Team + ' · ' + known.Event).tolist(), mode='markers', name=name,
            marker=dict(size=12, color=ACCENT if name == team else SECONDARY,
                        symbol=[symbols.get(e,'diamond') for e in known.Event]),
            customdata=known[['Minute','Player','Event']].astype(str).values.tolist(),
            hovertemplate='%{customdata[0]} · %{customdata[1]}<br>%{customdata[2]}<extra>%{fullData.name}</extra>'))
    ticks = events.dropna(subset=['Minute order']).drop_duplicates('Minute order')
    fig.update_xaxes(tickmode='array', tickvals=ticks['Minute order'].tolist(), ticktext=ticks.Minute.tolist())
    fig.update_layout(xaxis_title='Ordered event minute · hover for player and raw minute')
    return finish(fig, 'Goals, cards and substitutions')


def formation_chart(forms, metric, team):
    if go is None:
        return None
    frame = forms[forms.Metric.eq(metric)]
    fig = go.Figure()
    for name, column, color in [(team,team,ACCENT),('Opponent','Opponent',SECONDARY)]:
        fig.add_bar(name=name, x=frame.Formation.tolist(), y=values(frame[column]), marker_color=color,
                    customdata=values(frame['Usage %']),
                    hovertemplate='%{x}<br>Value: %{y}<br>Reported usage: %{customdata}%<extra>%{fullData.name}</extra>')
    return finish(fig, f'{metric} · reported formation periods', metric)


def player_chart(frame, column):
    if go is None:
        return None
    fig = go.Figure(go.Bar(x=frame.Player.tolist(), y=values(frame[column]),
                          marker_color=[ACCENT, SECONDARY][:len(frame)],
                          hovertemplate='%{x}<br>%{y:.2f}<extra></extra>'))
    return finish(fig, column, 'Percentage points' if column.endswith('%') else column)
