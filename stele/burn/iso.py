"""Export the same STELE tree IMAPI would burn, as a UDF image file."""

from __future__ import annotations

from pathlib import Path

from stele.burn.imapi import ImapiError, build_udf_stream, save_stream


def export_iso(stele_root: Path, dest: Path, volume_name: str) -> Path:
    """Write dest as a UDF image. Raises ImapiError; the vault is not modified."""
    if not stele_root.exists():
        raise ImapiError("There is no disc tree to export.")
    stream = build_udf_stream(stele_root, volume_name)
    save_stream(stream, dest)
    return dest
