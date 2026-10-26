"""Build Stele standalone executable for Windows using PyInstaller."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def build() -> int:
    root = Path(__file__).resolve().parent
    spec = root / "stele.spec"
    dist_exe = root / "dist" / "Stele" / "Stele.exe"

    sys.path.insert(0, str(root / "tools"))
    from fetch_par2 import fetch

    fetch()

    print("=== Building Stele with PyInstaller ===")
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", str(spec)]
    res = subprocess.run(cmd, cwd=root)
    if res.returncode != 0:
        print(f"Error: PyInstaller build failed with exit code {res.returncode}")
        return res.returncode

    if not dist_exe.exists():
        print(f"Error: Expected output binary not found: {dist_exe}")
        return 1

    size_mb = dist_exe.stat().st_size / (1024 * 1024)
    print(f"Build successful: {dist_exe} ({size_mb:.2f} MB)")

    manifest_dest = root / "dist" / "Stele" / "_internal" / "stele" / "runtime" / "manifest.json"
    alt_manifest = root / "dist" / "Stele" / "stele" / "runtime" / "manifest.json"
    if manifest_dest.exists() or alt_manifest.exists():
        print("Asset verification: runtime manifest.json included.")
    else:
        print("Warning: runtime manifest.json not found in expected dist locations.")

    print("Running binary smoke test...")
    smoke = subprocess.run([str(dist_exe), "--smoke"], capture_output=True, text=True, timeout=15)
    print("Smoke output:", smoke.stdout.strip())
    if smoke.returncode != 0:
        print(f"Smoke test failed with code {smoke.returncode}")
        if smoke.stderr:
            print("Stderr:", smoke.stderr)
        return smoke.returncode

    print("=== Stele Standalone Packaging Complete ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
