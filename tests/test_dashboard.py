"""Lightweight KPI/scope tests use existing CSV fixtures, not extraction runs."""
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from opponent_intelligence import ExtractionResult
from opponent_intelligence.dashboard.catalog import table_info
from opponent_intelligence.dashboard.data import (
    overview, per90, success_rate, formation_usage, available_metrics, player_frame,
    match_events, clock_value, filter_table, quality_notes,
)
from opponent_intelligence.dashboard import charts

PROJECT=Path(__file__).resolve().parents[1]
CSV=PROJECT.parent/'00_assignments/assignment_4/ajax_report/csv'


@pytest.fixture
def report():
    return ExtractionResult(team='Ajax',matches=5,tables={p.name:pd.read_csv(p,encoding='utf-8-sig') for p in sorted(CSV.glob('*.csv'))})


def test_full_sample_outcomes_are_not_formation_goals(report):
    summary=overview(report)
    assert (summary['matches'],summary['wins'],summary['draws'],summary['losses'])==(5,3,1,1)
    assert (summary['goals_for'],summary['goals_against'])==(7,6)
    assert formation_usage(report)['Usage %'].sum()==86
    assert any('86%' in note for note in quality_notes(report))


def test_missing_outcomes_never_become_zero(report):
    report.tables['05_match_results.csv'].loc[0,'Ajax']=float('nan')
    summary=overview(report)
    assert summary['goals_for'] is None
    assert summary['unknown']==1
    report.tables.pop('05_match_results.csv')
    assert overview(report) is None


def test_rates_and_denominators():
    rates=success_rate(pd.Series([0,1,8,None,11]),pd.Series([0,0,10,10,10]))
    assert rates.isna().tolist()==[True,True,False,True,True]
    assert rates.iloc[2]==80
    normalized=per90(pd.Series([10,10,10,0,None,'<0.01']),pd.Series([90,0,None,45,90,90]))
    assert normalized.iloc[0]==10 and normalized.iloc[3]==0
    assert normalized.iloc[[1,2,4,5]].isna().all()


def test_player_comparisons_keep_raw_counts_and_percentages(report):
    selected=[m for m in available_metrics(report) if m.label=='Defensive duels']
    frame=player_frame(report,selected,True,90).set_index('Player')
    assert 'O. Wijndal' not in frame.index
    assert frame.loc['J. Henderson','Defensive duels']==8
    assert frame.loc['J. Henderson','Defensive duels successful']==1
    assert frame.loc['J. Henderson','Defensive duels success %']==12.5
    assert frame.loc['J. Henderson','Defensive duels /90']==pytest.approx(8*90/242)
    assert not any('success % /90' in c for c in frame)
    assert not any(c in frame for c in ['Position','Date','Match'])


def test_creation_definitions_are_not_merged(report):
    selected=[m for m in available_metrics(report) if m.key=='04' and m.attempts in {'Shot Assists','Key Passes'}]
    frame=player_frame(report,selected).set_index('Player')
    assert frame.loc['O. Edvardsen','Shot assists']==5
    assert frame.loc['O. Edvardsen','Key passes — passing page']==1
    assert 'separate' in table_info('23',5).note or 'do not merge' in table_info('23',5).note


def test_shortlists_never_supply_complete_player_statistics(report):
    assert 'Selected' in table_info('18',5).coverage
    assert 'All reported outfield' in table_info('02',5).coverage
    report.tables.pop('04_player_passing.csv')
    assert 'Progressive passes' not in [m.label for m in available_metrics(report)]
    assert 'Shot assists' not in [m.label for m in available_metrics(report)]


def test_match_filter_is_local_and_clock_preserves_added_time(report):
    original=report.tables['02_player_general.csv'].copy(deep=True)
    events=match_events(report,'2025-03-13')
    assert events.Date.nunique()==1
    assert clock_value("45'") < clock_value("45+3'") < clock_value("46'")
    assert pd.isna(clock_value('unknown'))
    pd.testing.assert_frame_equal(report.tables['02_player_general.csv'],original)
    assert overview(report)['goals_for']==7


def test_search_literal_and_combined_filters():
    frame=pd.DataFrame({'Player':['A. Test','Another',None],'Minutes':[90,0,None]})
    assert len(filter_table(frame,'A.'))==1
    assert len(filter_table(frame,'test','Minutes',['90.0']))==1
    assert len(filter_table(frame,'absent'))==0
    assert frame.Player.isna().sum()==1


