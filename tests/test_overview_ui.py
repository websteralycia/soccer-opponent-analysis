"""Fixture callbacks and readable event presentation without PDF parsing."""
import pandas as pd
from opponent_intelligence.dashboard.overview_ui import event_groups, events_html, avatar, number
from test_dashboard import report, loaded_app


def test_substitutions_group_by_team_minute_without_pairing(report):
    events=report.tables['07_match_events.csv']
    events=events[events.Date.eq('2025-03-13')]
    groups=event_groups(events)
    batch=next(g for g in groups if g['team']=='Ajax' and g['kind']=='Substitution' and g['minute']=="63'")
    assert len(batch['incoming'])==3 and len(batch['outgoing'])==3
    assert {p['name'] for p in batch['incoming']}=={'K. Taylor','M. Godts','B. Traoré'}
    html=events_html([batch])
    for word in ["63'",'↑','↓','M. Godts','S. Berghuis','Ajax']:
        # Apostrophe is safely escaped in HTML.
        assert word.replace("'",'&#x27;') in html
    assert ' for ' not in html


def test_opponents_and_matches_are_never_grouped_together():
    events=pd.DataFrame([
        ['A','One','Home',1,'Incoming','Subbed on',"45+3'"],
        ['A','One','Away',2,'Other','Subbed off',"45+3'"],
        ['B','Two','Home',3,'Different match','Subbed off',"45+3'"],
    ],columns=['Date','Match','Team','No','Player','Event','Minute'])
    groups=event_groups(events)
    assert len(groups)==3
    assert not groups[0]['outgoing']
    assert 'No off player recorded' in events_html(groups)


def test_stoppage_time_raw_notation_and_order():
    events=pd.DataFrame([
        ['Team','Later','Goal',"46'"],['Team','Extra','Red card',"45+3'"],
        ['Team','Earlier','Yellow card',"45'"],['Team','Unknown','Goal','unknown'],
    ],columns=['Team','Player','Event','Minute'])
    groups=event_groups(events)
    assert [g['minute'] for g in groups]==["45'","45+3'","46'",'unknown']
    html=events_html(groups)
    assert '45+3&#x27;' in html
    assert 'Yellow card' in html and 'Red card' in html and 'Goal' in html


def test_event_text_and_assets_are_safe():
    events=pd.DataFrame([['<Team>','<script>','Goal',"90+2'"]],columns=['Team','Player','Event','Minute'])
    html=events_html(event_groups(events))
    assert '<script>' not in html
    assert '&lt;script&gt;' in html and '&lt;Team&gt;' in html
    assert '<img' not in avatar('Sample Person',b'not an image')
    assert 'SP' in avatar('Sample Person')
    assert number('<0.01')=='<0.01'


def test_fixture_changes_events_not_sample_or_player_data(report):
    app=loaded_app(report)
    assert not app.exception
    assert app.session_state['overview_match']=='2025-03-30'
    assert not any(s.label=='Match' for s in app.selectbox)
    app.button(key='overview_fixture_2025-03-13').click().run(timeout=30)
    assert not app.exception
    assert app.session_state['overview_match']=='2025-03-13'
    assert [m.value for m in app.metric]==['3–1–1','7','6','4-3-3 · 73%']
    app.segmented_control(key='overview_primary').set_value('Formations').run(timeout=30)
    app.segmented_control(key='formation_side').set_value('Opponents').run(timeout=30)
    assert not app.exception
    assert app.session_state['overview_match']=='2025-03-13'
    assert len(app.tabs[0].get('plotly_chart'))==0  # Player comparison is now a compact table; no oversized chart.


def test_substitutions_use_arrows_and_match_positions(report):
    from opponent_intelligence.dashboard.data import match_events
    events=match_events(report,'2025-03-13')
    groups=event_groups(events)
    batch=next(g for g in groups if g['team']=='Ajax' and g['kind']=='Substitution' and g['minute']=="63'")
    html=events_html([batch])
    assert '<small>On</small>' not in html and '<small>Off</small>' not in html
    assert '↑' in html and '↓' in html
    assert '<small>LCMF</small>' in html and '<small>CF</small>' in html
    assert {p['name']:p['position'] for p in batch['incoming']}=={'K. Taylor':'LCMF','M. Godts':'LW','B. Traoré':'CF'}


def test_overview_explanations_are_in_quality_section(report):
    from opponent_intelligence.dashboard.data import quality_notes
    notes=' '.join(quality_notes(report))
    assert 'Fixture selection updates match details only' in notes
    assert 'Percentage rows use percentage points' in notes
    assert 'Source minutes are retained' in notes
    app=loaded_app(report)
    assert not app.exception
    captions=' '.join(c.value for c in app.caption)
    assert 'Selected fixture →' not in captions
    assert 'Added time retained' not in captions
    assert 'Percentage rows use percentage points' not in captions


