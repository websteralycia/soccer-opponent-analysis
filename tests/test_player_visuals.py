"""Meaningful player-model, chart and navigation regressions."""
import pandas as pd
import pytest
from test_dashboard import report,loaded_app
from opponent_intelligence.dashboard.data import available_metrics,player_frame
from opponent_intelligence.dashboard.player_models import action_rows,reported_position,scatter_population,observation_data
from opponent_intelligence.dashboard import player_charts
from opponent_intelligence.workflow.store import FindingsStore,report_identifier


def frame_for(report,normalize=False,minimum=0):
    return player_frame(report,available_metrics(report),normalize,minimum)


def test_action_chart_per90_uses_raw_success_denominators(report):
    frame=frame_for(report,True)
    row=frame[frame.Player.eq('J. Hato')].iloc[0]
    metric=next(m for m in available_metrics(report) if m.label=='Progressive passes')
    data=action_rows(row,[metric],True)
    assert data.iloc[0].Total==pytest.approx(26*90/402)
    assert data.iloc[0].Good==pytest.approx(19*90/402)
    assert data.iloc[0].Other==pytest.approx(7*90/402)
    assert data.iloc[0].Rate==pytest.approx(100*19/26)
    assert data.iloc[0].Attempts==26
    fig=player_charts.action_chart(data,True)
    assert fig.data[0].customdata[0][0:2]==['19','26']
    assert 'Actions /90'==fig.layout.xaxis.title.text


def test_unknown_and_zero_outcomes_remain_distinct(report):
    metric=next(m for m in available_metrics(report) if m.label=='Defensive duels')
    row=frame_for(report).iloc[0].copy()
    row['Defensive duels']=10;row['Defensive duels successful']=None
    data=action_rows(row,[metric])
    assert data.Successful.isna().all() and data.Other.isna().all()
    assert data.Total.iloc[0]==10
    assert player_charts.action_chart(data).data[-1].name=='Attempts · outcome unavailable'
    row['Defensive duels']=0;row['Defensive duels successful']=0
    data=action_rows(row,[metric])
    assert data.Good.iloc[0]==0 and data.Other.iloc[0]==0 and pd.isna(data.Rate.iloc[0])
    row.Minutes=0
    assert action_rows(row,[metric],True).Total.isna().all()


def test_scatter_uses_complete_eligible_outfield_population(report):
    frame=frame_for(report,False,90)
    data=scatter_population(frame)
    assert len(data)==18
    row=data[data.Player.eq('K. Taylor')].iloc[0]
    assert row['xG /90']==pytest.approx(1.32*90/396)
    assert row['xA /90']==pytest.approx(row.xA*90/396)
    assert set(data.Player)==set(frame.Player)
    broken=frame.copy();broken.loc[broken.index[0],'Minutes']=0;broken.loc[broken.index[1],'xG']=float('nan')
    assert len(scatter_population(broken))==16
    fig=player_charts.contribution_chart(data,['K. Taylor'])
    assert sum(len(trace.x) for trace in fig.data)==18
    chosen=next(t for t in fig.data if t.name=='Selected players')
    assert len(chosen.x)==1
    assert chosen.customdata[0][0]=='K. Taylor'


def test_rate_ranking_uses_attempt_threshold_and_correct_evidence(report):
    metric=next(m for m in available_metrics(report) if m.label=='Defensive duels')
    data,item,unit=observation_data(frame_for(report),metric,'Success rate',False,0)
    assert item.names==('J. Šutalo',)
    assert item.value==pytest.approx(100*10/12)
    assert unit=='percent' and item.metric=='Defensive Duels Won'
    assert data['Defensive duels'].ge(10).all()
    assert 'D. Konadu' not in data.Player.tolist()
    assert 'at least 10' in item.detail
    altered=frame_for(report).iloc[:2].copy()
    altered['Defensive duels']=10;altered['Defensive duels successful']=5;altered['Defensive duels success %']=50
    _,item,_=observation_data(altered,metric,'Success rate',False,0)
    assert item is None


