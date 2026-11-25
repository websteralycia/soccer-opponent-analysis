"""Stable evidence references with scope/definitions, not automatic conclusions."""
from .store import report_identifier
from ..dashboard.catalog import table_info,METRICS
from ..dashboard.data import overview


def report_metadata(result):
    summary=overview(result)
    return dict(team=result.team,matches=result.matches,
                start=str(summary['start'].date()) if summary else 'Unknown',
                end=str(summary['end'].date()) if summary else 'Unknown')


def reference(result,filename,column='',snapshot='',calculation='Reported source value; no added calculation.'):
    info=table_info(filename[:2],result.matches)
    definition=next((metric.definition for metric in METRICS if metric.key==filename[:2] and column in (metric.attempts,metric.successful)),info.note)
    return dict(table=filename,column=column,scope=info.scope+' · '+info.coverage,page=info.page,
                definition=definition,calculation=calculation,snapshot=str(snapshot))


def reference_options(result):
    return {f'{name} | {column}':reference(result,name,column)
            for name,frame in result.tables.items() for column in frame.columns}


def seed_from_standout(result,item):
    filename=next((name for name in result.tables if name.startswith(item.source+'_')),'')
    column=item.metric
    if column=='_success_rate':
        from ..dashboard.standouts import RATE_PAIRS
        column=RATE_PAIRS.get(item.source,('', ''))[1]
    formatted=f'{item.value:.1f}%' if item.unit=='percent' else f'{item.value:.1f}' if item.unit=='rate' else f'{item.value:.2f}' if item.unit=='decimal' else f'{item.value:,.0f}'
    snapshot=f'{item.label}: {", ".join(item.names)} = {formatted}. {item.population}; {item.eligible} eligible with known values.'
    return dict(title=item.label,observation=snapshot,supporting_evidence=snapshot,
                source_refs=[reference(result,filename,column,snapshot,item.detail or 'Maximum of known values within the stated source population; ties retained.')],
                category=({'03':'Defensive organization','12':'Transitions','19':'Transitions','25':'Transitions','14':'Buildup and progression','15':'Buildup and progression','04':'Buildup and progression','16':'Attacking patterns','18':'Attacking patterns','30':'Set pieces','31':'Set pieces','32':'Set pieces','33':'Set pieces'}.get(item.source,'General')),status='Draft')