def test_primary_views_disclose_only_selected_content(report):
    app=loaded_app(report)
    assert app.segmented_control(key='overview_primary').value=='Matches'
    assert app.segmented_control(key='overview_detail').value=='Events'
    assert not any(s.key=='formation_side' for s in app.segmented_control)
    assert not any(b.key=='workflow_add_overview' for b in app.button)
    app.button(key='overview_fixture_2025-03-13').click().run(timeout=30)
    for detail in ['Lineups','Formation Periods','Source Rows','Events']:
        app.segmented_control(key='overview_detail').set_value(detail).run(timeout=30)
        assert not app.exception
        assert app.session_state['overview_match']=='2025-03-13'
    app.segmented_control(key='overview_primary').set_value('Formations').run(timeout=30)
    assert not any(s.key=='overview_detail' for s in app.segmented_control)
    assert not any((b.key or '').startswith('overview_fixture_') for b in app.button)
    app.segmented_control(key='overview_formation_display').set_value('Source Rows').run(timeout=30)
    assert not app.exception
    assert any('report-level aggregates' in m.value for m in app.markdown)
    app.segmented_control(key='overview_primary').set_value('Statistical Observations').run(timeout=30)
    assert not app.exception
    assert any(b.key=='workflow_add_overview' for b in app.button)
    assert any(b.key=='workflow_add_overview_1' for b in app.button)
    assert [m.value for m in app.metric]==['3–1–1','7','6','4-3-3 · 73%']
    app.segmented_control(key='overview_primary').set_value('Matches').run(timeout=30)
    assert app.session_state['overview_match']=='2025-03-13'


def test_observation_cards_preserve_all_comparisons_and_evidence(report):
    from opponent_intelligence.dashboard.overview_workspace import observation_cards
    cards=observation_cards(report)
    assert len(cards)==2
    assert cards[0]['value']=='6 goals in 2/5 matches'
    assert sum(v for _,v in cards[0]['rows'])==6
    assert cards[1]['value']=='+1.17 xG balance'
    assert len(cards[1]['rows'])==2
    assert cards[0]['seed']['source_refs'][0]['table']=='05_match_results.csv'
    assert cards[1]['seed']['source_refs'][0]['table']=='09_formations.csv'


def test_positions_never_fall_back_to_other_matches_or_squad(report):
    from opponent_intelligence.dashboard.data import match_events
    lineups=report.tables['06_match_lineups.csv']
    report.tables['06_match_lineups.csv']=lineups[~(lineups.Date.eq('2025-03-13') & lineups.Team.eq('Ajax') & lineups.Player.eq('B. Traoré'))]
    events=match_events(report,'2025-03-13')
    assert events.loc[events.Player.eq('B. Traoré'),'Position'].isna().all()


def test_missing_match_details_remain_navigable(report):
    for key in ['06_match_lineups.csv','07_match_events.csv','08_match_formations.csv']:
        report.tables.pop(key,None)
    app=loaded_app(report)
    for detail in ['Lineups','Formation Periods','Source Rows','Events']:
        app.segmented_control(key='overview_detail').set_value(detail).run(timeout=30)
        assert not app.exception


def test_lineups_are_roster_only_and_original_columns_are_preserved(report):
    original=report.tables['06_match_lineups.csv'].copy(deep=True)
    app=loaded_app(report)
    app.segmented_control(key='overview_detail').set_value('Lineups').run(timeout=30)
    assert not app.exception
    columns=['Date','Match','Team','Starter','Position','No','Player']
    roster=next(df.value for df in app.dataframe if list(df.value.columns)==columns)
    assert len(roster)==len(original[original.Date.eq('2025-03-30')])
    assert 'Subbed On' not in roster and 'Goals' not in roster
    app.selectbox(key='explorer_table').select('06_match_lineups.csv').run(timeout=30)
    assert any(list(df.value.columns)==list(original.columns) for df in app.dataframe)
    pd.testing.assert_frame_equal(report.tables['06_match_lineups.csv'],original)


def test_sample_limits_distinguish_formation_periods_and_aggregates(report):
    from opponent_intelligence.dashboard.data import quality_notes
    notes=' '.join(quality_notes(report))
    assert 'repeated rows can use the same formation' in notes
    assert 'without having a summary KPI row' in notes
    assert 'missing metrics are not inferred' in notes