def test_profile_role_and_missing_roster_never_invent_positions(report):
    assert reported_position(report,'J. Hato',4)=='LB'
    assert reported_position(report,'Unknown',4)=='—'
    report.tables.pop('01_squad.csv')
    assert reported_position(report,'J. Hato',4)=='—'


def test_all_profile_focuses_and_supporting_tables(report):
    before={k:v.copy(deep=True) for k,v in report.tables.items()}
    app=loaded_app(report)
    assert app.segmented_control(key='player_primary').value=='Player Profile'
    for focus,count in [('Progression',1),('Attacking',2),('Defending',2)]:
        app.segmented_control(key='player_focus').set_value(focus).run(timeout=30)
        assert not app.exception
        assert len(app.tabs[1].get('plotly_chart'))==count
    app.selectbox(key='player_profile').select('K. Taylor').run(timeout=30)
    app.toggle(key='player_per90').set_value(True).run(timeout=30)
    assert not app.exception
    assert [m.value for m in app.metric]==['3–1–1','7','6','4-3-3 · 73%']
    app.selectbox(key='player_source').select('04_player_passing.csv').run(timeout=30)
    for key,data in before.items():pd.testing.assert_frame_equal(report.tables[key],data)


def test_multiple_comparisons_scatter_metric_customization_and_filters(report):
    app=loaded_app(report)
    app.segmented_control(key='player_primary').set_value('Comparisons').run(timeout=30)
    assert len(app.multiselect(key='player_comparison_players').value)==2
    names=['J. Hato','K. Taylor','M. Godts']
    app.multiselect(key='player_comparison_players').set_value(names).run(timeout=30)
    app.selectbox(key='player_comparison_metric').select('Defensive duels').run(timeout=30)
    assert not app.exception
    assert len(app.tabs[1].get('plotly_chart'))==2
    app.segmented_control(key='player_comparison_chart').set_value('Attacking contribution').run(timeout=30)
    assert not app.exception
    assert len(app.tabs[1].get('plotly_chart'))==1
    app.multiselect(key='player_families').set_value(['Goals','xG','xA']).run(timeout=30)
    app.segmented_control(key='player_comparison_chart').set_value('Action comparison').run(timeout=30)
    assert app.selectbox(key='player_comparison_metric').value in ['Goals','xG','xA']
    app.number_input(key='player_minimum').set_value(400).run(timeout=30)
    assert not app.exception
    assert app.multiselect(key='player_comparison_players').value==['J. Hato']
    app.multiselect(key='player_comparison_players').set_value([]).run(timeout=30)
    assert not app.exception
    assert any('Select players to compare' in i.value for i in app.info)


def test_observation_highlights_threshold_and_unsaved_finding_draft(report):
    app=loaded_app(report)
    app.segmented_control(key='player_primary').set_value('Statistical Observations').run(timeout=30)
    app.segmented_control(key='player_primary').set_value(None).run(timeout=30)
    assert app.segmented_control(key='player_primary').value=='Statistical Observations'
    app.selectbox(key='player_observation_metric').select('Defensive duels').run(timeout=30)
    app.segmented_control(key='player_observation_measure').set_value('Success rate').run(timeout=30)
    app.multiselect(key='player_observation_highlights').set_value(['J. Šutalo','J. Hato']).run(timeout=30)
    assert not app.exception
    app.button(key='workflow_add_player').click().run(timeout=30)
    assert not app.exception
    assert app.session_state['workflow_navigation']=='Scouting Findings'
    seed=app.session_state['workflow_pending']['seed']
    assert '83.3%' in seed['observation'] and seed['status']=='Draft'
    assert 'Defensive Duels Won'==seed['source_refs'][0]['column']
    assert not FindingsStore().list(report_identifier(report))


def test_partial_player_pages_and_zero_minutes_remain_usable(report):
    report.tables.pop('03_player_duels_set_pieces.csv')
    report.tables.pop('04_player_passing.csv')
    report.tables['02_player_general.csv'].loc[0,'Minutes']=0
    app=loaded_app(report)
    for focus in ['Progression','Attacking','Defending']:
        app.segmented_control(key='player_focus').set_value(focus).run(timeout=30)
        assert not app.exception
    app.number_input(key='player_minimum').set_value(0).run(timeout=30)
    app.toggle(key='player_per90').set_value(True).run(timeout=30)
    assert not app.exception


