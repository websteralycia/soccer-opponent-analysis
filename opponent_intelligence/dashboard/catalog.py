"""Source scopes and explicit metric semantics; no club-specific content."""
from dataclasses import dataclass


@dataclass(frozen=True)
class TableInfo:
    scope: str
    coverage: str
    page: str
    note: str = ''


def table_info(key: str, matches: int) -> TableInfo:
    n = matches
    if key in {'05', '06', '07', '08'}:
        notes = {'05': 'Scores are the source for full-sample goals, independent of formation metrics.',
                 '06': 'Both teams. Lineup position is not a complete record of in-game roles.',
                 '07': 'Both teams. Raw numbered event minutes may differ from elapsed video timestamps.',
                 '08': 'Focal team only. Reported snapshots can have gaps; no interpolation or performance allocation.'}
        return TableInfo('Match-level', 'Reported match records', f'7–{6+n}', notes[key])
    if key in {'09', '10'}:
        return TableInfo('Formation aggregate' if key == '09' else 'Representative formation lineup',
                         'Selected reported formations', '6',
                         'Usage repeats for each metric. Other shapes may appear in matches without metrics.' if key == '09'
                         else 'An illustrative report lineup, not every match’s starting lineup or full positional history.')
    if key == '34':
        return TableInfo('Definitions', 'Report glossary', str(n+14))
    if key in {'35', '36'}:
        return TableInfo('Full-sample aggregate', 'All reported outfield players', 'Calculated from player pages 3–5',
                         'Outfield totals exclude goalkeepers. Central-mid groups use majority of lineup appearances, not minutes in role. Rounded player sums may differ from report totals.')
    if key == '01':
        return TableInfo('Full-sample squad', 'Reported squad, including goalkeepers', '2',
                         'Squad positions are reference labels, not action-by-position statistics.')
    if key in {'02', '03', '04'}:
        return TableInfo('Full-sample player aggregate', 'All reported outfield players', str(int(key)+1),
                         'Full-sample totals cannot be filtered to a match or attributed to a lineup role.' +
                         (' Key Passes and Shot Assists are separate provider fields; keep both definitions distinct.' if key == '04' else ''))
    page = next((page for keys, page in [({'11','12','13'},n+7), ({'14','15'},n+8),
                ({'16','17','18','19'},n+9), ({'20','21','22','23'},n+10),
                ({'24','25','26'},n+11), ({'27','28','29'},n+12),
                ({'30','31','32','33'},n+13)] if key in keys), None)
    coverage = 'Selected players / reported leaders'
    note = 'Do not treat omitted players as zero or sum this list as a complete team total.'
    if key == '14':
        coverage = 'Selected buildup passers'
        note += ' These are selected buildup actions, not all passes.'
    if key == '15':
        coverage = 'Selected buildup passers and receiver links'
        note += ' Receiver percentages use all accurate passes by the passer, not only displayed links.'
    if key in {'20','21'}:
        coverage = 'Team summary'
        note = ('Shot categories overlap; do not sum category rows. Use Total for the headline.' if key == '20'
                else 'Intervals aggregate all matches, include stoppage time, and differ in duration.')
    if key == '23':
        note += ' Finishing-page Key Passes match Shot Assists on the passing page in tested reports; do not merge with passing-page Key Passes.'
    if key == '12':
        note += ' Shots/xG after losses describe subsequent outcomes, not a full opponent xG total.'
    if key == '11':
        note += ' The own-third map includes interceptions and tackles; do not substitute this for all-area defensive-duel win rates.'
    return TableInfo('Full-sample aggregate', coverage, str(page or 'Unknown'), note)


@dataclass(frozen=True)
class Metric:
    label: str
    key: str
    attempts: str
    successful: str | None = None
    definition: str = ''


# Only metrics whose source columns are actually available are offered in the UI.
METRICS = (
    Metric('Progressive passes', '04', 'Progressive Passes', 'Progressive Passes Accurate', 'Provider-defined forward progression; see report glossary for distance thresholds.'),
    Metric('Passes to final third', '04', 'Passes to Final Third', 'Passes to Final Third Accurate', 'Passes into the zone within 35 metres of the opponent goal line.'),
    Metric('Defensive duels', '03', 'Defensive Duels', 'Defensive Duels Won', 'Provider-defined duels while the opponent possesses the ball; all pitch areas.'),
    Metric('Aerial duels', '03', 'Aerial Duels', 'Aerial Duels Won', 'All-area aerial duel attempts and wins.'),
    Metric('Dribbles', '02', 'Dribbles', 'Dribbles Successful', 'All-area attempts and successful dribbles; not only final-third actions.'),
    Metric('Crosses', '02', 'Crosses', 'Crosses Accurate', 'All reported outfield crossing attempts and accurate deliveries.'),
    Metric('Shots', '02', 'Shots', 'Shots on Target', 'Shots and shots on target, across all matches.'),
    Metric('Shot assists', '04', 'Shot Assists', definition='Passing-page shot assists. Keep separate from passing-page Key Passes and the finishing-page label.'),
    Metric('Key passes — passing page', '04', 'Key Passes', definition='Separate provider field on the passing page; not interchangeable with finishing-page Key Passes.'),
    Metric('Deep completions', '04', 'Deep Completions', definition='Completed non-cross passes into a 20-metre radius from the opponent goal line.'),
    Metric('Recoveries', '02', 'Recoveries', definition='Possession recoveries, all areas. Outfield players only.'),
    Metric('Interceptions', '03', 'Interceptions', definition='Recorded interceptions, all areas.'),
    Metric('Goals', '02', 'Goals', definition='Recorded player goals; use match scores for team sample goals.'),
    Metric('xG', '02', 'xG', definition='Sum of shot scoring probabilities. Player values may be rounded.'),
    Metric('xA', '02', 'xA', definition='Provider-reported expected assists, not actual assists.'),
)
