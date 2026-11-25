"""Compact editor and session-only protection; all DBs are isolated by conftest."""
from copy import deepcopy
from opponent_intelligence.workflow.drafts import request_draft,keep_current,replace_current,remember_editor
from opponent_intelligence.workflow.store import FindingsStore,report_identifier
from test_dashboard import report,loaded_app
from test_workflow import setup_store,payload


def prefix(app):
    return 'workflow_editor_new_'+str(app.session_state.get('workflow_revision',0))


def send_overview(app,index=0):
    app.segmented_control(key='overview_primary').set_value('Statistical Observations').run(timeout=30)
    app.button(key='workflow_add_overview'+('_'+str(index) if index else '')).click().run(timeout=30)
    assert not app.exception


def test_draft_replacement_requires_explicit_confirmation_and_preserves_values():
    state={}
    first={'title':'First','observation':'Source statement'}
    assert request_draft(state,'report',first)
    revision=state['workflow_revision']
    meta=dict(prefix='workflow_editor_new_1',report_id='report',finding_id=None,
              baseline={'title':'First','observation':'Source statement'})
    state['workflow_active_editor']=meta;state['workflow_new_editor']=meta
    state[meta['prefix']+'_title']='Analyst wording'
    remember_editor(state,meta)
    # Simulate widget cleanup while visiting another view.
    state.pop(meta['prefix']+'_title')
    second={'title':'Second'}
    assert not request_draft(state,'report',second)
    assert state['workflow_pending']['seed']==first and state['workflow_revision']==revision
    keep_current(state)
    assert state['workflow_editor_cache'][meta['prefix']]['title']=='Analyst wording'
    assert not request_draft(state,'report',second)
    replace_current(state,'other report')
    assert state['workflow_pending']['seed']==first
    replace_current(state,'report')
    assert state['workflow_pending']['seed']==second
    assert meta['prefix'] not in state['workflow_editor_cache']


def test_manual_create_all_fields_and_bottom_save(report):
    app=loaded_app(report);key=prefix(app)
    app.text_input(key=key+'_title').set_value('Manual finding')
    app.selectbox(key=key+'_category').set_value('Transitions')
    app.selectbox(key=key+'_status').set_value('Needs Video Review')
    app.selectbox(key=key+'_classification').set_value('Potential Weakness')
    for suffix,value in [('observation','Observed pattern'),('supporting','Recorded numbers'),('contradictory','Possible counterexample'),
                         ('context','One match; trailing'),('interpretation','Analyst hypothesis'),('implication','Review with staff')]:
        app.text_area(key=key+'_'+suffix).set_value(value)
    app.text_input(key=key+'_video').set_value('PlayBase: clip 1, 63:20; clip 2, 74:00')
    app.button(key=key+'_save_bottom').click().run(timeout=30)
    assert not app.exception
    store,ident=setup_store(report);saved=store.list(ident)[0]
    assert saved['title']=='Manual finding' and saved['status']=='Needs Video Review'
    assert saved['classification']=='Potential Weakness' and not saved['included']
    assert saved['video_reference']=='PlayBase: clip 1, 63:20; clip 2, 74:00'
    assert saved['contradictory_evidence']=='Possible counterexample' and saved['coach_summary']==''
    assert {'Video Review','Analyst Assessment','Contradictory evidence & linked sources'}.issubset({e.label for e in app.expander})


def test_prefilled_evidence_from_all_three_pages_is_saved_unchanged(report):
    app=loaded_app(report);store,ident=setup_store(report)
    send_overview(app)
    for source in ['overview','player','tactical']:
        if source=='player':
            app.segmented_control(key='player_primary').set_value('Statistical Observations').run(timeout=30)
            app.button(key='workflow_add_player').click().run(timeout=30)
        elif source=='tactical':
            app.segmented_control(key='tactical_category').set_value('Transitions').run(timeout=30)
            app.button(key='workflow_add_tactical_evidence_0').click().run(timeout=30)
        seed=deepcopy(app.session_state['workflow_pending']['seed']);key=prefix(app)
        assert app.text_area(key=key+'_observation').value==seed['observation']
        assert app.text_area(key=key+'_supporting').value==seed['supporting_evidence']
        assert app.selectbox(key=key+'_classification').value is None
        app.button(key=key+'_save').click().run(timeout=30)
        assert not app.exception
        saved=next(f for f in store.list(ident) if f['title']==seed['title'])
        assert saved['source_refs']==seed['source_refs']
        assert saved['observation']==seed['observation'] and saved['status']=='Draft'
        assert saved['category']==seed['category'] and saved['visual_key']==seed.get('visual_key','')
    assert len(store.list(ident))==3


