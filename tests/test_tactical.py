"""Source identity, scope, optional assets and category switching."""
from pathlib import Path
from io import BytesIO
from unittest.mock import patch
import hashlib
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from opponent_intelligence.dashboard.spatial import spatial_maps,registry,checked_asset,CATEGORIES
from opponent_intelligence.dashboard.tactical import total,focus_asset
from opponent_intelligence.dashboard.tactical_models import FOCUSES,CONTROL_KEYS,scoped_frame,manual_seed,team_actions
from opponent_intelligence.dashboard import spatial
from test_dashboard import report,loaded_app,PROJECT

PDF=PROJECT.parent/'00_assignments/assignment_4/AFC Ajax.pdf'
FINGERPRINT=hashlib.sha256(PDF.read_bytes()).hexdigest()


def test_exact_source_has_verified_maps(report):
    maps=spatial_maps(report,FINGERPRINT,'Transitions')
    assert {m['key'] for m in maps}=={'recoveries','final_third_recoveries','losses','lost_duels'}
    assert all(m['path'].is_file() and m['report']['matches']==5 for m in maps)
    assert all(m['page'] in [12,14,16] for m in maps)


@pytest.mark.parametrize('fingerprint',[None,'not-a-pdf-hash','0'*64])
def test_no_image_fallback_for_unknown_report(report,fingerprint):
    assert not spatial_maps(report,fingerprint,'Defensive organization')


def test_same_team_different_sample_cannot_reuse_assets(report):
    report.matches=6
    assert not spatial_maps(report,FINGERPRINT,'Transitions')
    report.matches=5
    report.tables['05_match_results.csv'].loc[0,'Date']='2025-04-01'
    assert not spatial_maps(report,FINGERPRINT,'Transitions')


def test_other_team_never_gets_registered_images(report):
    report.team='Example United'
    assert not spatial_maps(report,FINGERPRINT,'Defensive organization')


def test_missing_files_registry_and_path_traversal_fail_closed(tmp_path,monkeypatch,report):
    assert checked_asset('../../README.md','wrong') is None
    assert checked_asset('spatial/recoveries.png','wrong') is None
    monkeypatch.setattr(spatial,'RESOURCES',tmp_path)
    assert registry()=={}
    assert spatial_maps(report,FINGERPRINT,'Transitions')==[]


def test_source_assets_match_their_registry():
    for source in registry().values():
        for entry in source['maps']:
            assert checked_asset(entry['file'],entry['sha256']) is not None
            if entry.get('support_file'):
                assert checked_asset(entry['support_file'],entry['support_sha256']) is not None


def test_no_selected_list_is_used_for_pooled_totals(report):
    assert total(report,'03','Defensive Duels')==268
    assert total(report,'03','Defensive Duels Won')==164
    assert total(report,'04','Shot Assists')==26
    with pytest.raises(ValueError,match='complete outfield'):
        total(report,'19','Recoveries')
    report.tables['02_player_general.csv'].loc[0,'Recoveries']=float('nan')
    assert total(report,'02','Recoveries') is None


def test_only_selected_category_renders(report):
    app=loaded_app(report)
    for category,focuses in FOCUSES.items():
        app.segmented_control(key='tactical_category').set_value(category).run(timeout=30)
        assert not app.exception
        assert app.segmented_control(key=CONTROL_KEYS[category]).value==next(iter(focuses))
        assert not any(c.key in [key for name,key in CONTROL_KEYS.items() if name!=category] for c in app.segmented_control)
        assert '#### Evidence worth investigating' in [m.value for m in app.markdown]
        if next(iter(focuses.values())).map_key:
            assert any('Spatial map unavailable' in item.value for item in app.info)
    assert [m.value for m in app.metric]==['3–1–1','7','6','4-3-3 · 73%']


def test_registered_map_is_labeled_and_setpieces_unavailable(report):
    app=AppTest.from_file(str(PROJECT/'app.py'))
    app.session_state['result']=report
    app.session_state['source_id']=FINGERPRINT
    with patch('streamlit.file_uploader',return_value=BytesIO(PDF.read_bytes())):
        app.run(timeout=30)
        assert not app.exception
        assert any('Source-specific image' in item.value and '5-match aggregate' in item.value for item in app.markdown)
        assert any(b.label=='Enlarge source map' for b in app.button)
        app.segmented_control(key='tactical_category').set_value('Set pieces').run(timeout=30)
        assert not app.exception
        assert not any(b.label=='Enlarge source map' for b in app.button)
        assert not any('Spatial map unavailable' in item.value for item in app.info)


