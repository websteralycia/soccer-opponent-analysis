"""Text-only monochrome reports; stored imagery remains untouched."""
from io import BytesIO
import re
import pytest
import pypdfium2 as pdfium
from PIL import ImageChops
from pypdf import PdfReader
from opponent_intelligence.workflow.reports import html_report,pdf_report
from opponent_intelligence.workflow import coach_editor
from test_coach_brief import model_for
from test_dashboard import report,loaded_app
from test_workflow import setup_store,payload


@pytest.mark.parametrize('count',[1,2,3])
def test_exports_are_image_free_black_and_white_with_complete_text(report,count):
    model=model_for(report,count)
    for item in model['findings']:
        item['highlight_players']=['Lucas Rosa']
        item['video_reference']='QA PlayBase clip 63:20'
        item['classification']='Tactical Tendency'
    html=html_report(model)
    assert not re.search(r'<(?:img|svg|picture|canvas|object)\b',html,re.I)
    assert 'data:image' not in html
    for color in re.findall(r'#[a-fA-F0-9]{3,6}\b',html):
        rgb=color[1:]
        if len(rgb)==3:rgb=''.join(c*2 for c in rgb)
        assert rgb[:2]==rgb[2:4]==rgb[4:]
    assert all(c.strip()=='#000' for c in re.findall(r'(?<![-\w])color\s*:\s*([^;}]+)',html))
    data=pdf_report(model);reader=PdfReader(BytesIO(data));doc=pdfium.PdfDocument(data)
    text=' '.join(' '.join(page.extract_text() for page in reader.pages).split())
    assert 'QA finding '+str(count) in text and 'Tactical Tendency' in text and '63:20' in text
    for index,page in enumerate(reader.pages):
        assert not list(page.images)
        rgb=doc[index].render(scale=.8).to_pil().convert('RGB');r,g,b=rgb.split()
        assert ImageChops.difference(r,g).getbbox() is None
        assert ImageChops.difference(r,b).getbbox() is None


def test_preview_is_collapsed_and_exports_are_outside_it(report):
    store,ident=setup_store(report);finding=store.create(ident,payload());store.select(ident,[finding['id']])
    app=loaded_app(report)
    preview=next(e for e in app.expander if e.label=='Report preview')
    assert not preview.proto.expanded
    assert not preview.get('download_button') and not preview.get('button')
    assert any(b.label=='Download shareable HTML' for b in app.get('download_button'))
    assert app.button(key='workflow_prepare_pdf')
    assert not any(e.label=='Supporting source visualization' for e in app.selectbox)
    assert not any(e.label=='Player highlights (optional)' for e in app.multiselect)


def test_saving_text_never_overwrites_hidden_image_fields_or_finding_content(report):
    store,ident=setup_store(report)
    f=store.create(ident,dict(payload(),visual_key='dribbles',highlight_players=['Lucas Rosa','J. Hato'],
                             source_refs=[{'table':'03_player_duels_set_pieces.csv','snapshot':'Retained evidence'}]))
    store.select(ident,[f['id']]);before=store.get(ident,f['id'])
    app=loaded_app(report)
    # Stale widget values from the previous editor must not be written back.
    app.session_state[coach_editor.widget_key(f['id'],'visual_key')]=''
    app.session_state[coach_editor.widget_key(f['id'],'highlight_players')]=[]
    app.text_area(key=coach_editor.widget_key(f['id'],'coach_summary')).set_value('Updated analyst-written summary')
    app.button(key='workflow_coach_save_'+f['id']).click().run(timeout=30)
    assert not app.exception
    saved=store.get(ident,f['id'])
    assert saved['coach_summary']=='Updated analyst-written summary'
    for key in ['visual_key','highlight_players','source_refs','supporting_evidence','observation','category','status','classification','included','position','created']:
        assert saved[key]==before[key]
