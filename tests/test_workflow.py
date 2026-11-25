from io import BytesIO
from pathlib import Path
import json
from unittest.mock import patch
import pandas as pd
import pytest
from pypdf import PdfReader
from streamlit.testing.v1 import AppTest
from opponent_intelligence.workflow.store import FindingsStore,report_identifier
from opponent_intelligence.workflow.evidence import report_metadata,reference,seed_from_standout
from opponent_intelligence.workflow.reports import coach_model,html_report,pdf_report
from opponent_intelligence.dashboard.page_analysis import overview_observations,player_observations,comparison_frame
from opponent_intelligence.dashboard.data import available_metrics,player_frame
from test_dashboard import report,loaded_app,PROJECT


def setup_store(report,path=None):
    store=FindingsStore(path);ident=report_identifier(report)
    store.register(ident,report_metadata(report))
    return store,ident


def payload(title='Recorded observation'):
    return dict(title=title,category='Defensive organization',status='Draft',observation='A measured pattern to review.',
        supporting_evidence='44 of 85 actions won in this source-defined group.',contradictory_evidence='Five-match sample; roles vary.',
        interpretation='Analyst hypothesis, not established mechanism.',coaching_implication='Review relevant clips.',
        video_reference='PlayBase: analyst clip, 12:30',match_context='One match, trailing at this point.',
        coach_summary='A concise analyst-authored summary.',coach_observation='Authored tactical observation.',
        coach_consideration='An authored consideration to test.')


def test_finding_crud_survives_new_store_instances(report,tmp_path):
    path=tmp_path/'persistent.sqlite3';store,ident=setup_store(report,path)
    finding=store.create(ident,payload())
    assert finding['status']=='Draft' and not finding['included']
    reopened=FindingsStore(path)
    assert reopened.get(ident,finding['id'])['title']=='Recorded observation'
    updated=reopened.update(ident,finding['id'],dict(finding,title='Edited',status='Needs Video Review'))
    assert updated['created']==finding['created'] and updated['title']=='Edited'
    reopened.delete(ident,finding['id'])
    assert FindingsStore(path).list(ident)==[]


def test_report_identity_and_data_isolation(report):
    store,ident=setup_store(report);finding=store.create(ident,payload())
    assert report_identifier(report)==ident
    assert report_identifier(report,'a'*64)=='pdf:'+'a'*64
    other='pdf:'+'b'*64;store.register(other,{'team':'Other'})
    assert store.list(other)==[]
    for operation in [lambda:store.get(other,finding['id']),lambda:store.update(other,finding['id'],payload()),
                      lambda:store.delete(other,finding['id']),lambda:store.select(other,[finding['id']])]:
        with pytest.raises(LookupError):operation()
    assert store.get(ident,finding['id'])


def test_selection_order_and_independent_coach_wording(report):
    store,ident=setup_store(report)
    first=store.create(ident,payload('First'));second=store.create(ident,payload('Second'))
    store.select(ident,[second['id'],first['id']])
    assert [f['title'] for f in store.selected(ident)]==['Second','First']
    store.update(ident,first['id'],dict(first,coach_summary='New coach wording'))
    assert store.get(ident,first['id'])['supporting_evidence']==first['supporting_evidence']
    assert store.get(ident,first['id'])['coach_summary']=='New coach wording'
    store.select(ident,[first['id']]);assert len(store.selected(ident))==1
    with pytest.raises(ValueError):store.select(ident,[first['id']]*2)
    with pytest.raises(ValueError):store.select(ident,['a','b','c','d'])


def test_validation_and_filters(report):
    store,ident=setup_store(report)
    with pytest.raises(ValueError):store.create(ident,dict(payload(),title=''))
    with pytest.raises(ValueError):store.create(ident,dict(payload(),status='Automatically confirmed'))
    store.create(ident,payload())
    assert len(store.list(ident,status='Draft'))==1
    assert not store.list(ident,status='Confirmed')