def test_partial_report_categories_still_render(report):
    report.tables={k:v for k,v in report.tables.items() if k.startswith(('05_','34_'))}
    app=loaded_app(report)
    for category in CATEGORIES:
        app.segmented_control(key='tactical_category').set_value(category).run(timeout=30)
        assert not app.exception


def test_every_focus_has_only_its_registered_relevant_map(report):
    for category,focuses in FOCUSES.items():
        for label,spec in focuses.items():
            asset=focus_asset(report,FINGERPRINT,category,spec)
            assert (asset['key'] if asset else None)==spec.map_key
            assert focus_asset(report,None,category,spec) is None
            seed=manual_seed(report,category,label,spec,asset)
            assert seed['classification'] is None and seed['status']=='Draft'
            assert seed['observation']=='' and seed['category']==category
            assert seed['source_refs']
    assert FOCUSES['Attacking patterns']['Crossing'].map_key=='crosses'
    assert FOCUSES['Transitions']['Own-third lost duels'].map_key=='lost_duels'


def test_all_evidence_focuses_render_and_source_rows_remain_accessible(report):
    app=loaded_app(report)
    for category,focuses in FOCUSES.items():
        app.segmented_control(key='tactical_category').set_value(category).run(timeout=30)
        for label in focuses:
            app.segmented_control(key=CONTROL_KEYS[category]).set_value(label).run(timeout=30)
            assert not app.exception, (category,label)
        app.segmented_control(key='tactical_data_view').set_value('Statistical comparisons').run(timeout=30)
        assert not app.exception
        app.segmented_control(key='tactical_data_view').set_value('Tables').run(timeout=30)
        assert app.selectbox(key='tactical_source_table').value in report.tables


def test_sharp_display_images_preserve_original_registry_assets(report):
    from PIL import Image
    for source in registry().values():
        for entry in source['maps']:
            original=checked_asset(entry['file'],entry['sha256'])
            display=checked_asset(entry['display_file'],entry['display_sha256'])
            assert original and display
            assert Image.open(display).width>Image.open(original).width


def test_receiver_scope_and_team_action_missing_denominators(report):
    links=scoped_frame(report,'15')
    passer=links.Passer.iloc[0]
    assert scoped_frame(report,'15',passer).Passer.eq(passer).all()
    assert len(scoped_frame(report,'15',passer))<len(links)
    report.tables[next(k for k in report.tables if k.startswith('04_'))].loc[0,'Progressive Passes']=float('nan')
    data=team_actions(report,'04',[('Progression','Progressive Passes','Progressive Passes Accurate')])
    assert pd.isna(data.Attempts.iloc[0]) and pd.isna(data.Rate.iloc[0])


def test_calculated_supporting_rates_and_scope_units(report):
    from opponent_intelligence.dashboard.tactical_charts import contributors
    frame=pd.DataFrame({'Player':['One','Two'],'% of Team':[40.,60.]})
    chart=contributors(frame,['% of Team'])
    assert chart.layout.xaxis.title.text=='Percentage (%)'
    assert 'receiver share' not in chart.data[0].hovertemplate.lower()
    app=loaded_app(report)
    app.segmented_control(key='tactical_category').set_value('Buildup and progression').run(timeout=30)
    name=next(k for k in report.tables if k.startswith('04_'))
    app.selectbox(key='tactical_source_table').set_value(name).run(timeout=30)
    app.checkbox(key='tactical_calculated_rates').check().run(timeout=30)
    assert not app.exception
    assert any('Progressive Passes Accurate %' in f.value for f in app.dataframe)


def test_final_third_recovery_focus_uses_page14_not_all_area_map(report):
    spec=FOCUSES['Transitions']['Attacking-third recoveries']
    assert spec.source=='19'
    asset=focus_asset(report,FINGERPRINT,'Transitions',spec)
    assert asset['key']=='final_third_recoveries' and asset['page']==14
    assert asset['context']['original_title']=='Recoveries in final third'
    all_area=focus_asset(report,FINGERPRINT,'Transitions',FOCUSES['Transitions']['All-area recoveries'])
    assert all_area['key']=='recoveries' and all_area['page']==16
    assert focus_asset(report,None,'Transitions',spec) is None
    app=loaded_app(report)
    app.segmented_control(key='tactical_category').set_value('Transitions').run(timeout=30)
    assert app.segmented_control(key='tactical_transition').value=='Attacking-third recoveries'
    content=' '.join(m.value for m in app.markdown)
    assert 'Recoveries · all areas' not in content and 'Possession losses · all areas' not in content
    assert any('Spatial map unavailable' in i.value for i in app.info)


