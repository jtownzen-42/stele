"""Build the canonical STELE tree for one volume or a spanned set.

Staging, the vault's model folders, an ISO, and a burned disc all use the
same relative layout. This module is what makes them match.
"""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from stele import __version__
from stele.burn.span import plan_volumes
from stele.docs.labels import write_case_insert, write_disc_face
from stele.download.worker import hash_file, write_checksum_file
from stele.models import (
    DISCLAIMER,
    ModelDiscMeta,
    PayloadFile,
    RuntimeDiscMeta,
    SpanFile,
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


def build_disc_set(
    out_root: Path,
    payload: list[PayloadFile],
    models: list[ModelDiscMeta],
    runtimes: list[RuntimeDiscMeta],
    capacity_bytes: int,
    created_utc: str,
    set_id: str | None = None,
    studio_name: str = "STELE",
) -> list[Path]:
    """Write `volume_XX/STELE/` trees. Returns each STELE directory.

    Raises ValueError when a file does not fit the media. Nothing is split.
    """
    if not payload:
        raise ValueError("Nothing selected to archive.")
    by_path = {item.disc_relative: item for item in payload}
    span = plan_volumes(
        [SpanFile(item.disc_relative, item.size) for item in payload],
        capacity_bytes,
    )
    if span.error:
        raise ValueError(span.error)
    if not span.volumes:
        raise ValueError("Nothing selected to archive.")

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
            shutil.copy2(payload_item.source, target)

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
        (root / "README_FIRST.txt").write_text(
            _readme(volume.index, count, models_here, runtimes_here),
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
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
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


def _readme(index: int, count: int, models: list[ModelDiscMeta], runtimes: list[RuntimeDiscMeta]) -> str:
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
    lines.append("Read DOCS for the specification and the how-to-use guide.")
    lines.append("See VOLUME.json for the other discs in this set.")
    lines.append("")
    return "\n".join(lines)
