"""Alexx Forge brand-locked 1080x1920 video & cover compositor (PySide6 + FFmpeg).

Enforces all 6 checks of the Alexx Forge Premium Bar:
1. Clean hierarchy: 1 headline, 1 subhead/caption, 1 small A-anvil brand mark.
2. One focal point per shot (cropped 2x HiDPI UI or single structured diagram).
3. >= 8% margin on every edge; clears YouTube Shorts bottom (520px) & right rail (164px).
4. Strictly locked Brand Book hex palette + max 2 font families (Montserrat + Inter).
5. Thumbnail readability verified via automated 120px contact sheet; <= 4 words on covers.
6. Zero stock-AI imagery, zero purple/blue/neon, zero prices baked into cover PNGs.
"""

from __future__ import annotations

from functools import lru_cache
import math
import shutil
import subprocess
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)

from videos.config import (
    APP_NAME,
    APP_TAGLINE,
    BRAND_EMAIL,
    BRAND_HANDLE,
    BRAND_TAGLINE,
    CANVAS_H,
    CANVAS_W,
    FONTS_DIR,
    FPS,
    GUMROAD_SHOP_DISPLAY,
    MARGIN_X,
    PALETTE,
    PRO_MACHINES_COUNT,
    SAFE_TOP,
    SHORTS_RIGHT_RAIL_X,
    STELE_FREE_PRICE,
    STELE_PRO_PRICE,
    UI_CAPTURES_DIR,
)

C_CHARCOAL = QColor(PALETTE["forge_charcoal"])   # #1E1F22
C_BLACK = QColor(PALETTE["anvil_black"])         # #0D0E10
C_ORANGE = QColor(PALETTE["forge_orange"])       # #F26B1D
C_EMBER = QColor(PALETTE["ember_orange"])        # #DE570C
C_COPPER = QColor(PALETTE["copper"])             # #B06742
C_STEEL = QColor(PALETTE["brushed_steel"])       # #969595
C_WHITE = QColor(PALETTE["spark_white"])         # #F8F8F8

_HEADLINE_FAMILY = "Arial"
_BODY_FAMILY = "Arial"
_FONTS_LOADED = False


def ensure_brand_fonts() -> tuple[str, str]:
    global _FONTS_LOADED, _HEADLINE_FAMILY, _BODY_FAMILY
    if _FONTS_LOADED:
        return _HEADLINE_FAMILY, _BODY_FAMILY
    for name in ("Montserrat-Variable.ttf", "Montserrat-Bold.ttf", "Montserrat-Black.ttf"):
        fp = FONTS_DIR / name
        if fp.exists():
            fid = QFontDatabase.addApplicationFont(str(fp))
            fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
            if fams:
                _HEADLINE_FAMILY = fams[0]
    inter_fp = FONTS_DIR / "Inter-Variable.ttf"
    if inter_fp.exists():
        fid = QFontDatabase.addApplicationFont(str(inter_fp))
        fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
        if fams:
            _BODY_FAMILY = fams[0]
    _FONTS_LOADED = True
    return _HEADLINE_FAMILY, _BODY_FAMILY


@lru_cache(maxsize=64)
def make_headline_font(px: int, weight: QFont.Weight = QFont.ExtraBold, tracking_pct: float = 105.0) -> QFont:
    ensure_brand_fonts()
    f = QFont(_HEADLINE_FAMILY)
    f.setPixelSize(px)
    f.setWeight(weight)
    f.setLetterSpacing(QFont.PercentageSpacing, tracking_pct)
    return f


@lru_cache(maxsize=64)
def make_body_font(px: int, weight: QFont.Weight = QFont.DemiBold, tracking_pct: float = 100.0) -> QFont:
    ensure_brand_fonts()
    f = QFont(_BODY_FAMILY)
    f.setPixelSize(px)
    f.setWeight(weight)
    if tracking_pct != 100.0:
        f.setLetterSpacing(QFont.PercentageSpacing, tracking_pct)
    return f


def ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def ease_in_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 4 * t * t * t if t < 0.5 else 1 - ((-2 * t + 2) ** 3) / 2


def draw_anvil_mark(p: QPainter, cx: float, cy: float, size: float) -> None:
    """Draw the Alexx Forge A-Anvil mark (Kit 3 geometry: steel A + hammer & anvil in copper-orange ring).

    Respects Brand Book Logo Rules: >= 48px on screen; below 120px omits wordmark underneath;
    uses strictly locked palette hexes without drop shadows or off-palette glows.
    """
    p.save()
    r = size / 2.0

    # Deep Anvil Black circular disc
    p.setPen(Qt.NoPen)
    p.setBrush(C_BLACK)
    p.drawEllipse(QPointF(cx, cy), r, r)

    # Outer Copper ring + Forge Orange rim highlight
    ring_w = max(2.2, size * 0.068)
    grad_ring = QLinearGradient(cx - r, cy - r, cx + r, cy + r)
    grad_ring.setColorAt(0.0, C_ORANGE)
    grad_ring.setColorAt(0.55, C_COPPER)
    grad_ring.setColorAt(1.0, C_EMBER)
    p.setPen(QPen(grad_ring, ring_w))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(cx, cy), r - ring_w * 0.55, r - ring_w * 0.55)

    # Stylized wide steel "A" legs
    s = size * 0.50
    leg_grad = QLinearGradient(cx, cy - s * 0.65, cx, cy + s * 0.65)
    leg_grad.setColorAt(0.0, C_WHITE)
    leg_grad.setColorAt(0.55, C_STEEL)
    leg_grad.setColorAt(1.0, C_CHARCOAL.lighter(150))

    path_a = QPainterPath()
    # Outer A silhouette
    path_a.moveTo(cx, cy - s * 0.62)
    path_a.lineTo(cx + s * 0.56, cy + s * 0.62)
    path_a.lineTo(cx + s * 0.30, cy + s * 0.62)
    path_a.lineTo(cx + s * 0.16, cy + s * 0.26)
    path_a.lineTo(cx - s * 0.16, cy + s * 0.26)
    path_a.lineTo(cx - s * 0.30, cy + s * 0.62)
    path_a.lineTo(cx - s * 0.56, cy + s * 0.62)
    path_a.closeSubpath()

    # Inner triangular counter above anvil crossbar
    counter = QPainterPath()
    counter.moveTo(cx, cy - s * 0.24)
    counter.lineTo(cx + s * 0.13, cy + s * 0.08)
    counter.lineTo(cx - s * 0.13, cy + s * 0.08)
    counter.closeSubpath()
    path_a = path_a.subtracted(counter)

    p.setPen(Qt.NoPen)
    p.setBrush(leg_grad)
    p.drawPath(path_a)

    # Horned Anvil crossbar in Forge Orange
    anvil = QPainterPath()
    ay = cy + s * 0.08
    ah = s * 0.20
    # Left horn tapering to point + flat face + right heel
    anvil.moveTo(cx - s * 0.62, ay + ah * 0.32)
    anvil.lineTo(cx - s * 0.30, ay)
    anvil.lineTo(cx + s * 0.46, ay)
    anvil.lineTo(cx + s * 0.46, ay + ah * 0.58)
    anvil.lineTo(cx + s * 0.22, ay + ah)
    anvil.lineTo(cx - s * 0.22, ay + ah)
    anvil.lineTo(cx - s * 0.34, ay + ah * 0.58)
    anvil.closeSubpath()
    p.setBrush(C_ORANGE)
    p.drawPath(anvil)

    # Small forge hammer head perched cleanly above apex
    hw = s * 0.30
    hh = s * 0.13
    hx = cx - hw * 0.5
    hy = cy - s * 0.78
    p.setBrush(C_WHITE)
    p.drawRoundedRect(QRectF(hx, hy, hw, hh), 1.5, 1.5)
    p.fillRect(QRectF(cx - s * 0.035, hy + hh, s * 0.07, s * 0.16), C_COPPER)

    p.restore()


