"""Files larger than a disc are split into parts, and RESTORE.ps1 rejoins and verifies them."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from stele.burn.layout import build_disc_set, split_oversized
from stele.download.worker import hash_file, parse_checksum_file
from stele.models import HEADROOM_BYTES, PayloadFile

POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")
needs_powershell = pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is not installed")


def _file(root: Path, name: str, size: int, seed: int = 1) -> PayloadFile:
    path = root / name
    block = hashlib.sha256(str(seed).encode()).digest()
    path.write_bytes((block * (size // len(block) + 1))[:size])
    return PayloadFile(path, f"MODELS/org--repo/abc/{name}", size, hash_file(path), "org--repo")


def test_split_makes_equal_parts_that_fit(tmp_path: Path):
    big = _file(tmp_path, "big.gguf", 10_000)
    small = _file(tmp_path, "small.json", 100, seed=2)
    out, splits = split_oversized([big, small], usable=4_000)
    assert len(splits) == 1
    parts = splits[0].parts
    assert [p.disc_relative for p in parts] == [
        "MODELS/org--repo/abc/big.gguf.part001",
        "MODELS/org--repo/abc/big.gguf.part002",
        "MODELS/org--repo/abc/big.gguf.part003",
    ]
    assert all(p.size <= 4_000 for p in parts)
    assert sum(p.size for p in parts) == 10_000
    assert max(p.size for p in parts) - min(p.size for p in parts) < len(parts)
    data = big.source.read_bytes()
    for part in parts:
        assert part.sha256 == hashlib.sha256(data[part.offset : part.offset + part.size]).hexdigest()
    assert small in out


def test_parts_are_aligned_on_large_discs(tmp_path: Path):
    item = PayloadFile(tmp_path / "x", "MODELS/a/b/x", 40 * 10**9, "0" * 64, "a")
    usable = 25 * 10**9
    # Avoid hashing 40 GB: only check the sizing arithmetic.
    import stele.burn.layout as layout

    original = layout.hash_range
    layout.hash_range = lambda *_args: "0" * 64
    try:
        _out, splits = split_oversized([item], usable)
    finally:
        layout.hash_range = original
    sizes = [p.size for p in splits[0].parts]
    assert len(sizes) == 2
    assert sizes[0] % (1024 * 1024) == 0
    assert all(size <= usable for size in sizes)


def _build(tmp_path: Path, sizes: dict[str, int], per_disc: int) -> tuple[list[Path], dict[str, Path]]:
    src = tmp_path / "src"
    src.mkdir()
    payload = [_file(src, name, size, seed=i) for i, (name, size) in enumerate(sizes.items())]
    roots = build_disc_set(
        tmp_path / "discs",
        payload,
        [],
        [],
        capacity_bytes=HEADROOM_BYTES + per_disc,
        created_utc="2026-10-26T00:00:00Z",
        set_id="feedfacecafebeef",
    )
    return roots, {item.source.name: item.source for item in payload}


def test_split_set_records_parts_in_volume_and_manifest(tmp_path: Path):
    roots, _ = _build(tmp_path, {"big.gguf": 9_000, "small.json": 50}, per_disc=4_000)
    assert len(roots) == 3
    seen = set()
    for root in roots:
        volume = json.loads((root / "VOLUME.json").read_text(encoding="utf-8"))
        manifest = json.loads((root / "ARCHIVE_MANIFEST.json").read_text(encoding="utf-8"))
        assert volume["split_files"] == manifest["split_files"]
        split = volume["split_files"][0]
        assert split["path"] == "MODELS/org--repo/abc/big.gguf"
        assert {p["volume"] for p in split["parts"]} == {1, 2, 3}
        for _sha, rel in parse_checksum_file(root / "checksums.sha256"):
            if rel.startswith("MODELS/"):
                seen.add(rel)
        assert "parts across discs" in (root / "README_FIRST.txt").read_text(encoding="utf-8")
    assert "MODELS/org--repo/abc/big.gguf" not in seen
    assert "MODELS/org--repo/abc/big.gguf.part003" in seen


def _restore(root: Path, dest: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(root / "RESTORE.ps1"), "-Destination", str(dest)],
        capture_output=True,
        text=True,
        timeout=120,
    )


@needs_powershell
def test_restore_joins_parts_after_last_disc(tmp_path: Path):
    roots, sources = _build(tmp_path, {"big.gguf": 9_000, "small.json": 50}, per_disc=4_000)
    dest = tmp_path / "restored"
    joined = dest / "MODELS" / "org--repo" / "abc" / "big.gguf"
    for number, root in enumerate(roots, start=1):
        result = _restore(root, dest)
        assert result.returncode == 0, result.stdout + result.stderr
        if number < len(roots):
            assert "Insert disc" in result.stdout
            assert not joined.exists()
    assert "Restore complete" in result.stdout
    assert joined.read_bytes() == sources["big.gguf"].read_bytes()
    assert (dest / "MODELS" / "org--repo" / "abc" / "small.json").read_bytes() == sources["small.json"].read_bytes()
    assert not list(joined.parent.glob("*.part*"))
    # Running a disc again after the join must not undo it.
    again = _restore(roots[0], dest)
    assert again.returncode == 0, again.stdout + again.stderr
    assert "Already joined" in again.stdout


@needs_powershell
def test_restore_reports_damaged_file(tmp_path: Path):
    roots, _ = _build(tmp_path, {"weights.gguf": 2_000}, per_disc=1_000_000)
    target = roots[0] / "MODELS" / "org--repo" / "abc" / "weights.gguf"
    data = bytearray(target.read_bytes())
    data[100] ^= 0xFF
    target.write_bytes(bytes(data))
    result = _restore(roots[0], tmp_path / "restored")
    assert result.returncode == 1
    assert "MISMATCH: MODELS/org--repo/abc/weights.gguf" in result.stdout
    assert "RESTORE FAILED" in result.stdout


def test_part_name_collision_is_refused(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    big = _file(src, "weights", 9_000)
    clash = _file(src, "weights.part001", 10, seed=5)
    with pytest.raises(ValueError, match="weights.part001 already exists"):
        build_disc_set(tmp_path / "discs", [big, clash], [], [], HEADROOM_BYTES + 4_000, "2026-10-26T00:00:00Z")


@needs_powershell
def test_stale_destination_file_is_not_taken_as_joined(tmp_path: Path):
    roots, sources = _build(tmp_path, {"big.gguf": 9_000, "small.json": 50}, per_disc=4_000)
    dest = tmp_path / "restored"
    stale = dest / "MODELS" / "org--repo" / "abc" / "big.gguf"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"truncated")
    # Disc 3 holds one part; the stale file must not be reported as joined.
    result = _restore(roots[-1], dest)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Already joined" not in result.stdout
    assert "Insert disc" in result.stdout
    for root in roots:
        result = _restore(root, dest)
    assert "Restore complete" in result.stdout
    assert stale.read_bytes() == sources["big.gguf"].read_bytes()
