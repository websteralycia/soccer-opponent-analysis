"""Pure calculations. None of these functions mutate extracted tables."""
import re
import pandas as pd
from .catalog import METRICS


def table(result, key):
    return next((df.copy() for name, df in result.tables.items() if name.startswith(key + '_')), pd.DataFrame())


def numeric(series):
    # Bounds such as <0.01 remain unavailable for exact arithmetic, never zero.
    return pd.to_numeric(series, errors='coerce').replace([float('inf'), -float('inf')], float('nan'))


def exact_sum(series):
    values = numeric(series)
    return None if values.empty or values.isna().any() else values.sum().item()


def success_rate(successful, attempts):
    attempts, successful = numeric(attempts), numeric(successful)
    valid = attempts.gt(0) & successful.ge(0) & successful.le(attempts)
    return (100 * successful / attempts).where(valid)


def per90(values, minutes):
    values, minutes = numeric(values), numeric(minutes)
    return (values * 90 / minutes).where(minutes.gt(0))


def overview(result):
    results = table(result, '05')
    if results.empty or result.team not in results:
        return None
    dates = pd.to_datetime(results.Date, errors='coerce')
    scores_for, scores_against = numeric(results[result.team]), numeric(results['Opponent Goals'])
    known = scores_for.notna() & scores_against.notna()
    return dict(matches=len(results), wins=int((known & scores_for.gt(scores_against)).sum()),
                draws=int((known & scores_for.eq(scores_against)).sum()),
                losses=int((known & scores_for.lt(scores_against)).sum()), unknown=int((~known).sum()),
                goals_for=exact_sum(results[result.team]), goals_against=exact_sum(results['Opponent Goals']),
                start=dates.min(), end=dates.max())


def formation_usage(result):
    forms = table(result, '09')
    if forms.empty:
        return pd.DataFrame(columns=['Formation', 'Usage %'])
    return forms[['Formation', 'Usage %']].drop_duplicates('Formation').reset_index(drop=True)


def available_metrics(result):
    return [metric for metric in METRICS
            if {'Player', 'Minutes', metric.attempts, *([metric.successful] if metric.successful else [])}
            .issubset(table(result, metric.key).columns)]


def player_frame(result, metrics, normalize=False, minimum=0):
    """Join only complete outfield statistic pages; never shortlist tables.

    Success rates always use raw pooled counts. Normalize count/xG/xA fields
    only, retaining raw attempt/success denominators beside their per-90 values.
    """
    general = table(result, '02')
    if general.empty:
        return pd.DataFrame()
    frame = general[['No', 'Player', 'Minutes']].copy()
    frame = frame[numeric(frame.Minutes).ge(minimum)]
    frame['Minutes'] = numeric(frame.Minutes)
    if normalize:
        frame = frame[frame.Minutes.gt(0)]
    for metric in metrics:
        source = table(result, metric.key)
        if not {'No', 'Player', metric.attempts}.issubset(source.columns):
            continue
        columns = ['No', 'Player', metric.attempts] + ([metric.successful] if metric.successful else [])
        source = source[columns].rename(columns={metric.attempts: metric.label,
                    **({metric.successful: metric.label + ' successful'} if metric.successful else {})})
        frame = frame.merge(source, on=['No', 'Player'], how='left', validate='one_to_one')
        frame[metric.label] = numeric(frame[metric.label])
        if metric.successful:
            good = metric.label + ' successful'
            frame[good] = numeric(frame[good])
            frame[metric.label + ' success %'] = success_rate(frame[good], frame[metric.label])
        if normalize:
            for column in [metric.label] + ([metric.label + ' successful'] if metric.successful else []):
                frame[column + ' /90'] = per90(frame[column], frame.Minutes)
    return frame.reset_index(drop=True)


def clock_value(raw):
    """Ordered minute coordinate, NOT elapsed seconds or duration.

    Added time is placed between its base minute and the next minute so that
    45+3 precedes second-half 46. Raw labels must remain visible in charts.
    """
    match = re.fullmatch(r"\s*(\d+)(?:\+(\d+))?['’]?\s*", str(raw))
    if not match:
        return float('nan')
    base, added = int(match[1]), int(match[2] or 0)
    return base + added / (added + 1)


