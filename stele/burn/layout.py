"""Build the canonical STELE tree for one volume or a spanned set.

Staging, the vault's model folders, an ISO, and a burned disc all use the
same relative layout. This module is what makes them match.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from pathlib import Path
from typing import Callable

from stele import __version__
from stele.burn.par2 import RECOVERY_DIR, create_recovery, payload_capacity
from stele.burn.span import part_sizes, plan_volumes, usable_bytes
from stele.docs.labels import write_case_insert, write_disc_face
from stele.download.worker import hash_file, write_checksum_file
from stele.license import FEATURE_SPAN, ProRequired
from stele.models import (
    DISCLAIMER,
    HEADROOM_BYTES,
    NOT_LEGAL_ADVICE,
    ModelDiscMeta,
    PayloadFile,
    RuntimeDiscMeta,
    SpanFile,
    SplitFile,
    part_name,
    safe_repo,
)
from stele.restore.restore_ps1 import write_restore_script


def collect_tree(root: Path, disc_prefix: str, owner: str) -> list[PayloadFile]:
    """Hash every file under root and name it disc_prefix + relative path."""
    files: list[PayloadFile] = []
    if not root.exists():
        return files
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "checksums.sha256":
            continue
        relative = path.relative_to(root).as_posix()
        files.append(
            PayloadFile(
                source=path,
                disc_relative=f"{disc_prefix.rstrip('/')}/{relative}",
                size=path.stat().st_size,
                sha256=hash_file(path),
                owner=owner,
            )
        )
    return files


def model_payload(revision_dir: Path, repo_id: str, commit_sha: str) -> list[PayloadFile]:
    safe = safe_repo(repo_id)
    return collect_tree(revision_dir, f"MODELS/{safe}/{commit_sha}", safe)


def runtime_payload(directory: Path, folder: str, version: str, pack_id: str) -> list[PayloadFile]:
    """Whole directory. Do not use this for packs that share a version folder."""
    return collect_tree(directory, f"RUNTIME/{folder}/{version}", pack_id)


def runtime_pack_file(
    directory: Path,
    folder: str,
    version: str,
    pack_id: str,
    filename: str,
) -> list[PayloadFile]:
    """One official file. CPU and CUDA llama.cpp builds share llama.cpp/<tag>/."""
    path = directory / filename
    if not path.is_file():
        return []
    return [
        PayloadFile(
            source=path,
            disc_relative=f"RUNTIME/{folder}/{version}/{filename}",
            size=path.stat().st_size,
            sha256=hash_file(path),
            owner=pack_id,
        )
    ]


_COPY_CHUNK = 8 * 1024 * 1024


def split_oversized(payload: list[PayloadFile], usable: int) -> tuple[list[PayloadFile], list[SplitFile]]:
    """Replace each file larger than `usable` with equal parts that each fit."""
    out: list[PayloadFile] = []
    splits: list[SplitFile] = []
    for item in payload:
        sizes = part_sizes(item.size, usable)
        if len(sizes) == 1:
            out.append(item)
            continue
        parts: list[PayloadFile] = []
        offset = 0
        for index, size in enumerate(sizes):
            parts.append(
                PayloadFile(
                    source=item.source,
                    disc_relative=part_name(item.disc_relative, index + 1),
                    size=size,
                    sha256=hash_range(item.source, offset, size),
                    owner=item.owner,
                    offset=offset,
                    split_of=item.disc_relative,
                    part_index=index + 1,
                )
            )
            offset += size
        out.extend(parts)
        splits.append(SplitFile(item.disc_relative, item.size, item.sha256, parts))
    return out, splits


def hash_range(path: Path, offset: int, length: int) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        handle.seek(offset)
        remaining = length
        while remaining > 0:
            block = handle.read(min(_COPY_CHUNK, remaining))
            if not block:
                raise ValueError(f"{path} is shorter than expected.")
            digest.update(block)
            remaining -= len(block)
    return digest.hexdigest()


def _copy_payload(item: PayloadFile, target: Path) -> None:
    if item.split_of is None:
        shutil.copy2(item.source, target)
        return
    with Path(item.source).open("rb") as src, target.open("wb") as dst:
        src.seek(item.offset)
        remaining = item.size
        while remaining > 0:
            block = src.read(min(_COPY_CHUNK, remaining))
            if not block:
                raise ValueError(f"{item.source} is shorter than expected.")
            dst.write(block)
            remaining -= len(block)


def build_disc_set(
    out_root: Path,
    payload: list[PayloadFile],
    models: list[ModelDiscMeta],
    runtimes: list[RuntimeDiscMeta],
    capacity_bytes: int,
    created_utc: str,
    set_id: str | None = None,
    studio_name: str = "STELE",
    max_volumes: int | None = None,
    recovery_percent: int = 0,
    par2_exe: Path | None = None,
    progress: Callable[[str], None] | None = None,
) -> list[Path]:
    """Write `volume_XX/STELE/` trees. Returns each STELE directory.

    A file larger than one volume is stored as numbered parts on several
    volumes; RESTORE.ps1 rejoins them and checks the whole-file SHA-256.
    Raises ProRequired when the set needs more than `max_volumes` volumes;
    the Free tier passes 1, because multi-disc spanning is a Pro feature.

    With `recovery_percent` > 0 each volume keeps room for, and gets, a PAR2
    recovery set under RECOVERY/ made by `par2_exe`.
    """
    if not payload:
        raise ValueError("Nothing selected to archive.")
    recovery_percent = max(0, int(recovery_percent))
    if recovery_percent and par2_exe is None:
        raise ValueError("PAR2 recovery data was requested but no par2 program was found.")
    usable = payload_capacity(usable_bytes(capacity_bytes), recovery_percent)
    if usable <= 0:
        raise ValueError("The disc is too small to hold recovery data. Lower the redundancy or use larger media.")
    payload, splits = split_oversized(payload, usable)
    by_path = {item.disc_relative: item for item in payload}
    if len(by_path) != len(payload):
        names = [item.disc_relative for item in payload]
        clash = next(name for name in names if names.count(name) > 1)
        raise ValueError(
            f"{clash} already exists in the selection, so a split part cannot use that name. "
            "Rename or remove that file and try again."
        )
    span = plan_volumes(
        [SpanFile(item.disc_relative, item.size) for item in payload],
        usable + HEADROOM_BYTES,
    )
    if span.error:
        raise ValueError(span.error)
    if not span.volumes:
        raise ValueError("Nothing selected to archive.")
    if max_volumes is not None and len(span.volumes) > max_volumes:
        raise ProRequired(f"{FEATURE_SPAN} ({len(span.volumes)} discs for this selection)")

    set_id = set_id or uuid.uuid4().hex
    count = len(span.volumes)
    path_volume = {item.path: volume.index for volume in span.volumes for item in volume.files}
    sibling_files = [
        {
            "path": item.disc_relative,
            "volume": path_volume[item.disc_relative],
            "bytes": item.size,
            "sha256": item.sha256,
        }
        for item in payload
    ]
    split_files = [
        {
            "path": split.disc_relative,
            "bytes": split.size,
            "sha256": split.sha256,
            "parts": [
                {
                    "part": part.part_index,
                    "path": part.disc_relative,
                    "volume": path_volume[part.disc_relative],
                    "bytes": part.size,
                    "sha256": part.sha256,
                }
                for part in split.parts
            ],
        }
        for split in splits
    ]
    if out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    roots: list[Path] = []
    for volume in span.volumes:
        label = f"STELE_{set_id[:8]}_{volume.index}"
        root = out_root / f"volume_{volume.index:02d}" / "STELE"
        root.mkdir(parents=True, exist_ok=True)
        present_owners: set[str] = set()
        for item in volume.files:
            payload_item = by_path[item.path]
            present_owners.add(payload_item.owner)
            target = root / payload_item.disc_relative
            target.parent.mkdir(parents=True, exist_ok=True)
            _copy_payload(payload_item, target)

        models_here = [model for model in models if model.safe_id in present_owners]
        runtimes_here = [pack for pack in runtimes if pack.pack_id in present_owners]
        docs = root / "DOCS"
        docs.mkdir(parents=True, exist_ok=True)
        for model in models_here:
            _copy_doc(model.spec_md, docs / f"{model.safe_id}_spec.md")
            _copy_doc(model.spec_pdf, docs / f"{model.safe_id}_spec.pdf")
            _copy_doc(model.howto_md, docs / f"{model.safe_id}_howto.md")
            _copy_doc(model.howto_pdf, docs / f"{model.safe_id}_howto.pdf")

        model_ids = [model.repo_id for model in models_here] or [pack.folder for pack in runtimes_here]
        commit_short = models_here[0].commit_sha[:12] if models_here else set_id[:12]
        prefixes = [by_path[item.path].sha256[:12] for item in volume.files][:12]
        summary = models_here[0].repo_id if models_here else "Runtime kit"
        if models_here:
            summary = f"{models_here[0].repo_id} @ {commit_short} · {models_here[0].profile}"
        write_disc_face(
            docs / "labels" / "disc_face.pdf",
            model_ids=model_ids or ["STELE"],
            commit_short=commit_short,
            when=created_utc[:10],
            volume=volume.index,
            count=count,
            studio_name=studio_name,
        )
        write_case_insert(
            docs / "labels" / "case_insert.pdf",
            model_ids=model_ids or ["STELE"],
            license_name=models_here[0].license_name if models_here else "vendor terms",
            summary=summary,
            checksum_prefixes=prefixes,
            studio_name=studio_name,
        )
        write_restore_script(root / "RESTORE.ps1")
        evidence_here = sorted(item.path for item in volume.files if item.path.startswith("EVIDENCE/"))
        (root / "README_FIRST.txt").write_text(
            _readme(volume.index, count, models_here, runtimes_here, splits, recovery_percent, label, evidence_here),
            encoding="utf-8",
            newline="\n",
        )
        (root / "VOLUME.json").write_text(
            json.dumps(
                {
                    "set_id": set_id,
                    "index": volume.index,
                    "count": count,
                    "label": label,
                    "files": sibling_files,
                    "split_files": split_files,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        if recovery_percent:
            create_recovery(root, label, recovery_percent, par2_exe, progress)
            tree_bytes = sum(path.stat().st_size for path in root.rglob("*") if path.is_file())
            if tree_bytes > capacity_bytes - HEADROOM_BYTES // 2:
                raise ValueError(
                    f"Volume {volume.index} with recovery data is {tree_bytes} bytes and does not fit the disc. "
                    "Lower the recovery percentage in Settings or use larger media."
                )

        hashed: list[tuple[str, str, int]] = []
        for path in sorted(root.rglob("*")):
            if path.is_file():
                relative = path.relative_to(root).as_posix()
                hashed.append((hash_file(path), relative, path.stat().st_size))
        write_checksum_file(root / "checksums.sha256", [(sha, rel) for sha, rel, _size in hashed])
        checksum_path = root / "checksums.sha256"
        hashed.append((hash_file(checksum_path), "checksums.sha256", checksum_path.stat().st_size))

        manifest = {
            "stele_version": __version__,
            "created_utc": created_utc,
            "set_id": set_id,
            "volume": {"index": volume.index, "count": count, "label": label},
            "disclaimer": DISCLAIMER,
            "models": [
                {
                    "repo_id": model.repo_id,
                    "revision": model.revision,
                    "commit": model.commit_sha,
                    "profile": model.profile,
                    "license": model.license_name,
                    "spec": f"DOCS/{model.safe_id}_spec.md",
                    "howto": f"DOCS/{model.safe_id}_howto.md",
                }
                for model in models_here
            ],
            "runtimes": [
                {
                    "pack_id": pack.pack_id,
                    "version": pack.version,
                    "filename": pack.filename,
                    "homepage": pack.homepage,
                }
                for pack in runtimes_here
            ],
            "files": [
                {"path": rel, "bytes": size, "sha256": sha, "volume": volume.index}
                for sha, rel, size in hashed
            ],
            "split_files": split_files,
            "evidence": evidence_here,
            "recovery": (
                {"format": "PAR2", "percent": recovery_percent, "index": f"{RECOVERY_DIR}/{label}.par2"}
                if recovery_percent
                else None
            ),
        }
        (root / "ARCHIVE_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        roots.append(root)
    return roots


def image_file_list(stele_root: Path) -> list[str]:
    """Relative paths IMAPI would add from this STELE directory."""
    return sorted(path.relative_to(stele_root).as_posix() for path in stele_root.rglob("*") if path.is_file())


def _copy_doc(source: Path | None, dest: Path) -> None:
    if source is None or not source.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)


def _readme(
    index: int,
    count: int,
    models: list[ModelDiscMeta],
    runtimes: list[RuntimeDiscMeta],
    splits: list[SplitFile] | None = None,
    recovery_percent: int = 0,
    label: str = "",
    evidence: list[str] | None = None,
) -> str:
    lines = [
        "STELE ARCHIVE",
        f"DISC {index} OF {count}",
        "",
        "Carve the model into stone.",
        "",
        "This disc is a permanent archive of Hugging Face model files and, when present, official runtime installers.",
        DISCLAIMER,
        "",
        "Restore (no network required):",
        "  powershell -ExecutionPolicy Bypass -File .\\RESTORE.ps1 -Destination D:\\Restored",
        "",
        "RESTORE.ps1 checks every copied file against checksums.sha256 and stops with an error on a mismatch.",
        "",
        "The full license file is on this disc, inside the model folder, when the repository published one.",
        "",
    ]
    if models:
        lines.append("Models on this volume:")
        for model in models:
            lines.append(f"  - {model.repo_id} @ {model.commit_sha}")
        lines.append("")
    if runtimes:
        lines.append("Runtimes on this volume (archived only, not installed):")
        for pack in runtimes:
            lines.append(f"  - {pack.folder} {pack.version}")
        lines.append("")
    if splits:
        lines.append("Files stored in parts across discs (larger than one disc):")
        for split in splits:
            lines.append(f"  - {split.disc_relative}: {len(split.parts)} parts, sha256 {split.sha256}")
        lines.append("")
        lines.append("Run RESTORE.ps1 from every disc in the set with the same -Destination.")
        lines.append("Once all parts are present it joins them and checks the whole-file SHA-256.")
        lines.append("Without PowerShell, join the parts in order: copy /b name.part001 + name.part002 name")
        lines.append("")
    if recovery_percent:
        lines.append(f"RECOVERY holds {recovery_percent}% PAR2 recovery data for this disc ({label}.par2).")
        lines.append("If a file cannot be read or does not match, RESTORE.ps1 repairs it when par2 is on PATH.")
        lines.append("Any PAR2 tool works (par2cmdline, MultiPar, QuickPar). After RESTORE.ps1 copies what it can read:")
        lines.append(f"  par2 r -p -B<Destination> <Destination>\\RECOVERY\\{label}.par2")
        lines.append("")
    if evidence:
        lines.append("EVIDENCE holds the Compliance Vault package for each model: provenance.json,")
        lines.append("the license files, a CycloneDX SBOM, and checksums, timestamped from the PC's own clock.")
        for path in evidence:
            lines.append(f"  - {path}")
        lines.append(NOT_LEGAL_ADVICE)
        lines.append("")
    lines.append("Read DOCS for the specification and the how-to-use guide.")
    lines.append("See VOLUME.json for the other discs in this set.")
    lines.append("")
    return "\n".join(lines)