def test_profile_selection_cannot_be_cleared_and_observation_modes_switch(report):
    app=loaded_app(report)
    app.segmented_control(key='player_focus').set_value(None).run(timeout=30)
    assert app.segmented_control(key='player_focus').value=='Progression'
    app.segmented_control(key='player_primary').set_value('Statistical Observations').run(timeout=30)
    app.segmented_control(key='player_primary').set_value(None).run(timeout=30)
    assert app.segmented_control(key='player_primary').value=='Statistical Observations'
    app.selectbox(key='player_observation_metric').select('Defensive duels').run(timeout=30)
    app.segmented_control(key='player_observation_measure').set_value('Success rate').run(timeout=30)
    app.selectbox(key='player_observation_metric').select('xG').run(timeout=30)
    assert not app.exception
    assert not any(s.key=='player_observation_measure' for s in app.segmented_control)


def test_scatter_padding_keeps_extreme_and_zero_markers_inside_axes(report):
    data=scatter_population(frame_for(report,False,0))
    extreme=[data.loc[data['xG /90'].idxmax(),'Player'],data.loc[data['xA /90'].idxmax(),'Player']]
    fig=player_charts.contribution_chart(data,extreme)
    for trace in fig.data:
        assert trace.mode=='markers'  # No permanent labels to collide or clip.
        assert all(fig.layout.xaxis.range[0]<x<fig.layout.xaxis.range[1] for x in trace.x)
        assert all(fig.layout.yaxis.range[0]<y<fig.layout.yaxis.range[1] for y in trace.y)
    assert fig.layout.height<=320
    data[['xG /90','xA /90']]=0
    fig=player_charts.contribution_chart(data,extreme)
    assert fig.layout.xaxis.range[0]<0<fig.layout.xaxis.range[1]
    assert fig.layout.yaxis.range[0]<0<fig.layout.yaxis.range[1]
    assert list(fig.layout.xaxis.tickvals)==[0]


def test_compact_profile_charts_preserve_counts_and_outcomes(report):
    frame=frame_for(report)
    row=frame[frame.Player.eq('J. Hato')].iloc[0]
    metrics=[m for m in available_metrics(report) if m.label in ['Progressive passes','Passes to final third']]
    data=action_rows(row,metrics)
    fig=player_charts.action_chart(data)
    assert fig.layout.height<240
    assert list(fig.data[0].x)==[19,12]
    assert list(fig.data[1].x)==[7,1]
    assert fig.layout.xaxis.range[1]>max(data.Total)
    count=player_charts.count_chart(['Recoveries','Interceptions'],[36,16],False,'Actions')
    assert count.layout.height<240 and list(count.data[0].x)==[36,16]
    metric=next(m for m in metrics if m.label=='Progressive passes')
    comp=player_charts.comparison_chart(frame,['J. Hato','K. Taylor'],metric,False)
    assert comp.layout.height<260


def test_attacking_summary_keeps_details_available_for_all_samples(report):
    app=loaded_app(report)
    app.segmented_control(key='player_focus').set_value('Attacking').run(timeout=30)
    assert any(e.label=='Detailed attacking charts' for e in app.expander)
    assert len(app.tabs[1].get('plotly_chart'))==2
    app.selectbox(key='player_profile').select('K. Taylor').run(timeout=30)
    app.toggle(key='player_per90').set_value(True).run(timeout=30)
    assert any(e.label=='Detailed attacking charts' for e in app.expander)
    app.number_input(key='player_minimum').set_value(0).run(timeout=30)
    app.selectbox(key='player_profile').select('O. Wijndal').run(timeout=30)
    assert not app.exception
    assert any(e.label=='Detailed attacking charts' for e in app.expander)


