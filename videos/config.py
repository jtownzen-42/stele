"""Locked Alexx Forge Brand Book tokens & swappable commercial config for Stele videos.

Edit PRICING_AND_LINKS below to run promos (e.g., $19 launch code) and re-run
`python videos/build_all_videos.py` — cover art never bakes prices in.
"""

from __future__ import annotations

from pathlib import Path

VIDEOS_ROOT = Path(__file__).resolve().parent
ASSETS_DIR = VIDEOS_ROOT / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
UI_CAPTURES_DIR = ASSETS_DIR / "ui_captures"
OUT_DIR = VIDEOS_ROOT / "out"
SHORTS_COVERS_DIR = OUT_DIR / "covers_shorts_9x16"
X_COVERS_DIR = OUT_DIR / "covers_x_16x9"

# ---------------------------------------------------------------------------
# Swappable Commercial Variables (Never baked into cover/thumbnail PNGs)
# ---------------------------------------------------------------------------
BRAND_NAME = "Alexx Forge"          # Two x's, two words. Never "Alex Forge".
BRAND_HANDLE = "@Alexxforge"
BRAND_EMAIL = "alexx.forge@proton.me"
BRAND_TAGLINE = "BUILD. CREATE. ELEVATE."
APP_NAME = "STELE"
APP_TAGLINE = "Carve the model into stone."

STELE_FREE_PRICE = "$0+"
STELE_PRO_PRICE = "$29 one-time"
PRO_MACHINES_COUNT = 3
DEFAULT_PAR2_PERCENT = 5

GUMROAD_SHOP_DISPLAY = "forgealex0.gumroad.com"
GUMROAD_FREE_URL = "https://forgealex0.gumroad.com/l/cxzlik"
GUMROAD_PRO_URL = "https://forgealex0.gumroad.com/l/varuz"

# ---------------------------------------------------------------------------
# Locked Alexx Forge Palette (Hex)
# ---------------------------------------------------------------------------
PALETTE = {
    "forge_charcoal": "#1E1F22",  # Main card / elevated surface
    "anvil_black": "#0D0E10",     # Deep background / vignette
    "forge_orange": "#F26B1D",    # Single hot accent (<= 10% area)
    "ember_orange": "#DE570C",    # Deep accent / progress edge
    "copper": "#B06742",          # Logo ring & warm hairline border
    "brushed_steel": "#969595",   # Secondary text & "ALEXX" metal tone
    "spark_white": "#F8F8F8",     # Primary headline & high-contrast text
}

# ---------------------------------------------------------------------------
# Master Video Canvas & Cross-Platform Safe Zones (X.com + YouTube Shorts)
# ---------------------------------------------------------------------------
CANVAS_W = 1080
CANVAS_H = 1920
FPS = 30

# 8% minimum margin per Brand Book Premium Bar Check #3 (1080 * 0.08 = 86.4 px)
MARGIN_X = 88
SAFE_TOP = 164
# Below y=940, keep key text left of x=916 to clear YouTube Shorts right icon rail
SHORTS_RIGHT_RAIL_X = 916
# Keep all critical text/UI above y=1392 to clear Shorts bottom overlay & X scrubber
SAFE_BOTTOM = 1392
