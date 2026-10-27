"""Compliance Vault evidence ZIP: provenance, licenses, SBOM, and the local-clock timestamp."""

from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from stele.db import Database
from stele.download.worker import write_checksum_file
from stele.evidence.clock import CLOCK_SOURCE, local_timestamp
from stele.evidence.package import CONTENTS_FILE, export_evidence
from stele.license import KEY_LICENSE_STATUS, TIER_PRO, ProRequired
from stele.models import CLOCK_NOTE, NOT_LEGAL_ADVICE

COMMIT = "a" * 40
NOW = datetime(2026, 10, 28, 9, 30, 15, tzinfo=timezone(timedelta(hours=-5)))


def _archive(tmp_path: Path, *, source: str = "huggingface", license_name: str = "apache-2.0") -> tuple[Database, Path, int]:
    db = Database(tmp_path / "stele.db")
    db.set_setting(KEY_LICENSE_STATUS, TIER_PRO)
    vault = tmp_path / "vault"
    repo_id = "org/model" if source == "huggingface" else "civitai/428983"
    commit = COMMIT if source == "huggingface" else "v555"
    item_dir = vault / "MODELS" / repo_id.replace("/", "--") / commit
    files = {"model.safetensors": b"weights" * 100, "config.json": b"{}", "LICENSE": b"Apache License 2.0"}
    for name, data in files.items():
        (item_dir / name).parent.mkdir(parents=True, exist_ok=True)
        (item_dir / name).write_bytes(data)
    (item_dir / "SOURCE.txt").write_text(f"repo: {repo_id}\n", encoding="utf-8")
    write_checksum_file(
        item_dir / "checksums.sha256", [(hashlib.sha256(data).hexdigest(), name) for name, data in files.items()]
    )
    docs = vault / "DOCS"
    docs.mkdir(parents=True)
    (docs / f"{repo_id.replace('/', '--')}_spec.md").write_text("# spec\n", encoding="utf-8")
    meta: dict = {}
    if source == "civitai":
        meta = {
            "source": "civitai",
            "download_urls": {name: f"https://civitai.com/api/download/models/555?f={name}" for name in files},
            "civitai": {
                "model_id": 428983,
                "name": "Test LoRA",
                "creator": "someone",
                "permissions": {"commercial_use": [], "derivatives": True},
                "version": {"id": 555, "name": "v1", "base_model": "SDXL 1.0"},
            },
        }
    job_id = db.insert_job(
        {
            "kind": "model",
            "repo_id": repo_id,
            "revision": "main",
            "commit_sha": commit,
            "profile": "Full repo",
            "license_name": license_name,
            "license_ack_utc": "2026-10-20T12:00:00Z",
            "meta_json": json.dumps(meta),
        },
        [{"relative_path": name, "size": len(data), "local_path": ""} for name, data in files.items()],
    )
    for row in db.list_files(job_id):
        data = files[row["relative_path"]]
        db.mark_file_done(int(row["id"]), hashlib.sha256(data).hexdigest(), len(data))
    catalog_id = db.insert_catalog(
        {
            "kind": "model",
            "repo_id": repo_id,
            "revision": "main",
            "commit_sha": commit,
            "profile": "Full repo",
            "license_name": license_name,
            "vault_path": str(item_dir),
            "bytes": sum(len(data) for data in files.values()),
            "file_count": len(files),
            "formats_json": "[]",
            "job_id": job_id,
        }
    )
    return db, vault, catalog_id


