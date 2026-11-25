"""Ranking populations, attempt thresholds, display formats and map meanings."""
import pandas as pd
import pytest
from opponent_intelligence.dashboard.standouts import table_standouts
from opponent_intelligence.dashboard.tactical_style import format_value,prepare_table,table_config
from opponent_intelligence.dashboard.spatial import registry
from test_dashboard import report,loaded_app


def rates(report,attempts,wins,names=None):
    report.tables['03_player_duels_set_pieces.csv']=pd.DataFrame({
        'Player':names or [f'Player {i}' for i in range(len(attempts))],
        'Defensive Duels':attempts,'Defensive Duels Won':wins})
    return [s for s in table_standouts(report,'03') if s.metric=='_success_rate']


def test_success_comparisons_exclude_tiny_samples(report):
    result=rates(report,[1,10,20],[1,8,12],['Tiny','Eligible','Other'])
    assert len(result)==1 and result[0].names==('Eligible',)
    assert result[0].value==80 and result[0].eligible==2
    assert 'at least 10 attempts' in result[0].detail


def test_threshold_boundary_and_insufficient_population(report):
    assert rates(report,[9,10],[9,8])==[]
    assert rates(report,[10,20],[10,12])[0].value==100


def test_ties_are_explicit_and_uniform_values_omitted(report):
    result=rates(report,[10,20,10],[8,16,4],['A','B','C'])
    assert result[0].names==('A','B')
    assert result[0].value==80
    assert rates(report,[10,20],[8,16])==[]


def test_unknown_bounds_and_invalid_success_are_not_candidates(report):
    result=rates(report,[10,20,1,10],[8,12,1,11],['A','B','Tiny','Invalid'])
    assert result[0].names==('A',)
    frame=pd.DataFrame({'Player':['A','B'],'Shots':[1,1],'xG':[.12,'<0.01']})
    report.tables['33_setpieces_free_kick_shots.csv']=frame
    assert table_standouts(report,'33')==[]


def test_reported_share_uses_team_denominator_not_shortlist(report):
    items=table_standouts(report,'18')
    share=next(item for item in items if item.metric=='% of Team')
    assert share.value==36.4
    assert 'Selected players' in share.population
    assert share.value!=pytest.approx(100*8/19)


def test_actual_duel_leader_uses_unrounded_counts(report):
    items=table_standouts(report,'03')
    rate=next(item for item in items if item.metric=='_success_rate')
    assert rate.names==('J. Šutalo',)
    assert rate.value==pytest.approx(100*10/12)
    assert '10/12' in rate.detail


@pytest.mark.parametrize('value,unit,expected',[
 (164/268*100,'percent','61.2%'),(62.5387,'percent','62.5%'),
 (398.0,'count','398'),(1234,'count','1,234'),(.47,'decimal','0.47'),
 (None,'percent','—'),(float('nan'),'count','—'),('<0.01','decimal','<0.01'),
])
def test_display_format(value,unit,expected):
    assert format_value(value,unit)==expected


def test_prepared_table_sorts_counts_and_preserves_denominators(report):
    original=report.tables['03_player_duels_set_pieces.csv'].copy(deep=True)
    frame=prepare_table(report,'03',['Player','Minutes','Defensive Duels','Defensive Duels Won','Defensive Duels Won %'])
    assert frame.iloc[0].Player=='Lucas Rosa'
    row=frame[frame.Player.eq('D. Konadu')].iloc[0]
    assert row['Defensive Duels Won %']==100
    assert 'Success' not in row.Standout  # 1/1 is displayed but never highlighted as a rate leader.
    config=table_config(frame)
    assert config['Defensive Duels']['type_config']['type']=='progress'
    assert config['Defensive Duels Won %']['type_config']['format']=='%.1f%%'
    pd.testing.assert_frame_equal(report.tables['03_player_duels_set_pieces.csv'],original)


def test_successful_only_selection_adds_attempts_and_rate(report):
    frame=prepare_table(report,'04',['Player','Passes to Final Third Accurate'])
    assert {'Passes to Final Third','Passes to Final Third Accurate','Passes to Final Third Accurate %'}.issubset(frame)


def test_zero_attempt_rate_stays_missing(report):
    frame=prepare_table(report,'16',['Player','Crosses','Crosses Successful'])
    report.tables['16_attack_crosses_takers.csv'].loc[0,['Crosses','Crosses Successful']]=[0,0]
    frame=prepare_table(report,'16',['Player','Crosses','Crosses Successful'])
    assert pd.isna(frame[frame.Player.eq('A. Gaaei')]['Crosses Successful %'].iloc[0])


def test_every_map_has_distinct_context():
    maps=next(iter(registry().values()))['maps']
    assert len(maps)==9
    for entry in maps:
        context=entry['context']
        assert all(context.get(field) for field in ['title','original_title','measurement','units','legend','orientation','limit'])
    by_key={entry['key']:entry['context'] for entry in maps}
    assert 'not success rate' in by_key['dribbles']['units']
    assert 'within that zone' in by_key['dribbles']['units']
    assert 'shirt numbers' in by_key['defensive_duels']['units']
    assert 'blue = less' in by_key['losses']['legend']
    assert 'blue = more' in by_key['recoveries']['legend']


def test_standouts_and_formatted_tables_render_all_categories(report):
    app=loaded_app(report)
    for category in ['Defensive organization','Transitions','Buildup and progression','Attacking patterns','Set pieces']:
        app.segmented_control(key='tactical_category').set_value(category).run(timeout=30)
        assert not app.exception
    app.segmented_control(key='tactical_setpieces').set_value('Free kicks').run(timeout=30)
    assert not app.exception  # Mixed numeric/<0.01 xG column survives formatting.
