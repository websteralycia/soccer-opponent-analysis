"""Coach report models and standalone HTML/PDF exports, authored content only."""
from html import escape
from io import BytesIO
from pathlib import Path
from .store import report_identifier
from .evidence import report_metadata
from ..dashboard.data import overview, table
from ..dashboard.spatial import spatial_maps


def visual_options(result,fingerprint):
    assets={}
    for category in ['Defensive organization','Transitions','Buildup and progression','Attacking patterns','Set pieces']:
        for asset in spatial_maps(result,fingerprint,category):assets[asset['key']]=asset
    return assets


def coach_model(result,findings,fingerprint=None):
    identity=report_identifier(result,fingerprint)
    if any(f['report_id']!=identity for f in findings):raise ValueError('Cannot combine findings from different reports.')
    selected=sorted([f for f in findings if f.get('included')],key=lambda f:(f['position'],f['id']))
    if len(selected)>3:raise ValueError('Coach report supports up to three primary findings.')
    assets=visual_options(result,fingerprint)
    squad=table(result,'01')
    names=set(squad.Player.dropna()) if 'Player' in squad else set()
    items=[]
    for finding in selected:
        asset=assets.get(finding.get('visual_key'))
        items.append(dict(finding,visual=asset,highlight_players=[name for name in finding.get('highlight_players',[]) if name in names],summary=finding['coach_summary'] or 'Coach-facing summary not written.',
                          tactical_observation=finding['coach_observation'] or finding['interpretation'] or 'No analyst interpretation recorded.',
                          consideration=finding['coach_consideration'] or 'No coaching consideration authored.'))
    return dict(report_id=identity,metadata=report_metadata(result),outcomes=overview(result),findings=items)


def readiness(model):
    """Non-blocking readiness; only saved analyst text and status are considered."""
    issues=[]
    for item in model['findings']:
        missing=[]
        if not item.get('coach_summary'):missing.append('coach-facing summary')
        if not (item.get('coach_observation') or item.get('interpretation')):missing.append('tactical observation')
        if not item.get('coach_consideration'):missing.append('coaching consideration')
        if item.get('status')!='Confirmed':missing.append('review status: '+item['status'])
        if missing:issues.append(dict(id=item['id'],title=item['title'],missing=missing))
    return issues


def visual_parts(asset):
    """Registered, checked paths only; preserve full source title/legend panels."""
    return ([asset['header_path']] if asset.get('header_path') else [])+[asset.get('display_path') or asset['path']]


def source_records(item):
    """Remove duplicate display text, never change the saved evidence snapshot."""
    import json
    out=[];seen=set();evidence=item.get('supporting_evidence','').strip()
    for original in item.get('source_refs',[]):
        token=json.dumps(original,sort_keys=True,ensure_ascii=False)
        if token in seen:continue
        seen.add(token);ref=dict(original);snapshot=str(ref.get('snapshot','')).strip()
        if evidence and snapshot.startswith(evidence):snapshot=snapshot[len(evidence):].lstrip(' ;.\n')
        ref['display_snapshot']=snapshot;out.append(ref)
    return out


def overview_line(model):
    o=model.get('outcomes')
    if not o:return 'Match results unavailable.'
    def val(value):return '—' if value is None else str(value)
    return f"{o['wins']}W / {o['draws']}D / {o['losses']}L · Goals {val(o['goals_for'])} for / {val(o['goals_against'])} against. Source: match results."


def key_finding(item):
    text=item.get('coach_summary') or item['title']
    return text if len(text)<=115 else text[:112].rstrip()+'…'


def visual_caption(asset,model):
    return f"{asset['label']} · {model['metadata']['matches']}-match aggregate · Wyscout PDF p.{asset['page']}; not match-specific."


