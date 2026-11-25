"""Scoped tactical evidence definitions and non-mutating data preparation."""
from dataclasses import dataclass
import pandas as pd
from .data import table, exact_sum, numeric, success_rate
from .catalog import table_info
from .standouts import table_standouts, rank_values
from ..workflow.evidence import reference


@dataclass(frozen=True)
class Focus:
    source: str
    kind: str = 'contributors'
    map_key: str | None = None
    fields: tuple = ()
    support_source: str | None = None
    support_fields: tuple = ()
    profile: str | None = None


FOCUSES={
 'Defensive organization':{
  'Own-third wins':Focus('11',map_key='defensive_duels',fields=('Defensive Duels Won','Interceptions','Sliding Tackles','% of Team')),
  'Own-third losses':Focus('12',map_key='lost_duels',fields=('Opponent Shots After','Duels Lost','Opponent xG After','% of Team')),
  'Foul locations':Focus('26',map_key='fouls',fields=('Total','Avg per 90')),
  'All-area duels':Focus('03','team_duels',fields=('Defensive Duels','Defensive Duels Won','Defensive Duels Lost','Defensive Duels Won %','Interceptions')),
  'Formation PPDA':Focus('09','formation'),
 },
 'Transitions':{
  'Attacking-third recoveries':Focus('19',map_key='final_third_recoveries',fields=('Shots After','Recoveries','xG','Goals After')),
  'All-area recoveries':Focus('24',map_key='recoveries',fields=('Total','Avg per 90')),
  'Own-third lost duels':Focus('12',map_key='lost_duels',fields=('Opponent Shots After','Duels Lost','Opponent xG After','% of Team')),
  'Possession losses':Focus('25',map_key='losses',fields=('Total','Avg per 90')),
 },
 'Buildup and progression':{
  'Progression':Focus('04','team_progression',fields=('Progressive Passes Accurate','Passes to Final Third Accurate','Deep Completions')),
  'Passers':Focus('14','pairs',fields=('Passes','Passes Accurate'),support_source='15',support_fields=('Accurate Passes to Teammate','Pct of All Accurate Passes')),
  'Receiver links':Focus('15','links',fields=('Accurate Passes to Teammate','Pct of All Accurate Passes'),support_source='14'),
 },
 'Attacking patterns':{
  'Final-third dribbles':Focus('18',map_key='final_third_dribbles',fields=('Shots After','Successful Dribbles','% of Team','xG','Goals After')),
  'Crossing':Focus('16','pairs',map_key='crosses',fields=('Crosses','Crosses Successful'),support_source='17',support_fields=('Shots','Crosses Received','xG')),
  'All-pitch dribbling':Focus('27',map_key='dribbles',fields=('Total','Won','Lost','Avg per 90')),
  'Shot creation':Focus('04','team_creation',fields=('Shot Assists','Deep Completions','Key Passes'),profile='creation'),
 },
 'Set pieces':{
  'Corners':Focus('30','deliveries',fields=('From Left','From Right'),support_source='31',support_fields=('Shots','xG','Goals')),
  'Free kicks':Focus('32','deliveries',fields=('From Left','From Right'),support_source='33',support_fields=('Shots','xG','Goals')),
 },
}
CONTROL_KEYS={'Defensive organization':'tactical_defence','Transitions':'tactical_transition',
 'Buildup and progression':'tactical_buildup','Attacking patterns':'tactical_attack','Set pieces':'tactical_setpieces'}
SOURCES={'Defensive organization':['02','03','09','11','12','13','26'],
 'Transitions':['02','12','19','24','25','26','27','28','29'],
 'Buildup and progression':['04','14','15','25'],
 'Attacking patterns':['04','16','17','18','19','20','21','22','23','27','28','29'],
 'Set pieces':['20','30','31','32','33']}


def total(result,key,column):
    if key not in {'02','03','04'}:raise ValueError('Pooled totals require a complete outfield player page')
    data=table(result,key)
    return exact_sum(data[column]) if column in data else None


def filename(result,key):
    return next((name for name in result.tables if name.startswith(key+'_')),key+' — unavailable')


def scoped_frame(result,key,passer=None):
    frame=table(result,key)
    if key=='03' and {'Defensive Duels','Defensive Duels Won'}.issubset(frame):
        attempted=numeric(frame['Defensive Duels']);won=numeric(frame['Defensive Duels Won'])
        valid=attempted.ge(0) & won.ge(0) & won.le(attempted)
        frame['Defensive Duels Lost']=(attempted-won).where(valid)
    if key=='09':
        return frame[frame.Metric.eq('PPDA')].copy() if 'Metric' in frame else pd.DataFrame()
    if key=='15' and passer and 'Passer' in frame:frame=frame[frame.Passer.eq(passer)].copy()
    return frame


def unit(column):
    if '%' in column or column=='Pct of All Accurate Passes':return 'percent'
    if column=='Avg per 90':return 'rate'
    if 'xG' in column or column=='xA':return 'decimal'
    return 'count'


