"""PAR2 recovery data for each volume.

Stele runs an external, standard PAR2 tool (par2cmdline or par2cmdline-turbo)
so the recovery files can be used years later with any PAR2 program,
without Stele. Each volume gets its own set under RECOVERY/, covering the
MODELS, RUNTIME, and DOCS folders on that volume. A scratched disc that loses
a few blocks can then be repaired after RESTORE.ps1 copies what it can read.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

RECOVERY_DIR = "RECOVERY"
PROTECTED_DIRS = ("MODELS", "RUNTIME", "DOCS")
DEFAULT_PERCENT = 5
MAX_PERCENT = 30
# PAR2 rounds every file up to whole blocks and adds packet headers, so the
# recovery set comes out a little larger than the nominal percentage.
OVERHEAD_FACTOR = 1.15
RESERVE_BYTES = 64 * 1024 * 1024


class Par2Error(RuntimeError):
    pass


def find_par2(configured: str | None = None) -> Path | None:
    """Return a par2 executable: the configured path, the bundled copy, or PATH."""
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured))
    bundle = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    for base in (bundle, Path(sys.executable).parent, Path(__file__).resolve().parents[2]):
        candidates.append(base / "tools" / "par2.exe")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    found = shutil.which("par2") or shutil.which("par2.exe")
    return Path(found) if found else None


def payload_capacity(usable: int, percent: int) -> int:
    """Bytes of payload per volume that leave room for `percent` recovery data."""
    if percent <= 0:
        return usable
    room = usable - RESERVE_BYTES
    if room <= 0:
        return 0
    return int(room / (1 + OVERHEAD_FACTOR * percent / 100))


def create_recovery(
    stele_root: Path,
    name: str,
    percent: int,
    exe: Path,
    progress: Callable[[str], None] | None = None,
) -> list[Path]:
    """Write RECOVERY/<name>.par2 (+ .vol files) for this volume's payload."""
    if not 0 < percent <= MAX_PERCENT:
        raise ValueError(f"Recovery percentage must be between 1 and {MAX_PERCENT}.")
    root = stele_root.resolve()
    targets = [str(root / folder) for folder in PROTECTED_DIRS if (root / folder).is_dir()]
    if not targets:
        return []
    out_dir = root / RECOVERY_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    index = out_dir / f"{name}.par2"
    cmd = [str(exe), "c", "-q", f"-r{percent}", "-n1", "-R", f"-B{root}", str(index), *targets]
    if progress:
        progress(f"Creating {percent}% PAR2 recovery data for {name}. Large volumes take several minutes.")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()[-1:] or ["no output"]
        raise Par2Error(f"par2 could not create recovery data (exit {result.returncode}): {detail[0]}")
    return sorted(out_dir.glob(f"{name}*.par2"))
