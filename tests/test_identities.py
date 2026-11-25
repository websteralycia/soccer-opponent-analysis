"""Optional images must be local, verified and scoped; fallbacks remain usable."""
import hashlib
import json
from io import BytesIO
import pandas as pd
from PIL import Image
import pytest
from opponent_intelligence import ExtractionResult
from opponent_intelligence import identities
from opponent_intelligence.workflow.reports import coach_model,html_report,pdf_report
from opponent_intelligence.workflow.store import FindingsStore,report_identifier


def test_normalized_alias_and_player_club_scope():
    assert identities.team_record('AFC Ajax')[0]=='ajax'
    assert identities.team_record('PSV Eindhoven')[0]=='psv'
    assert identities.player_record('AFC Ajax','J. Sutalo')['name']=='J. Šutalo'
    assert not identities.player_record('Another club','J. Hato')
    assert identities.normalize('  J. Šutalo ')==identities.normalize('J. Sutalo')


def test_missing_images_and_safe_accessible_placeholders():
    assert identities.image_bytes('Future FC') is None
    assert 'crest unavailable' in identities.identity_html('Future FC')
    assert 'headshot unavailable' in identities.identity_html('Ajax','Unknown Player')
    markup=identities.profile_html('Future FC','<script>x</script>',90)
    assert '<script>' not in markup and '&lt;script&gt;' in markup
    with Image.open(BytesIO(identities.identity_png('Future FC','A. Player'))) as image:
        assert image.size==(96,96)


def test_verified_assets_and_invalid_provenance_fail_closed(tmp_path,monkeypatch):
    monkeypatch.setattr(identities,'ROOT',tmp_path)
    image=Image.new('RGB',(24,24),'white');output=BytesIO();image.save(output,format='PNG')
    raw=output.getvalue();(tmp_path/'example.png').write_bytes(raw)
    record=dict(file='example.png',verified=True,source='Test fixture',license='Synthetic test raster',sha256=hashlib.sha256(raw).hexdigest())
    assert identities.checked_image(record)
    for changes in [dict(verified=False),dict(license=''),dict(source=''),dict(sha256='bad'),dict(file='../example.png'),dict(file='https://example.com/p.png')]:
        assert identities.checked_image(dict(record,**changes)) is None
    (tmp_path/'registry.json').write_text('{broken')
    assert identities.registry()=={}
    (tmp_path/'registry.json').write_text(json.dumps(dict(teams={'test':dict(name='Test',aliases=[],**record)})))
    assert 'data:image/png' in identities.identity_html('Test')
    assert identities.image_bytes('Test','Unknown') is None


def test_coach_highlights_only_include_actual_report_players(tmp_path):
    report=ExtractionResult(team='Future FC',matches=1,tables={'01_squad.csv':pd.DataFrame({'Player':['A. Player']})})
    store=FindingsStore(tmp_path/'test.sqlite3');ident=report_identifier(report);store.register(ident,{})
    finding=store.create(ident,dict(title='Authored example',highlight_players=['A. Player','Invented Player']))
    store.select(ident,[finding['id']])
    model=coach_model(report,store.selected(ident))
    assert model['findings'][0]['highlight_players']==['A. Player']
    markup=html_report(model)
    # Legacy highlight selections remain compatible but are not presented in
    # the text-first coaching brief.
    assert 'A. Player' not in markup and 'Invented Player' not in markup
    assert store.get(ident,finding['id'])['highlight_players']==['A. Player','Invented Player']
    assert 'crest unavailable' not in markup and 'headshot unavailable' not in markup
    assert 'http://' not in markup and 'https://' not in markup
    assert pdf_report(model).startswith(b'%PDF')
    with pytest.raises(ValueError,match='Player highlights'):
        FindingsStore.validated(dict(title='Bad',highlight_players='A. Player'))


def test_verified_espn_identity_reference_resolves_local_portrait():
    entry=identities.player_record('Ajax','Lucas Oliveira Rosa')
    assert entry['identity_reference']['player_id']=='351281'
    assert entry['identity_reference']['verified'] is True
    assert entry['image_reference']['status']=='verified_local'
    assert entry['verified'] is True and entry['file']
    assert identities.image_bytes('Ajax','Lucas Rosa')
