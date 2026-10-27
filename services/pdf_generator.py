from pathlib import Path
from tempfile import NamedTemporaryFile
from html import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable
from pypdf import PdfReader

ORANGE=colors.HexColor("#B55228"); GREEN=colors.HexColor("#187A3C"); RED=colors.HexColor("#B22222")
class DigestPDF:
    def __init__(self):
        ss=getSampleStyleSheet(); self.title=ParagraphStyle("DigestTitle", parent=ss["Title"], textColor=colors.HexColor("#1A1A1A"), fontName="Helvetica-Bold", fontSize=19, leading=23, spaceAfter=3)
        self.subtitle=ParagraphStyle("DigestSubtitle", parent=ss["BodyText"], textColor=colors.HexColor("#555555"), fontSize=10.2, leading=14, spaceAfter=12)
        self.heading=ParagraphStyle("DigestHeading", parent=ss["Heading2"], textColor=ORANGE, fontName="Helvetica-Bold", fontSize=12.5, leading=16, spaceBefore=13, spaceAfter=7, keepWithNext=True)
        self.body=ParagraphStyle("DigestBody", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.6, leading=15, spaceAfter=6)
        self.small=ParagraphStyle("DigestSmall", parent=self.body, fontSize=8.3, leading=12)
    def p(self,text,style=None): return Paragraph(escape(str(text)),style or self.body)
    def link(self, title, url):
        return Paragraph(f'• <a href="{escape(url, quote=True)}" color="#222222"><b>{escape(title)}</b></a>', self.body)
    def colored(self, text, color):
        return Paragraph(escape(str(text)), ParagraphStyle("movement", parent=self.small, textColor=color))
    def _table(self, headers, rows):
        def cell(value): return value if isinstance(value, Paragraph) else self.p(str(value),self.small)
        header_style=ParagraphStyle("TableHeader",parent=self.body,fontName="Helvetica-Bold",fontSize=9.1,leading=12)
        formatted=[[self.p(h,header_style) for h in headers]]+[[cell(v) for v in row] for row in rows]
        table=Table(formatted, colWidths=[67*mm,43*mm,43*mm] if len(headers)==3 else None, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([("LINEBELOW",(0,0),(-1,0),0.6,colors.HexColor("#CFCFCF")),("LINEBELOW",(0,1),(-1,-1),0.35,colors.HexColor("#E0E0E0")),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),1),("RIGHTPADDING",(0,0),(-1,-1),4),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),("NOSPLIT",(0,0),(-1,-1))]))
        return table
    def build(self,digest,output):
        output=Path(output); output.parent.mkdir(parents=True,exist_ok=True)
        tmp=NamedTemporaryFile(suffix=".pdf",dir=str(output.parent),delete=False); tmp.close()
        doc=SimpleDocTemplate(tmp.name,pagesize=A4,rightMargin=20*mm,leftMargin=20*mm,topMargin=16*mm,bottomMargin=18*mm,title="Daily Market Digest")
        story=[self.p(f"Market Digest — {digest.trading_date:%Y-%m-%d}",self.title),HRFlowable(width="100%",thickness=1.3,color=ORANGE,spaceAfter=8),self.p(f"Daily Market Digest — {digest.trading_date:%B %d, %Y}",self.subtitle)]
        if digest.mode == "demo": story += [self.p("DEMONSTRATION REPORT: all market values, organisations, and news below are fictional synthetic fixtures; not live market data.", ParagraphStyle("warning",parent=self.small,textColor=RED,fontName="Helvetica-Bold",spaceAfter=5))]
        story += [self.p("Index Snapshot",self.heading)]
        indexes=[]
        for i in digest.indexes:
            color=GREEN if i.percent_change>=0 else RED
            indexes.append(Paragraph(f'• <b>{escape(i.name)}:</b> {i.close:,.2f} (<font color="{color.hexval()}">{i.percent_change:+.2f}%</font>)',self.body))
        story += indexes+[Spacer(1,3),self.p("Values are calculated from the stated data source using current and prior session closes.",self.small),self.p("Market Narrative",self.heading),self.p(digest.narrative)]
        story += [self.p("News Headlines",self.heading)]
        if digest.news:
            for a in digest.news:
                when=a.published_at.strftime("%d %b %Y %H:%M UTC") if a.published_at else "Publication time unavailable"
                story.append(KeepTogether([self.link(a.title,a.url),self.p(f"{a.summary or 'Summary unavailable.'} {a.publisher or 'Publisher unavailable'} · {when}",self.small)]))
        else: story.append(self.p("No verified news items were available."))
        story += [self.p("Stock & Company Updates",self.heading)]
        if digest.company_updates:
            for a in digest.company_updates: story.append(KeepTogether([self.link(a.title,a.url),self.p(a.summary or "Reported company-specific item; see source link.",self.small)]))
        else: story.append(self.p("No distinct company updates were available from the collected evidence."))
        e=digest.education
        story += [self.p(f"Word of the Day: {e.term}",self.heading),self.p(e.definition+" "+e.explanation+" "+e.why_it_matters,self.body)]
        def rows(items): return [(m.name,f"Rs {m.close:,.2f}",self.colored(("▲ " if m.percent_change>=0 else "▼ ")+f"{abs(m.percent_change):.2f}%", GREEN if m.percent_change>=0 else RED)) for m in items]
        story += [self.p("Top Gainers (Nifty 50)",self.heading),self._table(["Stock","Price (INR)","Change"],rows(digest.gainers)) if digest.gainers else self.p("No validated gainers available."),self.p("Top Losers (Nifty 50)",self.heading),self._table(["Stock","Price (INR)","Change"],rows(digest.losers)) if digest.losers else self.p("No validated losers available.")]
        if digest.disclosures: story += [self.p("Data-quality disclosures",self.heading)]+[self.p("• "+x,self.small) for x in digest.disclosures]
        story.append(Spacer(1,13)); story.append(HRFlowable(width="100%",thickness=0.35,color=colors.HexColor("#D8D8D8"),spaceAfter=6)); story.append(self.p("Generated automatically by the Daily Market Digest pipeline (prototype) — Internal use only. Not for client distribution.",self.small))
        def footer(canvas,doc): canvas.saveState(); canvas.setFont("Helvetica",7); canvas.setFillColor(colors.grey); canvas.drawRightString(A4[0]-17*mm,9*mm,f"Page {doc.page}"); canvas.restoreState()
        doc.build(story,onFirstPage=footer,onLaterPages=footer)
        reader=PdfReader(tmp.name); text="\n".join(p.extract_text() or "" for p in reader.pages)
        for heading in ["Index Snapshot","Market Narrative","News Headlines","Stock & Company Updates","Word of the Day","Top Gainers","Top Losers"]:
            if heading not in text: raise RuntimeError("PDF validation failed: missing "+heading)
        Path(tmp.name).replace(output); return output
