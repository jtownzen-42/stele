"""Gather what Stele knows about one vault item and write provenance.json."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import quote

from stele import __version__
from stele.db import Database, loads_meta
from stele.download.worker import hash_file, parse_checksum_file
from stele.models import DISCLAIMER, NOT_LEGAL_ADVICE, safe_repo

SCHEMA = "stele.provenance/1"
# Files Stele writes into a model folder itself; they are not downloads.
STELE_WRITTEN = ("SOURCE.txt", "checksums.sha256", "civitai_model.json")


@dataclass
class EvidenceFile:
    path: str  # relative to the vault item, forward slashes
    recorded_sha256: str
    download_url: str
    bytes: int = 0
    sha256: str = ""  # measured now; empty when the file is missing

    @property
    def status(self) -> str:
        if not self.sha256:
            return "missing"
        if not self.recorded_sha256:
            return "no record"
        return "matches" if self.sha256 == self.recorded_sha256 else "changed"


@dataclass
class EvidenceItem:
    kind: str  # "model" or "runtime"
    source: str  # "huggingface", "civitai", or "runtime"
    repo_id: str
    revision: str
    commit_sha: str
    profile: str
    license_name: str
    license_ack_utc: str
    archived_utc: str
    vault_dir: Path
    page_url: str
    files: list[EvidenceFile]
    docs: list[Path] = field(default_factory=list)
    pipeline_tag: str = ""
    library_name: str = ""
    civitai: dict | None = None

    @property
    def safe_id(self) -> str:
        return safe_repo(self.repo_id)


def load_item(db: Database, vault_root: Path, catalog_id: int) -> EvidenceItem:
    """Build an EvidenceItem from the catalog, its job, and the vault folder."""
    row = db.get_catalog(catalog_id)
    if row is None:
        raise ValueError("That vault item is no longer in the catalog.")
    vault_dir = Path(str(row["vault_path"]))
    if not vault_dir.is_dir():
        raise ValueError(f"The vault folder is missing: {vault_dir}")
    job = db.get_job(int(row["job_id"])) if row.get("job_id") else None
    meta = loads_meta(job.get("meta_json")) if job else {}
    job_files = db.list_files(int(job["id"])) if job else []
    repo_id = str(row["repo_id"])
    commit = str(row.get("commit_sha") or row.get("revision") or "")
    common = {
        "repo_id": repo_id,
        "revision": str(row.get("revision") or ""),
        "commit_sha": commit,
        "profile": str(row.get("profile") or ""),
        "license_name": str(row.get("license_name") or "unknown"),
        "license_ack_utc": str((job or {}).get("license_ack_utc") or ""),
        "archived_utc": str(row.get("created_utc") or ""),
        "vault_dir": vault_dir,
        "pipeline_tag": str((job or {}).get("pipeline_tag") or ""),
        "library_name": str((job or {}).get("library_name") or ""),
    }

    if row["kind"] == "runtime":
        filename = str(meta.get("filename") or (job_files[0]["relative_path"] if job_files else ""))
        recorded = str(meta.get("sha256") or (job_files[0].get("sha256") if job_files else "") or "")
        files = [EvidenceFile(filename, recorded.lower(), str(meta.get("url") or ""))] if filename else []
        return EvidenceItem(
            kind="runtime",
            source="runtime",
            page_url=str(meta.get("homepage") or ""),
            files=files,
            **common,
        )

    source = "civitai" if meta.get("source") == "civitai" else "huggingface"
    recorded = _recorded_hashes(vault_dir, job_files)
    urls = meta.get("download_urls") or {}
    files = [
        EvidenceFile(path, sha, str(urls.get(path) or "") if source == "civitai" else hf_file_url(repo_id, commit, path))
        for path, sha in sorted(recorded.items())
    ]
    if source == "civitai":
        from stele.hub.civitai import model_url

        page_url = model_url(repo_id, commit)
    else:
        page_url = f"https://huggingface.co/{repo_id}/tree/{commit}"
    safe = safe_repo(repo_id)
    docs_dir = vault_root / "DOCS"
    docs = [
        docs_dir / f"{safe}_{name}"
        for name in ("spec.pdf", "spec.md", "howto.pdf", "howto.md")
        if (docs_dir / f"{safe}_{name}").is_file()
    ]
    return EvidenceItem(
        kind="model",
        source=source,
        page_url=page_url,
        files=files,
        docs=docs,
        civitai=meta.get("civitai") if source == "civitai" else None,
        **common,
    )


def hf_file_url(repo_id: str, commit: str, path: str) -> str:
    return f"https://huggingface.co/{repo_id}/resolve/{commit}/{quote(path)}"


def _recorded_hashes(vault_dir: Path, job_files: list[dict]) -> dict[str, str]:
    """Path -> SHA-256 Stele recorded when the item was archived."""
    recorded: dict[str, str] = {}
    for row in job_files:
        path = str(row["relative_path"]).replace("\\", "/")
        recorded[path] = str(row.get("sha256") or "").lower()
    checksums = vault_dir / "checksums.sha256"
    if checksums.is_file():
        for sha, rel in parse_checksum_file(checksums):
            if not recorded.get(rel):
                recorded[rel] = sha.lower()
    if not recorded:
        # No job and no checksum file: describe what is on disk now.
        for path in sorted(vault_dir.rglob("*")):
            if path.is_file() and path.name not in STELE_WRITTEN:
                recorded[path.relative_to(vault_dir).as_posix()] = ""
    return recorded


def measure(
    item: EvidenceItem,
    progress: Callable[[str], None] | None = None,
    known: dict[Path, str] | None = None,
) -> None:
    """Hash every file as it is on disk now.

    `known` maps absolute paths to a SHA-256 measured moments ago (the burn
    payload already hashed every model file), so large models are read once.
    """
    known = {Path(path).resolve(): sha for path, sha in (known or {}).items()}
    for index, entry in enumerate(item.files, start=1):
        target = item.vault_dir / entry.path
        if target.is_file():
            entry.bytes = target.stat().st_size
            entry.sha256 = known.get(target.resolve()) or ""
            if not entry.sha256:
                if progress:
                    progress(f"Hashing {index} of {len(item.files)}: {entry.path}")
                entry.sha256 = hash_file(target)
        else:
            entry.bytes = 0
            entry.sha256 = ""


def problems(item: EvidenceItem) -> list[str]:
    return [f"{entry.path} ({entry.status})" for entry in item.files if entry.status in ("missing", "changed")]


def build_provenance(item: EvidenceItem, stamp: dict[str, str], licenses: list[str]) -> dict:
    """The provenance.json document. Call measure() first."""
    model = {
        "kind": item.kind,
        "source": item.source,
        "repo_id": item.repo_id,
        "revision": item.revision,
        "commit": item.commit_sha,
        "profile": item.profile,
        "page_url": item.page_url,
        "pipeline_tag": item.pipeline_tag,
        "library_name": item.library_name,
    }
    if item.civitai:
        version = item.civitai.get("version") or {}
        model["civitai"] = {
            "model_id": item.civitai.get("model_id"),
            "name": item.civitai.get("name"),
            "creator": item.civitai.get("creator"),
            "version_id": version.get("id"),
            "version_name": version.get("name"),
            "base_model": version.get("base_model"),
        }
    return {
        "schema": SCHEMA,
        "generated": stamp,
        "generator": {"name": "Stele", "version": __version__},
        "notice": NOT_LEGAL_ADVICE,
        "disclaimer": DISCLAIMER,
        "model": model,
        "license": {
            "name": item.license_name,
            "acknowledged_utc": item.license_ack_utc or None,
            "files": licenses,
            "permissions": (item.civitai or {}).get("permissions"),
        },
        "archived_utc": item.archived_utc,
        "files": [
            {
                "path": entry.path,
                "bytes": entry.bytes,
                "sha256": entry.sha256 or None,
                "recorded_sha256": entry.recorded_sha256 or None,
                "status": entry.status,
                "download_url": entry.download_url or None,
            }
            for entry in item.files
        ],
        "verification": {
            "files": len(item.files),
            "matching": sum(1 for entry in item.files if entry.status == "matches"),
            "problems": problems(item),
        },
    }