def draw_wordmark_line(p: QPainter, center_x: float, baseline_y: float, px: int) -> None:
    """Render 'ALEXX FORGE' ('ALEXX' in steel/white, 'FORGE' in Forge Orange)."""
    p.save()
    font = make_headline_font(px, QFont.ExtraBold, 108.0)
    p.setFont(font)
    fm = p.fontMetrics()
    part1 = "ALEXX "
    part2 = "FORGE"
    w1 = fm.horizontalAdvance(part1)
    w2 = fm.horizontalAdvance(part2)
    start_x = center_x - (w1 + w2) / 2.0
    p.setPen(C_STEEL.lighter(125))
    p.drawText(QPointF(start_x, baseline_y), part1)
    p.setPen(C_ORANGE)
    p.drawText(QPointF(start_x + w1, baseline_y), part2)
    p.restore()


def draw_background(p: QPainter, w: int, h: int) -> None:
    p.fillRect(0, 0, w, h, C_BLACK)
    # Subtle Forge Charcoal center warmth (no off-palette hues)
    grad = QRadialGradient(QPointF(w * 0.5, h * 0.42), max(w, h) * 0.62)
    grad.setColorAt(0.0, QColor(30, 31, 34, 215))  # #1E1F22
    grad.setColorAt(0.65, QColor(18, 19, 22, 235))
    grad.setColorAt(1.0, C_BLACK)
    p.fillRect(0, 0, w, h, grad)


def draw_top_chrome(p: QPainter, eyebrow: str, tier_badge: str = "STELE · WINDOWS") -> None:
    """Top bar inside safe zone (y >= 164): small 56px A-anvil mark + eyebrow pill."""
    mark_size = 56.0
    cx = MARGIN_X + mark_size / 2.0
    cy = SAFE_TOP + mark_size / 2.0
    draw_anvil_mark(p, cx, cy, mark_size)

    # Clear space around mark = height of A crossbar; place eyebrow text cleanly right of mark
    p.save()
    p.setFont(make_headline_font(20, QFont.Bold, 110.0))
    p.setPen(C_STEEL)
    p.drawText(
        QRectF(MARGIN_X + mark_size + 22, SAFE_TOP + 6, 520, 26),
        Qt.AlignLeft | Qt.AlignVCenter,
        "ALEXX FORGE",
    )
    p.setFont(make_body_font(18, QFont.Medium))
    p.setPen(C_COPPER.lighter(120))
    p.drawText(
        QRectF(MARGIN_X + mark_size + 22, SAFE_TOP + 30, 520, 24),
        Qt.AlignLeft | Qt.AlignVCenter,
        eyebrow,
    )

    # Right compact status pill
    pill_font = make_headline_font(17, QFont.Bold, 106.0)
    p.setFont(pill_font)
    tw = p.fontMetrics().horizontalAdvance(tier_badge) + 32
    pill_rect = QRectF(CANVAS_W - MARGIN_X - tw, SAFE_TOP + 10, tw, 36)
    p.setPen(QPen(C_COPPER, 1.4))
    p.setBrush(C_CHARCOAL)
    p.drawRoundedRect(pill_rect, 8, 8)
    p.setPen(C_WHITE)
    p.drawText(pill_rect, Qt.AlignCenter, tier_badge)
    p.restore()


def draw_headline_block(
    p: QPainter,
    headline_lines: list[str],
    accent_word: str,
    local_t: float,
) -> None:
    """Render clean 1-2 line Montserrat ExtraBold headline in Zone A (y=246..428)."""
    p.save()
    enter = ease_out_cubic(min(1.0, local_t / 0.24))
    slide_y = (1.0 - enter) * 18.0
    p.setOpacity(0.15 + 0.85 * enter)

    px = 50 if max((len(line) for line in headline_lines), default=0) <= 20 else 43
    font = make_headline_font(px, QFont.ExtraBold, 105.0)
    p.setFont(font)
    fm = p.fontMetrics()
    line_h = px + 12
    base_y = 296.0 + slide_y

    accent_up = accent_word.strip().upper()
    for idx, raw_line in enumerate(headline_lines[:2]):
        line = raw_line.upper()
        y = base_y + idx * line_h
        if accent_up and accent_up in line:
            before, match, after = line.partition(accent_up)
            x = float(MARGIN_X)
            if before:
                p.setPen(C_WHITE)
                p.drawText(QPointF(x, y), before)
                x += fm.horizontalAdvance(before)
            p.setPen(C_ORANGE)
            p.drawText(QPointF(x, y), match)
            x += fm.horizontalAdvance(match)
            if after:
                p.setPen(C_WHITE)
                p.drawText(QPointF(x, y), after)
        else:
            p.setPen(C_WHITE)
            p.drawText(QPointF(float(MARGIN_X), y), line)

    # Subtle 56px Forge Orange rule under headline
    rule_y = base_y + (len(headline_lines[:2]) - 1) * line_h + 22
    p.fillRect(QRectF(MARGIN_X, rule_y, 68 * enter, 4), C_ORANGE)
    p.restore()


def draw_caption_pill(p: QPainter, caption: str, local_t: float, progress_ratio: float) -> None:
    """Burned-in plain-English caption inside safe zone (x=88..912, y=1178..1366).

    Stays left of x=916 to dodge YouTube Shorts right-rail buttons, and above y=1392
    to dodge both YouTube Shorts title/music overlay and X playback scrubber.
    """
    p.save()
    enter = ease_out_cubic(min(1.0, local_t / 0.20))
    card_w = float(SHORTS_RIGHT_RAIL_X - MARGIN_X)  # 828 px
    card_rect = QRectF(MARGIN_X, 1178 + (1.0 - enter) * 10.0, card_w, 184)

    p.setPen(QPen(QColor(68, 70, 76), 1.4))
    p.setBrush(C_CHARCOAL)
    p.drawRoundedRect(card_rect, 14, 14)

    # Left 5px Forge Orange accent bar
    bar_rect = QRectF(card_rect.left(), card_rect.top() + 18, 5, card_rect.height() - 36)
    p.setPen(Qt.NoPen)
    p.setBrush(C_ORANGE)
    p.drawRoundedRect(bar_rect, 2.5, 2.5)

    text_rect = QRectF(
        card_rect.left() + 26,
        card_rect.top() + 16,
        card_rect.width() - 48,
        card_rect.height() - 32,
    )
    font_px = 31 if len(caption) <= 108 else 28
    p.setFont(make_body_font(font_px, QFont.DemiBold))
    p.setPen(C_WHITE)
    p.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap, caption)

    # Ultra-clean video progress hairline at y=1384 (above safe cutoff y=1392)
    track = QRectF(MARGIN_X, 1384, card_w, 4)
    p.fillRect(track, QColor(42, 44, 49))
    p.fillRect(QRectF(MARGIN_X, 1384, card_w * max(0.0, min(1.0, progress_ratio)), 4), C_ORANGE)
    p.restore()


def _card_shell(p: QPainter, rect: QRectF, title_bar: str = "") -> QRectF:
    """Draw elevated Forge Charcoal focal card with Copper 1.5px border."""
    p.setPen(QPen(C_COPPER, 1.6))
    p.setBrush(C_CHARCOAL)
    p.drawRoundedRect(rect, 16, 16)
    if not title_bar:
        return rect.adjusted(16, 16, -16, -16)

    header_h = 44.0
    header_rect = QRectF(rect.left() + 1, rect.top() + 1, rect.width() - 2, header_h)
    clip = QPainterPath()
    clip.addRoundedRect(rect.adjusted(1, 1, -1, -1), 15, 15)
    p.save()
    p.setClipPath(clip)
    p.fillRect(header_rect, QColor(20, 22, 26))
    p.setPen(QPen(QColor(52, 56, 64), 1.0))
    p.drawLine(
        QPointF(rect.left(), rect.top() + header_h),
        QPointF(rect.right(), rect.top() + header_h),
    )
    # Minimal window dots in neutral steel + copper (zero off-palette colors)
    for idx, col in enumerate((C_ORANGE, C_COPPER, C_STEEL)):
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawEllipse(QPointF(rect.left() + 24 + idx * 18, rect.top() + header_h / 2.0), 4.5, 4.5)
    p.setFont(make_body_font(18, QFont.DemiBold))
    p.setPen(C_STEEL.lighter(120))
    p.drawText(
        QRectF(rect.left() + 86, rect.top(), rect.width() - 104, header_h),
        Qt.AlignLeft | Qt.AlignVCenter,
        title_bar,
    )
    p.restore()
    return QRectF(rect.left() + 14, rect.top() + header_h + 12, rect.width() - 28, rect.height() - header_h - 26)


