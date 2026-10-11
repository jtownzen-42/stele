"""Canonical disc tree, volume index, and the five-page window."""

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from stele.burn.layout import build_disc_set, image_file_list
from stele.db import Database
from stele.download.worker import parse_checksum_file
from stele.models import DISCLAIMER, HEADROOM_BYTES, ModelDiscMeta, PayloadFile
from stele.settings import Settings


def _payload(root: Path, name: str, size: int, owner: str) -> PayloadFile:
    path = root / name
    path.write_bytes(b"x" * size)
    from stele.download.worker import hash_file

    return PayloadFile(path, f"MODELS/org--repo/abc/{name}", size, hash_file(path), owner)


def _meta(tmp: Path) -> ModelDiscMeta:
    spec = tmp / "spec.md"
    spec.write_text(f"# spec\n\n{DISCLAIMER}\n", encoding="utf-8")
    return ModelDiscMeta(
        repo_id="org/repo",
        safe_id="org--repo",
        revision="main",
        commit_sha="abc123def456",
        profile="GGUF inference pack",
        license_name="apache-2.0",
        spec_md=spec,
    )


def test_single_volume_matches_canonical_tree(tmp_path: Path):
    payload = [_payload(tmp_path, "weights.gguf", 32, "org--repo")]
    roots = build_disc_set(
        tmp_path / "out",
        payload,
        [_meta(tmp_path)],
        [],
        capacity_bytes=25_025_314_816,
        created_utc="2026-09-24T00:00:00Z",
        set_id="deadbeefcafebabe",
    )
    assert len(roots) == 1
    root = roots[0]
    readme = (root / "README_FIRST.txt").read_text(encoding="utf-8")
    assert "DISC 1 OF 1" in readme
    assert DISCLAIMER in readme
    spec = (root / "DOCS" / "org--repo_spec.md").read_text(encoding="utf-8")
    assert DISCLAIMER in spec
    manifest = json.loads((root / "ARCHIVE_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["volume"] == {"index": 1, "count": 1, "label": "STELE_deadbeef_1"}
    assert manifest["disclaimer"] == DISCLAIMER
    volume = json.loads((root / "VOLUME.json").read_text(encoding="utf-8"))
    assert volume["files"][0]["path"] == "MODELS/org--repo/abc/weights.gguf"
    assert (root / "RESTORE.ps1").exists()
    assert (root / "DOCS" / "labels" / "disc_face.pdf").stat().st_size > 100
    assert (root / "DOCS" / "labels" / "case_insert.pdf").stat().st_size > 100
    listed = image_file_list(root)
    assert "README_FIRST.txt" in listed
    assert "MODELS/org--repo/abc/weights.gguf" in listed
    names = {rel for _sha, rel in parse_checksum_file(root / "checksums.sha256")}
    assert "MODELS/org--repo/abc/weights.gguf" in names
    assert "ARCHIVE_MANIFEST.json" not in names


def test_span_writes_disc_n_of_m_and_keeps_files_whole(tmp_path: Path):
    payload = [
        _payload(tmp_path, "a.bin", 800_000, "org--repo"),
        _payload(tmp_path, "b.bin", 800_000, "org--repo"),
    ]
    capacity = HEADROOM_BYTES + 1_000_000
    roots = build_disc_set(
        tmp_path / "span",
        payload,
        [_meta(tmp_path)],
        [],
        capacity_bytes=capacity,
        created_utc="2026-09-24T00:00:00Z",
        set_id="abcdef0123456789",
    )
    assert len(roots) >= 2
    seen: dict[str, int] = {}
    for root in roots:
        readme = (root / "README_FIRST.txt").read_text(encoding="utf-8")
        manifest = json.loads((root / "ARCHIVE_MANIFEST.json").read_text(encoding="utf-8"))
        assert f"DISC {manifest['volume']['index']} OF {manifest['volume']['count']}" in readme
        volume = json.loads((root / "VOLUME.json").read_text(encoding="utf-8"))
        assert len(volume["files"]) == 2
        for _sha, rel in parse_checksum_file(root / "checksums.sha256"):
            if rel.startswith("MODELS/"):
                assert rel not in seen
                seen[rel] = manifest["volume"]["index"]
        assert (root / "DOCS" / "org--repo_spec.md").exists()
    assert set(seen) == {
        "MODELS/org--repo/abc/a.bin",
        "MODELS/org--repo/abc/b.bin",
    }


def test_shared_runtime_folder_archives_one_pack_file(tmp_path: Path):
    from stele.burn.layout import runtime_pack_file

    folder = tmp_path / "llama.cpp" / "b1"
    folder.mkdir(parents=True)
    (folder / "cpu.zip").write_bytes(b"cpu")
    (folder / "cuda.zip").write_bytes(b"cuda")
    (folder / "SOURCE.txt").write_text("note", encoding="utf-8")
    files = runtime_pack_file(folder, "llama.cpp", "b1", "llama-cpp-cpu", "cpu.zip")
    assert [item.disc_relative for item in files] == ["RUNTIME/llama.cpp/b1/cpu.zip"]


def test_restore_script_does_not_launch_installers(tmp_path: Path):
    payload = [_payload(tmp_path, "w.gguf", 8, "org--repo")]
    root = build_disc_set(
        tmp_path / "restore",
        payload,
        [_meta(tmp_path)],
        [],
        capacity_bytes=25_025_314_816,
        created_utc="2026-09-24T00:00:00Z",
    )[0]
    text = (root / "RESTORE.ps1").read_text(encoding="utf-8")
    assert "Destination" in text
    assert "Start-Process" not in text
    assert "Invoke-WebRequest" not in text
    assert DISCLAIMER in text


def test_main_window_has_five_sections(tmp_path: Path):
    old = os.environ.get("LOCALAPPDATA")
    os.environ["LOCALAPPDATA"] = str(tmp_path / "local")
    try:
        from PySide6.QtWidgets import QApplication

        from stele.ui.main_window import MainWindow

        app = QApplication.instance() or QApplication([])
        db = Database(tmp_path / "stele.db")
        settings = Settings(db)
        settings.set_vault(tmp_path / "vault")
        settings.set_staging(tmp_path / "staging")
        window = MainWindow(db, settings, start_worker=False)
        assert window.nav_labels() == ["Discover", "Queue", "Library", "Burn", "Runtimes"]
        window.close()
        db.close()
        assert app is not None
    finally:
        if old is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = old
