"""EULA acceptance, notices content, LM Studio opt-in (off by default), model-license acknowledgment."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import stele.legal as legal
from stele.db import Database
from stele.download.queue import Queue
from stele.settings import Settings

PACKS = json.loads((Path(legal.__file__).resolve().parents[1] / "runtime" / "manifest.json").read_text(encoding="utf-8"))["packs"]


@pytest.fixture
def db(tmp_path) -> Database:
    return Database(tmp_path / "t.db")


# ---------------------------------------------------------------- A1 / A2 text

def test_eula_covers_required_points():
    text = legal.eula_text().lower()
    for needle in ("free", "pro", "one-time", "redistribut", "as is",
                   "refund", "support", "14 days", "gumroad"):
        assert needle in text, needle
    assert "texas" not in text  # no jurisdiction the seller has not chosen
    assert "draft" not in text  # approved by the seller 2026-10-17; no draft wording may ship


def test_notices_list_the_shipped_dependencies():
    text = legal.notices_text()
    for name in ("PySide6", "LGPL", "huggingface_hub", "ReportLab", "keyring", "comtypes", "httpx",
                 "Ollama", "llama.cpp", "LM Studio", "PyInstaller"):
        assert name in text, name


def test_notices_cover_every_direct_import():
    root = Path(legal.__file__).resolve().parents[1]
    imports = set()
    for path in root.rglob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(("import ", "from ")) and not line.startswith(("from stele", "from .", "from __future__")):
                imports.add(line.split()[1].split(".")[0])
    third_party = {"PySide6": "PySide6", "httpx": "httpx", "reportlab": "ReportLab", "keyring": "keyring",
                   "comtypes": "comtypes", "huggingface_hub": "huggingface_hub"}
    text = legal.notices_text()
    for module, label in third_party.items():
        if module in imports:
            assert label in text, module


# ---------------------------------------------------------------- A5 first-run acceptance

def test_eula_is_asked_until_accepted_and_again_for_a_new_version(db, monkeypatch):
    assert not legal.eula_accepted(db)
    legal.accept_eula(db)
    assert legal.eula_accepted(db)
    assert db.get_setting(legal.KEY_EULA_UTC)
    monkeypatch.setattr(legal, "EULA_VERSION", "2")
    assert not legal.eula_accepted(db)


# ---------------------------------------------------------------- A3 LM Studio opt-in

def test_lmstudio_is_in_the_manifest_but_hidden_by_default(db):
    assert any(p["id"] == "lmstudio" for p in PACKS)
    assert not legal.lmstudio_enabled(db)
    ids = [p["id"] for p in legal.visible_packs(db, PACKS)]
    assert "lmstudio" not in ids and "ollama" in ids


def test_lmstudio_needs_an_explicit_acknowledgment(db):
    legal.set_lmstudio_optin(db, False)
    assert not legal.lmstudio_enabled(db)
    legal.set_lmstudio_optin(db, True)
    assert legal.lmstudio_enabled(db)
    assert "lmstudio" in [p["id"] for p in legal.visible_packs(db, PACKS)]
    legal.set_lmstudio_optin(db, False)
    assert not legal.lmstudio_enabled(db)


def test_saved_lmstudio_selection_never_reaches_a_burn_without_opt_in(db):
    saved = ["lmstudio", "ollama"]
    assert legal.allowed_runtime_ids(db, saved) == ["ollama"]
    legal.set_lmstudio_optin(db, True)
    assert legal.allowed_runtime_ids(db, saved) == saved


def test_lmstudio_notice_names_the_terms():
    assert "lmstudio.ai" in legal.LMSTUDIO_NOTICE and "never runs" in legal.LMSTUDIO_NOTICE


# ---------------------------------------------------------------- A4 model-license acknowledgment

def _enqueue(queue, ack):
    return queue.enqueue_model(
        repo_id="org/model", revision="main", commit_sha="a" * 40, profile="default",
        license_name="apache-2.0", license_excerpt="x", license_ack_utc=ack, card_excerpt="",
        pipeline_tag="text-generation", library_name="transformers", files=[object()],
    )


def test_model_download_is_refused_without_license_acknowledgment(db, tmp_path):
    queue = Queue(db, Settings(db))
    with pytest.raises(ValueError, match="Acknowledge the license"):
        _enqueue(queue, None)
    with pytest.raises(ValueError, match="Acknowledge the license"):
        _enqueue(queue, "")


def test_release_build_bundles_the_legal_texts():
    """The frozen app reads EULA.txt and THIRD_PARTY_NOTICES.txt at startup, so stele.spec must ship them."""
    spec = (Path(legal.__file__).resolve().parents[2] / "stele.spec").read_text(encoding="utf-8")
    for name in ("EULA.txt", "THIRD_PARTY_NOTICES.txt"):
        assert f"('stele/legal/{name}', 'stele/legal')" in spec