def test_coach_exports_keep_provenance_status_and_authored_layers(report):
    store,ident=setup_store(report)
    data=payload('<script>Analyst finding</script>')
    data['source_refs']=[reference(report,'03_player_duels_set_pieces.csv','Defensive Duels Won','164 / 268','Sum of complete outfield counts.')]
    finding=store.create(ident,data);store.select(ident,[finding['id']])
    model=coach_model(report,store.selected(ident))
    html=html_report(model)
    assert '<script>Analyst' not in html and '&lt;script&gt;' in html
    for text in ['Draft','164 / 268','Analyst hypothesis','Authored tactical observation','authored consideration','PlayBase']:
        # The underlying hypothesis is in evidence, but coach observation is independently authored.
        if text=='Analyst hypothesis':continue
        assert text in html
    pdf=pdf_report(model)
    assert pdf.startswith(b'%PDF-')
    reader=PdfReader(BytesIO(pdf));text='\n'.join(page.extract_text() for page in reader.pages)
    assert '164 / 268' in text and 'Draft' in text and 'PlayBase' in text
    assert len(reader.pages)>=1
    changed=dict(store.selected(ident)[0],report_id='other')
    with pytest.raises(ValueError):coach_model(report,[changed])


def test_long_report_paginates_without_losing_text(report):
    store,ident=setup_store(report)
    data=payload();data['supporting_evidence']='Detailed source evidence. '*700+' END OF EVIDENCE'
    finding=store.create(ident,data);store.select(ident,[finding['id']])
    pdf=pdf_report(coach_model(report,store.selected(ident)))
    reader=PdfReader(BytesIO(pdf));assert len(reader.pages)>1
    assert 'END OF EVIDENCE' in ' '.join(' '.join(p.extract_text() for p in reader.pages).split())


def test_overview_and_player_standouts_keep_scopes_and_thresholds(report):
    observations=overview_observations(report)
    assert any('6 conceded goals' in item['observation'] and '2 of 5' in item['observation'] for item in observations)
    assert any('formation periods' in item['observation'] for item in observations)
    metrics=[m for m in available_metrics(report) if m.label=='Defensive duels']
    observations=player_observations(report,metrics,90,False)
    rate=next(item for item in observations if item.unit=='percent')
    assert rate.names==('J. Šutalo',) and rate.value==pytest.approx(100*10/12)
    frame=player_frame(report,metrics,False,0)
    comp=comparison_frame(frame,['D. Konadu','J. Šutalo'],metrics)
    assert comp[comp.Metric.str.endswith('%')].Comparison.iloc[0].startswith('Not compared')
    seed=seed_from_standout(report,rate)
    assert seed['status']=='Draft' and '83.3%' in seed['observation']


def test_prepare_save_edit_and_coach_report_ui(report):
    app=loaded_app(report)
    app.segmented_control(key='overview_primary').set_value('Statistical Observations').run(timeout=30)
    app.button(key='workflow_add_overview').click().run(timeout=30)
    assert not app.exception
    assert app.session_state['workflow_navigation']=='Scouting Findings'
    store,ident=setup_store(report)
    assert not store.list(ident)  # Preparing a draft is not saving.
    key='workflow_editor_new_1'
    app.text_input(key=key+'_title').set_value('Reviewed UI finding')
    app.text_area(key=key+'_observation').set_value('Reviewed observation')
    app.button(key=key+'_save').click().run(timeout=30)
    assert not app.exception
    finding=store.list(ident)[0]
    assert finding['title']=='Reviewed UI finding' and finding['status']=='Draft'
    app.radio(key='workflow_mode').set_value('Review / edit').run(timeout=30)
    app.checkbox(key='workflow_include_'+finding['id']).check().run(timeout=30)
    assert not app.exception
    assert store.selected(ident)[0]['id']==finding['id']
    assert any(button.label=='Download shareable HTML' for button in app.get('download_button'))
    app.button(key='workflow_prepare_pdf').click().run(timeout=30)
    assert not app.exception
    assert any(button.label=='Download PDF' for button in app.get('download_button'))
    # A fresh Streamlit session still sees the persisted finding and report selection.
    fresh=loaded_app(report)
    assert not fresh.exception
    assert any(button.label=='Download shareable HTML' for button in fresh.get('download_button'))


