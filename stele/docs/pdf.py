"""PDF siblings for the Markdown spec and how-to. ReportLab only."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle

from stele.docs.howto import HowtoGuide
from stele.docs.spec import SpecSheet
from stele.models import DISCLAIMER, human_bytes

INK = colors.HexColor("#1c1917")
RULE = colors.HexColor("#44403c")
PAPER = colors.HexColor("#fafaf9")


def _styles():
    base = getSampleStyleSheet()
    base.add(ParagraphStyle(name="SteleTitle", parent=base["Title"], textColor=INK, fontName="Times-Bold", fontSize=16))
    base.add(ParagraphStyle(name="SteleH", parent=base["Heading2"], textColor=INK, fontName="Times-Bold", fontSize=12, spaceBefore=10))
    base.add(ParagraphStyle(name="SteleBody", parent=base["BodyText"], textColor=INK, fontName="Times-Roman", fontSize=10, leading=13))
    return base


def _doc(path: Path) -> SimpleDocTemplate:
    path.parent.mkdir(parents=True, exist_ok=True)
    return SimpleDocTemplate(
        str(path),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        title="Stele",
    )


def write_spec_pdf(spec: SpecSheet, path: Path) -> None:
    styles = _styles()
    story = [
        Paragraph("STELE", styles["SteleH"]),
        Paragraph(spec.repo_id, styles["SteleTitle"]),
        Paragraph(
            f"Revision {spec.revision} · commit {spec.commit_sha} · {spec.snapshot_utc}",
            styles["SteleBody"],
        ),
        Spacer(1, 8),
        Paragraph("License", styles["SteleH"]),
        Paragraph(f"{spec.license_name}. {spec.license_excerpt}", styles["SteleBody"]),
        Paragraph("Full license file is on this disc.", styles["SteleBody"]),
        Paragraph(DISCLAIMER, styles["SteleBody"]),
        Paragraph("Architecture", styles["SteleH"]),
        Paragraph(
            f"Architecture {spec.facts.architecture}. Parameters {spec.facts.parameter_count}. "
            f"Context {spec.facts.context}. Vocab {spec.facts.vocab}.",
            styles["SteleBody"],
        ),
        Paragraph(
            f"GGUF quants: {', '.join(spec.quants) or 'none'}. "
            f"Safetensors dtype: {', '.join(spec.safetensors_dtypes) or 'none'}. "
            f"Hardware class {spec.hardware_class}. "
            f"Weights about {spec.weight_bytes / (1024 ** 3):.2f} GB; plan headroom for the KV cache.",
            styles["SteleBody"],
        ),
        Paragraph("Files", styles["SteleH"]),
    ]
    data = [["Path", "Bytes", "SHA-256"]]
    for row in spec.files:
        data.append([row.path, human_bytes(row.nbytes), row.sha256[:16]])
    table = Table(data, colWidths=[3.4 * inch, 0.9 * inch, 2.2 * inch])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Times-Roman"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e7e5e4")),
                ("TEXTCOLOR", (0, 0), (-1, -1), INK),
                ("GRID", (0, 0), (-1, -1), 0.25, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(table)
    _doc(path).build(story)


def write_howto_pdf(guide: HowtoGuide, path: Path) -> None:
    styles = _styles()
    story = [
        Paragraph("STELE", styles["SteleH"]),
        Paragraph(f"How to use {guide.repo_id}", styles["SteleTitle"]),
    ]
    for block in guide.markdown.split("\n\n"):
        text = block.strip()
        if not text or text.startswith("# "):
            continue
        if text.startswith("## "):
            story.append(Paragraph(text[3:], styles["SteleH"]))
        elif text.startswith("`") and text.endswith("`"):
            story.append(Preformatted(text.strip("`"), styles["SteleBody"]))
        else:
            safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
            story.append(Paragraph(safe, styles["SteleBody"]))
    _doc(path).build(story)