def html_report(model):
    def txt(value):return escape(str('' if value is None else value)).replace('\n','<br>')
    m=model['metadata'];draft=bool(readiness(model));parts=[]
    parts.append('''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Opposition scouting brief</title><style>
    *{box-sizing:border-box}html,body{background:#fff;color:#000;color-scheme:light}body{font:15px/1.45 Arial,sans-serif;max-width:960px;margin:22px auto;padding:0 24px}header{margin-bottom:7px}h1{font-size:25px;margin:0}h2{font-size:19px;line-height:1.3;margin:0 0 7px}h3{font-size:14px;margin:13px 0 4px}p{margin:6px 0 10px}.scope,footer{font-size:12px;color:#000}.overview{margin-bottom:18px}.overview ol{padding-left:21px;margin:8px 0}.draft{border:1px solid #999;background:#fff;padding:8px 12px;font-size:13px}.finding{background:#fff;border:0;border-top:1px solid #999;padding:17px 0;margin:14px 0}.summary{font-size:16px;font-weight:600}.status{font-size:12px;color:#000}.sources{font-size:11px;line-height:1.4;color:#000;border-top:1px solid #aaa;margin-top:12px;padding-top:7px}.sources p{margin:5px 0}.sources h3{font-size:12px;margin:0 0 5px}.consideration{border-left:2px solid #000;padding:5px 10px;margin-top:10px;background:#fff}footer{border-top:1px solid #999;margin-top:15px;padding-top:7px;overflow-wrap:anywhere}@media print{html,body{background:#fff;color:#000}body{margin:0;padding:0;max-width:none;font-size:10pt}.finding{break-inside:auto}h2,h3{break-after:avoid}.sources{font-size:8pt}}
    </style></head><body>''')
    parts.append(f'<section class="overview"><header><h1>{txt(m["team"])} · opposition scouting brief</h1></header>')
    parts.append(f'<p class="scope">{m["matches"]} matches · {txt(m["start"])} to {txt(m["end"])}</p><p>{txt(overview_line(model))}</p>')
    if draft:parts.append('<p class="draft"><b>Draft brief</b> · Coaching content or review status is incomplete. Confirmed is an analyst status, not automated verification.</p>')
    if model['findings']:
        parts.append('<h3>Key findings · analyst selected</h3><ol>'+''.join('<li>'+txt(key_finding(item))+'</li>' for item in model['findings'])+'</ol>')
    else:parts.append('<p>No findings selected.</p>')
    parts.append('</section>')
    for index,item in enumerate(model['findings'],1):
        classification=(' · Analyst classification: '+item['classification']) if item.get('classification') else ''
        parts.append(f'<section class="finding"><h2>{index}. {txt(item["title"])}</h2><p class="status">{txt(item["status"]+classification)}</p><p class="summary">{txt(item["summary"])}</p>')
        parts.append('<h3>Tactical observation · analyst interpretation</h3><p>'+txt(item['tactical_observation'])+'</p>')
        if item.get('supporting_evidence'):parts.append('<h3>Supporting statistical evidence</h3><p>'+txt(item['supporting_evidence'])+'</p>')
        for label,key in [('Match context','match_context'),('Video references · analyst supplied','video_reference')]:
            if item.get(key):parts.append('<h3>'+label+'</h3><p>'+txt(item[key])+'</p>')
        parts.append('<div class="consideration"><h3>Coaching consideration · analyst authored</h3><p>'+txt(item['consideration'])+'</p></div>')
        refs=source_records(item)
        if refs or item.get('contradictory_evidence'):
            parts.append('<div class="sources"><h3>Supporting sources &amp; limits</h3>')
            if item.get('contradictory_evidence'):parts.append('<p><b>Contrary evidence / limits:</b> '+txt(item['contradictory_evidence'])+'</p>')
            for ref in refs:
                parts.append('<p><b>'+txt(ref.get('table',''))+' · '+txt(ref.get('column',''))+'</b><br>'+txt(ref.get('display_snapshot',''))+' '+txt(ref.get('scope',''))+'; PDF p.'+txt(ref.get('page',''))+'. '+txt(ref.get('calculation',''))+' '+txt(ref.get('definition',''))+'</p>')
            parts.append('</div>')
        parts.append('</section>')
    parts.append('<footer>Report ID: '+txt(model['report_id'])+' · Analyst-authored; source scope and sample limitations apply.</footer></body></html>')
    return ''.join(parts)


