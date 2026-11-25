"""Report-scoped portrait mappings, local integrity and unavailable-image fallbacks."""
from io import BytesIO
from pathlib import Path
import hashlib
import pandas as pd
import pytest
from PIL import Image
from opponent_intelligence import identities

MATCHES=[('Matheus','158174',True),('J. Hato','353951',True),('Y. Baas','305590',True),('A. Gaaei','333312',True),('J. Šutalo','305552',True),('D. Rugani','181673',True),('Lucas Rosa','351281',True),('A. Kaplan','306806',True),('D. Janse','368818',True),('O. Wijndal','241392',True),('K. Taylor','282228',True),('D. Klaassen','168993',True),('J. Henderson','127262',True),('J. Mokio','381074',True),('O. Edvardsen','295861',True),('K. Fitz-Jim','305589',True),('B. van den Boomen','196234',True),('M. Godts','353363',True),('S. Berghuis','149577',True),('B. Brobbey','282229',True),('B. Traoré','169661',True),('D. Konadu','386841',True)]

@pytest.mark.parametrize('name,espn_id,available',MATCHES)
def test_verified_report_identity_local_portrait_or_fallback(name,espn_id,available):
    entry=identities.player_record('AFC Ajax',name)
    assert entry['identity_reference']['player_id']==espn_id
    assert entry['identity_reference']['historical_ajax_sources']
    assert identities.image_bytes('Other club',name) is None
    assert bool(identities.image_bytes('Ajax',name))==available
    for alias in entry['aliases']:
        assert identities.player_record('Ajax',alias)==entry
    for size in [24,48,56]:
        markup=identities.identity_html('Ajax',name,size)
        if available:
            assert f'width="{size}" height="{size}"' in markup
            assert 'class="oi-identity headshot"' in markup
        else:assert 'headshot unavailable' in markup
    if available:
        raw=(identities.ROOT/entry['file']).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==entry['sha256']
        with Image.open(BytesIO(raw)) as original,Image.open(BytesIO(identities.image_bytes('Ajax',name))) as rendered:
            expected_ratio=original.width/original.height
            assert rendered.width/rendered.height==pytest.approx(expected_ratio,abs=.01)
            if entry['image_reference'].get('provider')=='User-supplied':
                assert original.width==original.height
                assert original.mode=='RGBA' and original.getextrema()[3][0]==0
                assert (identities.ROOT/entry['image_reference']['original_file']).is_file()
            else:assert original.size==(350,254)
    else:
        assert entry['file'] is None and entry['verified'] is False
        assert entry['image_reference']['status']=='unavailable'


def test_mapping_population_is_exact_report_roster():
    csv=Path(__file__).resolve().parents[2]/'00_assignments/assignment_4/ajax_report/csv/01_squad.csv'
    assert set(pd.read_csv(csv).Player)=={name for name,_,_ in MATCHES}
    assert sum(bool(identities.image_bytes('Ajax',name)) for name,_,_ in MATCHES)==22


def test_unknown_players_still_use_initials_after_roster_is_fully_populated():
    assert identities.image_bytes('Ajax','Unknown report player') is None
    assert 'headshot unavailable' in identities.identity_html('Ajax','Unknown report player')
