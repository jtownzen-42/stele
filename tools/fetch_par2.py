"""Download the pinned par2cmdline-turbo Windows build into tools/.

build_stele.py runs this before PyInstaller so stele.spec can bundle
tools/par2.exe and its GPL-2.0 license. The download is checked against a
pinned SHA-256; a mismatch stops the build.

par2cmdline-turbo is GPL-2.0. Stele runs it as a separate program. The
corresponding source is the tagged release linked in THIRD_PARTY_NOTICES.txt.
"""

from __future__ import annotations

import hashlib
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

VERSION = "1.5.0"
ZIP_URL = (
    "https://github.com/animetosho/par2cmdline-turbo/releases/download/"
    f"v{VERSION}/par2cmdline-turbo-{VERSION}-win-x64.zip"
)
ZIP_SHA256 = "873a6f25822415f432224cc6f734407ca2732004184e002960fc68ed1e99c5d7"
EXE_SHA256 = "36ce11d92c895a552485ba8cb1ad4b92ca62a00333f1aa6308daafbc371e69e9"
LICENSE_URL = f"https://raw.githubusercontent.com/animetosho/par2cmdline-turbo/v{VERSION}/COPYING"
LICENSE_SHA256 = "edaef632cbb643e4e7a221717a6c441a4c1a7c918e6e4d56debc3d8739b233f6"

TOOLS = Path(__file__).resolve().parent
EXE = TOOLS / "par2.exe"
LICENSE = TOOLS / "par2-COPYING.txt"


def _get(url: str, sha256: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 - pinned https URL
        data = response.read()
    actual = hashlib.sha256(data).hexdigest()
    if actual != sha256:
        raise SystemExit(f"SHA-256 mismatch for {url}: expected {sha256}, got {actual}")
    return data


def _matches(path: Path, sha256: str) -> bool:
    return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == sha256


def fetch(force: bool = False) -> Path:
    # A cached copy is reused only when it is byte-for-byte the pinned release.
    if not force and _matches(EXE, EXE_SHA256) and _matches(LICENSE, LICENSE_SHA256):
        print(f"par2: {EXE} already present and verified")
        return EXE
    archive = zipfile.ZipFile(io.BytesIO(_get(ZIP_URL, ZIP_SHA256)))
    exe = archive.read("par2.exe")
    if hashlib.sha256(exe).hexdigest() != EXE_SHA256:
        raise SystemExit("SHA-256 mismatch for par2.exe inside the pinned archive")
    EXE.write_bytes(exe)
    LICENSE.write_bytes(_get(LICENSE_URL, LICENSE_SHA256))
    print(f"par2: fetched par2cmdline-turbo {VERSION} into {TOOLS}")
    return EXE


if __name__ == "__main__":
    fetch(force="--force" in sys.argv)
