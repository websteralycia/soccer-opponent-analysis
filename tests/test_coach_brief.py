"""Coach brief layout, readiness, saved content and session edit preservation."""
from copy import deepcopy
from io import BytesIO
import json
import pytest
from pypdf import PdfReader
from opponent_intelligence.workflow.reports import coach_model,html_report,pdf_report,readiness,source_records,visual_parts
from opponent_intelligence.workflow import coach_editor
from test_dashboard import report,loaded_app,PROJECT
from test_workflow import setup_store,payload


def model_for(report,count=1,visual=False):
    store,ident=setup_store(report)
    rows=[]
    for index in range(count):
        f=store.create(ident,dict(payload('QA finding '+str(index+1)),status='Confirmed',classification=None))
        rows.append(f)
    store.select(ident,[f['id'] for f in rows])
    return coach_model(report,store.selected(ident))


@pytest.mark.parametrize('count',[0,1,2,3])
def test_brief_supports_zero_to_three_without_identifier_only_pages(report,count):
    model=model_for(report,count)
    data=pdf_report(model);pages=PdfReader(BytesIO(data)).pages
    text='\n'.join(p.extract_text() for p in pages)
    assert 'opposition scouting brief' in text
    assert len(pages)<=3
    assert all(len(p.extract_text().strip())>180 for p in pages)
    if count:assert 'QA finding '+str(count) in text
    else:assert 'No findings selected.' in text


def test_readiness_is_nonblocking_and_never_changes_status_or_writes_wording(report):
    model=model_for(report)
    assert not readiness(model)
    item=model['findings'][0];item.update(coach_summary='',coach_observation='',interpretation='',coach_consideration='',status='Needs Video Review')
    before=deepcopy(model)
    issues=readiness(model)
    assert len(issues[0]['missing'])==4
    assert 'Draft brief' in html_report(model)
    assert 'Draft brief' in '\n'.join(p.extract_text() for p in PdfReader(BytesIO(pdf_report(model))).pages)
    assert model==before
    item['interpretation']='Existing analyst-authored interpretation'
    assert 'tactical observation' not in readiness(model)[0]['missing']


def test_sources_deduplicate_display_text_without_changing_saved_snapshots(report):
    model=model_for(report);f=model['findings'][0]
    f['supporting_evidence']='Recorded source count.'
    ref=dict(table='03_player_duels_set_pieces.csv',column='Defensive Duels',snapshot='Recorded source count. Selected population; 10 eligible.',
             scope='All reported outfield players',page='4',calculation='Reported count',definition='Report definition')
    f['source_refs']=[deepcopy(ref),deepcopy(ref)]
    records=source_records(f)
    assert len(records)==1 and records[0]['display_snapshot']=='Selected population; 10 eligible.'
    assert f['source_refs']==[ref,ref]
    output=html_report(model)
    assert output.count('Recorded source count.')==1
    assert '10 eligible' in output and 'Report definition' in output


def test_registered_visuals_remain_available_but_are_not_presented_in_reports(report):
    import hashlib
    from opponent_intelligence.workflow.evidence import report_metadata
    from opponent_intelligence.workflow.store import FindingsStore,report_identifier
    fingerprint=hashlib.sha256((PROJECT.parent/'00_assignments/assignment_4/AFC Ajax.pdf').read_bytes()).hexdigest()
    store=FindingsStore();ident=report_identifier(report,fingerprint);store.register(ident,report_metadata(report))
    f=store.create(ident,dict(payload(),visual_key='dribbles',status='Confirmed',highlight_players=['Lucas Rosa']))
    store.select(ident,[f['id']]);model=coach_model(report,store.selected(ident),fingerprint)
    asset=model['findings'][0]['visual']
    assert len(visual_parts(asset))==2
    assert visual_parts(asset)[0]==asset['header_path'] and visual_parts(asset)[1]==asset['display_path']
    output=html_report(model)
    assert '<img' not in output and 'data:image' not in output
    reader=PdfReader(BytesIO(pdf_report(model)))
    assert all(not list(page.images) for page in reader.pages)
    assert model['findings'][0]['highlight_players']==['Lucas Rosa']
    assert store.get(ident,f['id'])['visual_key']=='dribbles'