def match_events(result, date):
    events = table(result, '07')
    if events.empty:
        return events
    events = events[events.Date.eq(date)].copy()
    lineups = table(result, '06')
    keys = ['Date', 'Match', 'Team', 'Player']
    if set(keys + ['Position']).issubset(lineups.columns) and set(keys).issubset(events.columns):
        def unique_position(values):
            known = values.dropna().astype(str).str.strip()
            known = known[known.ne('')].unique()
            return known[0] if len(known) == 1 else None
        positions = lineups.groupby(keys, dropna=False)['Position'].agg(unique_position).reset_index()
        events = events.drop(columns='Position', errors='ignore').merge(positions, on=keys, how='left', validate='many_to_one')
    events['Minute order'] = events.Minute.map(clock_value)
    return events.sort_values('Minute order', kind='stable')


def filter_table(frame, query='', column=None, values=None):
    filtered = frame.copy()
    if column and values:
        filtered = filtered[filtered[column].astype('string').isin(values)]
    if query.strip():
        mask = pd.Series(False, index=filtered.index)
        for col in filtered:
            mask |= filtered[col].astype('string').str.contains(query.strip(), case=False, regex=False, na=False)
        filtered = filtered[mask]
    return filtered


def quality_notes(result):
    notes = [f'{result.matches}-match report sample. Small samples describe this report, not a stable team trait.',
             'Player statistics cover the whole sample, across roles. Match selection only changes match events and lineups.',
             'Selected-player lists are incomplete. Missing players are not zero; shortlist sums are not team totals.',
             'Fixture selection updates match details only. Formation and player statistics remain report aggregates.',
             'Overview sources: match results 05; lineups 06; events 07; reported formation periods 08; formation aggregates 09 (PDF page 6). Conceded-goal observations count matches conceding >0; formation xG balance is team xG minus opponent xG, compared only across reported formations.',
             'Formation Periods lists match-level spells from the report; repeated rows can use the same formation. The Formations view shows only formations with reported aggregate KPIs. A formation can appear in a match without having a summary KPI row; missing metrics are not inferred.',
             'Lineups shows roster and reported roles only. Goals, cards and substitutions are shown in Events; all original lineup columns remain available in Data Explorer and CSV exports.',
             'Percentage rows use percentage points. PPDA is pressing intensity, not block height. Goals/xG cover formation periods, not whole matches.',
             'Substitution positions are reported roles from the exact match lineup, not tracked positions at the event minute. Missing/conflicting roles remain unknown.',
             'Source minutes are retained, including added time. Same-minute substitutions are batches; individual replacement pairings and within-minute ordering are not inferred.',
             'Key passes and shot assists retain their source definitions. Finishing-page Key Passes are kept separate.',
             'Player visuals use complete outfield pages 02–04, across matches and roles. Squad positions are reference labels, not action-by-position allocations. Selected-player shortlists do not populate these comparisons.',
             'Player per-90 values are raw counts or xG/xA × 90 ÷ positive minutes. Success percentages use raw successes ÷ attempts × 100, not normalized counts. Minutes and percentages are never normalized; unknown values are not zero.',
             'Player observation success-rate leaders require at least 10 raw attempts; ties are retained. A higher numerical value is not an overall player rating. Count and success-rate charts use separate axes.',
             'Attacking-contribution scatterplots always use xG/90 and xA/90 for eligible outfield players with positive minutes and known non-negative values, regardless of the totals toggle. No league benchmarks, role percentiles or inferred spatial coordinates are supplied. Goals/xG and assists/xA comparisons are descriptive; short samples and source rounding limit interpretation.',
             'Recovery/loss/dribble grids and defensive channel counts are not in the extracted CSVs.']
    usage = formation_usage(result)
    total = exact_sum(usage['Usage %']) if not usage.empty else None
    if total is not None:
        notes.append(f'Formation KPI table covers {total:g}% of reported time; {max(0,100-total):g}% has no metrics in that table. Usage is rounded; period snapshots can have gaps.')
    general, summary = table(result, '02'), table(result, '20')
    if not general.empty and not summary.empty:
        total_rows = summary[summary['Shot Type'].eq('Total')]
        if not total_rows.empty:
            players = exact_sum(general.xG)
            report = numeric(total_rows.xG).iloc[0]
            if players is not None and pd.notna(report) and abs(players - report) > .005:
                notes.append(f'Report xG {report:.2f} differs from summed player xG {players:.2f}; retain the report total and source rounding.')
    if result.errors:
        notes.append(f'{len(result.errors)} tables failed extraction/validation. Dependent views may be unavailable.')
    return notes