def _read(zip_path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(zip_path) as archive:
        return {info.filename.split("/", 1)[1]: archive.read(info) for info in archive.infolist()}


def test_local_timestamp_uses_the_pc_clock_and_says_so():
    stamp = local_timestamp(NOW)
    assert stamp["utc"] == "2026-10-28T14:30:15Z"
    assert stamp["source"] == CLOCK_SOURCE
    assert stamp["note"] == CLOCK_NOTE
    assert stamp["utc_offset"].count(":") == 1


def test_evidence_zip_holds_every_part(tmp_path: Path):
    db, vault, catalog_id = _archive(tmp_path)
    result = export_evidence(db, vault, catalog_id, tmp_path / "out", now=NOW)
    assert result.problems == []
    assert result.path.name.startswith("org--model_aaaaaaaaaaaa_evidence_")
    files = _read(result.path)
    assert {
        "README.txt",
        "provenance.json",
        "sbom.cdx.json",
        "checksums.sha256",
        "LICENSES/LICENSE_SUMMARY.txt",
        "LICENSES/LICENSE",
        "DOCS/org--model_spec.md",
        "SOURCE/SOURCE.txt",
        CONTENTS_FILE,
    } <= set(files)
    assert NOT_LEGAL_ADVICE in files["README.txt"].decode()
    assert CLOCK_NOTE in files["README.txt"].decode()

    provenance = json.loads(files["provenance.json"])
    assert provenance["generated"]["utc"] == "2026-10-28T14:30:15Z"
    assert provenance["generated"]["source"] == CLOCK_SOURCE
    assert provenance["notice"] == NOT_LEGAL_ADVICE
    assert provenance["model"]["commit"] == COMMIT
    assert provenance["license"]["acknowledged_utc"] == "2026-10-20T12:00:00Z"
    assert "LICENSES/LICENSE" in provenance["license"]["files"]
    weights = next(f for f in provenance["files"] if f["path"] == "model.safetensors")
    assert weights["status"] == "matches"
    assert weights["download_url"] == f"https://huggingface.co/org/model/resolve/{COMMIT}/model.safetensors"

    # ZIP_CONTENTS.sha256 covers every other entry.
    listed = dict(
        (rel, sha) for sha, _, rel in (line.partition("  ") for line in files[CONTENTS_FILE].decode().splitlines())
    )
    assert set(listed) == set(files) - {CONTENTS_FILE}
    for name, sha in listed.items():
        assert hashlib.sha256(files[name]).hexdigest() == sha


def test_changed_and_missing_files_are_reported(tmp_path: Path):
    db, vault, catalog_id = _archive(tmp_path)
    item_dir = Path(db.get_catalog(catalog_id)["vault_path"])
    (item_dir / "model.safetensors").write_bytes(b"tampered")
    (item_dir / "config.json").unlink()
    result = export_evidence(db, vault, catalog_id, tmp_path / "out", now=NOW)
    assert sorted(result.problems) == ["config.json (missing)", "model.safetensors (changed)"]
    files = _read(result.path)
    assert "WARNING" in files["README.txt"].decode()
    statuses = {f["path"]: f["status"] for f in json.loads(files["provenance.json"])["files"]}
    assert statuses == {"LICENSE": "matches", "config.json": "missing", "model.safetensors": "changed"}


def test_sbom_is_valid_cyclonedx_16(tmp_path: Path):
    db, vault, catalog_id = _archive(tmp_path)
    sbom = json.loads(_read(export_evidence(db, vault, catalog_id, tmp_path / "out", now=NOW).path)["sbom.cdx.json"])
    main = sbom["metadata"]["component"]
    assert main["type"] == "machine-learning-model"
    assert main["purl"] == f"pkg:huggingface/org/model@{COMMIT}"
    assert main["licenses"] == [{"license": {"id": "Apache-2.0"}}]
    assert len(sbom["components"]) == 3
    validation = pytest.importorskip("cyclonedx.validation.json")
    from cyclonedx.schema import SchemaVersion

    error = validation.JsonStrictValidator(SchemaVersion.V1_6).validate_str(json.dumps(sbom))
    assert error is None, error


def test_civitai_item_keeps_permissions_and_links(tmp_path: Path):
    db, vault, catalog_id = _archive(tmp_path, source="civitai", license_name="Civitai permissions: commercial use none")
    files = _read(export_evidence(db, vault, catalog_id, tmp_path / "out", now=NOW).path)
    assert json.loads(files["LICENSES/civitai_permissions.json"])["derivatives"] is True
    provenance = json.loads(files["provenance.json"])
    assert provenance["model"]["civitai"]["version_id"] == 555
    assert provenance["files"][0]["download_url"].startswith("https://civitai.com/api/download/models/555")
    sbom = json.loads(files["sbom.cdx.json"])
    assert "purl" not in sbom["metadata"]["component"]
    assert sbom["metadata"]["component"]["licenses"] == [
        {"license": {"name": "Civitai permissions: commercial use none"}}
    ]


def test_unknown_license_is_flagged(tmp_path: Path):
    db, vault, catalog_id = _archive(tmp_path, license_name="other")
    summary = _read(export_evidence(db, vault, catalog_id, tmp_path / "out", now=NOW).path)["LICENSES/LICENSE_SUMMARY.txt"]
    assert b"WARNING: the license is unknown" in summary


def test_evidence_export_needs_pro(tmp_path: Path):
    db, vault, catalog_id = _archive(tmp_path)
    db.set_setting(KEY_LICENSE_STATUS, "Free")
    with pytest.raises(ProRequired):
        export_evidence(db, vault, catalog_id, tmp_path / "out", now=NOW)
    assert not (tmp_path / "out").exists()


def test_copy_avoids_banned_words(tmp_path: Path):
    db, vault, catalog_id = _archive(tmp_path)
    files = _read(export_evidence(db, vault, catalog_id, tmp_path / "out", now=NOW).path)
    text = (files["README.txt"] + files["LICENSES/LICENSE_SUMMARY.txt"] + files["provenance.json"]).decode().lower()
    for banned in ("insurance", "proof", "mandatory", "eu ai act"):
        assert banned not in text


def test_evidence_goes_on_the_disc_with_the_model(tmp_path: Path, monkeypatch):
    from stele.burn.layout import build_disc_set, model_payload
    from stele.evidence import provenance
    from stele.evidence.package import disc_evidence
    from stele.models import ModelDiscMeta

    db, vault, catalog_id = _archive(tmp_path)
    row = db.get_catalog(catalog_id)
    files = model_payload(Path(row["vault_path"]), row["repo_id"], COMMIT)

    def no_rehash(path):
        raise AssertionError(f"{path} was hashed twice")

    monkeypatch.setattr(provenance, "hash_file", no_rehash)
    evidence = disc_evidence(db, vault, catalog_id, tmp_path / "work_evidence", files, now=NOW)
    monkeypatch.undo()
    assert evidence.disc_relative.startswith("EVIDENCE/org--model_aaaaaaaaaaaa_evidence_")
    assert evidence.owner == "org--model"

    meta = ModelDiscMeta("org/model", "org--model", "main", COMMIT, "Full repo", "apache-2.0")
    roots = build_disc_set(tmp_path / "work", files + [evidence], [meta], [], 25_025_314_816, "2026-10-28T14:30:15Z")
    root = roots[0]
    assert (root / evidence.disc_relative).read_bytes() == evidence.source.read_bytes()
    readme = (root / "README_FIRST.txt").read_text(encoding="utf-8")
    assert evidence.disc_relative in readme
    assert NOT_LEGAL_ADVICE in readme
    manifest = json.loads((root / "ARCHIVE_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["evidence"] == [evidence.disc_relative]
    assert evidence.disc_relative in (root / "checksums.sha256").read_text(encoding="utf-8")


def test_runtime_item_evidence(tmp_path: Path):
    db = Database(tmp_path / "stele.db")
    db.set_setting(KEY_LICENSE_STATUS, TIER_PRO)
    folder = tmp_path / "vault" / "RUNTIME" / "llama.cpp" / "b1"
    folder.mkdir(parents=True)
    data = b"zip bytes"
    (folder / "llama.zip").write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    job_id = db.insert_job(
        {
            "kind": "runtime",
            "repo_id": "llama-cpu",
            "revision": "b1",
            "commit_sha": "b1",
            "license_name": "MIT",
            "meta_json": json.dumps(
                {"filename": "llama.zip", "url": "https://github.com/x/llama.zip", "sha256": sha, "homepage": "https://github.com/x"}
            ),
        },
        [{"relative_path": "llama.zip", "size": len(data), "local_path": ""}],
    )
    catalog_id = db.insert_catalog(
        {"kind": "runtime", "repo_id": "llama-cpu", "revision": "b1", "commit_sha": "b1", "license_name": "MIT",
         "vault_path": str(folder), "bytes": len(data), "file_count": 1, "formats_json": "[]", "job_id": job_id}
    )
    result = export_evidence(db, tmp_path / "vault", catalog_id, tmp_path / "out", now=NOW)
    assert result.problems == []
    sbom = json.loads(_read(result.path)["sbom.cdx.json"])
    assert sbom["metadata"]["component"]["type"] == "application"
    assert sbom["components"][0]["externalReferences"][0]["url"] == "https://github.com/x/llama.zip"