def test_keep_then_save_current_draft_before_opening_incoming_observation(report):
    app=loaded_app(report);send_overview(app);key=prefix(app)
    old_seed=deepcopy(app.session_state['workflow_pending']['seed'])
    app.text_input(key=key+'_title').set_value('Analyst-edited first finding').run(timeout=30)
    app.text_area(key=key+'_observation').set_value('My working observation').run(timeout=30)
    app.selectbox(key=key+'_classification').set_value('Tactical Tendency').run(timeout=30)
    revision=app.session_state['workflow_revision']
    send_overview(app,1)
    assert any('Unsaved work' in w.value for w in app.warning)
    assert app.session_state['workflow_revision']==revision
    assert app.session_state['workflow_pending']['seed']==old_seed
    app.button(key='workflow_keep_draft').click().run(timeout=30)
    assert app.text_input(key=key+'_title').value=='Analyst-edited first finding'
    assert app.text_area(key=key+'_observation').value=='My working observation'
    store,ident=setup_store(report);assert not store.list(ident)
    send_overview(app,1)
    incoming=deepcopy(app.session_state['workflow_replacement']['seed'])
    app.button(key=key+'_save').click().run(timeout=30)
    assert not app.exception
    saved=store.list(ident)[0]
    assert saved['title']=='Analyst-edited first finding' and saved['classification']=='Tactical Tendency'
    assert saved['source_refs']==old_seed['source_refs']
    assert app.session_state['workflow_pending']['seed']==incoming
    assert app.text_input(key=prefix(app)+'_title').value==incoming['title']
    assert 'workflow_replacement' not in app.session_state


def test_replace_discards_only_explicitly_confirmed_unsaved_draft(report):
    app=loaded_app(report);send_overview(app);old=prefix(app)
    app.text_input(key=old+'_title').set_value('Unsaved analyst text').run(timeout=30)
    send_overview(app,1)
    incoming=deepcopy(app.session_state['workflow_replacement']['seed'])
    app.button(key='workflow_replace_draft').click().run(timeout=30)
    assert not app.exception
    assert app.session_state['workflow_pending']['seed']==incoming
    assert app.text_input(key=prefix(app)+'_title').value==incoming['title']
    store,ident=setup_store(report);assert not store.list(ident)


def test_manual_unsaved_edits_are_protected_from_first_statistical_draft(report):
    app=loaded_app(report);key=prefix(app)
    app.text_input(key=key+'_title').set_value('Manual work in progress').run(timeout=30)
    app.text_area(key=key+'_observation').set_value('My notes').run(timeout=30)
    send_overview(app)
    assert 'workflow_pending' not in app.session_state
    assert app.text_input(key=key+'_title').value=='Manual work in progress'
    app.button(key='workflow_keep_draft').click().run(timeout=30)
    app.button(key=key+'_save').click().run(timeout=30)
    assert not app.exception
    store,ident=setup_store(report)
    assert store.list(ident)[0]['observation']=='My notes'


def test_switching_saved_findings_preserves_working_edits_and_coach_selection(report):
    store,ident=setup_store(report)
    first=store.create(ident,payload('First'));second=store.create(ident,payload('Second'))
    store.select(ident,[second['id'],first['id']])
    app=loaded_app(report)
    app.radio(key='workflow_mode').set_value('Review / edit').run(timeout=30)
    app.selectbox(key='workflow_finding').set_value(first['id']).run(timeout=30)
    key='workflow_editor_'+first['id']
    app.text_input(key=key+'_title').set_value('Unsaved first edit').run(timeout=30)
    app.selectbox(key='workflow_finding').set_value(second['id']).run(timeout=30)
    app.selectbox(key='workflow_finding').set_value(first['id']).run(timeout=30)
    assert not app.exception
    assert app.text_input(key=key+'_title').value=='Unsaved first edit'
    assert store.get(ident,first['id'])['title']=='First'
    app.button(key=key+'_save').click().run(timeout=30)
    assert not app.exception
    assert store.get(ident,first['id'])['title']=='Unsaved first edit'
    assert store.get(ident,first['id'])['coach_summary']==first['coach_summary']
    assert [f['id'] for f in store.selected(ident)]==[second['id'],first['id']]


def test_unsaved_saved_record_edits_are_protected_when_sending_a_draft(report):
    store,ident=setup_store(report);finding=store.create(ident,payload())
    app=loaded_app(report)
    app.radio(key='workflow_mode').set_value('Review / edit').run(timeout=30)
    key='workflow_editor_'+finding['id']
    app.text_input(key=key+'_title').set_value('Unsaved reviewed title').run(timeout=30)
    send_overview(app)
    assert app.radio(key='workflow_mode').value=='Review / edit'
    app.button(key='workflow_keep_draft').click().run(timeout=30)
    assert app.text_input(key=key+'_title').value=='Unsaved reviewed title'
    assert store.get(ident,finding['id'])['title']==finding['title']


def test_failed_save_preserves_edits_and_pending_replacement(report):
    import sqlite3
    from unittest.mock import patch
    app=loaded_app(report);send_overview(app);key=prefix(app)
    app.text_input(key=key+'_title').set_value('Keep my edited title').run(timeout=30)
    send_overview(app,1)
    with patch('opponent_intelligence.workflow.store.FindingsStore.create',side_effect=sqlite3.OperationalError('database or disk is full')):
        app.button(key=key+'_save').click().run(timeout=30)
    assert not app.exception
    assert any('Your edits are kept' in e.value for e in app.error)
    assert app.text_input(key=key+'_title').value=='Keep my edited title'
    assert 'workflow_replacement' in app.session_state
    store,ident=setup_store(report);assert not store.list(ident)
    app.button(key=key+'_save').click().run(timeout=30)
    assert not app.exception
    assert store.list(ident)[0]['title']=='Keep my edited title'
    assert 'workflow_replacement' not in app.session_state