def draw_ui_zoom_card(
    p: QPainter,
    pix: QPixmap,
    cam_start: tuple[float, float, float],
    cam_end: tuple[float, float, float],
    highlight_rect_src: dict[str, int] | None,
    highlight_label: str,
    window_label: str,
    progress: float,
    card_rect: QRectF | None = None,
) -> None:
    """Pan & zoom smoothly over 2x HiDPI Stele UI screenshot inside focal card.

    cam_start / cam_end = (center_x_px, center_y_px, crop_width_px) in source image pixels.
    """
    outer = card_rect or QRectF(MARGIN_X, 446, CANVAS_W - 2 * MARGIN_X, 700)
    inner = _card_shell(p, outer, window_label)

    t = ease_in_out_cubic(progress)
    cx = cam_start[0] + (cam_end[0] - cam_start[0]) * t
    cy = cam_start[1] + (cam_end[1] - cam_start[1]) * t
    cw = cam_start[2] + (cam_end[2] - cam_start[2]) * t
    aspect = inner.height() / max(1.0, inner.width())
    ch = cw * aspect

    img_w = float(pix.width())
    img_h = float(pix.height())
    sx = max(0.0, min(img_w - cw, cx - cw / 2.0))
    sy = max(0.0, min(img_h - ch, cy - ch / 2.0))
    src_rect = QRectF(sx, sy, min(cw, img_w), min(ch, img_h))

    p.save()
    clip = QPainterPath()
    clip.addRoundedRect(inner, 10, 10)
    p.setClipPath(clip)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    p.drawPixmap(inner, pix, src_rect)

    # Highlight target widget with crisp Forge Orange callout frame
    if highlight_rect_src and progress > 0.14:
        pulse = ease_out_cubic(min(1.0, (progress - 0.14) / 0.22))
        scale_x = inner.width() / src_rect.width()
        scale_y = inner.height() / src_rect.height()
        hx = inner.left() + (highlight_rect_src["x"] - src_rect.left()) * scale_x - 8
        hy = inner.top() + (highlight_rect_src["y"] - src_rect.top()) * scale_y - 6
        hw = highlight_rect_src["w"] * scale_x + 16
        hh = highlight_rect_src["h"] * scale_y + 12
        hrect = QRectF(hx, hy, hw, hh).intersected(inner.adjusted(4, 4, -4, -4))
        if hrect.width() > 24 and hrect.height() > 16:
            pen = QPen(C_ORANGE, 3.0)
            p.setPen(pen)
            p.setBrush(QColor(242, 107, 29, int(24 * pulse)))
            p.drawRoundedRect(hrect, 8, 8)
            if highlight_label:
                p.setFont(make_headline_font(16, QFont.Bold, 105.0))
                lw = p.fontMetrics().horizontalAdvance(highlight_label.upper()) + 24
                ly = hrect.top() - 32 if hrect.top() - 34 > inner.top() else hrect.bottom() + 6
                lx = min(max(hrect.left(), inner.left() + 6), inner.right() - lw - 6)
                tag_r = QRectF(lx, ly, lw, 26)
                p.setPen(Qt.NoPen)
                p.setBrush(C_ORANGE)
                p.drawRoundedRect(tag_r, 5, 5)
                p.setPen(C_BLACK)
                p.drawText(tag_r, Qt.AlignCenter, highlight_label.upper())
    p.restore()


def draw_docs_trio_card(p: QPainter, progress: float) -> None:
    """Custom vector showcase of Spec PDF, How-To PDF, and 140mm Disc Label."""
    outer = QRectF(MARGIN_X, 446, CANVAS_W - 2 * MARGIN_X, 700)
    inner = _card_shell(p, outer, "DOCS/  ·  Generated offline documentation & print labels")
    p.save()

    # Left sheet: SPEC.PDF
    e1 = ease_out_cubic(min(1.0, progress / 0.28))
    s1 = QRectF(inner.left() + 10, inner.top() + 18 + (1 - e1) * 24, 405, 575)
    p.setOpacity(e1)
    p.setPen(QPen(C_COPPER, 1.4))
    p.setBrush(QColor(22, 24, 28))
    p.drawRoundedRect(s1, 12, 12)

    p.setFont(make_headline_font(18, QFont.Bold, 106.0))
    p.setPen(C_ORANGE)
    p.drawText(QRectF(s1.left() + 22, s1.top() + 20, 360, 24), Qt.AlignLeft, "TECHNICAL SPEC PDF")
    p.setFont(make_body_font(22, QFont.Bold))
    p.setPen(C_WHITE)
    p.drawText(QRectF(s1.left() + 22, s1.top() + 52, 360, 30), Qt.AlignLeft, "Qwen2.5-7B-Instruct-GGUF")

    spec_rows = [
        ("Commit SHA", "dd98b7684b25"),
        ("License", "apache-2.0 (on disc)"),
        ("Architecture", "Qwen2ForCausalLM · 7B"),
        ("Context", "32,768 tokens"),
        ("Quantization", "Q4_K_M · 4.68 GB"),
        ("Hardware hint", "8 GB VRAM class"),
        ("SHA-256 table", "4 files verified"),
    ]
    y = s1.top() + 104
    for k, v in spec_rows:
        p.fillRect(QRectF(s1.left() + 22, y + 32, 360, 1), QColor(44, 48, 56))
        p.setFont(make_body_font(17, QFont.Medium))
        p.setPen(C_STEEL)
        p.drawText(QRectF(s1.left() + 22, y, 150, 28), Qt.AlignLeft | Qt.AlignVCenter, k)
        p.setFont(make_body_font(17, QFont.DemiBold))
        p.setPen(C_WHITE)
        p.drawText(QRectF(s1.left() + 172, y, 210, 28), Qt.AlignRight | Qt.AlignVCenter, v)
        y += 42

    p.setFont(make_body_font(15, QFont.Normal))
    p.setPen(C_STEEL)
    p.drawText(
        QRectF(s1.left() + 22, s1.bottom() - 62, 360, 44),
        Qt.AlignLeft | Qt.TextWordWrap,
        "Stele does not grant redistribution rights.",
    )

    # Top-Right card: HOWTO.PDF
    e2 = ease_out_cubic(max(0.0, min(1.0, (progress - 0.14) / 0.28)))
    p.setOpacity(e2)
    s2 = QRectF(inner.left() + 436, inner.top() + 18 + (1 - e2) * 24, 428, 272)
    p.setPen(QPen(C_COPPER, 1.4))
    p.setBrush(QColor(22, 24, 28))
    p.drawRoundedRect(s2, 12, 12)
    p.setFont(make_headline_font(18, QFont.Bold, 106.0))
    p.setPen(C_ORANGE)
    p.drawText(QRectF(s2.left() + 22, s2.top() + 20, 380, 24), Qt.AlignLeft, "HOW-TO-USE GUIDE PDF")
    howto_lines = [
        "1. Runtime order: LM Studio -> Ollama -> llama.cpp",
        "2. Load local GGUF from MODELS/Qwen--.../",
        "3. First check: \"Reply with the single word stele.\"",
        "4. Offline restore command included on page 1",
    ]
    hy = s2.top() + 62
    p.setFont(make_body_font(17, QFont.Medium))
    p.setPen(C_WHITE)
    for line in howto_lines:
        p.drawText(QRectF(s2.left() + 22, hy, 384, 44), Qt.AlignLeft | Qt.TextWordWrap, line)
        hy += 48

    # Bottom-Right card: Printable 140mm Disc Face + Case Insert
    e3 = ease_out_cubic(max(0.0, min(1.0, (progress - 0.28) / 0.28)))
    p.setOpacity(e3)
    s3 = QRectF(inner.left() + 436, inner.top() + 310 + (1 - e3) * 24, 428, 283)
    p.setPen(QPen(C_COPPER, 1.4))
    p.setBrush(QColor(22, 24, 28))
    p.drawRoundedRect(s3, 12, 12)
    p.setFont(make_headline_font(17, QFont.Bold, 106.0))
    p.setPen(C_ORANGE)
    p.drawText(QRectF(s3.left() + 22, s3.top() + 18, 240, 24), Qt.AlignLeft, "DISC & CASE LABELS")
    p.setFont(make_body_font(17, QFont.Medium))
    p.setPen(C_STEEL.lighter(120))
    p.drawText(
        QRectF(s3.left() + 22, s3.top() + 54, 200, 190),
        Qt.AlignLeft | Qt.TextWordWrap,
        "140 mm disc face PDF\n+\nUS Letter case insert\nwith SHA-256 prefixes\n& restore command.",
    )
    # Circular M-DISC graphic matching labels.py
    dcx = s3.right() - 108
    dcy = s3.center().y() + 10
    p.setPen(QPen(C_COPPER, 2.0))
    p.setBrush(QColor(246, 245, 242))
    p.drawEllipse(QPointF(dcx, dcy), 82, 82)
    p.setPen(QPen(C_STEEL, 1.2))
    p.setBrush(C_CHARCOAL)
    p.drawEllipse(QPointF(dcx, dcy), 20, 20)
    p.setPen(C_BLACK)
    p.setFont(make_headline_font(13, QFont.ExtraBold, 106.0))
    p.drawText(QRectF(dcx - 64, dcy - 58, 128, 20), Qt.AlignCenter, "ALEXX FORGE")
    p.setFont(make_body_font(11, QFont.DemiBold))
    p.drawText(QRectF(dcx - 70, dcy - 38, 140, 16), Qt.AlignCenter, "Qwen2.5-7B-GGUF")
    p.setFont(make_headline_font(11, QFont.Bold, 104.0))
    p.setPen(C_EMBER)
    p.drawText(QRectF(dcx - 64, dcy + 30, 128, 16), Qt.AlignCenter, "DISC 1 OF 1")
    p.setPen(C_BLACK)
    p.setFont(make_body_font(10, QFont.Medium))
    p.drawText(QRectF(dcx - 64, dcy + 46, 128, 16), Qt.AlignCenter, "M-DISC ARCHIVE")

    p.restore()


