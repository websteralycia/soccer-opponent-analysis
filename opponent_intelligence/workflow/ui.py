"""Streamlit workflow forms. Draft preparation never writes a finding."""
import json
from html import escape
import sqlite3
import streamlit as st
from .store import FindingsStore,report_identifier,CATEGORIES,STATUSES,CLASSIFICATIONS
from .evidence import report_metadata,reference_options
from .reports import coach_model,html_report,pdf_report,visual_options,readiness
from . import coach_editor as coach_edits
from .drafts import request_draft,keep_current,replace_current,remember_editor,editor_values,clear_editor,unsaved_work,apply_draft


def prepare_draft(report_id,seed):
    request_draft(st.session_state,report_id,seed)


def remember_working_editor(meta):
    remember_editor(st.session_state,meta)


def keep_draft():
    keep_current(st.session_state)


def confirm_draft_replacement(report_id):
    replace_current(st.session_state,report_id)


def draft_action(result,seed,key,label='Add to scouting findings'):
    ident=report_identifier(result,st.session_state.get('source_id'))
    st.button(label,key='workflow_add_'+key,on_click=prepare_draft,args=(ident,seed),
              help='Prepares an editable draft. Nothing is saved or confirmed until you review and save it.')


def evidence_navigation(filename):
    st.session_state['explorer_table']=filename
    st.session_state['workflow_navigation']='Data Explorer'


def context(result):
    report_id=report_identifier(result,st.session_state.get('source_id'))
    store=FindingsStore();store.register(report_id,report_metadata(result))
    return store,report_id


def save_editor(store,report_id,seed,meta,options):
    values=editor_values(st.session_state,meta)
    try:
        refs=[options[code] for code in values['refs']]
        payload=dict(seed,title=values['title'],category=values['category'],status=values['status'],
            classification=values['classification'],observation=values['observation'],
            supporting_evidence=values['supporting'],contradictory_evidence=values['contradictory'],
            source_refs=refs,match_context=values['context'],video_reference=values['video'],
            interpretation=values['interpretation'],coaching_implication=values['implication'])
        if meta['finding_id']:store.update(report_id,meta['finding_id'],payload)
        else:store.create(report_id,payload)
    except (ValueError,LookupError,sqlite3.Error,OSError) as exc:
        message=('Could not save. Your edits are kept. ' if isinstance(exc,(sqlite3.Error,OSError)) else '')+str(exc)
        st.session_state['workflow_editor_error']={'prefix':meta['prefix'],'message':message}
        return
    if not meta['finding_id']:
        st.session_state.pop('workflow_pending',None)
        st.session_state['workflow_revision']=st.session_state.get('workflow_revision',0)+1
    clear_editor(st.session_state,meta['prefix'])
    st.session_state['workflow_message']='Finding saved locally.'
    proposal=st.session_state.get('workflow_replacement',{})
    if proposal.get('report_id')==report_id and not unsaved_work(st.session_state,report_id):
        apply_draft(st.session_state,report_id,proposal['seed'])
        st.session_state['workflow_message']='Finding saved locally. New observation ready to review.'


