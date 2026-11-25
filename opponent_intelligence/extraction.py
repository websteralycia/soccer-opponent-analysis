"""In-memory extraction API. Paths, PDF bytes and binary streams are accepted."""
from dataclasses import dataclass, field
from io import BytesIO
import json
from pathlib import Path
import re
import zipfile

import pandas as pd
import pdfplumber

from . import parsers as p
from .validation import validate

SCHEMAS = json.loads((p.RESOURCES / 'schemas.json').read_text())
MAX_BYTES = 30 * 1024 * 1024


@dataclass
class ExtractionResult:
    team: str = ''
    matches: int = 0
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    errors: dict[str, list[str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def successful(self):
        return len(self.tables) == 36 and not self.errors

    def status(self):
        return [dict(table=s['filename'], status='failed' if s['filename'] in self.errors else
                     'extracted' if s['filename'] in self.tables else 'not extracted',
                     rows=len(self.tables[s['filename']]) if s['filename'] in self.tables else 0,
                     detail='; '.join(self.errors.get(s['filename'], []))) for s in SCHEMAS.values()]

    def csv_bytes(self, filename):
        if filename in self.errors:
            raise ValueError('Failed tables cannot be downloaded')
        return self.tables[filename].to_csv(index=False).encode('utf-8-sig')

    def zip_bytes(self):
        """Include valid tables and a manifest; never hide partial failures."""
        output = BytesIO()
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
            for filename in self.tables:
                archive.writestr(filename, self.csv_bytes(filename))
            archive.writestr('extraction_status.json', json.dumps(dict(
                team=self.team, matches=self.matches, complete=self.successful,
                tables=self.status(), warnings=self.warnings), indent=2))
        return output.getvalue()


def _read(source):
    if isinstance(source, (str, Path)):
        with open(source, 'rb') as handle:
            data = handle.read(MAX_BYTES + 1)
    elif isinstance(source, bytes):
        data = source
    else:
        data = source.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('PDF exceeds the 30 MB processing limit')
    if not data.startswith(b'%PDF-'):
        raise ValueError('Input is not a PDF')
    return data


def extract_report(source) -> ExtractionResult:
    """Extract the tested standard Wyscout layout, preserving Ajax-style CSVs.

    No files are written. Page-group failures are isolated and dependent tables
    are marked failed. Invalid input returns a report with all 36 failures.
    """
    result = ExtractionResult(warnings=[
        'Report dashes become zero for counts; missing values and zero-attempt percentages are blank.',
        'Percentages are percentage points (84.4 means 84.4%); <0.01 remains text.',
        'Most tactical/player tables aggregate the report sample; some list only leading players.',
        'Layout support is tested on Ajax and Frankfurt reports, not arbitrary Wyscout exports.',
    ])

    def fail(keys, error):
        message = str(error) or type(error).__name__
        for key in keys:
            name = SCHEMAS[key]['filename']
            result.errors.setdefault(name, []).append(message)
            result.tables.pop(name, None)

    def store(keys, callback):
        try:
            outputs = callback()
            if len(outputs) != len(keys):
                raise ValueError(f'Expected {len(keys)} tables, found {len(outputs)}')
            staged = {}
            for key, records in zip(keys, outputs):
                columns = [c.replace('Frankfurt', result.team) for c in SCHEMAS[key]['columns']]
                if any(len(row) != len(columns) for row in records):
                    raise ValueError(f'Table {key}: row width does not match schema')
                df = p.frame(records, columns)
                if df.empty:
                    raise ValueError(f'Table {key}: no rows found; empty sections require review')
                staged[SCHEMAS[key]['filename']] = df
            result.tables.update(staged)
        except Exception as exc:
            fail(keys, exc)

    try:
        data = _read(source)
        with pdfplumber.open(BytesIO(data)) as pdf:
            n = len(pdf.pages) - 14
            if not 1 <= n <= 20:
                raise ValueError('Unsupported page count for the standard Wyscout layout')
            cover = (pdf.pages[0].extract_text() or '').splitlines()
            if len(cover) < 2 or re.sub(r'\s', '', cover[0]).upper() != 'TEAMREPORT':
                raise ValueError('Wyscout team-report cover not recognized; scans need OCR')
            result.team, result.matches = cover[1].strip(), n
            cover_dates = re.findall(r'(?m)^\d{2}\.\d{2}\.\d{4}$', '\n'.join(cover))
            if len(cover_dates) != n:
                raise ValueError('Cover match count does not match page layout')
            P = lambda number: pdf.pages[number - 1]
            squad = []
            try:
                squad = p.squad(P(2))
                for player in squad:
                    if player['Player'].endswith('…'):
                        first, stem = player['Player'].rstrip('…').rsplit(' ', 1)
                        full = {w['text'] for page in pdf.pages for w in p.words(page)
                                if w['text'].startswith(stem) and len(w['text']) > len(stem) and '…' not in w['text']}
                        if len(full) != 1:
                            raise ValueError(f"Ambiguous truncated player: {player['Player']}")
                        player['Player'] = f'{first} {full.pop()}'
                store(['01'], lambda: [[[r[k] for k in ('No', 'Player', 'Group', 'Position', 'Age', 'Foot',
                    'Height', 'Matches', 'Total', 'Avg', 'Goals', 'Assists', 'YC', 'RC', 'In', 'Out')]
                    for r in squad]])
            except Exception as exc:
                fail(['01'], exc)
            names = {r['No']: r['Player'] for r in squad}
            for page, key in ((3, '02'), (4, '03'), (5, '04')):
                store([key], lambda page=page: [p.player_page(P(page), p.PLAYER_PAGES[page], names)])
            store(['09', '10'], lambda: p.formations(P(6)))

            def matches():
                tables = [[], [], [], []]
                for page in range(7, 7 + n):
                    try:
                        records = p.match_page(P(page), result.team)
                    except Exception as exc:
                        raise ValueError(f'Match page {page}: {exc}') from exc
                    tables[0].append(records[0])
                    for target, records_ in zip(tables[1:], records[1:]):
                        target.extend(records_)
                return tables
            store(['05', '06', '07', '08'], matches)
            # Use the existing Ajax-first results schema for every team.
            name = SCHEMAS['05']['filename']
            if name in result.tables:
                df = result.tables[name]
                result.tables[name] = pd.DataFrame({
                    'Date': df.Date, 'Competition': df.Competition, 'Opponent': df.Opponent,
                    'Home/Away': df[f'{result.team} Venue'], result.team: df[f'{result.team} Goals'],
                    'Opponent Goals': df['Opponent Goals'], 'Result': df.Result,
                    f'{result.team} Team Width m': df[f'{result.team} Team Width m'],
                    f'{result.team} Team Depth m': df[f'{result.team} Team Depth m'],
                })
            store(['11', '12', '13'], lambda: p.defence(P(n + 7), names))
            store(['14', '15'], lambda: p.build_up(P(n + 8), names, {r['Player']: r['Foot'] for r in squad}))
            store(['16', '17', '18', '19'], lambda: p.attack(P(n + 9), names))
            store(['20', '21', '22', '23'], lambda: p.finishing(P(n + 10), names))
            store(['24', '25', '26'], lambda: p.per90_tables(P(n + 11), names, [['num'] * 3] * 3))
            store(['27', '28', '29'], lambda: p.per90_tables(P(n + 12), names,
                [['num'] * 5, ['num'] * 5, ['num'] * 3]))
            store(['30', '31', '32', '33'], lambda: p.set_pieces(P(n + 13), names))
            store(['34'], lambda: [p.glossary(P(n + 14))])
            dependencies = ['01', '02', '03', '04', '06']
            if all(SCHEMAS[k]['filename'] in result.tables for k in dependencies):
                get = lambda key: result.tables[SCHEMAS[key]['filename']]
                store(['35', '36'], lambda: p.team_totals(get('02'), get('03'), get('04'),
                    p.central_mids(get('06'), result.team), n))
            else:
                fail(['35', '36'], 'Required squad/player/lineup extraction failed')
    except Exception as exc:
        fail(list(SCHEMAS), exc)
        return result

    try:
        validation_errors = validate(result.tables, result.team, result.matches)
    except Exception as exc:
        fail(list(SCHEMAS), f'Validation could not complete: {exc}')
        return result
    for key, messages in validation_errors.items():
        fail([key], '; '.join(messages))
    # Derived totals must not survive invalid source tables.
    if any(SCHEMAS[k]['filename'] in result.errors for k in ('01', '02', '03', '04', '06')):
        fail(['35', '36'], 'Required source table failed validation')
    result.tables = dict(sorted(result.tables.items()))
    return result
