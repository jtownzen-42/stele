"""PAR2 recovery data on each volume, and repair during RESTORE.ps1."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from stele.burn.layout import build_disc_set
from stele.burn.par2 import RESERVE_BYTES, find_par2, payload_capacity
from stele.download.worker import hash_file, parse_checksum_file
from stele.models import HEADROOM_BYTES, PayloadFile

PAR2 = find_par2()
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")
needs_par2 = pytest.mark.skipif(PAR2 is None, reason="par2 is not installed")
needs_both = pytest.mark.skipif(PAR2 is None or POWERSHELL is None, reason="par2 or PowerShell is not installed")

BD25 = 25_025_314_816


def test_payload_capacity_reserves_room():
    usable = BD25 - HEADROOM_BYTES
    assert payload_capacity(usable, 0) == usable
    room = payload_capacity(usable, 5)
    assert room < usable * 0.96
    assert room * 1.05 + RESERVE_BYTES < usable


def test_recovery_needs_a_par2_program(tmp_path: Path):
    src = tmp_path / "w.bin"
    src.write_bytes(b"x" * 10)
    item = PayloadFile(src, "MODELS/a--b/c/w.bin", 10, hash_file(src), "a--b")
    with pytest.raises(ValueError, match="no par2 program"):
        build_disc_set(tmp_path / "out", [item], [], [], BD25, "2026-10-26T00:00:00Z", recovery_percent=5)


def _volume(tmp_path: Path) -> tuple[Path, bytes]:
    src = tmp_path / "src"
    src.mkdir()
    data = os.urandom(3_000_000)
    weights = src / "weights.gguf"
    weights.write_bytes(data)
    config = src / "config.json"
    config.write_text('{"a": 1}', encoding="utf-8")
    payload = [
        PayloadFile(weights, "MODELS/org--repo/abc/weights.gguf", len(data), hash_file(weights), "org--repo"),
        PayloadFile(config, "MODELS/org--repo/abc/config.json", config.stat().st_size, hash_file(config), "org--repo"),
    ]
    messages: list[str] = []
    roots = build_disc_set(
        tmp_path / "discs",
        payload,
        [],
        [],
        BD25,
        "2026-10-26T00:00:00Z",
        set_id="0123456789abcdef",
        recovery_percent=10,
        par2_exe=PAR2,
        progress=messages.append,
    )
    assert messages and "PAR2" in messages[0]
    return roots[0], data


@needs_par2
def test_volume_carries_recovery_set(tmp_path: Path):
    root, _ = _volume(tmp_path)
    index = root / "RECOVERY" / "STELE_01234567_1.par2"
    assert index.is_file()
    assert list((root / "RECOVERY").glob("STELE_01234567_1.vol*.par2"))
    names = {rel for _sha, rel in parse_checksum_file(root / "checksums.sha256")}
    assert "RECOVERY/STELE_01234567_1.par2" in names
    manifest = json.loads((root / "ARCHIVE_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["recovery"] == {"format": "PAR2", "percent": 10, "index": "RECOVERY/STELE_01234567_1.par2"}
    assert "PAR2 recovery data" in (root / "README_FIRST.txt").read_text(encoding="utf-8")
    verify = subprocess.run([str(PAR2), "v", "-q", f"-B{root}", str(index)], capture_output=True, text=True)
    assert verify.returncode == 0, verify.stdout + verify.stderr


def _damage(root: Path) -> None:
    target = root / "MODELS" / "org--repo" / "abc" / "weights.gguf"
    data = bytearray(target.read_bytes())
    data[200_000:240_000] = b"\0" * 40_000
    target.write_bytes(bytes(data))


def _restore(root: Path, dest: Path, path_env: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, PATH=path_env)
    return subprocess.run(
        [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(root / "RESTORE.ps1"), "-Destination", str(dest)],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )


@needs_both
def test_restore_repairs_damage_with_par2(tmp_path: Path):
    root, data = _volume(tmp_path)
    _damage(root)
    dest = tmp_path / "restored"
    result = _restore(root, dest, os.environ["PATH"])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Repaired: MODELS/org--repo/abc/weights.gguf" in result.stdout
    assert (dest / "MODELS" / "org--repo" / "abc" / "weights.gguf").read_bytes() == data


@needs_both
def test_restore_without_par2_explains_repair(tmp_path: Path):
    root, data = _volume(tmp_path)
    _damage(root)
    dest = tmp_path / "restored"
    shell_dir = str(Path(POWERSHELL).resolve().parent)
    result = _restore(root, dest, shell_dir)
    assert result.returncode == 1
    assert "carries PAR2 recovery data" in result.stdout
    # Repair by hand as the message says, then RESTORE.ps1 keeps the repaired file.
    index = dest / "RECOVERY" / "STELE_01234567_1.par2"
    subprocess.run([str(PAR2), "r", "-q", "-p", f"-B{dest}", str(index)], check=True, capture_output=True)
    again = _restore(root, dest, shell_dir)
    assert again.returncode == 0, again.stdout + again.stderr
    assert (dest / "MODELS" / "org--repo" / "abc" / "weights.gguf").read_bytes() == data
