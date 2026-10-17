"""Unit tests for post-burn STELE volume discovery."""

from __future__ import annotations

import os
from pathlib import Path

from stele.burn import imapi


def test_volume_has_stele_accepts_canonical_layout(tmp_path: Path) -> None:
    stele = tmp_path / "STELE"
    stele.mkdir()
    (stele / "checksums.sha256").write_text(
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  MODELS/x.bin\n",
        encoding="utf-8",
    )
    assert imapi._volume_has_stele(tmp_path) == stele


def test_volume_has_stele_accepts_stele_root_itself(tmp_path: Path) -> None:
    stele = tmp_path / "STELE"
    stele.mkdir()
    (stele / "checksums.sha256").write_text("deadbeef  a\n", encoding="utf-8")
    assert imapi._volume_has_stele(stele) == stele


def test_volume_has_stele_rejects_incomplete(tmp_path: Path) -> None:
    (tmp_path / "STELE").mkdir()
    assert imapi._volume_has_stele(tmp_path) is None


def test_find_disc_stele_root_uses_volume_paths(tmp_path: Path, monkeypatch) -> None:
    stele = tmp_path / "STELE"
    stele.mkdir()
    (stele / "checksums.sha256").write_text("deadbeef  a\n", encoding="utf-8")
    monkeypatch.setattr(imapi, "_iter_windows_volume_names", lambda: [])
    monkeypatch.setattr(imapi, "_recorder_volume_paths", lambda recorder_id: [])
    found = imapi.find_disc_stele_root(
        volume_label="STELE_TEST_1",
        volume_paths=[str(tmp_path)],
        settle_seconds=0,
    )
    assert found == stele


def test_find_disc_stele_root_matches_volume_label(tmp_path: Path, monkeypatch) -> None:
    stele = tmp_path / "STELE"
    stele.mkdir()
    (stele / "checksums.sha256").write_text("deadbeef  a\n", encoding="utf-8")
    # Windows volume names end with a separator; use this OS's separator so the test runs anywhere.
    vol = str(tmp_path) if str(tmp_path).endswith(os.sep) else str(tmp_path) + os.sep
    monkeypatch.setattr(imapi, "_iter_windows_volume_names", lambda: [vol])
    monkeypatch.setattr(imapi, "_volume_label", lambda name: "STELE_TEST_1")
    monkeypatch.setattr(imapi, "_recorder_volume_paths", lambda recorder_id: [])
    found = imapi.find_disc_stele_root(
        volume_label="STELE_TEST_1",
        volume_paths=[],
        settle_seconds=0,
    )
    assert found == stele