def finding_editor(result,store,report_id,finding=None):
    pending=st.session_state.get('workflow_pending',{})
    seed=finding or (pending.get('seed',{}) if pending.get('report_id')==report_id else {})
    suffix=(finding['id'] if finding else 'new_'+str(st.session_state.get('workflow_revision',0)))
    prefix='workflow_editor_'+suffix
    options=reference_options(result)
    default_refs=[]
    for index,ref in enumerate(seed.get('source_refs',[])):
        code=f'Saved evidence {index+1}: {ref.get("table","")} · {ref.get("column","")} · {ref.get("snapshot","")[:90]}'
        options[code]=ref;default_refs.append(code)
    baseline=dict(title=seed.get('title',''),category=seed.get('category','General'),status=seed.get('status','Draft'),
        classification=seed.get('classification') or None,observation=seed.get('observation',''),
        supporting=seed.get('supporting_evidence',''),contradictory=seed.get('contradictory_evidence',''),
        refs=default_refs,context=seed.get('match_context',''),video=seed.get('video_reference',''),
        interpretation=seed.get('interpretation',''),implication=seed.get('coaching_implication',''))
    meta=dict(prefix=prefix,report_id=report_id,finding_id=finding['id'] if finding else None,baseline=baseline)
    st.session_state['workflow_active_editor']=meta
    if finding is None:st.session_state['workflow_new_editor']=meta
    values=editor_values(st.session_state,meta)
    def widget(field):
        return dict(key=prefix+'_'+field,on_change=remember_working_editor,args=(meta,))
    def save_button(key,kind):
        st.button('Save finding',key=key,type=kind,on_click=save_editor,args=(store,report_id,seed,meta,options))
    error=st.session_state.get('workflow_editor_error',{})
    if error.get('prefix')==prefix:st.error(error['message'])
    with st.container(border=True,key='findings_editor_'+suffix,gap='small'):
        heading,action=st.columns([.76,.24],vertical_alignment='center')
        with heading:st.markdown('**Finding Details**')
        with action:save_button(prefix+'_save','primary')
        st.text_input('Finding title',value=values['title'],**widget('title'))
        a,b,c=st.columns(3,gap='small')
        a.selectbox('Tactical category',CATEGORIES,index=CATEGORIES.index(values['category']),**widget('category'))
        b.selectbox('Finding status',STATUSES,index=STATUSES.index(values['status']),**widget('status'))
        choices=[None]+list(CLASSIFICATIONS)
        c.selectbox('Finding classification (optional)',choices,index=choices.index(values['classification']),
            format_func=lambda value:value or 'Unclassified',**widget('classification'),
            help='Analyst-selected finding type. Independent of tactical category and review status; never assigned automatically.')
        st.markdown('**Statistical Evidence**')
        observation,evidence=st.columns(2,gap='medium')
        with observation:st.text_area('Observation or hypothesis',value=values['observation'],height=110,**widget('observation'))
        with evidence:st.text_area('Supporting statistical evidence',value=values['supporting'],height=110,**widget('supporting'))
        with st.expander('Contradictory evidence & linked sources',expanded=bool(values['contradictory'])):
            st.text_area('Contradictory evidence / limitations',value=values['contradictory'],height=80,**widget('contradictory'))
            st.multiselect('Linked source metrics / prepared evidence snapshots',list(options),default=values['refs'],**widget('refs'))
            if seed.get('source_refs'):
                st.markdown('**Prepared evidence: source definitions and snapshots**')
                st.json(seed['source_refs'],expanded=False)
        with st.expander('Video Review',expanded=bool(values['context'] or values['video'])):
            st.text_area('Match context (opponent, date, score or relevant conditions)',value=values['context'],height=80,**widget('context'))
            st.text_input('Video reference / timestamp (PlayBase clip name, path or link)',value=values['video'],**widget('video'))
        with st.expander('Analyst Assessment',expanded=bool(values['interpretation'] or values['implication'])):
            st.text_area('Analyst interpretation',value=values['interpretation'],height=80,**widget('interpretation'))
            st.text_area('Potential coaching implication',value=values['implication'],height=80,**widget('implication'))
        save_button(prefix+'_save_bottom','secondary')


