"""Windows IMAPI2: list drives, build a UDF image, burn, verify.

Dry-run is a real mode. It records that no disc was written. ISO export uses
the same image builder and does not require a drive.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from stele.download.worker import hash_file, parse_checksum_file
from stele.models import (
    DVD_M_DISC_NOTE,
    FULL_VERIFY_LIMIT,
    MSG_CANCEL_UNAVAILABLE,
    MSG_EMPTY_TRAY,
    MSG_NO_DRIVE,
    SAMPLE_LIMIT,
    msg_imapi,
)

log = logging.getLogger("stele.burn")

FSI_UDF = 4
# 2.60 is not implemented on every Windows build. 2.50 still allows files over 4 GB.
_UDF_PREFERENCE = (0x260, 0x250, 0x201, 0x200)

# A useful subset of IMAPI_MEDIA_PHYSICAL_TYPE. Unknown numbers are shown raw.
_MEDIA = {
    0: "Unknown",
    1: "CD-ROM",
    2: "CD-R",
    3: "CD-RW",
    4: "DVD-ROM",
    5: "DVD-RAM",
    6: "DVD+R",
    7: "DVD+RW",
    8: "DVD+R DL",
    9: "DVD-R",
    10: "DVD-RW",
    11: "DVD-R DL",
    12: "DVD+RW DL",
    17: "BD-ROM",
    18: "BD-R",
    19: "BD-RE",
    20: "BD-R dual",
    21: "BD-RE dual",
}


class ImapiError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _create(progid: str):
    import comtypes.client

    return comtypes.client.CreateObject(progid)


def probe() -> str | None:
    """None when IMAPI2 can be created. Otherwise the COM error text."""
    try:
        _create("IMAPI2FS.MsftFileSystemImage")
    except Exception as exc:
        return str(exc)
    return None


def media_name(value) -> str:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return str(value or "Unknown")
    return _MEDIA.get(number, f"Media type {number}")


def enumerate_recorders() -> list[dict]:
    """Return one dict per recorder. An empty list means no drive, not a crash."""
    try:
        master = _create("IMAPI2.MsftDiscMaster2")
    except Exception as exc:
        raise ImapiError(msg_imapi(str(exc))) from exc
    found: list[dict] = []
    try:
        count = int(master.Count)
    except Exception as exc:
        raise ImapiError(msg_imapi(str(exc))) from exc
    for index in range(count):
        unique = str(master.Item(index))
        entry = {
            "id": unique,
            "name": unique,
            "media_type": "",
            "media_raw": None,
            "free_bytes": None,
            "blank": None,
            "note": MSG_EMPTY_TRAY,
            "warning": "",
        }
        try:
            recorder = _create("IMAPI2.MsftDiscRecorder2")
            recorder.InitializeDiscRecorder(unique)
            vendor = str(getattr(recorder, "VendorId", "") or "").strip()
            product = str(getattr(recorder, "ProductId", "") or "").strip()
            entry["name"] = " ".join(part for part in (vendor, product) if part) or unique
            fmt = _create("IMAPI2.MsftDiscFormat2Data")
            fmt.Recorder = recorder
            raw = int(fmt.CurrentPhysicalMediaType)
            entry["media_raw"] = raw
            entry["media_type"] = media_name(raw)
            entry["free_bytes"] = int(fmt.FreeSectorsOnMedia) * 2048
            entry["blank"] = bool(fmt.MediaHeuristicallyBlank)
            entry["note"] = ""
            if "DVD" in entry["media_type"]:
                entry["warning"] = DVD_M_DISC_NOTE
            elif "BD" in entry["media_type"]:
                entry["warning"] = "BD M-DISC is written as a standard BD-R. " + DVD_M_DISC_NOTE
        except Exception as exc:
            text = str(exc)
            entry["note"] = MSG_EMPTY_TRAY if text else MSG_EMPTY_TRAY
            entry["warning"] = DVD_M_DISC_NOTE
            log.info("recorder %s has no usable media: %s", unique, text)
        found.append(entry)
    return found


def choose_udf_revision(image) -> int:
    try:
        supported = {int(value) for value in list(image.UDFRevisionsSupported)}
    except Exception:
        supported = set()
    for revision in _UDF_PREFERENCE:
        if revision in supported:
            return revision
    if supported:
        return max(supported)
    return 0x250


def build_udf_stream(stele_root: Path, volume_name: str, recorder_id: str | None = None):
    """Create an IMAPI image stream whose root contains the STELE directory."""
    try:
        image = _create("IMAPI2FS.MsftFileSystemImage")
        recorder = None
        if recorder_id:
            recorder = _create("IMAPI2.MsftDiscRecorder2")
            recorder.InitializeDiscRecorder(recorder_id)
            image.ChooseImageDefaults(recorder)
        image.FileSystemsToCreate = FSI_UDF
        image.UDFRevision = choose_udf_revision(image)
        image.VolumeName = (volume_name or "STELE")[:32]
        image.Root.AddTree(str(stele_root), True)
        result = image.CreateResultImage()
        return result.ImageStream
    except ImapiError:
        raise
    except Exception as exc:
        raise ImapiError(msg_imapi(str(exc))) from exc


def save_stream(stream, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    try:
        _save_by_read(stream, dest)
    except Exception as exc:
        raise ImapiError(msg_imapi(str(exc))) from exc
    if not dest.exists() or dest.stat().st_size == 0:
        raise ImapiError(msg_imapi("IMAPI produced an empty image."))


def _save_by_read(stream, dest: Path) -> None:
    """Copy an IMAPI IStream. comtypes exposes RemoteRead, not Read."""
    total = int(stream.Stat(1).cbSize)
    written = 0
    with dest.open("wb") as handle:
        while written < total:
            chunk = min(1024 * 1024, total - written)
            buffer, count = stream.RemoteRead(int(chunk))
            count = int(count)
            if count <= 0:
                break
            handle.write(bytes(buffer)[:count])
            written += count


def set_conservative_speed(fmt, requested_x: int) -> str:
    """Ask for 2x–4x. If the recorder rejects it, keep its own speed and say so."""
    requested_x = min(4, max(2, int(requested_x)))
    try:
        speeds = list(fmt.SupportedWriteSpeeds)
    except Exception:
        return "recorder default (supported speeds unavailable)"
    if not speeds:
        return "recorder default"
    # Supported speeds come back as sectors/second or descriptors. Use the slowest
    # numeric value so a long archive is not written at the drive's maximum.
    numeric = []
    for item in speeds:
        if isinstance(item, int):
            numeric.append(item)
        else:
            for attr in ("WriteSpeed", "value"):
                if hasattr(item, attr):
                    numeric.append(int(getattr(item, attr)))
                    break
    if not numeric:
        return "recorder default"
    numeric.sort()
    # 1x DVD is about 1385 KB/s, which IMAPI reports as sectors/sec. Without a
    # reliable unit, pick the slowest supported speed and log the request.
    chosen = numeric[0]
    try:
        fmt.SetWriteSpeed(int(chosen), False)
        return f"conservative speed requested ({requested_x}x). Recorder accepted {chosen}."
    except Exception as exc:
        return f"recorder kept its own speed ({exc})."


def burn_directory(
    recorder_id: str,
    stele_root: Path,
    volume_name: str,
    *,
    speed_x: int = 4,
    close_disc: bool = True,
) -> dict:
    """Write one closed UDF disc. The vault is not touched here."""
    if not recorder_id:
        raise ImapiError(MSG_NO_DRIVE)
    try:
        recorder = _create("IMAPI2.MsftDiscRecorder2")
        recorder.InitializeDiscRecorder(recorder_id)
        fmt = _create("IMAPI2.MsftDiscFormat2Data")
        fmt.Recorder = recorder
        fmt.ClientName = "Stele"
        if not bool(fmt.MediaHeuristicallyBlank):
            raise ImapiError("The disc is not blank. Insert a blank M-DISC.")
        speed_note = set_conservative_speed(fmt, speed_x)
        fmt.ForceMediaToBeClosed = bool(close_disc)
        image = _create("IMAPI2FS.MsftFileSystemImage")
        image.ChooseImageDefaults(recorder)
        image.FileSystemsToCreate = FSI_UDF
        image.UDFRevision = choose_udf_revision(image)
        image.VolumeName = (volume_name or "STELE")[:32]
        image.Root.AddTree(str(stele_root), True)
        stream = image.CreateResultImage().ImageStream
        cancel_note = MSG_CANCEL_UNAVAILABLE
        if hasattr(fmt, "CancelWrite"):
            cancel_note = ""
        fmt.Write(stream)
        volume_paths: list[str] = []
        try:
            volume_paths = [str(path) for path in list(recorder.VolumePathNames)]
        except Exception:
            volume_paths = []
        stele_on_disc = find_disc_stele_root(
            volume_label=volume_name,
            volume_paths=volume_paths,
            recorder_id=recorder_id,
        )
        return {
            "ok": True,
            "speed_note": speed_note,
            "cancel_note": cancel_note,
            "drive_name": " ".join(
                part
                for part in (
                    str(getattr(recorder, "VendorId", "") or "").strip(),
                    str(getattr(recorder, "ProductId", "") or "").strip(),
                )
                if part
            ),
            "media_type": media_name(fmt.CurrentPhysicalMediaType),
            "volume_paths": volume_paths,
            "stele_root": None if stele_on_disc is None else str(stele_on_disc),
        }
    except ImapiError:
        raise
    except Exception as exc:
        raise ImapiError(msg_imapi(str(exc))) from exc


def _volume_has_stele(root: Path) -> Path | None:
    """Return the STELE folder under root when it looks like our layout."""
    stele = root / "STELE"
    if stele.is_dir() and (stele / "checksums.sha256").is_file():
        return stele
    if root.name.upper() == "STELE" and (root / "checksums.sha256").is_file():
        return root
    return None


def _iter_windows_volume_names() -> list[str]:
    """Enumerate Volume{guid} names via FindFirstVolumeW. Empty on non-Windows."""
    if os.name != "nt":
        return []
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    FindFirstVolumeW = kernel32.FindFirstVolumeW
    FindFirstVolumeW.argtypes = [wintypes.LPWSTR, wintypes.DWORD]
    FindFirstVolumeW.restype = wintypes.HANDLE
    FindNextVolumeW = kernel32.FindNextVolumeW
    FindNextVolumeW.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD]
    FindNextVolumeW.restype = wintypes.BOOL
    FindVolumeClose = kernel32.FindVolumeClose
    FindVolumeClose.argtypes = [wintypes.HANDLE]
    FindVolumeClose.restype = wintypes.BOOL

    buf = ctypes.create_unicode_buffer(1024)
    handle = FindFirstVolumeW(buf, len(buf))
    invalid = ctypes.c_void_p(-1).value
    if handle == invalid or handle is None:
        return []
    names: list[str] = []
    try:
        while True:
            names.append(buf.value)
            if not FindNextVolumeW(handle, buf, len(buf)):
                break
    finally:
        FindVolumeClose(handle)
    return names


def _volume_label(volume_name: str) -> str:
    """Read the filesystem label for a Volume{guid} name. Empty on failure."""
    if os.name != "nt":
        return ""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    GetVolumeInformationW = kernel32.GetVolumeInformationW
    GetVolumeInformationW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    GetVolumeInformationW.restype = wintypes.BOOL
    label_buf = ctypes.create_unicode_buffer(261)
    fs_buf = ctypes.create_unicode_buffer(261)
    serial = wintypes.DWORD()
    max_comp = wintypes.DWORD()
    flags = wintypes.DWORD()
    name = volume_name if volume_name.endswith("\\") else volume_name + "\\"
    ok = GetVolumeInformationW(
        name,
        label_buf,
        len(label_buf),
        ctypes.byref(serial),
        ctypes.byref(max_comp),
        ctypes.byref(flags),
        fs_buf,
        len(fs_buf),
    )
    if not ok:
        return ""
    return label_buf.value or ""


def _recorder_volume_paths(recorder_id: str | None) -> list[str]:
    if not recorder_id:
        return []
    try:
        recorder = _create("IMAPI2.MsftDiscRecorder2")
        recorder.InitializeDiscRecorder(recorder_id)
        return [str(path) for path in list(recorder.VolumePathNames)]
    except Exception as exc:
        log.info("recorder volume paths unavailable: %s", exc)
        return []


def find_disc_stele_root(
    *,
    volume_label: str | None = None,
    volume_paths: list[str] | None = None,
    recorder_id: str | None = None,
    settle_seconds: float = 8.0,
    poll_interval: float = 0.5,
) -> Path | None:
    """Locate the on-disc STELE folder after a burn.

    Windows often mounts a closed UDF disc with a volume GUID and no drive
    letter. IMAPI VolumePathNames is then empty even though the tree is
    readable. Prefer letter paths when present, then match the volume label,
    then any unique volume that hosts our layout.
    """
    import time

    deadline = time.monotonic() + max(0.0, float(settle_seconds))
    wanted = (volume_label or "").strip().upper()
    seed_paths = list(volume_paths or [])

    while True:
        candidates: list[Path] = []
        paths: list[str] = []
        seen: set[str] = set()
        for path in [*seed_paths, *_recorder_volume_paths(recorder_id)]:
            key = path.rstrip("\\/")
            if key in seen:
                continue
            seen.add(key)
            paths.append(path)

        for path in paths:
            found = _volume_has_stele(Path(path))
            if found is not None:
                return found

        labeled: Path | None = None
        for volume_name in _iter_windows_volume_names():
            stele = _volume_has_stele(Path(volume_name))
            if stele is None:
                continue
            label = _volume_label(volume_name)
            if wanted and label.upper() == wanted:
                log.info("found STELE on labeled volume %s (%s)", label, volume_name)
                labeled = stele
                break
            candidates.append(stele)
        if labeled is not None:
            return labeled

        if time.monotonic() >= deadline:
            if len(candidates) == 1:
                log.info("found unique STELE volume without label match: %s", candidates[0])
                return candidates[0]
            if candidates:
                log.info(
                    "multiple STELE volumes visible (%s); no label match for %s",
                    len(candidates),
                    volume_label,
                )
            return None
        time.sleep(poll_interval)


def eject(recorder_id: str) -> None:
    try:
        recorder = _create("IMAPI2.MsftDiscRecorder2")
        recorder.InitializeDiscRecorder(recorder_id)
        recorder.EjectMedia()
    except Exception as exc:
        log.info("eject failed: %s", exc)


def verify_volume(disc_root: Path, source_root: Path | None = None) -> tuple[str, str]:
    """Return (status, note). status is full, sampled, or failed."""
    checksums = disc_root / "checksums.sha256"
    if not checksums.exists():
        return "failed", "checksums.sha256 is missing on the volume."
    rows = parse_checksum_file(checksums)
    present: list[tuple[str, str, Path, int]] = []
    total = 0
    for sha, relative in rows:
        path = disc_root / relative
        if not path.exists():
            return "failed", f"Missing on the volume: {relative}"
        size = path.stat().st_size
        total += size
        present.append((sha, relative, path, size))
    mode = "full" if total <= FULL_VERIFY_LIMIT else "sampled"
    if mode == "full":
        for sha, relative, path, _size in present:
            if hash_file(path) != sha:
                return "failed", f"Checksum mismatch: {relative}"
        return "full", "Full verify: every file was hashed and matched checksums.sha256."
    for sha, relative, path, size in present:
        if size < SAMPLE_LIMIT:
            if hash_file(path) != sha:
                return "failed", f"Checksum mismatch: {relative}"
            continue
        source = None if source_root is None else source_root / relative
        if source is None or not source.exists():
            return "failed", f"No source to sample against: {relative}"
        if not _samples_match(path, source):
            return "failed", f"Sample mismatch: {relative}"
    return (
        "sampled",
        "Sampled verify: every file under 64 MB was hashed. "
        "Each larger file was compared at the head, middle, and tail against the staged tree.",
    )


def _samples_match(disc: Path, source: Path) -> bool:
    size = disc.stat().st_size
    if source.stat().st_size != size:
        return False
    window = SAMPLE_LIMIT
    starts = sorted({0, max(0, size // 2 - window // 2), max(0, size - window)})
    with disc.open("rb") as left, source.open("rb") as right:
        for start in starts:
            left.seek(start)
            right.seek(start)
            if left.read(window) != right.read(window):
                return False
    return True
