"""Optional classification is independent, backwards compatible and exportable."""
from io import BytesIO
import json
import pytest
from pypdf import PdfReader
from opponent_intelligence.workflow.store import FindingsStore,CLASSIFICATIONS
from opponent_intelligence.workflow.reports import coach_model,html_report,pdf_report
from test_dashboard import report,loaded_app
from test_workflow import setup_store,payload


def legacy_record(report,tmp_path):
    store,ident=setup_store(report,tmp_path/'legacy.sqlite3')
    finding=store.create(ident,dict(payload(),source_refs=[{'file':'original.csv','snapshot':'44/85'}],visual_key='lost_duels'))
    store.select(ident,[finding['id']])
    with store.connection() as db:
        row=dict(db.execute('SELECT * FROM findings WHERE id=?',(finding['id'],)).fetchone())
        legacy=json.loads(row['payload']);legacy.pop('classification')
        db.execute('UPDATE findings SET payload=? WHERE id=?',(json.dumps(legacy),finding['id']))
        before=dict(db.execute('SELECT * FROM findings WHERE id=?',(finding['id'],)).fetchone())
    return store,ident,finding,before


def test_legacy_read_does_not_rewrite_or_drop_evidence(report,tmp_path):
    store,ident,finding,before=legacy_record(report,tmp_path)
    record=FindingsStore(store.path).get(ident,finding['id'])
    assert record['classification'] is None
    assert record['included'] and record['position']==0
    assert record['video_reference']==finding['video_reference']
    with store.connection() as db:
        assert dict(db.execute('SELECT * FROM findings WHERE id=?',(finding['id'],)).fetchone())==before
    changed=store.update(ident,finding['id'],{'classification':'Potential Weakness'})
    for field in ['id','created','status','category','source_refs','supporting_evidence','video_reference','included','position','visual_key']:
        assert changed[field]==record[field]
    assert changed['classification']=='Potential Weakness'
    assert json.loads(json.dumps(store.list(ident)))[0]['classification']=='Potential Weakness'
    assert store.update(ident,finding['id'],{'classification':None})['classification'] is None


@pytest.mark.parametrize('classification',CLASSIFICATIONS)
def test_classification_independent_of_category_status_and_report_order(report,classification):
    store,ident=setup_store(report)
    a=store.create(ident,dict(payload('One'),classification=classification,status='Confirmed',category='General'))
    b=store.create(ident,payload('Two'));store.select(ident,[b['id'],a['id']])
    assert [r['id'] for r in store.selected(ident)]==[b['id'],a['id']]
    assert store.list(ident,classification=classification)[0]['id']==a['id']
    assert store.list(ident,classification=None)[0]['id']==b['id']
    assert store.update(ident,a['id'],{'coach_summary':'Coach edit'})['classification']==classification
    assert [r['id'] for r in store.selected(ident)]==[b['id'],a['id']]
    model=coach_model(report,store.selected(ident))
    assert 'Analyst classification: '+classification in html_report(model)
    pdf=pdf_report(model)
    text=' '.join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)
    assert 'Analyst classification: '+classification in text


def test_invalid_classification_and_unclassified_exports(report):
    store,ident=setup_store(report)
    with pytest.raises(ValueError,match='classification'):
        store.create(ident,dict(payload(),classification='Automatic weakness'))
    finding=store.create(ident,payload());store.select(ident,[finding['id']])
    assert 'Analyst classification:' not in html_report(coach_model(report,store.selected(ident)))


def test_legacy_editor_classification_preserves_selection_and_source(report):
    store,ident=setup_store(report)
    finding=store.create(ident,payload());store.select(ident,[finding['id']])
    with store.connection() as db:
        row=db.execute('SELECT payload FROM findings WHERE id=?',(finding['id'],)).fetchone()
        data=json.loads(row['payload']);data.pop('classification')
        db.execute('UPDATE findings SET payload=? WHERE id=?',(json.dumps(data),finding['id']))
    app=loaded_app(report)
    app.radio(key='workflow_mode').set_value('Review / edit').run(timeout=30)
    prefix='workflow_editor_'+finding['id']
    assert app.selectbox(key=prefix+'_classification').value is None
    app.selectbox(key=prefix+'_classification').set_value('Tactical Tendency')
    app.button(key=prefix+'_save').click().run(timeout=30)
    assert not app.exception
    saved=store.get(ident,finding['id'])
    assert saved['classification']=='Tactical Tendency' and saved['included']
    assert saved['supporting_evidence']==finding['supporting_evidence']
    assert saved['status']=='Draft'
