"""Consistency checks adapted from the assignment's verification methods."""
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
import math
import pandas as pd


def validate(tables, team, matches):
    errors = defaultdict(list)
    by_key = {name[:2]: df for name, df in tables.items()}

    def error(key, message):
        errors[key].append(message)

    def half_up(value, decimals=0):
        return float(Decimal(str(value)).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP))

    for key, df in by_key.items():
        columns = list(df.columns)
        for col in columns:
            if col in ('Date',):
                if pd.to_datetime(df[col], format='%Y-%m-%d', errors='coerce').isna().any():
                    error(key, 'Invalid match date')
            if '%' in col or col == 'Pct of All Accurate Passes':
                if col in ('% of Team', 'Pct of All Accurate Passes'):
                    previous = columns[columns.index(col) - 1]
                    counts = pd.to_numeric(df[previous], errors='coerce')
                    if (counts.gt(0) & df[col].isna()).any():
                        error(key, f'{col}: missing share for a positive count')
                values = pd.to_numeric(df[col], errors='coerce')
                if (df[col].notna() & values.isna()).any() or ((values < 0) | (values > 100)).any():
                    error(key, f'{col}: expected percentage points between 0 and 100')
        for index, col in enumerate(columns):
            # Adjacent total/success/% triples; team totals have a separate prefix.
            if not col.endswith('%') or index < 2 or col in ('Usage %', '% of Team', 'Central Mids Share of Team %'):
                continue
            if key == '09':
                continue
            total_col, success_col = columns[index - 2:index]
            for row_index, row in df.iterrows():
                total, success, percent = row[total_col], row[success_col], row[col]
                if pd.isna(total) or pd.isna(success):
                    error(key, f'Row {row_index + 1}: missing attempts/successes for {col}')
                    continue
                try:
                    total, success = float(total), float(success)
                    if not math.isfinite(total + success) or total < 0 or success < 0 or success > total:
                        raise ValueError()
                    if total == 0:
                        valid = pd.isna(percent)
                    else:
                        exact = 100 * success / total
                        valid = pd.notna(percent) and any(abs(float(percent) - half_up(exact, d)) < 1e-8 for d in (0, 1))
                    if not valid:
                        error(key, f'Row {row_index + 1}: {col} inconsistent with {success}/{total}')
                except (ValueError, TypeError):
                    error(key, f'Row {row_index + 1}: invalid attempts/successes for {col}')

    squad = by_key.get('01')
    if squad is not None:
        if squad.Player.duplicated().any() or squad.No.duplicated().any():
            error('01', 'Duplicate player name or shirt number')
        indexed = squad.set_index('Player')
        for key in ('02', '03', '04'):
            if key not in by_key:
                continue
            df = by_key[key]
            outfield = set(squad.loc[squad.Group != 'Goalkeepers', 'Player'])
            if set(df.Player) != outfield or df.Player.duplicated().any():
                error(key, 'Player rows do not match the outfield squad')
            for _, row in df.iterrows():
                if row.Player in indexed.index and not indexed.index.duplicated().any():
                    if row.Minutes != indexed.loc[row.Player, 'Total Minutes']:
                        error(key, f'{row.Player}: minutes differ from squad')

    results, events = by_key.get('05'), by_key.get('07')
    if results is not None:
        if len(results) != matches or results.Date.duplicated().any():
            error('05', 'Results count/unique dates do not match cover')
        if events is not None:
            for _, row in results.iterrows():
                for name, goals in ((team, row[team]), (row.Opponent, row['Opponent Goals'])):
                    count = len(events[(events.Date == row.Date) & (events.Team == name) & (events.Event == 'Goal')])
                    if count != goals:
                        error('07', f'{row.Date}: {name} goal events differ from score')
        lineups = by_key.get('06')
        if lineups is not None:
            for _, row in results.iterrows():
                for name in (team, row.Opponent):
                    starters = lineups[(lineups.Date == row.Date) & (lineups.Team == name) & (lineups.Starter == 'Yes')]
                    if len(starters) != 11:
                        error('06', f'{row.Date}: {name} must have 11 starters')
    formations = by_key.get('09')
    if formations is not None:
        if formations.groupby('Formation')['Usage %'].nunique().gt(1).any():
            error('09', 'Inconsistent formation usage')
        usage = formations.drop_duplicates('Formation')['Usage %'].sum()
        if not 0 < usage <= 101:  # Report rounding may produce 101%.
            error('09', f'Formation usage sums to {usage}%')
        for name, group in formations.groupby('Formation'):
            if set(group.Metric) != {'Goals', 'xG', 'Possession %', 'Pass Accuracy %', 'Match Tempo', 'Long Pass Share %', 'PPDA'} or len(group) != 7:
                error('09', f'{name}: missing or duplicate formation metrics')
    return dict(errors)