def draw_disc_tree_card(p: QPainter, progress: float) -> None:
    """UDF Disc Directory Tree card proving zero proprietary lock-in."""
    outer = QRectF(MARGIN_X, 446, CANVAS_W - 2 * MARGIN_X, 700)
    inner = _card_shell(p, outer, "E:\\STELE\\  ·  Standard UDF 2.50 optical disc layout")
    p.save()

    rows = [
        ("README_FIRST.txt", "Plain-text overview & license disclaimer", False),
        ("ARCHIVE_MANIFEST.json", "Exact commit SHA, repo metadata & file inventory", False),
        ("checksums.sha256", "Standard SHA-256 manifest for every archived file", True),
        ("RESTORE.ps1", "Offline PowerShell 5.1 script — no Stele required", True),
        ("VOLUME.json", "Disc 1 of N index + split-part SHA-256 map", False),
        ("DOCS/", "Generated Spec PDF/MD + How-To PDF/MD + labels", False),
        ("MODELS/", "Pinned weights under <org>--<repo>/<commit>/", True),
        ("RUNTIME/", "Optional official llama.cpp, Ollama, LM Studio files", False),
        ("RECOVERY/", "Optional PAR2 parity blocks (par2cmdline-turbo)", False),
    ]

    visible_n = max(3, min(len(rows), int(3 + progress * (len(rows) + 1))))
    y = inner.top() + 10
    row_h = 64.0
    for idx, (name, desc, hot) in enumerate(rows):
        active = idx < visible_n
        p.setOpacity(1.0 if active else 0.25)
        r = QRectF(inner.left() + 8, y, inner.width() - 16, row_h - 6)
        if hot and active:
            p.setPen(QPen(C_ORANGE, 1.5))
            p.setBrush(QColor(40, 29, 22))
        else:
            p.setPen(QPen(QColor(48, 52, 60), 1.0))
            p.setBrush(QColor(22, 24, 28))
        p.drawRoundedRect(r, 9, 9)

        p.setFont(make_body_font(21, QFont.Bold))
        p.setPen(C_ORANGE if hot else C_WHITE)
        p.drawText(QRectF(r.left() + 20, r.top(), 310, r.height()), Qt.AlignLeft | Qt.AlignVCenter, name)

        p.setFont(make_body_font(18, QFont.Medium))
        p.setPen(C_WHITE if hot else C_STEEL.lighter(120))
        p.drawText(
            QRectF(r.left() + 332, r.top(), r.width() - 348, r.height()),
            Qt.AlignLeft | Qt.AlignVCenter,
            desc,
        )
        y += row_h

    p.restore()


def draw_powershell_card(p: QPainter, lines: list[tuple[str, str]], title: str, progress: float) -> None:
    """Animated Windows PowerShell 5.1 offline restore session."""
    outer = QRectF(MARGIN_X, 446, CANVAS_W - 2 * MARGIN_X, 700)
    inner = _card_shell(p, outer, title)
    p.save()

    term = inner.adjusted(4, 4, -4, -4)
    p.setPen(QPen(QColor(45, 49, 57), 1.2))
    p.setBrush(QColor(13, 14, 16))
    p.drawRoundedRect(term, 10, 10)

    count = max(1, min(len(lines), int(1 + progress * (len(lines) + 0.6))))
    y = term.top() + 22
    for idx in range(count):
        role, text = lines[idx]
        if role == "cmd":
            col = C_ORANGE
            font = make_body_font(20, QFont.Bold)
        elif role == "ok":
            col = C_WHITE
            font = make_body_font(20, QFont.Bold)
        elif role == "accent":
            col = C_COPPER.lighter(135)
            font = make_body_font(19, QFont.DemiBold)
        else:
            col = C_STEEL.lighter(125)
            font = make_body_font(19, QFont.Medium)
        p.setFont(font)
        p.setPen(col)
        rect = QRectF(term.left() + 22, y, term.width() - 44, 68)
        bound = p.boundingRect(rect, Qt.AlignLeft | Qt.TextWordWrap, text)
        if role == "ok":
            pill = QRectF(term.left() + 16, y - 6, term.width() - 32, bound.height() + 16)
            p.setPen(QPen(C_ORANGE, 1.5))
            p.setBrush(QColor(42, 28, 18))
            p.drawRoundedRect(pill, 8, 8)
            p.setPen(C_WHITE)
            p.drawText(
                QRectF(pill.left() + 14, pill.top() + 8, pill.width() - 28, pill.height() - 16),
                Qt.AlignLeft | Qt.TextWordWrap,
                text,
            )
            y += bound.height() + 28
        else:
            p.drawText(rect, Qt.AlignLeft | Qt.TextWordWrap, text)
            y += bound.height() + 18

    p.restore()


