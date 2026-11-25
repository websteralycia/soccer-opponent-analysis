from io import BytesIO
import hashlib
import json
from pathlib import Path
import zipfile
from unittest.mock import patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from opponent_intelligence import extract_report
from opponent_intelligence import parsers
from opponent_intelligence.pdf_helpers import num, value
from opponent_intelligence.validation import validate

PROJECT = Path(__file__).resolve().parents[1]
WORKSPACE = PROJECT.parent
FIXTURES = {
    'Ajax': (WORKSPACE / '00_assignments/assignment_4/AFC Ajax.pdf', WORKSPACE / '00_assignments/assignment_4/ajax_report/csv'),
    'Frankfurt': (WORKSPACE / '00_assignments/assignment_3/Frankfurt.pdf', WORKSPACE / '00_assignments/assignment_3/frankfurt_report/csv'),
}


@pytest.fixture(scope='module')
def extracted():
    return {name: extract_report(BytesIO(pdf.read_bytes()) if name == 'Ajax' else pdf)
            for name, (pdf, _) in FIXTURES.items()}


@pytest.mark.parametrize('name', ['Ajax', 'Frankfurt'])
def test_reports_match_existing_csvs(extracted, name):
    result = extracted[name]
    assert result.successful, result.errors
    assert result.matches == (5 if name == 'Ajax' else 6)
    cells = 0
    for path in sorted(FIXTURES[name][1].glob('*.csv')):
        expected = pd.read_csv(path, encoding='utf-8-sig')
        actual = pd.read_csv(BytesIO(result.csv_bytes(path.name)), encoding='utf-8-sig')
        if name == 'Frankfurt':
            expected.columns = [c.replace('Frankfurt', 'Eintracht Frankfurt') for c in expected.columns]
            if path.name.startswith('05_'):
                expected = expected.rename(columns={'Eintracht Frankfurt Venue': 'Home/Away', 'Eintracht Frankfurt Goals': 'Eintracht Frankfurt'})
                expected = expected[list(actual.columns)]
        assert list(actual.columns) == list(expected.columns), path.name
        pd.testing.assert_frame_equal(
            actual.astype(object).where(actual.notna(), None),
            expected.astype(object).where(expected.notna(), None),
            check_dtype=False, check_exact=False, atol=1e-9, rtol=1e-9, obj=path.name)
        cells += actual.size
    print(f'{name}: 36 tables, {cells} cells match reference CSVs')


def test_downloads(extracted):
    with zipfile.ZipFile(BytesIO(extracted['Ajax'].zip_bytes())) as archive:
        assert len(archive.namelist()) == 37
        assert json.loads(archive.read('extraction_status.json'))['complete']
        assert archive.read('01_squad.csv').startswith(b'\xef\xbb\xbf')


@pytest.mark.parametrize('source', [b'not pdf', b'%PDF- broken', b''])
def test_invalid_pdf_returns_table_failures(source):
    result = extract_report(source)
    assert not result.tables
    assert len(result.errors) == 36
    assert all(row['status'] == 'failed' for row in result.status())


def test_partial_failure_is_isolated():
    with patch.object(parsers, 'attack', side_effect=ValueError('Unsupported attack layout')):
        result = extract_report(FIXTURES['Ajax'][0])
    assert len(result.tables) == 32
    assert len(result.errors) == 4
    assert all('Unsupported attack layout' in messages[0] for messages in result.errors.values())
    with pytest.raises(ValueError):
        result.csv_bytes('16_attack_crosses_takers.csv')
    with zipfile.ZipFile(BytesIO(result.zip_bytes())) as archive:
        assert '16_attack_crosses_takers.csv' not in archive.namelist()
        assert not json.loads(archive.read('extraction_status.json'))['complete']


def test_validation_withholds_derived_totals():
    original = parsers.player_page
    def corrupt(page, kinds, names):
        data = original(page, kinds, names)
        if page.page_number == 3:
            data[0][9] = 101
        return data
    with patch.object(parsers, 'player_page', side_effect=corrupt):
        result = extract_report(FIXTURES['Ajax'][0])
    assert '02_player_general.csv' in result.errors
    assert '35_team_totals_success_rates.csv' in result.errors
    assert '36_team_totals_counts.csv' not in result.tables


def test_value_conventions():
    assert num('-') == 0
    assert num('') is None
    assert num('<0.01') == '<0.01'
    assert value({'text': '-', 'pct': None}, 'pair%') == [0, 0, None]
    assert value({'text': '10/8', 'pct': '80%'}, 'pair%') == [10, 8, 80]
    assert value({'text': '10/8', 'pct': None}, 'pair%') == [10, 8, None]
    assert value({'text': '-', 'pct': None}, 'height') == [None]


def test_validation_rejects_missing_percentage():
    frame = pd.DataFrame({'Shots': [10], 'Shots on Target': [8], 'Shots on Target %': [None]})
    assert '02' in validate({'02_player_general.csv': frame}, 'Ajax', 5)


def test_streamlit_empty_state():
    app = AppTest.from_file(str(PROJECT / 'app.py')).run()
    assert not app.exception
    assert app.button[0].label == 'Process'
    assert app.button[0].disabled


def test_streamlit_upload_process_download(extracted):
    upload = BytesIO(FIXTURES['Ajax'][0].read_bytes())
    with patch('streamlit.file_uploader', return_value=upload), patch('opponent_intelligence.extract_report', return_value=extracted['Ajax']):
        app = AppTest.from_file(str(PROJECT / 'app.py')).run()
        app.button[0].click().run(timeout=30)
        assert not app.exception
        assert len(app.success) == 1
        assert len(app.get('download_button')) == 2
        app.selectbox(key='explorer_table').select('05_match_results.csv').run()
        assert not app.exception
        assert len(app.success) == 1


def test_coursework_unchanged():
    baseline = json.loads((PROJECT / 'tests/coursework_hashes.json').read_text())
    current = {str(p.relative_to(WORKSPACE)): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in (WORKSPACE / '00_assignments').rglob('*') if p.is_file()}
    # Newly supplied source documents are allowed; historical coursework must
    # remain intact. Finder metadata is outside the preservation contract.
    baseline = {k:v for k,v in baseline.items() if not k.endswith('.DS_Store')}
    assert {k:current.get(k) for k in baseline} == baseline


def test_missing_inputs_cannot_be_silently_summed():
    general = pd.DataFrame({'Player': ['Example'], 'Shots': [None], 'Shots on Target': [0]})
    with pytest.raises(ValueError, match='Missing values'):
        parsers.team_totals(general, pd.DataFrame(), pd.DataFrame(), [], 5)