def test_zero_shot_indicator_keeps_accuracy_unknown(report):
    from unittest.mock import patch
    from opponent_intelligence.dashboard.player_workspace import shot_indicator
    metric=next(m for m in available_metrics(report) if m.label=='Shots')
    row=frame_for(report).iloc[0].copy()
    row['Shots']=0;row['Shots successful']=0
    with patch('opponent_intelligence.dashboard.player_workspace.st.html') as html:
        shot_indicator(action_rows(row,[metric]))
    markup=html.call_args.args[0]
    assert '0 / 0 on target' in markup
    assert 'Accuracy —' in markup
    assert 'Accuracy 0.0%' not in markup


def test_native_rounded_bars_keep_exact_stacked_values_and_label_spacing(report):
    row=frame_for(report).iloc[0]
    metrics=[m for m in available_metrics(report) if m.label in ['Progressive passes','Passes to final third']]
    fig=player_charts.action_chart(action_rows(row,metrics))
    assert fig.layout.barcornerradius==6
    assert fig.layout.yaxis.ticklabelstandoff>=12
    assert list(fig.data[0].x)==[19,12] and list(fig.data[1].x)==[7,1]
    assert fig.layout.barmode=='stack'


def test_duel_rings_use_raw_counts_in_both_display_modes(report):
    metrics=[m for m in available_metrics(report) if m.label in ['Defensive duels','Aerial duels']]
    for normalize in [False,True]:
        row=frame_for(report,normalize).iloc[0]
        fig=player_charts.duel_success_chart(action_rows(row,metrics,normalize),normalize)
        assert fig.data[0].type=='pie' and fig.data[0].hole>.7
        assert list(fig.data[0].values)==[13,6]
        assert list(fig.data[1].values)==[8,6]
        annotations=' '.join(a.text for a in fig.layout.annotations)
        assert '68.4%' in annotations and '13 / 19 won' in annotations
        if normalize:assert '2.9 / 4.3 per 90' in annotations
    row=frame_for(report).iloc[0].copy()
    row['Defensive duels']=0;row['Defensive duels successful']=0
    fig=player_charts.duel_success_chart(action_rows(row,[metrics[0]]))
    assert len(fig.data)==0  # No invented neutral count or 100% donut.
    assert '—' in [a.text for a in fig.layout.annotations]


def test_recoveries_subset_is_on_same_row_and_never_added_to_total():
    fig=player_charts.recovery_dot_chart([36,5,16])
    total=next(t for t in fig.data if t.name=='Total')
    subset=next(t for t in fig.data if t.name=='Opponent-half recovery subset')
    assert list(total.x)==[36,16] and list(total.y)==[0,1]
    assert list(subset.x)==[5] and list(subset.y)==[0]
    assert list(fig.layout.yaxis.ticktext)==['Recoveries','Interceptions']
    invalid=player_charts.recovery_dot_chart([5,8,2])
    assert next(t for t in invalid.data if t.name=='Opponent-half recovery subset').x[0] is None


def test_attacking_summary_separates_shot_assists_actual_assists_and_expected(report):
    from unittest.mock import patch
    from opponent_intelligence.dashboard.player_workspace import attacking_summary
    from opponent_intelligence.dashboard.player_models import extra_value
    row=frame_for(report).loc[lambda d:d.Player.eq('K. Taylor')].iloc[0]
    shot=next(m for m in available_metrics(report) if m.label=='Shots')
    with patch('opponent_intelligence.dashboard.player_workspace.st.html') as html:
        attacking_summary(row,extra_value(report,row,'Assists'),action_rows(row,[shot]),False)
    markup=' '.join(c.args[0] for c in html.call_args_list)
    assert 'Goals · actual</span><strong>3</strong>' in markup
    assert 'xG · expected</span><strong>1.32</strong>' in markup
    assert 'Shot assists</span><strong>3</strong>' in markup
    assert 'Assists · actual</span><strong>0</strong>' in markup
    assert 'xA · expected</span><strong>1.05</strong>' in markup
    assert 'Shots</span><strong>8</strong>' in markup
    assert 'On target</span><strong>3</strong>' in markup