def test_recovery_labels_identify_the_attacking_team_without_changing_fields(report):
    from opponent_intelligence.dashboard.tactical_models import metric_label
    from opponent_intelligence.dashboard.tactical_charts import contributors
    frame=scoped_frame(report,'19')
    before=frame.copy(deep=True)
    label=metric_label('19','Shots After')
    assert label=='Team shots following recovery'
    assert metric_label('12','Opponent Shots After')=='Opponent Shots After'
    fig=contributors(frame,['Shots After'],metric_labels={'Shots After':label})
    assert fig.data[0].name==label
    pd.testing.assert_frame_equal(frame,before)
    app=loaded_app(report)
    app.segmented_control(key='tactical_category').set_value('Transitions').run(timeout=30)
    assert app.segmented_control(key='tactical_transition').value=='Attacking-third recoveries'
    control=app.selectbox(key='tactical_primary_Transitions_Attacking-third recoveries')
    assert control.value=='Shots After'  # Display labels do not rename source data.
    assert any('Ajax shots following recoveries in the attacking third.' in m.value for m in app.markdown)
    assert any('Selected players · 7/7 shown' in m.value for m in app.markdown)
    assert not any('not necessarily shots by the recovering player' in m.value for m in app.markdown)


def test_attacking_maps_and_loss_location_have_distinct_scopes(report):
    assert 'Loss locations · context' not in FOCUSES['Buildup and progression']
    assert not spatial_maps(report,FINGERPRINT,'Buildup and progression')
    assert FOCUSES['Transitions']['Possession losses'].map_key=='losses'
    for label,key in [('Final-third dribbles','final_third_dribbles'),('Crossing','crosses')]:
        asset=focus_asset(report,FINGERPRINT,'Attacking patterns',FOCUSES['Attacking patterns'][label])
        assert asset['key']==key and asset['page']==14
        assert focus_asset(report,None,'Attacking patterns',FOCUSES['Attacking patterns'][label]) is None
    asset=focus_asset(report,FINGERPRINT,'Attacking patterns',FOCUSES['Attacking patterns']['All-pitch dribbling'])
    assert asset['page']==17 and asset['header_path'].is_file()


def test_kpi_cards_do_not_promote_shortlists_or_formation_coverage(report):
    from opponent_intelligence.dashboard.tactical import context_cards
    with patch('opponent_intelligence.dashboard.tactical.card_strip') as cards:
        for category,label in [('Defensive organization','Formation PPDA'),('Attacking patterns','Final-third dribbles'),('Attacking patterns','All-pitch dribbling')]:
            context_cards(report,category,label)
        cards.assert_not_called()
        context_cards(report,'Attacking patterns','Shot creation')
        items=cards.call_args.args[0]
        assert [(i[0],i[1]) for i in items]==[('Shots','51'),('xG','6.62'),('Goals','7')]
        context_cards(report,'Attacking patterns','Crossing')
        assert [(i[0],i[1]) for i in cards.call_args.args[0]]==[('Shots','5'),('xG','0.82'),('Goals','0')]
        context_cards(report,'Set pieces','Corners')
        assert [(i[0],i[1]) for i in cards.call_args.args[0]]==[('Shots','4'),('xG','0.47'),('Goals','1')]


def test_ppda_is_a_compact_table_with_original_period_values(report):
    from opponent_intelligence.dashboard.tactical_models import formation_ppda_frame
    frame=formation_ppda_frame(report)
    assert list(frame)==['Formation','Usage %','Team PPDA','Opponent PPDA']
    assert frame['Usage %'].sum()==86
    assert frame['Team PPDA'].tolist()==[16.76,16.41]
    app=loaded_app(report)
    app.segmented_control(key='tactical_defence').set_value('Formation PPDA').run(timeout=30)
    assert not app.exception
    assert any(list(e.value.columns)==list(frame.columns) for e in app.dataframe)
    assert not any(e.key=='tactical_plot_Defensive organization_Formation PPDA' for e in app.get('plotly_chart'))
    report.tables[next(k for k in report.tables if k.startswith('09_'))].loc[lambda d:d.Metric.eq('PPDA'),'Ajax']=float('nan')
    assert formation_ppda_frame(report)['Team PPDA'].isna().all()