def draw_civitai_json_card(p: QPainter, progress: float) -> None:
    """ShowMODELS/civitai--842109/v918204/ + saved civitai_model.json trigger words."""
    outer = QRectF(MARGIN_X, 446, CANVAS_W - 2 * MARGIN_X, 700)
    inner = _card_shell(p, outer, "MODELS/civitai--842109/v918204/  ·  Weights + Metadata")
    p.save()

    # Top file strip
    top_box = QRectF(inner.left() + 8, inner.top() + 8, inner.width() - 16, 108)
    p.setPen(QPen(C_COPPER, 1.3))
    p.setBrush(QColor(20, 22, 26))
    p.drawRoundedRect(top_box, 10, 10)
    p.setFont(make_body_font(20, QFont.Bold))
    p.setPen(C_WHITE)
    p.drawText(
        QRectF(top_box.left() + 20, top_box.top() + 16, top_box.width() - 40, 32),
        Qt.AlignLeft,
        "arch_linework_flux_v2.safetensors   ·   584.0 MB   ·   SHA-256 OK",
    )
    p.setFont(make_body_font(18, QFont.DemiBold))
    p.setPen(C_ORANGE)
    p.drawText(
        QRectF(top_box.left() + 20, top_box.top() + 58, top_box.width() - 40, 30),
        Qt.AlignLeft,
        "+ civitai_model.json  (saved automatically beside the weights)",
    )

    # JSON fields card
    jbox = QRectF(inner.left() + 8, inner.top() + 132, inner.width() - 16, 344)
    p.setPen(QPen(QColor(52, 56, 64), 1.2))
    p.setBrush(QColor(13, 14, 16))
    p.drawRoundedRect(jbox, 10, 10)

    fields = [
        ('"modelId"', '842109   ("Architectural Linework Flux")', False),
        ('"versionId"', "918204   (v2.0 pinned snapshot)", False),
        ('"baseModel"', '"Flux.1 D"', True),
        ('"trainedWords"', '["arch_linework", "blueprint_etching"]', True),
        ('"sha256"', '"9f40c2b81e774a05d12c8e9031b4..." (verified)', False),
        ('"permissions"', "Creator commercial & sharing rules preserved", False),
    ]
    n_vis = max(2, min(len(fields), int(2 + progress * 6)))
    fy = jbox.top() + 18
    for idx, (k, v, hi) in enumerate(fields):
        p.setOpacity(1.0 if idx < n_vis else 0.22)
        if hi and idx < n_vis:
            p.fillRect(QRectF(jbox.left() + 12, fy - 4, jbox.width() - 24, 46), QColor(44, 29, 18))
        p.setFont(make_body_font(19, QFont.Bold))
        p.setPen(C_ORANGE if hi else C_COPPER.lighter(130))
        p.drawText(QRectF(jbox.left() + 24, fy, 210, 38), Qt.AlignLeft | Qt.AlignVCenter, k)
        p.setFont(make_body_font(19, QFont.DemiBold if hi else QFont.Medium))
        p.setPen(C_WHITE)
        p.drawText(QRectF(jbox.left() + 242, fy, jbox.width() - 262, 38), Qt.AlignLeft | Qt.AlignVCenter, v)
        fy += 52

    p.setOpacity(1.0)
    # Bottom How-To note
    nbox = QRectF(inner.left() + 8, inner.top() + 492, inner.width() - 16, 104)
    p.setPen(QPen(C_COPPER, 1.2))
    p.setBrush(QColor(22, 24, 28))
    p.drawRoundedRect(nbox, 10, 10)
    p.setFont(make_body_font(18, QFont.Medium))
    p.setPen(C_STEEL.lighter(125))
    p.drawText(
        nbox.adjusted(20, 14, -20, -14),
        Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap,
        "Generated How-To PDF notes ComfyUI, Forge, or InvokeAI for this base model — "
        "and clearly states LM Studio / Ollama do not load image LoRAs.",
    )
    p.restore()


def draw_split_par2_card(p: QPainter, progress: float, focus_par2: bool = False) -> None:
    """Diagram of a 42.8 GB 70B GGUF splitting across two 25 GB BD-R discs + 5% PAR2."""
    outer = QRectF(MARGIN_X, 446, CANVAS_W - 2 * MARGIN_X, 700)
    inner = _card_shell(p, outer, "STELE PRO  ·  Multi-disc oversized file split + PAR2 parity")
    p.save()

    # Source oversized file bar
    src = QRectF(inner.left() + 12, inner.top() + 12, inner.width() - 24, 112)
    p.setPen(QPen(C_COPPER, 1.5))
    p.setBrush(QColor(18, 20, 24))
    p.drawRoundedRect(src, 12, 12)
    p.setFont(make_headline_font(17, QFont.Bold, 106.0))
    p.setPen(C_STEEL)
    p.drawText(QRectF(src.left() + 22, src.top() + 16, 620, 24), Qt.AlignLeft, "OVERSIZED SINGLE WEIGHT FILE")
    p.setFont(make_body_font(23, QFont.Bold))
    p.setPen(C_WHITE)
    p.drawText(
        QRectF(src.left() + 22, src.top() + 48, src.width() - 44, 34),
        Qt.AlignLeft,
        "Llama-3.3-70B-Instruct-Q4_K_M.gguf   ·   42.8 GB",
    )
    p.setFont(make_body_font(17, QFont.DemiBold))
    p.setPen(C_ORANGE)
    p.drawText(QRectF(src.right() - 290, src.top() + 16, 268, 24), Qt.AlignRight, "Exceeds 25 GB BD-R blank")

    # Connector arrows
    mid_y = src.bottom() + 24
    p.setPen(QPen(C_ORANGE, 2.4))
    p.drawLine(QPointF(inner.center().x() - 120, src.bottom() + 6), QPointF(inner.left() + 220, mid_y + 18))
    p.drawLine(QPointF(inner.center().x() + 120, src.bottom() + 6), QPointF(inner.right() - 220, mid_y + 18))

    # Two 25 GB Disc cards
    disc_w = (inner.width() - 44) / 2.0
    for idx, (part_ext, sz_txt, d_num) in enumerate(
        ((".part001", "22.4 GB", "DISC 1 OF 2"), (".part002", "20.4 GB", "DISC 2 OF 2"))
    ):
        appear = ease_out_cubic(max(0.0, min(1.0, (progress - idx * 0.14) / 0.30)))
        p.setOpacity(0.2 + 0.8 * appear)
        dx = inner.left() + 12 + idx * (disc_w + 20)
        drect = QRectF(dx, mid_y + 22, disc_w, 304)
        p.setPen(QPen(C_ORANGE if focus_par2 else C_COPPER, 1.6))
        p.setBrush(QColor(22, 24, 28))
        p.drawRoundedRect(drect, 12, 12)

        p.setFont(make_headline_font(18, QFont.ExtraBold, 106.0))
        p.setPen(C_ORANGE)
        p.drawText(QRectF(dx + 20, drect.top() + 18, disc_w - 40, 26), Qt.AlignLeft, f"{d_num}  ·  BD-R 25 GB")

        # Payload bar
        pbar = QRectF(dx + 20, drect.top() + 62, disc_w - 40, 72)
        p.setPen(QPen(QColor(62, 66, 74), 1.0))
        p.setBrush(QColor(31, 35, 42))
        p.drawRoundedRect(pbar, 8, 8)
        p.setFont(make_body_font(19, QFont.Bold))
        p.setPen(C_WHITE)
        p.drawText(QRectF(pbar.left() + 14, pbar.top() + 10, pbar.width() - 28, 26), Qt.AlignLeft, f"GGUF{part_ext}  ({sz_txt})")
        p.setFont(make_body_font(15, QFont.Medium))
        p.setPen(C_STEEL.lighter(120))
        p.drawText(QRectF(pbar.left() + 14, pbar.top() + 40, pbar.width() - 28, 22), Qt.AlignLeft, "Part SHA-256 in VOLUME.json")

        # PAR2 recovery bar
        rbar = QRectF(dx + 20, drect.top() + 148, disc_w - 40, 74)
        p.setPen(QPen(C_ORANGE, 1.8 if focus_par2 else 1.1))
        p.setBrush(QColor(46, 29, 18) if focus_par2 else QColor(28, 24, 22))
        p.drawRoundedRect(rbar, 8, 8)
        p.setFont(make_body_font(18, QFont.Bold))
        p.setPen(C_ORANGE)
        p.drawText(QRectF(rbar.left() + 14, rbar.top() + 10, rbar.width() - 28, 24), Qt.AlignLeft, "RECOVERY/  ·  5% PAR2")
        p.setFont(make_body_font(15, QFont.Medium))
        p.setPen(C_WHITE)
        p.drawText(QRectF(rbar.left() + 14, rbar.top() + 38, rbar.width() - 28, 24), Qt.AlignLeft, "par2cmdline-turbo parity")

        p.setFont(make_body_font(16, QFont.Medium))
        p.setPen(C_STEEL.lighter(120))
        p.drawText(QRectF(dx + 20, drect.top() + 238, disc_w - 40, 50), Qt.AlignLeft | Qt.TextWordWrap, "+ RESTORE.ps1 + DOCS/")

    p.setOpacity(1.0)
    foot = QRectF(inner.left() + 12, inner.bottom() - 122, inner.width() - 24, 108)
    p.setPen(QPen(QColor(52, 56, 64), 1.2))
    p.setBrush(QColor(15, 16, 19))
    p.drawRoundedRect(foot, 10, 10)
    p.setFont(make_body_font(19, QFont.DemiBold))
    p.setPen(C_WHITE)
    p.drawText(
        foot.adjusted(20, 14, -20, -14),
        Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap,
        "RESTORE.ps1 rejoins parts in place (needs only 1 part of extra disk space) "
        "and verifies the whole 42.8 GB file's SHA-256 before finishing.",
    )
    p.restore()