def findings_view(result):
    st.subheader('Scouting findings')
    st.caption('Local analyst workspace · drafts require review and explicit report selection')
    try:store,report_id=context(result)
    except (sqlite3.Error,OSError) as exc:
        st.error(f'Local findings storage unavailable: {exc}');return
    if st.session_state.get('workflow_message'):
        st.success(st.session_state.pop('workflow_message'))
    with st.expander('Report identity and local storage'):
        st.caption(f'{result.team} · {report_id} · persisted in SQLite between sessions')
    proposal=st.session_state.get('workflow_replacement',{})
    if proposal.get('report_id')==report_id:
        st.warning('Unsaved work is open. Keep it, save it, or explicitly replace it with the new observation.')
        st.write('New observation: '+proposal['seed'].get('title','Untitled observation'))
        keep,replace=st.columns(2,gap='small')
        keep.button('Keep current draft',key='workflow_keep_draft',on_click=keep_draft)
        replace.button('Replace unsaved draft',key='workflow_replace_draft',on_click=confirm_draft_replacement,args=(report_id,))
    mode=st.radio('Findings workspace',['Create new','Review / edit'],horizontal=True,key='workflow_mode')
    if mode=='Create new':
        if st.session_state.get('workflow_pending',{}).get('report_id')==report_id:
            st.info('Prepared statistical draft. Review the wording, source scope and status before saving.')
        finding_editor(result,store,report_id)
    else:
        a,b,c=st.columns(3)
        category=a.selectbox('Filter category',['All']+list(CATEGORIES),key='workflow_filter_category')
        status=b.selectbox('Filter status',['All']+list(STATUSES),key='workflow_filter_status')
        classification=c.selectbox('Filter classification',['All',None]+list(CLASSIFICATIONS),format_func=lambda value:value or 'Unclassified',key='workflow_filter_classification')
        findings=store.list(report_id,None if category=='All' else category,None if status=='All' else status,classification)
        if not findings:st.info('No findings match this report and filters.')
        else:
            by_id={f['id']:f for f in findings}
            ident=st.selectbox('Finding',list(by_id),format_func=lambda k:by_id[k]['title']+' · '+by_id[k]['status'],key='workflow_finding')
            finding=by_id[ident]
            for index,ref in enumerate(finding['source_refs']):
                with st.expander(f'Evidence {index+1}: {ref.get("table","")} · {ref.get("column","")}'):
                    st.write(ref)
                    if ref.get('table') in result.tables:
                        st.button('Open supporting evidence',key='workflow_back_'+str(index),on_click=evidence_navigation,args=(ref['table'],))
                    else:st.warning('Source table is unavailable in this extraction. The saved evidence snapshot is retained.')
            included=st.checkbox('Include in coach report',value=finding['included'],key='workflow_include_'+ident)
            if included!=finding['included']:
                order=[f['id'] for f in store.selected(report_id) if f['id']!=ident]
                if included:order.append(ident)
                try:store.select(report_id,order);st.rerun()
                except ValueError as exc:st.error(str(exc))
            finding_editor(result,store,report_id,finding)
            with st.expander('Delete finding'):
                confirm=st.checkbox('Delete this finding permanently',key='workflow_delete_confirm_'+ident)
                if st.button('Delete finding',disabled=not confirm,key='workflow_delete_'+ident):
                    store.delete(report_id,ident);st.rerun()
    all_findings=store.list(report_id)
    if all_findings:
        with st.expander('Local backup and storage'):
            st.caption('This is a single-user local workspace. Back up the database file or download a report-scoped JSON copy. It is not an access-control boundary for a shared server.')
            st.code(str(store.path))
            st.download_button('Download findings backup',json.dumps(dict(report_id=report_id,metadata=report_metadata(result),findings=all_findings),ensure_ascii=False,indent=2).encode(),file_name='scouting_findings.json',mime='application/json',key='workflow_backup')


def remember_coach_editor(report_id,finding):
    coach_edits.remember(st.session_state,report_id,finding)


def save_coach_editor(store,report_id,finding):
    try:store.update(report_id,finding['id'],coach_edits.values(st.session_state,report_id,finding))
    except (ValueError,LookupError,sqlite3.Error,OSError) as exc:
        st.session_state['workflow_coach_error']='Could not save coach wording; your edits are retained. '+str(exc)
        return
    coach_edits.clear(st.session_state,report_id,finding['id'])
    st.session_state.pop('workflow_coach_error',None)
    st.session_state['workflow_coach_message']='Coach wording saved.'