def test_long_content_and_video_keep_their_text_and_page_context(report):
    model=model_for(report)
    f=model['findings'][0]
    f['tactical_observation']=('Long analyst-authored layout fixture. '*500)+' END OF LONG OBSERVATION'
    f['video_reference']='QA PlayBase clip A 12:30; clip B 63:20'
    reader=PdfReader(BytesIO(pdf_report(model)))
    text='\n'.join(p.extract_text() for p in reader.pages)
    assert 'END OF LONG OBSERVATION' in ' '.join(text.split()) and 'clip B 63:20' in text
    assert all('Ajax · opposition brief' in p.extract_text() for p in reader.pages)
    assert len(reader.pages)>1


def test_coach_edit_cache_is_report_scoped_and_retained_without_saving():
    f=dict(id='f1',coach_summary='Saved',coach_observation='',coach_consideration='',visual_key='',highlight_players=[])
    state={coach_editor.widget_key('f1','coach_summary'):'Unsaved'}
    coach_editor.remember(state,'report-a',f)
    state.pop(coach_editor.widget_key('f1','coach_summary'))
    assert coach_editor.changed(state,'report-a',f)
    assert coach_editor.values(state,'report-b',f)['coach_summary']=='Saved'
    assert f['coach_summary']=='Saved'
    coach_editor.clear(state,'report-a','f1')
    assert not coach_editor.changed(state,'report-a',f)


def test_unsaved_coach_wording_survives_exclusion_reselection_and_reopening(report):
    store,ident=setup_store(report)
    first=store.create(ident,payload('First'));second=store.create(ident,payload('Second'))
    store.select(ident,[first['id'],second['id']])
    app=loaded_app(report)
    key=coach_editor.widget_key(first['id'],'coach_summary')
    app.text_area(key=key).set_value('Unsaved coach wording').run(timeout=30)
    assert store.get(ident,first['id'])['coach_summary']==first['coach_summary']
    app.multiselect(key='workflow_coach_selection_ids').set_value([second['id']])
    app.button(key='workflow_report_selection_save').click().run(timeout=30)
    assert not app.exception
    assert any('excluded finding' in w.value for w in app.warning)
    app.multiselect(key='workflow_coach_selection_ids').set_value([second['id'],first['id']])
    app.button(key='workflow_report_selection_save').click().run(timeout=30)
    assert app.text_area(key=key).value=='Unsaved coach wording'
    app.button(key='workflow_coach_save_'+first['id']).click().run(timeout=30)
    assert not app.exception
    assert store.get(ident,first['id'])['coach_summary']=='Unsaved coach wording'
    assert store.get(ident,first['id'])['supporting_evidence']==first['supporting_evidence']
    assert [f['id'] for f in store.selected(ident)]==[second['id'],first['id']]
    fresh=loaded_app(report)
    assert fresh.text_area(key=key).value=='Unsaved coach wording'
    fresh.multiselect(key='workflow_coach_selection_ids').set_value([])
    fresh.button(key='workflow_report_selection_save').click().run(timeout=30)
    assert not fresh.exception and not store.selected(ident)


def test_reordering_with_unsaved_edits_never_overwrites_saved_fields(report):
    store,ident=setup_store(report)
    first=store.create(ident,payload('First'));second=store.create(ident,payload('Second'))
    store.select(ident,[first['id'],second['id']]);app=loaded_app(report)
    key=coach_editor.widget_key(first['id'],'coach_consideration')
    app.text_area(key=key).set_value('Work in progress').run(timeout=30)
    app.button(key='workflow_down_'+first['id']).click().run(timeout=30)
    assert not app.exception and app.text_area(key=key).value=='Work in progress'
    assert store.get(ident,first['id'])['coach_consideration']==first['coach_consideration']
    assert [r['id'] for r in store.selected(ident)]==[second['id'],first['id']]


def test_new_finding_page_header_uses_that_finding_not_the_previous_one(report):
    model=model_for(report,3)
    pages=PdfReader(BytesIO(pdf_report(model))).pages
    assert len(pages)>1
    assert 'Ajax · opposition brief · QA finding 3' in pages[-1].extract_text()