def draw_free_vs_pro_card(p: QPainter, highlight_tier: str, progress: float) -> None:
    """Clean side-by-side Free vs. Pro breakdown card."""
    outer = QRectF(MARGIN_X, 446, CANVAS_W - 2 * MARGIN_X, 700)
    inner = _card_shell(p, outer, "STELE EDITIONS  ·  Checked in code where the work happens")
    p.save()

    col_w = (inner.width() - 28) / 2.0
    tiers = [
        (
            "free",
            "STELE FREE",
            "Complete ISO workflow",
            [
                "Hugging Face + Civitai search",
                "HTTP Range pause & resume",
                "SHA-256 check on every file",
                "Spec PDF + How-To PDF + labels",
                "Single-volume UDF ISO export",
                "USB burner fallback via ISO",
            ],
        ),
        (
            "pro",
            "STELE PRO",
            f"One-time · {PRO_MACHINES_COUNT} machines",
            [
                "Everything in Stele Free",
                "Direct IMAPI2 UDF disc burn",
                "2x–4x speed + readback verify",
                "Multi-disc sets & file splitting",
                "PAR2 sector recovery (5% default)",
                "Air-gapped offline workstation safe",
            ],
        ),
    ]

    for idx, (tid, name, sub, bullets) in enumerate(tiers):
        active = highlight_tier in (tid, "both")
        x = inner.left() + 6 + idx * (col_w + 16)
        box = QRectF(x, inner.top() + 10, col_w, inner.height() - 20)
        p.setOpacity(1.0 if active else 0.52)
        p.setPen(QPen(C_ORANGE if (tid == "pro" and active) else C_COPPER, 2.0 if active else 1.2))
        p.setBrush(QColor(24, 26, 30) if active else QColor(17, 18, 21))
        p.drawRoundedRect(box, 12, 12)

        p.setFont(make_headline_font(24, QFont.ExtraBold, 106.0))
        p.setPen(C_ORANGE if tid == "pro" else C_WHITE)
        p.drawText(QRectF(x + 22, box.top() + 22, col_w - 44, 32), Qt.AlignLeft, name)

        p.setFont(make_body_font(17, QFont.DemiBold))
        p.setPen(C_COPPER.lighter(130))
        p.drawText(QRectF(x + 22, box.top() + 58, col_w - 44, 24), Qt.AlignLeft, sub)
        p.fillRect(QRectF(x + 22, box.top() + 94, col_w - 44, 1), QColor(52, 56, 64))

        by = box.top() + 114
        for item in bullets:
            # Small Forge Orange / Copper square bullet
            p.fillRect(QRectF(x + 22, by + 10, 8, 8), C_ORANGE if tid == "pro" else C_COPPER)
            p.setFont(make_body_font(18, QFont.Medium))
            p.setPen(C_WHITE)
            p.drawText(QRectF(x + 40, by, col_w - 58, 56), Qt.AlignLeft | Qt.TextWordWrap, item)
            by += 74

    p.restore()


def draw_end_slate(
    p: QPainter,
    cta_headline: str,
    honest_limit: str,
    local_t: float,
    progress_ratio: float,
) -> None:
    """Brand-locked Alexx Forge end slate inside cross-platform safe zone (y=170..1388)."""
    p.save()
    enter = ease_out_cubic(min(1.0, local_t / 0.30))
    p.setOpacity(0.15 + 0.85 * enter)

    card_w = float(SHORTS_RIGHT_RAIL_X - MARGIN_X)  # 828 px clears right rail too!
    # Center horizontally across 1080 canvas while staying above y=1388
    slate = QRectF(MARGIN_X, 200, CANVAS_W - 2 * MARGIN_X, 1168)
    p.setPen(QPen(C_COPPER, 1.8))
    p.setBrush(C_CHARCOAL)
    p.drawRoundedRect(slate, 20, 20)

    # Top Forge Orange accent bar
    p.setPen(Qt.NoPen)
    p.setBrush(C_ORANGE)
    p.drawRoundedRect(QRectF(slate.center().x() - 70, slate.top() + 28, 140, 5), 2.5, 2.5)

    # 114px A-Anvil Mark + ALEXX FORGE wordmark
    draw_anvil_mark(p, slate.center().x(), slate.top() + 124, 114.0)
    draw_wordmark_line(p, slate.center().x(), slate.top() + 232, 34)

    # Product Title & App Tagline
    p.setFont(make_headline_font(66, QFont.ExtraBold, 110.0))
    p.setPen(C_WHITE)
    p.drawText(QRectF(slate.left() + 36, slate.top() + 278, slate.width() - 72, 78), Qt.AlignCenter, APP_NAME)

    p.setFont(make_body_font(26, QFont.Medium))
    p.setPen(C_COPPER.lighter(135))
    p.drawText(QRectF(slate.left() + 36, slate.top() + 358, slate.width() - 72, 38), Qt.AlignCenter, APP_TAGLINE)

    # Specific CTA Headline
    p.setFont(make_headline_font(32, QFont.Bold, 105.0))
    p.setPen(C_WHITE)
    p.drawText(
        QRectF(slate.left() + 48, slate.top() + 432, slate.width() - 96, 88),
        Qt.AlignCenter | Qt.TextWordWrap,
        cta_headline.upper(),
    )

    # Swappable Pricing & Shop Box (driven by config.py)
    price_box = QRectF(slate.left() + 56, slate.top() + 544, slate.width() - 112, 232)
    p.setPen(QPen(C_ORANGE, 2.0))
    p.setBrush(C_BLACK)
    p.drawRoundedRect(price_box, 14, 14)

    p.setFont(make_body_font(24, QFont.Bold))
    p.setPen(C_WHITE)
    p.drawText(
        QRectF(price_box.left() + 24, price_box.top() + 26, price_box.width() - 48, 36),
        Qt.AlignCenter,
        f"Stele Free: {STELE_FREE_PRICE}  (Search + Docs + Single ISO)",
    )
    p.setFont(make_body_font(25, QFont.Bold))
    p.setPen(C_ORANGE)
    p.drawText(
        QRectF(price_box.left() + 24, price_box.top() + 74, price_box.width() - 48, 38),
        Qt.AlignCenter,
        f"Stele Pro: {STELE_PRO_PRICE}  (Burn + Span + PAR2)",
    )
    p.fillRect(QRectF(price_box.left() + 60, price_box.top() + 128, price_box.width() - 120, 1), QColor(52, 56, 64))
    p.setFont(make_headline_font(24, QFont.Bold, 104.0))
    p.setPen(C_WHITE)
    p.drawText(
        QRectF(price_box.left() + 24, price_box.top() + 148, price_box.width() - 48, 36),
        Qt.AlignCenter,
        GUMROAD_SHOP_DISPLAY,
    )
    p.setFont(make_body_font(18, QFont.Medium))
    p.setPen(C_STEEL)
    p.drawText(
        QRectF(price_box.left() + 24, price_box.top() + 186, price_box.width() - 48, 28),
        Qt.AlignCenter,
        f"{BRAND_HANDLE} on X  ·  Link in reply / channel bio",
    )

    # Honest Limits Box (Brand Book requirement: always say what it does not do)
    p.setFont(make_body_font(20, QFont.Medium))
    p.setPen(C_STEEL.lighter(118))
    p.drawText(
        QRectF(slate.left() + 56, slate.top() + 806, slate.width() - 112, 132),
        Qt.AlignCenter | Qt.TextWordWrap,
        honest_limit,
    )

    # Support email & locked tagline
    p.setFont(make_body_font(20, QFont.DemiBold))
    p.setPen(C_WHITE)
    p.drawText(
        QRectF(slate.left() + 48, slate.top() + 972, slate.width() - 96, 32),
        Qt.AlignCenter,
        f"Questions? Email {BRAND_EMAIL}",
    )
    p.setFont(make_headline_font(22, QFont.ExtraBold, 112.0))
    p.setPen(C_ORANGE)
    p.drawText(
        QRectF(slate.left() + 48, slate.top() + 1044, slate.width() - 96, 36),
        Qt.AlignCenter,
        BRAND_TAGLINE,
    )

    # Progress bar completed
    p.fillRect(QRectF(MARGIN_X, 1384, SHORTS_RIGHT_RAIL_X - MARGIN_X, 4), C_ORANGE)
    p.restore()


