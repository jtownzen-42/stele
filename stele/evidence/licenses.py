"""The LICENSES folder: license files found with the model, plus a summary."""

from __future__ import annotations

import json
from pathlib import Path

from stele.evidence.provenance import EvidenceItem
from stele.models import DISCLAIMER, NOT_LEGAL_ADVICE

LICENSE_PREFIXES = ("license", "licence", "copying", "notice", "use_policy", "acceptable_use")
MAX_LICENSE_BYTES = 2_000_000


def license_files(item: EvidenceItem) -> list[tuple[str, Path]]:
    """(name inside LICENSES/, source path) for each license-like file in the vault item."""
    found: list[tuple[str, Path]] = []
    for path in sorted(item.vault_dir.rglob("*")):
        if not path.is_file() or not path.name.lower().startswith(LICENSE_PREFIXES):
            continue
        if path.stat().st_size > MAX_LICENSE_BYTES:
            continue
        found.append((path.relative_to(item.vault_dir).as_posix().replace("/", "__"), path))
    return found


def license_entries(item: EvidenceItem) -> list[tuple[str, bytes]]:
    """Every file for LICENSES/, as (name, content). LICENSE_SUMMARY.txt comes first."""
    files = license_files(item)
    entries: list[tuple[str, bytes]] = []
    permissions = (item.civitai or {}).get("permissions")
    if permissions:
        entries.append(
            ("civitai_permissions.json", (json.dumps(permissions, indent=2) + "\n").encode("utf-8"))
        )
    for name, path in files:
        entries.append((name, path.read_bytes()))
    names = [name for name, _ in entries]
    return [("LICENSE_SUMMARY.txt", summary_text(item, names).encode("utf-8"))] + entries


def summary_text(item: EvidenceItem, names: list[str]) -> str:
    lines = [
        f"License summary for {item.repo_id} @ {item.commit_sha}",
        "",
        f"License name recorded by Stele: {item.license_name}",
        f"License acknowledged in Stele (UTC, local clock): {item.license_ack_utc or 'not recorded'}",
        "",
    ]
    if names:
        lines.append("Files in this folder:")
        lines.extend(f"  - {name}" for name in names)
    else:
        lines.append("No license file was published with this model.")
        lines.append("The license name above comes from the model page metadata. Check the terms on the source page:")
        lines.append(f"  {item.page_url}")
    if item.license_name.strip().lower() in ("", "unknown", "other"):
        lines.append("")
        lines.append("WARNING: the license is unknown or non-standard. Read the source page before relying on it.")
    lines.extend(["", DISCLAIMER, NOT_LEGAL_ADVICE, ""])
    return "\n".join(lines)