def test_attacking_full_sample_goals_follow_match_results_not_formation_or_finishing_rows(report):
    from opponent_intelligence.dashboard.tactical import context_cards
    report.tables['05_match_results.csv']['Ajax']=0
    with patch('opponent_intelligence.dashboard.tactical.card_strip') as cards:
        context_cards(report,'Attacking patterns','Shot creation')
        assert cards.call_args.args[0][-1]==('Goals','0','Match results · full sample')


def test_defensive_cards_follow_focus_without_inventing_team_totals(report):
    from opponent_intelligence.dashboard.tactical import context_cards,ratio_summary
    with patch('opponent_intelligence.dashboard.tactical.card_strip') as cards:
        context_cards(report,'Defensive organization','Own-third wins')
        wins=cards.call_args.args[0]
        assert wins[0][0]=='Most listed own-third defensive-duel wins'
        assert wins[0][1]=='13' and 'Lucas Rosa' in wins[0][2]
        assert all('selected players' in card[2] for card in wins)
        context_cards(report,'Defensive organization','Own-third losses')
        losses=cards.call_args.args[0]
        assert losses[0][1]=='9' and 'lost duels' in losses[0][0]
        assert all('selected players' in card[2] for card in losses)
        context_cards(report,'Defensive organization','Foul locations')
        assert cards.call_args.args[0]==[('Fouls committed',format(total(report,'03','Fouls'),'.0f'),'All reported outfield players')]
        context_cards(report,'Defensive organization','All-area duels')
        duels=cards.call_args.args[0]
        assert duels[0][1]=='164 / 268 · 61.2%'
        assert duels[1][1]==ratio_summary(report,'03','Aerial Duels','Aerial Duels Won')
        cards.reset_mock()
        context_cards(report,'Defensive organization','Formation PPDA')
        cards.assert_not_called()


def test_defensive_leader_cards_omit_insufficient_data_and_keep_ties(report):
    from opponent_intelligence.dashboard.tactical import context_cards
    name=next(k for k in report.tables if k.startswith('11_'))
    frame=report.tables[name]
    frame.loc[frame.Player.eq('J. Hato'),'Defensive Duels Won']=13
    with patch('opponent_intelligence.dashboard.tactical.card_strip') as cards:
        context_cards(report,'Defensive organization','Own-third wins')
        assert cards.call_args.args[0][0][2]=='2 players tied · selected players'
        report.tables.pop(name)
        cards.reset_mock()
        context_cards(report,'Defensive organization','Own-third wins')
        cards.assert_not_called()


def test_transition_cards_follow_selected_evidence(report):
    from opponent_intelligence.dashboard.tactical import context_cards
    with patch('opponent_intelligence.dashboard.tactical.card_strip') as cards:
        context_cards(report,'Transitions','All-area recoveries')
        assert cards.call_args.args[0]==[('Recoveries · all areas','398','All reported outfield players')]
        context_cards(report,'Transitions','Possession losses')
        assert cards.call_args.args[0]==[('Possession losses · all areas','505','All reported outfield players')]
        context_cards(report,'Transitions','Own-third lost duels')
        assert cards.call_args.args[0]==[('Most opponent shots following lost duels','4','2 players tied · selected players')]
        cards.reset_mock()
        context_cards(report,'Transitions','Attacking-third recoveries')
        cards.assert_not_called()


def test_transition_cards_do_not_replace_missing_values_with_zero(report):
    from opponent_intelligence.dashboard.tactical import context_cards
    general=next(k for k in report.tables if k.startswith('02_'))
    report.tables[general].loc[0,'Losses']=float('nan')
    report.tables.pop(next(k for k in report.tables if k.startswith('12_')))
    with patch('opponent_intelligence.dashboard.tactical.card_strip') as cards:
        context_cards(report,'Transitions','Possession losses')
        assert cards.call_args.args[0][0][1]=='—'
        cards.reset_mock()
        context_cards(report,'Transitions','Own-third lost duels')
        cards.assert_not_called()


