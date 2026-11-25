"""Verified local team crests reuse existing identities without changing reports."""
import hashlib
from pathlib import Path
import json
import pytest
from opponent_intelligence import identities
from opponent_intelligence.dashboard.overview_ui import fixture_strip
from opponent_intelligence.workflow.reports import html_report,pdf_report
from test_dashboard import report
from test_coach_brief import model_for
from pypdf import PdfReader
from io import BytesIO

TEAMS=[('ajax','139',['Ajax','AFC Ajax','Ajax Amsterdam','AFC Ajax Amsterdam']),
       ('psv','148',['PSV','PSV Eindhoven']),('az','140',['AZ','AZ Alkmaar']),
       ('eintracht-frankfurt','125',['Eintracht Frankfurt','Frankfurt']),
       ('pec-zwolle','2565',['PEC Zwolle','Zwolle']),('almere-city','5291',['Almere City','Almere City FC'])]

@pytest.mark.parametrize('key,espn_id,aliases',TEAMS)
def test_crest_aliases_digest_and_existing_dimensions(key,espn_id,aliases):
    entry=identities.registry()['teams'][key]
    assert entry['identity_reference']['team_id']==espn_id
    assert hashlib.sha256((identities.ROOT/entry['file']).read_bytes()).hexdigest()==entry['sha256']
    for alias in aliases:
        assert identities.team_record(alias)[0]==key
        assert identities.image_bytes(alias)
        for size in [28,32,36,52]:
            markup=identities.identity_html(alias,size=size)
            assert f'width="{size}" height="{size}"' in markup
            assert 'class="oi-identity crest"' in markup and 'data:image/png;base64,' in markup
    assert identities.image_bytes(aliases[0],'Unknown Player') is None


def test_ajax_sample_opponents_have_crests_without_adding_report_images(report):
    assert identities.image_bytes(report.team)
    for opponent in report.tables['05_match_results.csv'].Opponent.unique():
        assert identities.image_bytes(opponent),opponent
    model=model_for(report,3)
    assert '<img' not in html_report(model)
    assert all(not list(page.images) for page in PdfReader(BytesIO(pdf_report(model))).pages)
    assert 'crest unavailable' in identities.identity_html('Unknown future team')