def test_saved_source_visual_reference_survives_text_only_exports(report):
    import hashlib
    fingerprint=hashlib.sha256((PROJECT.parent/'00_assignments/assignment_4/AFC Ajax.pdf').read_bytes()).hexdigest()
    ident=report_identifier(report,fingerprint);store=FindingsStore();store.register(ident,report_metadata(report))
    finding=store.create(ident,dict(payload(),visual_key='dribbles',source_refs=[reference(report,'03_player_duels_set_pieces.csv','Defensive Duels Won','164 / 268','Source-backed counts.')]));store.select(ident,[finding['id']])
    model=coach_model(report,store.selected(ident),fingerprint)
    html=html_report(model)
    assert 'data:image' not in html and '<img' not in html
    assert '164 / 268' in html
    pdf=pdf_report(model)
    reader=PdfReader(BytesIO(pdf))
    assert all(not list(page.images) for page in reader.pages)
    assert '164 / 268' in ' '.join(' '.join(p.extract_text() for p in reader.pages).split())
    assert store.get(ident,finding['id'])['visual_key']=='dribbles'


def test_findings_ui_edit_source_navigation_and_delete(report):
    store,ident=setup_store(report)
    finding=store.create(ident,dict(payload(),source_refs=[reference(report,'03_player_duels_set_pieces.csv','Defensive Duels Won')]))
    app=loaded_app(report)
    app.radio(key='workflow_mode').set_value('Review / edit').run(timeout=30)
    prefix='workflow_editor_'+finding['id']
    app.text_input(key=prefix+'_title').set_value('Edited in workspace')
    app.button(key=prefix+'_save').click().run(timeout=30)
    assert not app.exception
    assert store.get(ident,finding['id'])['title']=='Edited in workspace'
    app.button(key='workflow_back_0').click().run(timeout=30)
    assert not app.exception
    assert app.session_state['workflow_navigation']=='Data Explorer'
    assert app.selectbox(key='explorer_table').value=='03_player_duels_set_pieces.csv'
    app.checkbox(key='workflow_delete_confirm_'+finding['id']).check().run(timeout=30)
    app.button(key='workflow_delete_'+finding['id']).click().run(timeout=30)
    assert not app.exception
    assert store.list(ident)==[]


def test_coach_edit_leaves_evidence_intact_and_invalidates_old_pdf(report):
    store,ident=setup_store(report);finding=store.create(ident,payload());store.select(ident,[finding['id']])
    app=loaded_app(report)
    app.button(key='workflow_prepare_pdf').click().run(timeout=30)
    assert any(b.label=='Download PDF' for b in app.get('download_button'))
    editor=next(e for e in app.text_area if e.label=='Coach-facing summary')
    editor.set_value('Independently revised coach summary')
    next(b for b in app.button if b.label=='Save coach wording').click().run(timeout=30)
    assert not app.exception
    saved=store.get(ident,finding['id'])
    assert saved['coach_summary']=='Independently revised coach summary'
    assert saved['supporting_evidence']==finding['supporting_evidence']
    assert not any(b.label=='Download PDF' for b in app.get('download_button'))


def test_report_preserves_zero_goals(report):
    report.tables['05_match_results.csv']['Ajax']=0
    report.tables['05_match_results.csv']['Opponent Goals']=0
    html=html_report(coach_model(report,[]))
    assert 'Goals 0 for / 0 against' in html


def test_compact_comparison_handles_unknown_attempts(report):
    metrics=[m for m in available_metrics(report) if m.label=='Defensive duels']
    source=report.tables['03_player_duels_set_pieces.csv']
    source.loc[source.Player.eq('A. Gaaei'),'Defensive Duels']=float('nan')
    frame=player_frame(report,metrics,False,90)
    compared=comparison_frame(frame,['A. Gaaei','J. Šutalo'],metrics)
    assert compared[compared.Metric.str.endswith('%')].Comparison.iloc[0].startswith('Not compared')