def test_crossing_selector_keeps_taker_and_receiver_sources_separate(report):
    from opponent_intelligence.dashboard.tactical_models import crossing_options,metric_label
    from opponent_intelligence.dashboard.tactical_charts import contributors
    spec=FOCUSES['Attacking patterns']['Crossing']
    options=crossing_options(report,spec)
    assert options[:2]==[('16','Crosses'),('16','Crosses Successful')]
    assert [metric_label(*choice) for choice in options]==['Cross attempts','Successful crosses','Shots from received crosses','Crosses received','xG from received crosses']
    fig=contributors(scoped_frame(report,'16'),['Crosses'])
    assert any('Cross attempts: 11' in detail and 'Successful crosses: 1' in detail for detail in fig.data[0].customdata)
    app=loaded_app(report)
    app.segmented_control(key='tactical_category').set_value('Attacking patterns').run(timeout=30)
    app.segmented_control(key='tactical_attack').set_value('Crossing').run(timeout=30)
    assert app.selectbox(key='tactical_crossing_metric').value==('16','Crosses')
    for choice in options:
        app.selectbox(key='tactical_crossing_metric').set_value(choice).run(timeout=30)
        assert not app.exception
        population='Selected cross takers' if choice[0]=='16' else 'Selected cross receivers'
        assert any(population in m.value for m in app.markdown)
    report.tables.pop(next(k for k in report.tables if k.startswith('16_')))
    assert all(key=='17' for key,field in crossing_options(report,spec))


def test_all_pitch_dribbling_uses_success_labels_without_renaming_source_fields(report):
    from opponent_intelligence.dashboard.tactical_models import metric_label
    assert metric_label('27','Won')=='Successful dribbles'
    assert metric_label('27','Lost')=='Unsuccessful dribbles'
    assert metric_label('27','Total')=='Dribble attempts'
    assert metric_label('27','Avg per 90')=='Dribbles per 90'
    assert metric_label('03','Won')=='Won'
    app=loaded_app(report)
    app.segmented_control(key='tactical_category').set_value('Attacking patterns').run(timeout=30)
    app.segmented_control(key='tactical_attack').set_value('All-pitch dribbling').run(timeout=30)
    for field in ['Won','Lost']:
        app.selectbox(key='tactical_primary_Attacking patterns_All-pitch dribbling').set_value(field).run(timeout=30)
        assert not app.exception
    assert {'Won','Lost'}.issubset(scoped_frame(report,'27').columns)


def test_all_area_losses_are_report_attempts_minus_wins_without_changing_source(report):
    from opponent_intelligence.dashboard.tactical_models import metric_label
    name=next(k for k in report.tables if k.startswith('03_'))
    original=report.tables[name].copy(deep=True)
    frame=scoped_frame(report,'03')
    assert frame['Defensive Duels Lost'].sum()==104
    assert frame['Defensive Duels Lost'].eq(frame['Defensive Duels']-frame['Defensive Duels Won']).all()
    pd.testing.assert_frame_equal(original,report.tables[name])
    assert metric_label('03','Defensive Duels Lost')=='Defensive duels lost (calculated)'
    assert metric_label('12','Duels Lost')=='Own-third duels lost'
    seed=manual_seed(report,'Defensive organization','All-area duels',FOCUSES['Defensive organization']['All-area duels'])
    assert 'minus' in seed['source_refs'][0]['calculation']
    app=loaded_app(report)
    app.segmented_control(key='tactical_defence').set_value('All-area duels').run(timeout=30)
    app.selectbox(key='tactical_support_metric_Defensive organization_All-area duels').set_value('Defensive Duels Lost').run(timeout=30)
    assert not app.exception


def test_derived_duel_losses_keep_zero_and_reject_unknown_or_inconsistent_inputs(report):
    name=next(k for k in report.tables if k.startswith('03_'))
    report.tables[name]=pd.DataFrame({'Player':['Zero','Missing','Negative','Too many wins','Unknown wins'],
        'Defensive Duels':[0,None,-1,3,5],'Defensive Duels Won':[0,1,0,4,None]})
    frame=scoped_frame(report,'03')
    assert frame['Defensive Duels Lost'].iloc[0]==0
    assert frame['Defensive Duels Lost'].iloc[1:].isna().all()