def pdf_report(model):
    """Text-only monochrome A4 brief, with sources and context on every page."""
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,CondPageBreak
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import reportlab
    fonts=Path(reportlab.__file__).parent/'fonts'
    for name,file in [('Scout','Vera.ttf'),('ScoutBold','VeraBd.ttf')]:
        if name not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont(name,str(fonts/file)))
    ink=colors.black;muted=colors.black
    base=ParagraphStyle('BriefBody',fontName='Scout',fontSize=10,leading=13.5,textColor=ink,spaceAfter=6,allowWidows=0,allowOrphans=0)
    styles={'body':base,'scope':ParagraphStyle('BriefScope',parent=base,fontSize=8,leading=10,spaceAfter=4,textColor=muted),
            'title':ParagraphStyle('BriefTitle',parent=base,fontName='ScoutBold',fontSize=18,leading=22,spaceAfter=7),
            'finding':ParagraphStyle('BriefFinding',parent=base,fontName='ScoutBold',fontSize=13,leading=17,spaceBefore=9,spaceAfter=5,keepWithNext=True),
            'summary':ParagraphStyle('BriefSummary',parent=base,fontName='ScoutBold',fontSize=10.5,leading=14),
            'source':ParagraphStyle('BriefSource',parent=base,fontSize=8,leading=10,spaceAfter=3,textColor=muted)}
    def clean(value):return escape(str('' if value is None else value)).replace('\n','<br/>')
    def para(value,style='body'):return Paragraph(clean(value),styles[style])
    def section(label,content,style='body'):
        # A single splittable paragraph avoids keeping an entire long section together.
        return Paragraph('<b>'+clean(label)+'</b><br/>'+clean(content),styles[style])
    metadata=model['metadata'];draft=bool(readiness(model))
    class BriefDocument(SimpleDocTemplate):
        current_finding=''
        def beforePage(self):
            self.page_finding=''
            self.canv.saveState();self.canv.setFillColor(colors.white)
            self.canv.rect(0,0,A4[0],A4[1],stroke=0,fill=1);self.canv.restoreState()
        def afterFlowable(self,flowable):
            if hasattr(flowable,'finding_title'):self.current_finding=flowable.finding_title
            if isinstance(flowable,Paragraph) and not self.page_finding and self.current_finding:
                self.page_finding=self.current_finding
        def afterPage(self):
            canvas=self.canv;canvas.saveState();canvas.setFillColor(muted);canvas.setFont('Scout',7.5)
            header=metadata['team']+' · opposition brief'+(' · '+self.page_finding if self.page_finding else '')
            while pdfmetrics.stringWidth(header,'Scout',7.5)>A4[0]-80:header=header[:-2].rstrip('…')+'…'
            canvas.drawString(40,A4[1]-24,header)
            canvas.setStrokeColor(colors.HexColor('#999999'));canvas.line(40,37,A4[0]-40,37)
            canvas.setFont('Scout',5.8);canvas.drawString(40,25,'Report ID: '+model['report_id'])
            canvas.setFont('Scout',7);canvas.drawRightString(A4[0]-40,25,('Draft · ' if draft else '')+f'Page {self.page}')
            canvas.restoreState()
    story=[]
    story.extend([para(metadata['team']+' · opposition scouting brief','title'),
                  para(f"{metadata['matches']} matches · {metadata['start']} to {metadata['end']}",'scope'),para(overview_line(model))])
    if draft:story.append(para('Draft brief · Coaching content or review status is incomplete. Confirmed is an analyst status, not automated verification.','scope'))
    if model['findings']:
        story.append(para('Key findings · analyst selected','summary'))
        for index,item in enumerate(model['findings'],1):story.append(para(f'{index}. '+key_finding(item),'scope'))
    else:story.append(para('No findings selected.'))
    for index,item in enumerate(model['findings'],1):
        story.append(CondPageBreak(100 if index==1 else 170))
        title=para(f'{index}. '+item['title'],'finding');title.finding_title=item['title'];story.append(title)
        state=item['status']+(' · Analyst classification: '+item['classification'] if item.get('classification') else '')
        story.extend([para(state,'scope'),para(item['summary'],'summary'),section('Tactical observation · analyst interpretation',item['tactical_observation'])])
        if item.get('supporting_evidence'):story.append(section('Supporting statistical evidence',item['supporting_evidence']))
        for label,key in [('Match context','match_context'),('Video references · analyst supplied','video_reference')]:
            if item.get(key):story.append(section(label,item[key]))
        story.append(section('Coaching consideration · analyst authored',item['consideration']))
        refs=source_records(item)
        if refs or item.get('contradictory_evidence'):
            story.append(para('Supporting sources & limits','scope'))
            if item.get('contradictory_evidence'):story.append(section('Contrary evidence / limits',item['contradictory_evidence'],'source'))
            for ref in refs:
                text=ref.get('table','')+' · '+ref.get('column','')+'; PDF p.'+str(ref.get('page',''))+'. '+ref.get('display_snapshot','')+' '+ref.get('scope','')+'. '+ref.get('calculation','')+' '+ref.get('definition','')
                story.append(para(text,'source'))
        story.append(Spacer(1,6))
    output=BytesIO();document=BriefDocument(output,pagesize=A4,leftMargin=40,rightMargin=40,topMargin=43,bottomMargin=46,title=metadata['team']+' opposition scouting brief',allowSplitting=True)
    document.build(story)
    return output.getvalue()
