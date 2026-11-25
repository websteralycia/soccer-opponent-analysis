"""Session-only coach edits, retained across selection/order changes."""
FIELDS=('coach_summary','coach_observation','coach_consideration')


def widget_key(finding_id,field):return 'workflow_coach_'+finding_id+'_'+field


def values(state,report_id,finding):
    cached=state.get('workflow_coach_edits',{}).get(report_id,{}).get(finding['id'],{})
    return {field:state.get(widget_key(finding['id'],field),cached.get(field,finding.get(field,[] if field=='highlight_players' else '')))
            for field in FIELDS}


def changed(state,report_id,finding):
    return values(state,report_id,finding)!={field:finding.get(field,[] if field=='highlight_players' else '') for field in FIELDS}


def remember(state,report_id,finding):
    cache=dict(state.get('workflow_coach_edits',{}));report=dict(cache.get(report_id,{}))
    report[finding['id']]=values(state,report_id,finding);cache[report_id]=report
    state['workflow_coach_edits']=cache


def clear(state,report_id,finding_id):
    cache=dict(state.get('workflow_coach_edits',{}));report=dict(cache.get(report_id,{}));report.pop(finding_id,None)
    cache[report_id]=report;state['workflow_coach_edits']=cache
    for field in FIELDS:state.pop(widget_key(finding_id,field),None)
