"""Build the reviewed AI4BRAIN technical report PDF from Markdown using ReportLab."""
from __future__ import annotations
from html import escape
from pathlib import Path
import re
from xml.sax.saxutils import escape as xml_escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer,
    Table, TableStyle, Preformatted, KeepTogether)

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'docs'/'submission'/'technical-report.md'
OUTPUT=ROOT/'docs'/'submission'/'AI4BRAIN-Technical-Report.pdf'
FONT=Path(r'C:\Windows\Fonts')


def inline_markup(text: str) -> str:
    value=xml_escape(text)
    value=re.sub(r'`([^`]+)`',r'<font name="Courier">\1</font>',value)
    value=re.sub(r'\*\*([^*]+)\*\*',r'<b>\1</b>',value)
    value=re.sub(r'\*([^*]+)\*',r'<i>\1</i>',value)
    return value


class ReportDoc(BaseDocTemplate):
    def __init__(self, filename: str):
        super().__init__(filename,pagesize=A4,leftMargin=18*mm,rightMargin=18*mm,topMargin=19*mm,bottomMargin=18*mm,
            title='AI4BRAIN Technical Report',author='AI4BRAIN project',subject='Implementation and software evidence')
        frame=Frame(self.leftMargin,self.bottomMargin,self.width,self.height,id='normal',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
        self.addPageTemplates([PageTemplate(id='report',frames=frame,onPage=self._chrome)])
    def _chrome(self,canvas,doc):
        canvas.saveState();w,h=A4
        canvas.setStrokeColor(colors.HexColor('#D8DDE5'));canvas.setLineWidth(.55)
        canvas.line(18*mm,h-12.5*mm,w-18*mm,h-12.5*mm)
        canvas.setFont('Arial',7.5);canvas.setFillColor(colors.HexColor('#596474'))
        canvas.drawString(18*mm,h-10.5*mm,'AI4BRAIN  |  TECHNICAL REPORT')
        canvas.drawRightString(w-18*mm,h-10.5*mm,'IMPLEMENTATION AND SOFTWARE EVIDENCE')
        canvas.line(18*mm,12.5*mm,w-18*mm,12.5*mm)
        canvas.drawString(18*mm,8.5*mm,'19 October 2026  |  Preliminary task-performance demonstrator')
        canvas.drawRightString(w-18*mm,8.5*mm,f'{doc.page}')
        canvas.restoreState()


def parse_markdown(text: str):
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='ReportTitle',parent=styles['Title'],fontName='Arial-Bold',fontSize=20,leading=24,
        textColor=colors.HexColor('#1E2630'),alignment=TA_LEFT,spaceAfter=5))
    styles.add(ParagraphStyle(name='ReportMeta',parent=styles['Normal'],fontName='Arial',fontSize=9,leading=12,
        textColor=colors.HexColor('#536274'),spaceAfter=12))
    styles.add(ParagraphStyle(name='H2custom',parent=styles['Heading2'],fontName='Arial-Bold',fontSize=12.2,leading=15,
        textColor=colors.HexColor('#173A63'),spaceBefore=8,spaceAfter=4,keepWithNext=True))
    styles.add(ParagraphStyle(name='H3custom',parent=styles['Heading3'],fontName='Arial-Bold',fontSize=10.3,leading=13,
        textColor=colors.HexColor('#27394E'),spaceBefore=6,spaceAfter=3,keepWithNext=True))
    styles.add(ParagraphStyle(name='BodyCustom',parent=styles['BodyText'],fontName='Arial',fontSize=8.55,leading=11.15,
        textColor=colors.HexColor('#242A32'),spaceAfter=5.2,allowWidows=0,allowOrphans=0))
    styles.add(ParagraphStyle(name='TableBody',parent=styles['BodyText'],fontName='Arial',fontSize=7.55,leading=9.2,
        textColor=colors.HexColor('#242A32'),spaceAfter=0))
    styles.add(ParagraphStyle(name='TableHead',parent=styles['BodyText'],fontName='Arial-Bold',fontSize=7.6,leading=9.2,
        textColor=colors.white,spaceAfter=0))
    styles.add(ParagraphStyle(name='CodeCustom',parent=styles['Code'],fontName='Courier',fontSize=6.7,leading=8.2,
        textColor=colors.HexColor('#263240'),backColor=colors.HexColor('#F2F5F8'),borderPadding=5,spaceBefore=2,spaceAfter=7))
    lines=text.splitlines();story=[];i=0;seen_title=False
    while i<len(lines):
        line=lines[i].strip()
        if not line:i+=1;continue
        if line.startswith('```'):
            i+=1;buf=[]
            while i<len(lines) and not lines[i].strip().startswith('```'):
                buf.append(lines[i]);i+=1
            i+=1;story.append(Preformatted('\n'.join(buf),styles['CodeCustom']));continue
        if line.startswith('|') and i+1<len(lines) and re.match(r'^\|?\s*:?-{2,}',lines[i+1].strip()):
            raw=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                cells=[cell.strip() for cell in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-{2,}:?',cell.replace(' ','')) for cell in cells):raw.append(cells)
                i+=1
            table_data=[]
            for r,row in enumerate(raw):
                cell_style=styles['TableHead'] if r==0 else styles['TableBody']
                table_data.append([Paragraph(inline_markup(c),cell_style) for c in row])
            avail=A4[0]-36*mm
            if len(table_data[0])==3 and table_data[0][0].getPlainText().strip()=='Sprint':
                col_widths=[32*mm,58*mm,avail-90*mm]
            elif len(table_data[0])==3:
                col_widths=[52*mm,38*mm,avail-90*mm]
            else:
                col_widths=None
            tbl=Table(table_data,colWidths=col_widths,repeatRows=1,hAlign='LEFT',splitByRow=1)
            tbl.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#29496D')),
                ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F4F7FA')]),
                ('GRID',(0,0),(-1,-1),.35,colors.HexColor('#D7DEE7')),
                ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
                ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
            story.extend([tbl,Spacer(1,7)]);continue
        if line.startswith('# '):
            story.append(Paragraph(inline_markup(line[2:]),styles['ReportTitle']));seen_title=True;i+=1;continue
        if line.startswith('## '):story.append(Paragraph(inline_markup(line[3:]),styles['H2custom']));i+=1;continue
        if line.startswith('### '):story.append(Paragraph(inline_markup(line[4:]),styles['H3custom']));i+=1;continue
        if re.match(r'^\*\*Technical report \|',line):
            story.append(Paragraph(inline_markup(line.replace('**','')),styles['ReportMeta']));i+=1;continue
        if line.startswith('|'):
            i+=1;continue
        # Keep numbered references and list rows compact but fully readable.
        style=styles['BodyCustom']
        if re.match(r'^(\d+\.|[-*] )',line):
            line=re.sub(r'^[-*] ','-  ',line)
        story.append(Paragraph(inline_markup(line),style));i+=1
    return story


def main():
    for alias,filename in [('Arial','arial.ttf'),('Arial-Bold','arialbd.ttf'),('Arial-Italic','ariali.ttf'),('Arial-BoldItalic','arialbi.ttf')]:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        pdfmetrics.registerFont(TTFont(alias,str(FONT/filename)))
    text=SOURCE.read_text(encoding='utf-8')
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    doc=ReportDoc(str(OUTPUT));doc.build(parse_markdown(text))
    from pypdf import PdfReader
    page_count=len(PdfReader(str(OUTPUT)).pages)
    if page_count > 8:
        raise RuntimeError(f'Report has {page_count} pages; the submission limit is 8.')
    print(f'Wrote {OUTPUT} ({page_count} pages)')

if __name__=='__main__':main()