def coach_view(result):
    st.subheader('Coach report')
    from ..identities import identity_html
    from ..dashboard.data import table
    st.html(f'<div class="oi-brand">{identity_html(result.team,size=36)}<b>{escape(result.team)}</b><span class="oi-hint">Up to three analyst-authored findings</span></div>')
    try:store,report_id=context(result)
    except (sqlite3.Error,OSError) as exc:
        st.error(f'Local findings storage unavailable: {exc}');return
    findings=store.list(report_id)
    if not findings:
        st.info('Create and save a finding in Scouting Findings to begin a coach report.');return
    if st.session_state.get('workflow_coach_message'):st.success(st.session_state.pop('workflow_coach_message'))
    if st.session_state.get('workflow_coach_error'):st.error(st.session_state['workflow_coach_error'])
    by_id={f['id']:f for f in findings};selected=store.selected(report_id)
    with st.form('workflow_report_selection'):
        ids=st.multiselect('Findings to include',list(by_id),default=[f['id'] for f in selected],format_func=lambda k:by_id[k]['title'],max_selections=3,key='workflow_coach_selection_ids')
        submitted=st.form_submit_button('Save report selection',key='workflow_report_selection_save')
    if submitted:store.select(report_id,ids);st.rerun()
    selected=store.selected(report_id);ids=[f['id'] for f in selected]
    dirty=[f for f in findings if coach_edits.changed(st.session_state,report_id,f)]
    dirty_notice=st.empty()
    if dirty:
        hidden=sum(f['id'] not in ids for f in dirty)
        dirty_notice.warning(f'{len(dirty)} finding(s) have unsaved coach edits. Preview and exports use saved wording.'+
                   (f' Edits for {hidden} excluded finding(s) are retained; reselect them to continue.' if hidden else ''))
    if not selected:
        st.info('Choose up to three findings. A one-finding draft can also be previewed.');return
    for index,finding in enumerate(selected):
        unsaved=coach_edits.changed(st.session_state,report_id,finding)
        with st.expander(f'{index+1}. {finding["title"]} · {finding["status"]}',expanded=False):
            if len(ids)>1:
                a,b=st.columns(2,gap='small')
                if a.button('Move up',disabled=index==0,key='workflow_up_'+finding['id']):
                    ids[index-1],ids[index]=ids[index],ids[index-1];store.select(report_id,ids);st.rerun()
                if b.button('Move down',disabled=index==len(ids)-1,key='workflow_down_'+finding['id']):
                    ids[index+1],ids[index]=ids[index],ids[index+1];store.select(report_id,ids);st.rerun()
            value=coach_edits.values(st.session_state,report_id,finding)
            def widget(field):return dict(key=coach_edits.widget_key(finding['id'],field),on_change=remember_coach_editor,args=(report_id,finding))
            st.text_area('Coach-facing summary',value=value['coach_summary'],height=80,**widget('coach_summary'))
            observation,consideration=st.columns(2,gap='medium')
            with observation:st.text_area('Tactical observation — analyst authored',value=value['coach_observation'],height=110,**widget('coach_observation'))
            with consideration:st.text_area('Coaching consideration — analyst authored',value=value['coach_consideration'],height=110,**widget('coach_consideration'))
            st.button('Save coach wording',key='workflow_coach_save_'+finding['id'],type='primary',on_click=save_coach_editor,args=(store,report_id,finding))
    model=coach_model(result,store.selected(report_id),st.session_state.get('source_id'))
    issues=readiness(model)
    if issues:
        st.warning('Draft brief — incomplete coaching content or unresolved review status. Draft exports are allowed and clearly marked.')
        with st.expander('Report readiness'):
            for issue in issues:st.write(issue['title']+' — '+', '.join(issue['missing']))
    else:st.success('Ready: selected findings have coach wording and Confirmed review status.')
    markup=html_report(model)
    import streamlit.components.v1 as components
    with st.expander('Report preview',expanded=False):
        components.html(markup,height=650,scrolling=True)
    st.download_button('Download shareable HTML',markup.encode('utf-8'),file_name='opponent_scouting_report.html',mime='text/html',key='workflow_html',
        help='Exports saved wording. Incomplete content and review status remain marked as Draft.')
    import hashlib
    digest=hashlib.sha256(markup.encode()).hexdigest()
    if st.button('Prepare PDF export',key='workflow_prepare_pdf'):
        try:st.session_state['workflow_pdf']=(report_id,digest,pdf_report(model))
        except ImportError:st.error('PDF export needs ReportLab. HTML export remains available.')
    cached=st.session_state.get('workflow_pdf')
    if cached and cached[:2]==(report_id,digest):
        st.download_button('Download PDF',cached[2],file_name='opponent_scouting_report.pdf',mime='application/pdf',key='workflow_pdf_download')
