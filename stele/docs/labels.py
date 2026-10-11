"""Printable disc face and US Letter case insert. No printer required to generate them."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from stele.models import DISCLAIMER


def write_disc_face(
    path: Path,
    *,
    model_ids: list[str],
    commit_short: str,
    when: str,
    volume: int,
    count: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    page = 140 * mm
    c = canvas.Canvas(str(path), pagesize=(page, page))
    c.setTitle("Stele disc face")
    cx = cy = page / 2
    radius = 60 * mm
    c.setStrokeColorRGB(0.11, 0.09, 0.09)
    c.setFillColorRGB(0.98, 0.98, 0.97)
    c.setLineWidth(1.2)
    c.circle(cx, cy, radius, stroke=1, fill=1)
    c.setFillColorRGB(0.11, 0.09, 0.09)
    c.setFont("Times-Bold", 18)
    c.drawCentredString(cx, cy + 28 * mm, "STELE")
    c.setFont("Times-Roman", 9)
    y = cy + 16 * mm
    for model_id in model_ids[:4]:
        c.drawCentredString(cx, y, model_id[:42])
        y -= 11
    c.setFont("Times-Roman", 9)
    c.drawCentredString(cx, cy - 8 * mm, commit_short)
    c.drawCentredString(cx, cy - 16 * mm, when)
    c.setFont("Times-Bold", 11)
    c.drawCentredString(cx, cy - 28 * mm, f"DISC {volume} OF {count}")
    c.setFont("Times-Roman", 8)
    c.drawCentredString(cx, cy - 38 * mm, "M-DISC ARCHIVE")
    c.showPage()
    c.save()


def write_case_insert(
    path: Path,
    *,
    model_ids: list[str],
    license_name: str,
    summary: str,
    checksum_prefixes: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=(612, 792))
    c.setTitle("Stele case insert")
    c.setFillColorRGB(0.98, 0.98, 0.97)
    c.rect(0, 0, 612, 792, stroke=0, fill=1)
    c.setFillColorRGB(0.11, 0.09, 0.09)
    c.setFont("Times-Bold", 22)
    c.drawString(54, 740, "STELE")
    c.setFont("Times-Roman", 11)
    c.drawString(54, 716, "M-DISC ARCHIVE")
    c.setFont("Times-Bold", 12)
    y = 680
    c.drawString(54, y, "Models")
    y -= 18
    c.setFont("Times-Roman", 11)
    for model_id in model_ids[:8]:
        c.drawString(54, y, model_id)
        y -= 14
    y -= 10
    c.setFont("Times-Bold", 12)
    c.drawString(54, y, "Specification")
    y -= 16
    c.setFont("Times-Roman", 10)
    for chunk in _wrap(summary, 78):
        c.drawString(54, y, chunk)
        y -= 13
    y -= 8
    c.setFont("Times-Bold", 12)
    c.drawString(54, y, "License")
    y -= 16
    c.setFont("Times-Roman", 11)
    c.drawString(54, y, license_name or "unknown")
    y -= 28
    c.setFont("Times-Bold", 12)
    c.drawString(54, y, "Checksum prefixes")
    y -= 16
    c.setFont("Times-Roman", 10)
    prefixes = checksum_prefixes[:12] or ["(none)"]
    c.drawString(54, y, "  ".join(prefixes))
    y -= 36
    c.setFont("Times-Bold", 12)
    c.drawString(54, y, "Restore")
    y -= 18
    c.setFont("Times-Roman", 10)
    c.drawString(54, y, "powershell -ExecutionPolicy Bypass -File .\\RESTORE.ps1 -Destination D:\\Restored")
    y -= 28
    c.setFont("Times-Italic", 10)
    for chunk in _wrap(DISCLAIMER, 78):
        c.drawString(54, y, chunk)
        y -= 13
    c.showPage()
    c.save()


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        if len(trial) > width:
            if current:
                lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines or [""]
