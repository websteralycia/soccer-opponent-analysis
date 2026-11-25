"""Descriptive maxima over explicitly scoped populations, never player ratings."""
from dataclasses import dataclass
import math
import pandas as pd
from .data import table,numeric,success_rate
from .catalog import table_info

MIN_ATTEMPTS=10


@dataclass(frozen=True)
class Standout:
    label: str
    names: tuple
    value: float
    unit: str
    source: str
    population: str
    eligible: int
    metric: str
    detail: str = ''


# label, value column, units; all comparisons remain within one source table.
RANKINGS={
 '03':[('Most defensive-duel attempts','Defensive Duels','count'),('Most defensive duels won','Defensive Duels Won','count')],
 '12':[('Most listed own-third lost duels','Duels Lost','count'),('Most opponent shots following losses','Opponent Shots After','count')],
 '19':[('Most listed attacking-third recoveries','Recoveries','count'),('Most team shots following listed recoveries','Shots After','count')],
 '25':[('Most listed possession losses','Total','count')],
 '14':[('Most listed buildup passes','Passes','count'),('Most accurate buildup passes','Passes Accurate','count')],
 '15':[('Most passes on a listed link','Accurate Passes to Teammate','count')],
 '04':[('Most progressive-pass attempts','Progressive Passes','count'),('Most completed progressive passes','Progressive Passes Accurate','count')],
 'creation':[('Most shot assists — passing page','Shot Assists','count'),('Most deep completions','Deep Completions','count')],
 '16':[('Most listed cross attempts','Crosses','count'),('Most successful listed crosses','Crosses Successful','count')],
 '18':[('Most listed successful final-third dribbles','Successful Dribbles','count'),('Largest reported team share','% of Team','percent'),('Most shots following dribbles','Shots After','count')],
 '30':[('Most listed corner deliveries','Corners','count')],
 '31':[('Most listed corner shots','Shots','count'),('Highest listed corner-shot xG','xG','decimal')],
 '32':[('Most listed free-kick deliveries','Free Kicks','count')],
 '33':[('Most listed free-kick shots','Shots','count'),('Highest listed free-kick-shot xG','xG','decimal')],
}
RATE_PAIRS={'03':('Defensive Duels','Defensive Duels Won'), '14':('Passes','Passes Accurate'),
            '04':('Progressive Passes','Progressive Passes Accurate'),'16':('Crosses','Crosses Successful')}


def rank_values(data,column,label,source,population,unit='count',eligible_mask=None,detail=''):
    """Require two known entities with differing values. Ties are retained."""
    if column not in data:
        return None
    values=numeric(data[column])
    valid=values.notna() & values.ge(0) & data.Entity.notna() & data.Entity.astype(str).str.strip().ne('')
    if eligible_mask is not None:valid &= eligible_mask
    if unit=='percent':valid &= values.le(100)
    candidates=data.loc[valid].copy()
    if len(candidates)<2 or candidates['Entity'].duplicated().any():return None
    candidates['_value']=values.loc[valid]
    high=float(candidates['_value'].max());low=float(candidates['_value'].min())
    if high<=0 or math.isclose(high,low,rel_tol=1e-9,abs_tol=1e-9):return None
    winners=candidates[candidates['_value'].map(lambda value:math.isclose(value,high,rel_tol=1e-9,abs_tol=1e-9))]
    return Standout(label,tuple(sorted(winners.Entity.astype(str))),high,unit,source,population,
                    len(candidates),column,detail)


def table_standouts(result,key,profile=None,min_attempts=MIN_ATTEMPTS):
    data=table(result,key)
    if data.empty:return []
    if 'Player' in data:data['Entity']=data.Player
    elif {'Passer','Receiver'}.issubset(data):data['Entity']=data.Passer+' → '+data.Receiver
    else:return []
    info=table_info(key,result.matches)
    population=info.coverage+' · whole report sample'
    output=[]
    selected_profile=profile or key
    for label,column,unit in RANKINGS.get(selected_profile,[]):
        item=rank_values(data,column,label,key,population,unit)
        if item:output.append(item)
    if selected_profile in RATE_PAIRS:
        attempts,successful=RATE_PAIRS[selected_profile]
        if {attempts,successful}.issubset(data):
            data['_success_rate']=success_rate(data[successful],data[attempts])
            eligible=numeric(data[attempts]).ge(min_attempts)
            item=rank_values(data,'_success_rate',f'Highest success rate (≥{min_attempts} attempts)',key,population,'percent',eligible,
                             f'{successful} ÷ {attempts} × 100; at least {min_attempts} attempts')
            if item:
                counts='; '.join(f'{r.Entity}: {int(r[successful])}/{int(r[attempts])}'
                                  for _,r in data[data.Entity.isin(item.names)].iterrows())
                item=Standout(**{**item.__dict__,'detail':item.detail+' · '+counts})
                output.append(item)
    return output
