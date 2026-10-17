"""Render buyer-docs/QUICKSTART.txt to a PDF: python scripts/make_quickstart_pdf.py buyer-docs/QUICKSTART.txt buyer-docs/QUICKSTART.pdf"""
import re, sys
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted
from xml.sax.saxutils import escape
src, out = sys.argv[1], sys.argv[2]
lines = open(src, encoding="utf-8").read().split("\n")
ink, copper, muted = HexColor("#1f2328"), HexColor("#8a5a17"), HexColor("#5c636d")
H1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=ink, spaceAfter=2)
TAG = ParagraphStyle("tag", fontName="Helvetica-Oblique", fontSize=10, textColor=copper, spaceAfter=10)
H2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12.5, leading=16, textColor=copper, spaceBefore=10, spaceAfter=4)
BODY = ParagraphStyle("b", fontName="Helvetica", fontSize=9.6, leading=13, textColor=ink, spaceAfter=3)
LIST = ParagraphStyle("l", parent=BODY, leftIndent=14, firstLineIndent=-10)
CODE = ParagraphStyle("c", fontName="Courier", fontSize=8.6, leading=11, textColor=muted, leftIndent=10, spaceAfter=4)
story=[]; para=[]; kind=None
def flush():
    global para, kind
    if para:
        text=" ".join(x.strip() for x in para)
        st = LIST if kind=="list" else BODY
        story.append(Paragraph(escape(text), st))
    para=[]; kind=None
i=0
story.append(Paragraph(escape(lines[0].title().replace("Stele 1.0 - Quick Start","Stele 1.0 — Quick Start")), H1))
story.append(Paragraph(escape(lines[1]), TAG))
prev_rule=False; just_heading=False
for ln in lines[2:]:
    if ln.strip() and set(ln.strip())=={"-"}:
        flush(); prev_rule = not just_heading; just_heading=False; continue
    just_heading=False
    if prev_rule and re.match(r"^\d+\. ", ln):
        flush(); prev_rule=False
        num, title = ln.split(". ",1)
        title = title[0] + title[1:].lower()
        title = title.replace("vs pro","vs Pro").replace("free vs","Free vs").replace("Free vs pro","Free vs Pro").replace(" pro"," Pro")
        story.append(Paragraph(escape(f"{num}. {title}"), H2)); just_heading=True; continue
    prev_rule=False
    if re.match(r"^(Free|Pro|You need|First launch|Where your|Moving to|Activation checks|Each disc|Email|Or reply|Logs|License agreement):", ln) or re.match(r"^(You need|First launch|Where your|Moving to|Activation checks|Each disc|Or reply|Logs|License agreement|You can move)\b", ln):
        flush()
    if not ln.strip(): flush(); continue
    if ln.startswith("  %") or ln.startswith("  - The") is False and re.match(r"^  \S+\\", ln):
        flush(); story.append(Preformatted(ln.strip(), CODE)); continue
    if re.match(r"^(\d+\.|-) ", ln) or re.match(r"^  - ", ln):
        flush(); kind="list"; para=[ln.strip()]; continue
    if kind=="list" and ln.startswith(("   ","  ")): para.append(ln); continue
    if kind=="list": flush()
    para.append(ln)
flush()
SimpleDocTemplate(out, pagesize=letter, leftMargin=54, rightMargin=54, topMargin=48, bottomMargin=48, title="Stele Quick Start", author="Alexx Forge").build(story)
print("ok")