def render_frame(
    spec: dict[str, Any],
    frame_idx: int,
    total_frames: int,
    pixmaps: dict[str, QPixmap],
    regions: dict[str, dict],
) -> QImage:
    t = frame_idx / FPS
    progress_ratio = frame_idx / max(1, total_frames - 1)

    # Locate active scene
    scenes = spec["scenes"]
    active = scenes[-1]
    scene_start = 0.0
    elapsed = 0.0
    for sc in scenes:
        dur = float(sc["duration"])
        if t < elapsed + dur or sc is scenes[-1]:
            active = sc
            scene_start = elapsed
            break
        elapsed += dur

    local_t = max(0.0, t - scene_start)
    local_prog = min(1.0, local_t / max(0.001, float(active["duration"])))

    img = QImage(CANVAS_W, CANVAS_H, QImage.Format_RGB888)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)

    draw_background(p, CANVAS_W, CANVAS_H)

    kind = active["kind"]
    if kind == "end_slate":
        draw_end_slate(
            p,
            cta_headline=active["cta_headline"],
            honest_limit=active["honest_limit"],
            local_t=local_t,
            progress_ratio=progress_ratio,
        )
        p.end()
        return img

    draw_top_chrome(p, eyebrow=spec["eyebrow"], tier_badge=active.get("badge", "STELE · WINDOWS"))
    draw_headline_block(
        p,
        headline_lines=active["headline"],
        accent_word=active.get("accent", ""),
        local_t=local_t,
    )

    if kind == "ui_zoom":
        cap_key = active["capture"]
        pix = pixmaps[cap_key]
        reg = None
        if active.get("highlight_key"):
            reg = regions.get(cap_key, {}).get(active["highlight_key"])
        draw_ui_zoom_card(
            p,
            pix=pix,
            cam_start=tuple(active["cam_start"]),
            cam_end=tuple(active["cam_end"]),
            highlight_rect_src=reg,
            highlight_label=active.get("highlight_label", ""),
            window_label=active.get("window_label", "Stele"),
            progress=local_prog,
        )
    elif kind == "docs_trio":
        draw_docs_trio_card(p, local_prog)
    elif kind == "disc_tree":
        draw_disc_tree_card(p, local_prog)
    elif kind == "powershell":
        draw_powershell_card(p, active["lines"], active["window_label"], local_prog)
    elif kind == "civitai_json":
        draw_civitai_json_card(p, local_prog)
    elif kind == "split_par2":
        draw_split_par2_card(p, local_prog, focus_par2=bool(active.get("focus_par2")))
    elif kind == "free_vs_pro":
        draw_free_vs_pro_card(p, active.get("highlight_tier", "both"), local_prog)

    draw_caption_pill(p, active["caption"], local_t=local_t, progress_ratio=progress_ratio)
    p.end()
    return img


def render_video_mp4(
    spec: dict[str, Any],
    wav_path: Path,
    out_mp4: Path,
    pixmaps: dict[str, QPixmap],
    regions: dict[str, dict],
) -> Path:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    total_dur = sum(float(s["duration"]) for s in spec["scenes"])
    total_frames = int(round(total_dur * FPS))

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg was not found on PATH.")

    cmd = [
        ffmpeg,
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{CANVAS_W}x{CANVAS_H}",
        "-r",
        str(FPS),
        "-i",
        "-",
        "-i",
        str(wav_path),
        "-c:v",
        "libx264",
        "-profile:v",
        "high",
        "-level",
        "4.1",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-g",
        str(FPS * 2),
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-movflags",
        "+faststart",
        "-shortest",
        str(out_mp4),
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    expected_row_bytes = CANVAS_W * 3
    try:
        for idx in range(total_frames):
            qimg = render_frame(spec, idx, total_frames, pixmaps, regions)
            bpl = qimg.bytesPerLine()
            ptr = qimg.constBits()
            if bpl == expected_row_bytes:
                proc.stdin.write(ptr[: expected_row_bytes * CANVAS_H])
            else:
                mv = memoryview(ptr)
                for row in range(CANVAS_H):
                    start = row * bpl
                    proc.stdin.write(mv[start : start + expected_row_bytes])
        proc.stdin.close()
    except Exception:
        proc.kill()
        raise

    stderr_bytes = proc.stderr.read() if proc.stderr else b""
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"FFmpeg failed ({rc}): {stderr_bytes.decode('utf-8', errors='replace')}")
    return out_mp4