def test_neutral_team_and_sample_size(report):
    team='Example United'
    report.team=team
    for filename in ['05_match_results.csv','09_formations.csv']:
        report.tables[filename]=report.tables[filename].rename(columns=lambda c:c.replace('Ajax',team))
    assert overview(report)['goals_for']==7
    assert team in charts.results_chart(report.tables['05_match_results.csv'],team).data[0].name
    assert table_info('23',6).page=='16'


def test_charts_serialize_without_changing_source(report):
    results=report.tables['05_match_results.csv']
    before=results.copy(deep=True)
    for fig in [charts.results_chart(results,report.team),charts.event_chart(match_events(report,'2025-03-13'),report.team),
                charts.formation_chart(report.tables['09_formations.csv'],'PPDA',report.team)]:
        assert fig.to_json()
    pd.testing.assert_frame_equal(results,before)


def loaded_app(report):
    app=AppTest.from_file(str(PROJECT/'app.py'))
    # No upload: existing session result is rendered without running extraction.
    app.session_state['result']=report
    app.session_state['source_id']=None
    return app.run(timeout=30)


def test_dashboard_controls_and_data_scope(report):
    app=loaded_app(report)
    assert not app.exception
    assert [t.label for t in app.tabs]==['Team Overview','Player Analysis','Tactical Analysis','Data Explorer','Scouting Findings','Coach Report']
    assert [m.value for m in app.metric]==['3–1–1','7','6','4-3-3 · 73%']
    app.toggle(key='player_per90').set_value(True).run(timeout=30)
    assert not app.exception
    app.button(key='overview_fixture_2025-03-16').click().run(timeout=30)
    assert [m.value for m in app.metric]==['3–1–1','7','6','4-3-3 · 73%']
    app.selectbox(key='explorer_table').select('18_attack_dribbles_final_third.csv').run(timeout=30)
    assert any('Selected players' in c.value for c in app.caption)
    app.text_input(key='explorer_search_18_attack_dribbles_final_third.csv').set_value('Godts').run(timeout=30)
    assert not app.exception
    assert any('1 of 7 rows' in c.value for c in app.caption)
    assert len(app.get('download_button'))==3
    app.number_input(key='player_minimum').set_value(10000).run(timeout=30)
    assert not app.exception
    assert any('No players meet' in c.value for c in app.info)


def test_partial_report_remains_reviewable(report):
    for name in ['05_match_results.csv','02_player_general.csv','09_formations.csv']:
        report.tables.pop(name)
        report.errors[name]=['Unavailable fixture']
    app=loaded_app(report)
    assert not app.exception
    assert any('Match results are unavailable' in info.value for info in app.info)
    assert len(app.warning)==1


def test_upload_change_clears_old_dashboard(report):
    app=loaded_app(report)
    with patch('streamlit.file_uploader',return_value=BytesIO(b'%PDF-new-file')):
        app.run(timeout=30)
    assert not app.exception
    assert len(app.tabs)==0
    assert len(app.metric)==0


def test_frankfurt_dashboard_uses_six_match_sample():
    folder=PROJECT.parent/'00_assignments/assignment_3/frankfurt_report/csv'
    tables={p.name:pd.read_csv(p,encoding='utf-8-sig') for p in sorted(folder.glob('*.csv'))}
    team='Eintracht Frankfurt'
    old=tables['05_match_results.csv']
    tables['05_match_results.csv']=pd.DataFrame({
        'Date':old.Date, 'Competition':old.Competition, 'Opponent':old.Opponent,
        'Home/Away':old['Frankfurt Venue'], team:old['Frankfurt Goals'],
        'Opponent Goals':old['Opponent Goals'], 'Result':old.Result,
        f'{team} Team Width m':old['Frankfurt Team Width m'],
        f'{team} Team Depth m':old['Frankfurt Team Depth m']})
    tables['09_formations.csv']=tables['09_formations.csv'].rename(columns={'Frankfurt':team})
    report=ExtractionResult(team=team,matches=6,tables=tables)
    app=loaded_app(report)
    assert not app.exception
    assert [m.value for m in app.metric]==['1–2–3','9','12','4-2-3-1 · 33%']


def test_missing_plotly_keeps_tables_and_extraction_available(report,monkeypatch):
    monkeypatch.setattr(charts,'go',None)
    app=loaded_app(report)
    assert not app.exception
    assert len(app.metric)==4
    assert len(app.get('download_button'))==2
    assert any('Interactive charts need Plotly' in item.value for item in app.info)
