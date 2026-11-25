"""Roster-based comparison populations and evidence scope, never inferred roles."""
import pandas as pd
from test_dashboard import report,loaded_app
from opponent_intelligence.dashboard.data import available_metrics,player_frame
from opponent_intelligence.dashboard.player_models import reported_roles,observation_data
from opponent_intelligence.dashboard.player_charts import ranking_chart
from opponent_intelligence.workflow.evidence import seed_from_standout


def test_report_groups_labels_and_filtered_evidence_preserve_raw_values(report):
    original=player_frame(report,available_metrics(report),False,0)
    before=original.copy(deep=True)
    data=reported_roles(report,original)
    assert data['Position group'].value_counts().to_dict()=={'Defenders':9,'Midfielders':7,'Forwards':5}
    assert data.set_index('Player').loc['O. Edvardsen','Position group']=='Midfielders'
    metric=next(m for m in available_metrics(report) if m.label=='xG')
    for normalize in [False,True]:
        frame=reported_roles(report,player_frame(report,available_metrics(report),normalize,90))
        mids=frame[frame['Position group'].eq('Midfielders')]
        compared,item,unit=observation_data(mids,metric,'Action volume',normalize,90,'Midfielders')
        assert item.names==(('O. Edvardsen',) if normalize else ('K. Taylor',))
        assert 'report position group: Midfielders' in item.population
        assert 'not actions isolated to this position' in item.population
        seed=seed_from_standout(report,item)
        assert 'Midfielders' in seed['observation']
        fig=ranking_chart(compared,['K. Taylor'],unit)
        assert all(' · ' in label for trace in fig.data for label in trace.y)
        assert 'K. Taylor · LCMF' in fig.layout.yaxis.categoryarray
    pd.testing.assert_frame_equal(original,before)


def test_missing_or_ambiguous_roster_remains_unreported(report):
    frame=player_frame(report,available_metrics(report),False,0)
    squad=report.tables['01_squad.csv']
    duplicate=squad[squad.Player.eq('J. Hato')].copy()
    duplicate['Group']='Midfielders';duplicate['Position']='CF'
    report.tables['01_squad.csv']=pd.concat([squad,duplicate],ignore_index=True)
    row=reported_roles(report,frame).set_index('Player').loc['J. Hato']
    assert row['Position group']=='Unreported' and row['Reported position']=='—'
    report.tables.pop('01_squad.csv')
    missing=reported_roles(report,frame)
    assert missing['Position group'].eq('Unreported').all()
    assert missing['Reported position'].eq('—').all()


def test_group_switch_highlights_minutes_per90_and_draft_scope(report):
    app=loaded_app(report)
    app.segmented_control(key='player_primary').set_value('Statistical Observations').run(timeout=30)
    assert app.selectbox(key='player_observation_group').value=='All positions'
    app.selectbox(key='player_observation_metric').select('xG').run(timeout=30)
    app.multiselect(key='player_observation_highlights').set_value(['J. Hato']).run(timeout=30)
    app.selectbox(key='player_observation_group').select('Forwards').run(timeout=30)
    assert not app.exception
    assert 'J. Hato' not in app.multiselect(key='player_observation_highlights').options
    assert 'J. Hato' not in app.multiselect(key='player_observation_highlights').value
    app.selectbox(key='player_observation_group').select('Midfielders').run(timeout=30)
    app.toggle(key='player_per90').set_value(True).run(timeout=30)
    assert 'K. Taylor' in app.multiselect(key='player_observation_highlights').options
    app.button(key='workflow_add_player').click().run(timeout=30)
    assert 'Midfielders' in app.session_state['workflow_pending']['seed']['observation']
    # A high minutes threshold removes midfielders without leaving a stale group.
    app.number_input(key='player_minimum').set_value(400).run(timeout=30)
    assert not app.exception
    assert app.selectbox(key='player_observation_group').value=='All positions'
    assert app.multiselect(key='player_observation_highlights').options==['J. Hato']
