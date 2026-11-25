"""Player-view data models using complete outfield pages and validated rates."""
from dataclasses import replace
import math
import pandas as pd
from .data import table, numeric, per90, success_rate
from .standouts import MIN_ATTEMPTS, rank_values

FOCUS = {
    'Progression': ['Progressive passes', 'Passes to final third'],
    'Attacking': ['Shots', 'Goals', 'xG', 'xA', 'Shot assists'],
    'Defending': ['Defensive duels', 'Aerial duels', 'Recoveries', 'Interceptions'],
}


def reported_position(result, name, number):
    squad = table(result, '01')
    if not {'Player', 'No', 'Position'}.issubset(squad): return '—'
    rows = squad[squad.Player.eq(name) & squad.No.eq(number)]
    known = rows.Position.dropna().astype(str).str.strip()
    known = known[known.ne('')].unique()
    return known[0] if len(known) == 1 else '—'


def reported_roles(result, frame):
    """Attach report roster labels without attributing aggregate actions to roles."""
    data = frame.copy()
    squad = table(result, '01')
    groups = {'attackers': 'Forwards', 'forwards': 'Forwards',
              'midfielders': 'Midfielders', 'defenders': 'Defenders'}
    positions, populations = [], []
    for _, row in data.iterrows():
        positions.append(reported_position(result, row.Player, row.No))
        known = []
        if {'Player', 'No', 'Group'}.issubset(squad):
            matches = squad[squad.Player.eq(row.Player) & squad.No.eq(row.No)]
            known = matches.Group.dropna().astype(str).str.strip()
            known = known[known.ne('')].unique()
        group = known[0] if len(known) == 1 else 'Unreported'
        populations.append(groups.get(group.casefold(), group))
    data['Reported position'] = positions
    data['Position group'] = populations
    data['Player label'] = data.Player.astype(str) + ' · ' + data['Reported position']
    return data


def extra_value(result, row, field, normalize=False):
    source = table(result, '02')
    if not {'Player', 'No', field}.issubset(source): return None
    found = source[source.Player.eq(row.Player) & source.No.eq(row.No)]
    if len(found) != 1: return None
    value = numeric(found[field]).iloc[0]
    return per90(pd.Series([value]), pd.Series([row.Minutes])).iloc[0] if normalize else value


def action_rows(row, metrics, normalize=False):
    rows = []
    for metric in metrics:
        if not metric.successful: continue
        attempts = numeric(pd.Series([row.get(metric.label)])).iloc[0]
        if pd.notna(attempts) and attempts < 0: attempts = float('nan')
        good = numeric(pd.Series([row.get(metric.label+' successful')])).iloc[0]
        valid = pd.notna(attempts) and pd.notna(good) and 0 <= good <= attempts
        rate = success_rate(pd.Series([good]), pd.Series([attempts])).iloc[0]
        scale = (90 / row.Minutes if row.Minutes > 0 else float('nan')) if normalize else 1
        rows.append(dict(Metric=metric.label, Attempts=attempts, Successful=good if valid else float('nan'),
                         Rate=rate, Total=attempts*scale,
                         Good=good*scale if valid else float('nan'),
                         Other=(attempts-good)*scale if valid else float('nan')))
    return pd.DataFrame(rows)


def scatter_population(frame):
    required = {'xG', 'xA', 'Minutes', 'Player'}
    if not required.issubset(frame): return pd.DataFrame()
    data = frame.copy()
    data['xG /90'] = per90(data.xG, data.Minutes)
    data['xA /90'] = per90(data.xA, data.Minutes)
    valid = data.Minutes.gt(0) & data['xG /90'].ge(0) & data['xA /90'].ge(0)
    return data.loc[valid].copy()


def observation_data(frame, metric, mode, normalize, minimum, position_group='All positions'):
    suffix = ' /90' if normalize else ''
    percent = mode == 'Success rate'
    good = mode == 'Successful actions'
    column = metric.label + (' success %' if percent else ' successful'+suffix if good else suffix)
    data = frame.copy()
    data['Entity'] = data.Player
    data['Value'] = numeric(data[column])
    data['Raw attempts'] = numeric(data[metric.label])
    data['Raw successful'] = numeric(data[metric.label+' successful']) if metric.successful else float('nan')
    mask = data.Value.notna() & data.Value.ge(0)
    if percent: mask &= numeric(data[metric.label]).ge(MIN_ATTEMPTS) & data.Value.le(100)
    data = data.loc[mask].sort_values('Value', ascending=False, kind='stable')
    unit = 'percent' if percent else 'rate' if normalize else 'decimal' if metric.attempts in {'xG','xA'} else 'count'
    source_field = metric.successful if good or percent else metric.attempts
    detail = (f'{metric.successful} ÷ {metric.attempts} × 100; at least {MIN_ATTEMPTS} raw attempts.' if percent else
              f'{source_field} × 90 ÷ positive Minutes.' if normalize else f'Maximum reported {source_field}.')
    label = ('Highest '+metric.label+' success rate (≥10 attempts)' if percent else 'Highest '+column)
    population = f'Filtered outfield players (≥{minimum} minutes); whole-sample statistics across roles'
    if position_group != 'All positions':
        population = (f'Filtered outfield players (≥{minimum} minutes); report position group: {position_group}; '
                      'whole-sample player statistics, not actions isolated to this position')
    item = rank_values(data, 'Value', label, metric.key, population, unit, detail=detail)
    if item: item = replace(item, metric=source_field)
    data['Leader'] = data.Value.map(lambda value: bool(item) and math.isclose(value, item.value, rel_tol=1e-9, abs_tol=1e-9))
    return data, item, unit
