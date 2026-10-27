"""Write the evidence ZIP for one vault item."""

from __future__ import annotations

import hashlib
import json
import os
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from stele.db import Database
from stele.download.worker import format_checksum_line, hash_file
from stele.evidence.clock import local_timestamp
from stele.evidence.licenses import license_entries
from stele.evidence.provenance import EvidenceItem, build_provenance, load_item, measure, problems
from stele.evidence.sbom import build_sbom
from stele.license import FEATURE_EVIDENCE, require_pro
from stele.models import CLOCK_NOTE, DISCLAIMER, NOT_LEGAL_ADVICE, PayloadFile

EVIDENCE_DIR = "EVIDENCE"

CONTENTS_FILE = "ZIP_CONTENTS.sha256"


@dataclass
class EvidenceResult:
    path: Path
    problems: list[str]


def export_evidence(
    db: Database,
    vault_root: Path,
    catalog_id: int,
    out_dir: Path,
    *,
    now: datetime | None = None,
    progress: Callable[[str], None] | None = None,
    known: dict[Path, str] | None = None,
) -> EvidenceResult:
    """Pro: hash the vault item as it is now and write its evidence ZIP into out_dir."""
    require_pro(db, FEATURE_EVIDENCE)
    item = load_item(db, Path(vault_root), catalog_id)
    if not item.files:
        raise ValueError("This vault item has no files to describe.")
    measure(item, progress, known)
    stamp = local_timestamp(now)
    return EvidenceResult(write_evidence_zip(item, stamp, Path(out_dir)), problems(item))


def disc_evidence(
    db: Database,
    vault_root: Path,
    catalog_id: int,
    work_dir: Path,
    model_files: list[PayloadFile],
    *,
    now: datetime | None = None,
    progress: Callable[[str], None] | None = None,
) -> PayloadFile:
    """Write the evidence ZIP into work_dir and return it as a file for the disc.

    It lands at EVIDENCE/<name>.zip and travels with the model (same owner),
    so README_FIRST and the docs on that volume describe it.
    """
    known = {item.source: item.sha256 for item in model_files if item.split_of is None}
    result = export_evidence(db, vault_root, catalog_id, work_dir, now=now, progress=progress, known=known)
    owner = model_files[0].owner if model_files else ""
    return PayloadFile(
        source=result.path,
        disc_relative=f"{EVIDENCE_DIR}/{result.path.name}",
        size=result.path.stat().st_size,
        sha256=hash_file(result.path),
        owner=owner,
    )


def zip_name(item: EvidenceItem, stamp: dict[str, str]) -> str:
    when = stamp["local"][:19].replace("-", "").replace(":", "").replace("T", "-")
    return f"{item.safe_id}_{(item.commit_sha or item.revision)[:12]}_evidence_{when}"


def write_evidence_zip(item: EvidenceItem, stamp: dict[str, str], out_dir: Path) -> Path:
    """Build the entries in a fixed order, then write them with one fixed date."""
    name = zip_name(item, stamp)
    licenses = license_entries(item)
    entries: list[tuple[str, bytes]] = [
        ("README.txt", readme_text(item, stamp).encode("utf-8")),
        (
            "provenance.json",
            _json(build_provenance(item, stamp, [f"LICENSES/{entry}" for entry, _ in licenses])),
        ),
        ("sbom.cdx.json", _json(build_sbom(item, stamp))),
        (
            "checksums.sha256",
            "".join(format_checksum_line(f.sha256, f.path) for f in item.files if f.sha256).encode("utf-8"),
        ),
    ]
    entries += [(f"LICENSES/{entry}", data) for entry, data in licenses]
    entries += [(f"DOCS/{doc.name}", doc.read_bytes()) for doc in item.docs]
    for record in ("SOURCE.txt", "civitai_model.json"):
        path = item.vault_dir / record
        if path.is_file():
            entries.append((f"SOURCE/{record}", path.read_bytes()))
    contents = "".join(
        format_checksum_line(hashlib.sha256(data).hexdigest(), entry) for entry, data in entries
    )
    entries.append((CONTENTS_FILE, contents.encode("utf-8")))

    date_time = tuple(int(part) for part in (
        stamp["local"][0:4], stamp["local"][5:7], stamp["local"][8:10],
        stamp["local"][11:13], stamp["local"][14:16], stamp["local"][17:19],
    ))
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{name}.zip"
    partial = out_dir / f"{name}.zip.partial"
    with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry, data in entries:
            info = zipfile.ZipInfo(f"{name}/{entry}", date_time=date_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    os.replace(partial, target)
    return target


def readme_text(item: EvidenceItem, stamp: dict[str, str]) -> str:
    found = problems(item)
    lines = [
        "STELE COMPLIANCE VAULT EVIDENCE",
        "",
        f"Item: {item.repo_id} @ {item.commit_sha}",
        f"Source: {item.page_url or item.source}",
        f"Created: {stamp['local']} ({stamp['utc']} UTC, {stamp['time_zone'] or stamp['utc_offset']})",
        CLOCK_NOTE,
        "",
        "This package is timestamped evidence of which files Stele archived, where they came from,",
        "and the license recorded for them. It does not show that any use of the model is permitted.",
        "",
        NOT_LEGAL_ADVICE,
        DISCLAIMER,
        "",
        "Contents:",
        "  provenance.json   source, commit, license, and the SHA-256 of every file, measured when this package was made",
        "  sbom.cdx.json     the same files as a CycloneDX 1.6 SBOM",
        "  checksums.sha256  SHA-256 of every model file, for sha256sum -c or RESTORE.ps1",
        "  LICENSES/         license files found with the model and LICENSE_SUMMARY.txt",
        "  DOCS/             the specification and how-to guide Stele wrote",
        "  SOURCE/           the source record Stele kept with the files",
        f"  {CONTENTS_FILE}  SHA-256 of every other file in this package",
        "",
    ]
    if item.docs_note:
        lines.extend([f"DOCS/ was left out. {item.docs_note}", ""])
    if found:
        lines.append("WARNING: these files did not match what Stele recorded when it archived them:")
        lines.extend(f"  - {entry}" for entry in found)
    matched = sum(1 for entry in item.files if entry.status == "matches")
    unrecorded = sum(1 for entry in item.files if entry.status == "no record")
    lines.append(f"{matched} of {len(item.files)} files matched the SHA-256 Stele recorded when it archived them.")
    if unrecorded:
        lines.append(f"{unrecorded} files had no recorded SHA-256; their hashes were measured for this package.")
    lines.append("")
    return "\n".join(lines)


def _json(value: dict) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