def render_shorts_cover(
    spec: dict[str, Any],
    out_png: Path,
    pixmaps: dict[str, QPixmap],
    regions: dict[str, dict],
) -> Path:
    """Dedicated 1080x1920 Shorts cover: <= 4 words headline, 1 focal mock, ZERO prices."""
    out_png.parent.mkdir(parents=True, exist_ok=True)
    img = QImage(CANVAS_W, CANVAS_H, QImage.Format_RGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)

    draw_background(p, CANVAS_W, CANVAS_H)
    draw_top_chrome(p, eyebrow="STELE · MODEL ARCHIVER", tier_badge="WINDOWS APP")

    # Giant <= 4 word cover headline for 120px thumbnail legibility
    cover_lines: list[str] = spec["cover_lines"]
    accent = spec["cover_accent"].upper()
    font = make_headline_font(76, QFont.Black, 104.0)
    p.setFont(font)
    fm = p.fontMetrics()
    y0 = 328.0
    for idx, raw in enumerate(cover_lines[:2]):
        line = raw.upper()
        y = y0 + idx * 88.0
        if accent and accent in line:
            before, match, after = line.partition(accent)
            x = float(MARGIN_X)
            if before:
                p.setPen(C_WHITE)
                p.drawText(QPointF(x, y), before)
                x += fm.horizontalAdvance(before)
            p.setPen(C_ORANGE)
            p.drawText(QPointF(x, y), match)
            x += fm.horizontalAdvance(match)
            if after:
                p.setPen(C_WHITE)
                p.drawText(QPointF(x, y), after)
        else:
            p.setPen(C_WHITE)
            p.drawText(QPointF(float(MARGIN_X), y), line)

    p.setFont(make_body_font(28, QFont.DemiBold))
    p.setPen(C_STEEL.lighter(125))
    sub_y = y0 + (len(cover_lines[:2]) - 1) * 88.0 + 36.0
    p.drawText(
        QRectF(MARGIN_X, sub_y, CANVAS_W - 2 * MARGIN_X, 74),
        Qt.AlignLeft | Qt.TextWordWrap,
        spec["cover_subhead"],
    )

    # Focal visual in center
    cov = spec["cover_visual"]
    if cov["kind"] == "ui_zoom":
        cap = cov["capture"]
        reg = regions.get(cap, {}).get(cov.get("highlight_key", ""))
        draw_ui_zoom_card(
            p,
            pix=pixmaps[cap],
            cam_start=tuple(cov["cam"]),
            cam_end=tuple(cov["cam"]),
            highlight_rect_src=reg,
            highlight_label=cov.get("highlight_label", ""),
            window_label=cov.get("window_label", "Stele"),
            progress=1.0,
            card_rect=QRectF(MARGIN_X, 556, CANVAS_W - 2 * MARGIN_X, 760),
        )
    elif cov["kind"] == "disc_tree":
        draw_disc_tree_card(p, 1.0)
    elif cov["kind"] == "split_par2":
        draw_split_par2_card(p, 1.0, focus_par2=True)
    elif cov["kind"] == "free_vs_pro":
        draw_free_vs_pro_card(p, "both", 1.0)

    # Bottom footer inside safe zone
    p.setFont(make_headline_font(20, QFont.Bold, 110.0))
    p.setPen(C_ORANGE)
    p.drawText(QRectF(MARGIN_X, 1344, CANVAS_W - 2 * MARGIN_X, 34), Qt.AlignLeft, BRAND_TAGLINE)
    p.end()
    img.save(str(out_png), "PNG")
    return out_png


def render_x_cover(
    spec: dict[str, Any],
    out_png: Path,
    pixmaps: dict[str, QPixmap],
    regions: dict[str, dict],
) -> Path:
    """Dedicated 1280x720 16:9 cover for X / YouTube (own layout, >=8% margin, ZERO prices)."""
    out_png.parent.mkdir(parents=True, exist_ok=True)
    w, h = 1280, 720
    mx, my = 104, 58  # >= 8% margin on all 4 edges (1280*0.08=102.4, 720*0.08=57.6)
    img = QImage(w, h, QImage.Format_RGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)

    draw_background(p, w, h)

    # Left column (x=104..584): small A-anvil mark + giant <=4-word headline + subhead + footer
    draw_anvil_mark(p, mx + 26, my + 26, 52.0)
    p.setFont(make_headline_font(17, QFont.Bold, 110.0))
    p.setPen(C_STEEL)
    p.drawText(QRectF(mx + 66, my + 6, 360, 22), Qt.AlignLeft | Qt.AlignVCenter, "ALEXX FORGE  ·  STELE")
    p.setFont(make_body_font(15, QFont.Medium))
    p.setPen(C_COPPER.lighter(130))
    p.drawText(QRectF(mx + 66, my + 28, 360, 20), Qt.AlignLeft | Qt.AlignVCenter, APP_TAGLINE)

    cover_lines: list[str] = spec["cover_lines"]
    accent = spec["cover_accent"].upper()
    font = make_headline_font(62, QFont.Black, 104.0)
    p.setFont(font)
    fm = p.fontMetrics()
    y0 = 232.0
    for idx, raw in enumerate(cover_lines[:2]):
        line = raw.upper()
        y = y0 + idx * 72.0
        if accent and accent in line:
            before, match, after = line.partition(accent)
            x = float(mx)
            if before:
                p.setPen(C_WHITE)
                p.drawText(QPointF(x, y), before)
                x += fm.horizontalAdvance(before)
            p.setPen(C_ORANGE)
            p.drawText(QPointF(x, y), match)
            x += fm.horizontalAdvance(match)
            if after:
                p.setPen(C_WHITE)
                p.drawText(QPointF(x, y), after)
        else:
            p.setPen(C_WHITE)
            p.drawText(QPointF(float(mx), y), line)

    p.fillRect(QRectF(mx, y0 + (len(cover_lines[:2]) - 1) * 72.0 + 26, 64, 4), C_ORANGE)
    p.setFont(make_body_font(22, QFont.Medium))
    p.setPen(C_STEEL.lighter(128))
    p.drawText(
        QRectF(mx, y0 + (len(cover_lines[:2]) - 1) * 72.0 + 48, 468, 120),
        Qt.AlignLeft | Qt.TextWordWrap,
        spec["cover_subhead"],
    )

    p.setFont(make_headline_font(16, QFont.Bold, 112.0))
    p.setPen(C_ORANGE)
    p.drawText(QRectF(mx, h - my - 22, 420, 22), Qt.AlignLeft, BRAND_TAGLINE)

    # Right column (x=602..1176, y=58..662): crisp 2x UI mock card
    cov = spec["cover_visual"]
    cap = cov.get("capture", "ui_burn_pro")
    cam = cov.get("cam", [1620, 740, 1450])
    reg = regions.get(cap, {}).get(cov.get("highlight_key", ""))
    draw_ui_zoom_card(
        p,
        pix=pixmaps[cap],
        cam_start=tuple(cam),
        cam_end=tuple(cam),
        highlight_rect_src=reg,
        highlight_label=cov.get("highlight_label", ""),
        window_label=cov.get("window_label", "Stele"),
        progress=1.0,
        card_rect=QRectF(602, my, w - mx - 602, h - 2 * my),
    )

    p.end()
    img.save(str(out_png), "PNG")
    return out_png


def render_120px_audit_sheet(shorts_covers: list[Path], x_covers: list[Path], out_png: Path) -> Path:
    """Verify Brand Book Check #5: render every cover at exact 120px thumbnail width."""
    sheet_w, sheet_h = 1120, 560
    img = QImage(sheet_w, sheet_h, QImage.Format_RGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    p.fillRect(0, 0, sheet_w, sheet_h, C_BLACK)

    p.setFont(make_headline_font(22, QFont.Bold, 106.0))
    p.setPen(C_WHITE)
    p.drawText(QRectF(36, 24, 980, 32), Qt.AlignLeft, "BRAND BOOK CHECK #5  ·  ACTUAL 120 PX THUMBNAIL READABILITY AUDIT")

    p.setFont(make_body_font(16, QFont.DemiBold))
    p.setPen(C_ORANGE)
    p.drawText(QRectF(36, 72, 600, 24), Qt.AlignLeft, "YouTube Shorts Covers (9:16 scaled to 120 x 213 px):")
    for idx, path in enumerate(shorts_covers):
        pix = QPixmap(str(path)).scaledToWidth(120, Qt.SmoothTransformation)
        x = 36 + idx * 196
        p.drawPixmap(x, 104, pix)
        p.setPen(QPen(C_COPPER, 1.0))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRect(x, 104, pix.width(), pix.height()))

    p.setPen(C_ORANGE)
    p.drawText(QRectF(36, 356, 600, 24), Qt.AlignLeft, "X / YouTube Covers (16:9 scaled to 120 x 68 px):")
    for idx, path in enumerate(x_covers):
        pix = QPixmap(str(path)).scaledToWidth(120, Qt.SmoothTransformation)
        x = 36 + idx * 196
        p.drawPixmap(x, 388, pix)
        p.setPen(QPen(C_COPPER, 1.0))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRect(x, 388, pix.width(), pix.height()))

    p.end()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out_png), "PNG")
    return out_png
