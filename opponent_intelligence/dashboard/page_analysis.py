"""Compact descriptive comparisons for overview/player pages."""
from dataclasses import replace
import pandas as pd
import streamlit as st
from .data import table,overview,numeric,player_frame
from .standouts import rank_values,MIN_ATTEMPTS
from .tactical_style import format_value,table_config
from .overview_ui import text
from ..workflow.evidence import reference
from ..workflow.ui import draft_action


def overview_observations(result):
    out=[];summary=overview(result);results=table(result,'05')
    if summary and not summary['unknown'] and summary['goals_against'] and len(results)>=2:
        count=int(numeric(results['Opponent Goals']).gt(0).sum())
        if count<len(results):
            observation=f"All {summary['goals_against']:g} conceded goals occurred in {count} of {len(results)} matches."
            out.append(dict(title='Conceded-goal concentration',observation=observation,
                source_refs=[reference(result,'05_match_results.csv','Opponent Goals',observation,'Sum match goals against; count matches with goals against > 0.')],category='Match context'))
    forms=table(result,'09')
    if not forms.empty and result.team in forms:
        xg=forms[forms.Metric.eq('xG')].copy()
        xg['balance']=numeric(xg[result.team])-numeric(xg.Opponent)
        valid=xg.dropna(subset=['balance'])
        if len(valid)>=2 and valid.balance.nunique()>1:
            leaders=valid[valid.balance.eq(valid.balance.max())]
            label=', '.join(leaders.Formation.astype(str))
            observation=f'{label}: highest reported formation xG balance ({valid.balance.max():+.2f}). This covers formation periods, not whole matches or a controlled tactical comparison.'
            out.append(dict(title='Formation xG comparison',observation=observation,
                source_refs=[reference(result,'09_formations.csv','Metric',observation,'Filter Metric = xG; focal-team formation xG minus Opponent; compare reported formations only.')],category='General'))
    return out


def player_observations(result,metrics,minimum=90,normalize=False):
    frame=player_frame(result,metrics,normalize,minimum)
    if frame.empty:return []
    frame['Entity']=frame.Player
    scope=f'Filtered outfield players (≥{minimum} minutes); whole-sample statistics across roles'
    items=[]
    for metric in metrics:
        column=metric.label+(' successful' if metric.successful else '')+(' /90' if normalize else '')
        item=rank_values(frame,column,'Highest '+column,metric.key,scope,'rate' if normalize else 'decimal' if metric.attempts in {'xG','xA'} else 'count')
        if item:
            item=replace(item,metric=metric.successful or metric.attempts,detail=(f'{metric.successful or metric.attempts} × 90 ÷ Minutes; eligible minutes ≥{minimum}.' if normalize else f'Maximum reported {metric.successful or metric.attempts}; eligible minutes ≥{minimum}.'))
            items.append(item)
        if metric.successful:
            rate=metric.label+' success %'
            eligible=numeric(frame[metric.label]).ge(MIN_ATTEMPTS)
            item=rank_values(frame,rate,f'Highest {metric.label} accuracy (≥{MIN_ATTEMPTS} attempts)',metric.key,scope,'percent',eligible,
                             'Unrounded successes ÷ attempts × 100. At least 10 attempts; both counts remain in supporting tables.')
            if item:items.append(replace(item,metric=metric.successful,detail=f'{metric.successful} ÷ {metric.attempts} × 100; at least 10 attempts; eligible minutes ≥{minimum}.'))
        if len(items)>=3:break
    return items[:3]


def observations_panel(result,seeds,key,display_rows=None):
    if not seeds:return
    html='<div class="oi-summary"><b>Key statistical observations</b><small class="oi-muted"> · descriptive calculations</small>'
    for seed in (display_rows if display_rows is not None else seeds):html+=f'<div class="oi-summary-line"><b>{text(seed["title"])}</b> · {text(seed["observation"])}</div>'
    st.html(html+'</div>')
    with st.expander('Record an observation as a finding'):
        selected=st.selectbox('Observation to review',range(len(seeds)),format_func=lambda index:seeds[index]['title'],key='workflow_observation_'+key)
        seed=dict(seeds[selected],supporting_evidence=seeds[selected].get('supporting_evidence',seeds[selected]['observation']),status='Draft')
        draft_action(result,seed,key)


def comparison_frame(frame,players,metrics,normalize=False):
    selected=frame.set_index('Player');rows=[]
    for metric in metrics:
        columns=[metric.label]
        if metric.successful:columns+=[metric.label+' successful',metric.label+' success %']
        if normalize:columns += [metric.label+' /90']+([metric.label+' successful /90'] if metric.successful else [])
        for column in columns:
            if column not in selected:continue
            values=[selected.loc[p,column] for p in players]
            unit='percent' if column.endswith('%') else 'rate' if column.endswith('/90') else 'decimal' if metric.attempts in {'xG','xA'} else 'count'
            attempts=numeric(pd.Series([selected.loc[p,metric.label] for p in players]))
            rate_ok=not column.endswith('%') or bool(attempts.ge(MIN_ATTEMPTS).fillna(False).all())
            known=all(pd.notna(v) for v in values)
            higher='Single player' if len(players)==1 else 'Not compared: unknown or fewer than 10 attempts' if not rate_ok else 'Unavailable' if not known else 'Equal' if len(set(values))==1 else players[values.index(max(values))]
            rows.append(dict(Metric=column,**{p:format_value(v,unit) for p,v in zip(players,values)},Comparison=higher))
    return pd.DataFrame(rows)


def player_column_config(frame):
    config=table_config(frame)
    for c in frame:
        if c.endswith('/90'):config[c]=st.column_config.NumberColumn(c,format='%.1f')
        elif c in {'xG','xA'}:config[c]=st.column_config.NumberColumn(c,format='%.2f')
    return config
