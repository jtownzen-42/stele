"""Light and dark themes: same structure, readable contrast, system-following."""
from __future__ import annotations

import re

import stele.ui.theme as theme


def _lum(hex_color: str) -> float:
    def ch(v: int) -> float:
        c = v / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_palettes_have_the_same_keys():
    assert set(theme.LIGHT) == set(theme.DARK)


def test_both_stylesheets_render_without_leftover_tokens():
    for scheme in ("light", "dark"):
        css = theme.stylesheet(scheme)
        assert "{" in css and not re.search(r"\{[a-zA-Z_]+\}", css)
        assert "ASSET" not in css


def test_light_assets_are_used_in_light_mode():
    assert "chevron-light.svg" in theme.stylesheet("light")
    assert "chevron-light.svg" not in theme.stylesheet("dark")


def test_text_contrast_meets_wcag_aa():
    for pal in (theme.LIGHT, theme.DARK):
        assert contrast(pal["text"], pal["bg"]) >= 4.5
        assert contrast(pal["muted"], pal["bg"]) >= 4.5
        assert contrast(pal["text"], pal["surface"]) >= 4.5
        assert contrast(pal["accentText"], pal["navSel"]) >= 4.5


def test_light_primary_button_text_is_readable():
    # Primary buttons use bg-coloured text on the accent.
    assert contrast(theme.LIGHT["bg"], theme.LIGHT["accent"]) >= 3.0


def test_window_follows_and_switches_scheme(qtbot=None):
    import os
    import tempfile
    from pathlib import Path

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from stele.db import Database
    from stele.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication(["test"])
    w = MainWindow(Database(Path(tempfile.mkdtemp()) / "t.db"), start_worker=False)
    w.apply_scheme("light")
    assert w.scheme == "light" and theme.LIGHT["bg"] in w.styleSheet()
    w.apply_scheme("dark")
    assert w.scheme == "dark" and theme.DARK["bg"] in w.styleSheet()
    w.close()
