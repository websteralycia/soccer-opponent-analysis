"""Session-only editor state and one explicit draft-replacement request.

No persistence or evidence generation lives here. Saved findings keep their
existing SQLite schema; working field values are not saved until Save finding.
"""
EDITOR_FIELDS=('title','category','status','classification','observation','supporting',
               'contradictory','refs','context','video','interpretation','implication')


def editor_values(state,meta):
    cached=state.get('workflow_editor_cache',{}).get(meta['prefix'],{})
    return {field:state.get(meta['prefix']+'_'+field,cached.get(field,default))
            for field,default in meta['baseline'].items()}


def editor_changed(state,meta,report_id):
    return bool(meta and meta.get('report_id')==report_id and editor_values(state,meta)!=meta['baseline'])


def remember_editor(state,meta):
    cache=dict(state.get('workflow_editor_cache',{}))
    cache[meta['prefix']]=editor_values(state,meta)
    state['workflow_editor_cache']=cache


def clear_editor(state,prefix):
    cache=dict(state.get('workflow_editor_cache',{}));cache.pop(prefix,None)
    state['workflow_editor_cache']=cache
    for field in EDITOR_FIELDS:state.pop(prefix+'_'+field,None)
    for key in ['workflow_active_editor','workflow_new_editor','workflow_editor_error']:
        if state.get(key,{}).get('prefix')==prefix:state.pop(key,None)


def unsaved_work(state,report_id):
    return (state.get('workflow_pending',{}).get('report_id')==report_id or
            editor_changed(state,state.get('workflow_new_editor'),report_id) or
            editor_changed(state,state.get('workflow_active_editor'),report_id))


def apply_draft(state,report_id,seed):
    active=state.get('workflow_active_editor')
    if editor_changed(state,active,report_id):clear_editor(state,active['prefix'])
    new_editor=state.get('workflow_new_editor')
    if new_editor and new_editor.get('report_id')==report_id:clear_editor(state,new_editor['prefix'])
    state.pop('workflow_replacement',None)
    state['workflow_pending']={'report_id':report_id,'seed':seed}
    state['workflow_mode']='Create new'
    state['workflow_revision']=state.get('workflow_revision',0)+1
    state['workflow_navigation']='Scouting Findings'


def request_draft(state,report_id,seed):
    if unsaved_work(state,report_id):
        state['workflow_replacement']={'report_id':report_id,'seed':seed}
        state['workflow_navigation']='Scouting Findings'
        return False
    apply_draft(state,report_id,seed)
    return True


def keep_current(state):
    state.pop('workflow_replacement',None)


def replace_current(state,report_id):
    proposal=state.get('workflow_replacement',{})
    if proposal.get('report_id')!=report_id:return
    apply_draft(state,report_id,proposal['seed'])
