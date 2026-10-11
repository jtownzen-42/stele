"""Tests for custom studio branding and printable labels."""

from __future__ import annotations

from pathlib import Path
import pytest

from stele.db import Database
from stele.docs.labels import write_case_insert, write_disc_face
from stele.settings import Settings


@pytest.fixture
def temp_settings(tmp_path: Path) -> Settings:
    db = Database(tmp_path / "test.db")
    return Settings(db)


def test_settings_studio_name_default_and_custom(temp_settings: Settings):
    assert temp_settings.studio_name() == "STELE"
    temp_settings.set_studio_name("Obsidian Cold Storage")
    assert temp_settings.studio_name() == "Obsidian Cold Storage"


def test_write_disc_face_custom_branding(tmp_path: Path):
    out = tmp_path / "disc_custom.pdf"
    write_disc_face(
        out,
        model_ids=["meta-llama/Llama-3-8B"],
        commit_short="123456789abc",
        when="2026-10-11",
        volume=1,
        count=2,
        studio_name="DeepMind Vault",
    )
    assert out.exists()
    assert out.stat().st_size > 200


def test_write_case_insert_custom_branding(tmp_path: Path):
    out = tmp_path / "insert_custom.pdf"
    write_case_insert(
        out,
        model_ids=["meta-llama/Llama-3-8B"],
        license_name="llama3",
        summary="Llama 3 8B GGUF Model Archive",
        checksum_prefixes=["abcdef123456"],
        studio_name="DeepMind Vault",
    )
    assert out.exists()
    assert out.stat().st_size > 200