def team_actions(result,key,pairs):
    rows=[]
    for label,attempts,good in pairs:
        attempts,good=total(result,key,attempts),total(result,key,good)
        valid=attempts is not None and good is not None and 0<=good<=attempts
        rate=success_rate(pd.Series([good]),pd.Series([attempts])).iloc[0]
        rows.append(dict(Metric=label,Attempts=attempts,Successful=good if valid else None,Rate=rate,
                         Total=attempts,Good=good if valid else None,Other=attempts-good if valid else None))
    return pd.DataFrame(rows)


def scope_text(key,matches):
    info=table_info(key,matches)
    return info.coverage+' · '+('formation periods' if key=='09' else f'{matches}-match aggregate')


def focus_items(result,spec,passer=None):
    items=table_standouts(result,spec.source,spec.profile)
    if spec.kind=='links' and passer:
        data=scoped_frame(result,'15',passer)
        if {'Receiver','Accurate Passes to Teammate'}.issubset(data):
            data['Entity']=data.Receiver
            item=rank_values(data,'Accurate Passes to Teammate','Largest listed receiver link','15',
                f'Reported receiver links for {passer}; full-sample buildup actions',detail='Maximum reported link count for the selected passer; not a complete network.')
            items=[item] if item else []
        else:items=[]
    if spec.source=='11':
        data=table(result,'11')
        if 'Player' in data:
            data['Entity']=data.Player
            for field,label in [('Defensive Duels Won','Most listed own-third defensive-duel wins'),('Interceptions','Most listed own-third interceptions')]:
                item=rank_values(data,field,label,'11','Reported own-third players · selected list',detail='Maximum within the reported player list; not a whole-team ranking or win rate.')
                if item:items.append(item)
    if spec.support_source and spec.source in {'30','32'}:items+=table_standouts(result,spec.support_source)
    return items


def manual_seed(result,category,label,spec,asset=None,passer=None):
    frame=scoped_frame(result,spec.source,passer)
    ref=reference(result,filename(result,spec.source),snapshot=frame.head(5).to_csv(index=False),
                  calculation='Snapshot of up to five rows for review, not a team total or tactical conclusion.'+
                  (' Defensive Duels Lost is calculated as reported Defensive Duels minus Defensive Duels Won; missing or invalid inputs remain unavailable.' if spec.source=='03' else ''))
    if asset:
        ref=dict(ref,visual=asset['key'],image_page=str(asset['page']),image_scope=f"Source-specific {result.matches}-match aggregate; not match-specific.")
    return dict(title='Review '+label,category=category,status='Draft',classification=None,observation='',
                source_refs=[ref],visual_key=asset['key'] if asset else '')


RECOVERY_LABELS={
 'Recoveries':'Attacking-third recoveries',
 'Shots After':'Team shots following recovery',
 'Shots After On Target':'Team shots on target following recovery',
 'xG':'Team xG following recovery',
 'Goals After':'Team goals following recovery',
}


def metric_label(key,field):
    labels=RECOVERY_LABELS if key=='19' else DRIBBLE_LABELS if key=='18' else ALL_PITCH_DRIBBLE_LABELS if key=='27' else DUEL_LABELS.get(key,CROSSING_LABELS.get(key,{}))
    return labels.get(field,field)


DRIBBLE_LABELS={'Shots After':'Team shots following dribble','xG':'Team xG following dribble',
 'Goals After':'Team goals following dribble','Successful Dribbles':'Successful attacking-third dribbles','% of Team':'Reported share of team successful dribbles'}


def formation_ppda_frame(result):
    frame=scoped_frame(result,'09')
    columns=['Formation','Usage %',result.team,'Opponent']
    if frame.empty or not set(columns).issubset(frame):return pd.DataFrame()
    frame=frame[columns].copy()
    for column in columns[1:]:frame[column]=numeric(frame[column])
    return frame.rename(columns={result.team:'Team PPDA','Opponent':'Opponent PPDA'})


CROSSING_LABELS={
 '16':{'Crosses':'Cross attempts','Crosses Successful':'Successful crosses'},
 '17':{'Shots':'Shots from received crosses','Crosses Received':'Crosses received','xG':'xG from received crosses'},
}


def crossing_options(result,spec):
    # Different selected-player lists stay in their own source tables.
    return [(key,field) for key,fields in [(spec.source,spec.fields),(spec.support_source,spec.support_fields)]
            if key for field in fields if field in table(result,key)]


ALL_PITCH_DRIBBLE_LABELS={'Total':'Dribble attempts','Won':'Successful dribbles',
 'Lost':'Unsuccessful dribbles','Avg per 90':'Dribbles per 90'}


DUEL_LABELS={
 '03':{'Defensive Duels':'Defensive duels attempted','Defensive Duels Won':'Defensive duels won',
       'Defensive Duels Lost':'Defensive duels lost (calculated)','Defensive Duels Won %':'Defensive duel success %'},
 '12':{'Duels Lost':'Own-third duels lost'},
}
