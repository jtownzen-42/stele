"""One-file-at-a-time transfers.

snapshot_download is never called. max_workers is not used. Each file is a
single HTTP Range stream so pause and relaunch can continue the partial.
"""

from __future__ import annotations

import hashlib
import logging
import re
import shutil
import threading
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urljoin, urlparse

from stele.models import MSG_AUTH, MSG_DISK

log = logging.getLogger("stele.download")

_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
CHUNK = 1024 * 1024
NETWORK_TRIES = 5


class TransferError(Exception):
    def __init__(self, message: str, kind: str = "network") -> None:
        super().__init__(message)
        self.kind = kind


class DiskFull(TransferError):
    def __init__(self) -> None:
        super().__init__(MSG_DISK, kind="disk")


class AuthRefused(TransferError):
    def __init__(self) -> None:
        super().__init__(MSG_AUTH, kind="auth")


class Cancelled(TransferError):
    def __init__(self, how: str) -> None:
        super().__init__(how, kind=how)


def partial_path(dest: Path) -> Path:
    """Sibling used for Range resume. Not Path.with_suffix: that drops the real extension."""
    return Path(str(dest) + ".partial")


def transfer_stop_reason(job_status: str | None, app_stopping: bool) -> str | None:
    """Why the current transfer should stop, or None to keep reading.

    Pause wins over application shutdown. Shutdown must not cancel the job:
    quit-during-pause has to leave it resumable.
    """
    if job_status is None:
        return "cancelled"
    if job_status == "paused":
        return "paused"
    if job_status == "cancelled":
        return "cancelled"
    if app_stopping:
        return "shutdown"
    return None


def hash_file(path: Path, chunk: int = CHUNK) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def evaluate_hash(expected: str | None, actual: str, attempts_already: int) -> str:
    """Return done, retry, or failed.

    attempts_already is the number of mismatches already recorded before this
    comparison. One mismatch retries; the second marks the file failed.
    A missing or non-sha256 etag cannot be compared and counts as done.
    """
    token = (expected or "").strip().strip('"').lower()
    if not _SHA256.fullmatch(token):
        return "done"
    if token == actual.lower():
        return "done"
    if attempts_already >= 1:
        return "failed"
    return "retry"


def format_checksum_line(sha256: str, relative: str) -> str:
    rel = relative.replace("\\", "/")
    return f"{sha256}  {rel}\n"


def write_checksum_file(path: Path, rows: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(format_checksum_line(sha, rel) for sha, rel in rows)
    path.write_text(text, encoding="utf-8", newline="\n")


def parse_checksum_file(path: Path) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        sha, _, rel = line.partition("  ")
        if rel:
            rows.append((sha.strip(), rel.strip()))
    return rows


def host_allowed(url: str, allow: list[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if urlparse(url).scheme != "https" or not host:
        return False
    for item in allow:
        permitted = item.lower().lstrip(".")
        if host == permitted or host.endswith("." + permitted):
            return True
    return False


def assert_url_allowed(url: str, allow: list[str]) -> None:
    if not host_allowed(url, allow):
        host = urlparse(url).hostname or url
        raise TransferError(f"Host {host} is not an official source for this pack.", kind="source")


def _free_bytes(path: Path) -> int:
    target = path if path.exists() else path.parent
    target.mkdir(parents=True, exist_ok=True)
    return shutil.disk_usage(target).free


def _ensure_space(path: Path, needed: int | None) -> None:
    if needed is None or needed <= 0:
        return
    try:
        free = _free_bytes(path)
    except OSError as exc:
        raise DiskFull() from exc
    if free < needed:
        raise DiskFull()


ProgressCb = Callable[[int, int | None], None]
StopCb = Callable[[], str | None]


def _is_disk_full(exc: OSError) -> bool:
    if exc.errno == 28:
        return True
    winerror = getattr(exc, "winerror", None)
    return winerror in (112, 39)


def stream_range(
    url: str,
    dest: Path,
    *,
    headers: dict[str, str] | None = None,
    allow_hosts: list[str] | None = None,
    expected_size: int | None = None,
    progress: ProgressCb | None = None,
    stop_check: StopCb | None = None,
) -> int:
    """Download one URL to dest, resuming a sibling .partial. One connection."""
    import httpx

    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = partial_path(dest)
    existing = partial.stat().st_size if partial.exists() else 0
    if dest.exists() and not partial.exists():
        size = dest.stat().st_size
        if progress:
            progress(size, size)
        return size

    request_headers = dict(headers or {})
    if existing:
        request_headers["Range"] = f"bytes={existing}-"
    if allow_hosts is not None:
        assert_url_allowed(url, allow_hosts)
    _ensure_space(dest, None if expected_size is None else max(0, expected_size - existing))

    # A stalled socket has to notice Pause or quit. 30s is the longest a chunk may block.
    timeout = httpx.Timeout(30.0, read=30.0)
    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        current = url
        response = None
        for _hop in range(6):
            if allow_hosts is not None:
                assert_url_allowed(current, allow_hosts)
            response = client.send(client.build_request("GET", current, headers=request_headers), stream=True)
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("location")
                response.close()
                response = None
                if not location:
                    raise TransferError("Redirect had no location.")
                current = urljoin(current, location)
                continue
            break
        if response is None:
            raise TransferError("Too many redirects.")
        try:
            if response.status_code in (401, 403):
                raise AuthRefused()
            if response.status_code == 416:
                response.close()
                if partial.exists():
                    partial.replace(dest)
                size = dest.stat().st_size if dest.exists() else existing
                if progress:
                    progress(size, size)
                return size
            if response.status_code not in (200, 206):
                raise TransferError(f"Download failed with HTTP {response.status_code}.")
            resume = existing > 0 and response.status_code == 206
            if not resume and partial.exists():
                partial.unlink()
                existing = 0
            written = existing if resume else 0
            total = expected_size
            content_range = response.headers.get("content-range")
            if content_range and "/" in content_range and content_range.rsplit("/", 1)[-1].isdigit():
                total = int(content_range.rsplit("/", 1)[-1])
            elif response.status_code == 200 and response.headers.get("content-length", "").isdigit():
                total = int(response.headers["content-length"])
            with partial.open("ab" if resume else "wb") as handle:
                for block in response.iter_bytes(CHUNK):
                    if stop_check:
                        how = stop_check()
                        if how:
                            handle.flush()
                            raise Cancelled(how)
                    if not block:
                        continue
                    try:
                        handle.write(block)
                    except OSError as exc:
                        if _is_disk_full(exc):
                            raise DiskFull() from exc
                        raise
                    written += len(block)
                    if progress:
                        progress(written, total)
            partial.replace(dest)
            return dest.stat().st_size
        finally:
            response.close()


def _hf_resolve(repo_id: str, filename: str, revision: str, token: str | None):
    from huggingface_hub import get_hf_file_metadata, hf_hub_url

    url = hf_hub_url(repo_id=repo_id, filename=filename, revision=revision)
    try:
        from huggingface_hub.utils import build_hf_headers
    except ImportError:  # older hub layouts
        from huggingface_hub import build_hf_headers  # type: ignore
    headers = build_hf_headers(token=token)
    meta = get_hf_file_metadata(url, token=token)
    location = getattr(meta, "location", None) or url
    size = getattr(meta, "size", None)
    etag = getattr(meta, "etag", None)
    return location, headers, size, etag


def download_hub_file(
    repo_id: str,
    filename: str,
    revision: str,
    dest: Path,
    token: str | None,
    *,
    progress: ProgressCb | None = None,
    stop_check: StopCb | None = None,
    expected_size: int | None = None,
) -> tuple[int, str | None]:
    """Download one Hub file. Returns (size, etag)."""
    location, headers, size, etag = _hf_resolve(repo_id, filename, revision, token)
    # Official Hugging Face CDN redirects are part of the Hub, not a runtime mirror.
    allow = [
        "huggingface.co",
        "hf.co",
        "cdn-lfs.huggingface.co",
        "cdn-lfs-us-1.huggingface.co",
        "cdn-lfs-eu-1.huggingface.co",
        "cas-bridge.xethub.hf.co",
        "transfer.xethub.hf.co",
    ]
    host = (urlparse(location).hostname or "").lower()
    if host and not host_allowed(location, allow):
        # Still a Hub-resolved URL. Permit that exact host for this one file
        # only when it was returned by get_hf_file_metadata, and record it.
        allow.append(host)
    written = stream_range(
        location,
        dest,
        headers=headers,
        allow_hosts=allow,
        expected_size=expected_size or size,
        progress=progress,
        stop_check=stop_check,
    )
    return written, etag


def download_civitai_file(
    url: str,
    dest: Path,
    api_key: str | None,
    *,
    progress: ProgressCb | None = None,
    stop_check: StopCb | None = None,
    expected_size: int | None = None,
) -> int:
    """Download one Civitai file. The key is sent to civitai.com only."""
    from stele.hub.civitai import CIVITAI_HOSTS, MSG_CIVITAI_AUTH, resolve_download
    from stele.hub.client import HubError

    assert_url_allowed(url, CIVITAI_HOSTS)
    try:
        location = resolve_download(url, api_key)
    except HubError as exc:
        kind = "auth" if exc.message == MSG_CIVITAI_AUTH else "network"
        raise TransferError(exc.message, kind=kind) from exc
    headers = {"User-Agent": "Stele/1.0"}
    host = (urlparse(location).hostname or "").lower()
    if api_key and (host == "civitai.com" or host.endswith(".civitai.com")):
        headers["Authorization"] = f"Bearer {api_key}"
    # The storage host is whatever civitai.com redirected to for this attempt.
    allow = [*CIVITAI_HOSTS, host] if host else list(CIVITAI_HOSTS)
    try:
        return stream_range(
            location,
            dest,
            headers=headers,
            allow_hosts=allow,
            expected_size=expected_size,
            progress=progress,
            stop_check=stop_check,
        )
    except AuthRefused as exc:
        raise TransferError(MSG_CIVITAI_AUTH, kind="auth") from exc


def download_runtime_file(
    url: str,
    dest: Path,
    allow_hosts: list[str],
    *,
    expected_size: int | None = None,
    expected_sha256: str | None = None,
    progress: ProgressCb | None = None,
    stop_check: StopCb | None = None,
) -> int:
    assert_url_allowed(url, allow_hosts)
    return stream_range(
        url,
        dest,
        headers={"User-Agent": "Stele/1.0"},
        allow_hosts=allow_hosts,
        expected_size=expected_size,
        progress=progress,
        stop_check=stop_check,
    )


def _win_disk_full(exc: BaseException) -> bool:
    if isinstance(exc, DiskFull):
        return True
    if isinstance(exc, OSError):
        if exc.errno == 28:
            return True
        winerror = getattr(exc, "winerror", None)
        if winerror in (112, 39):
            return True
    return False


class DownloadWorker:
    """QThread started from the UI. Constructed lazily so tests need no display."""

    def __init__(self, queue, wake: threading.Event, stop: threading.Event) -> None:
        from PySide6.QtCore import QThread, Signal

        class _Thread(QThread):
            progress = Signal(object)
            changed = Signal()
            message = Signal(str)

            def __init__(self, outer: DownloadWorker) -> None:
                super().__init__()
                self.outer = outer

            def run(self) -> None:
                self.outer._loop(self)

        self.queue = queue
        self.wake = wake
        self.stop = stop
        self.thread = _Thread(self)

    def start(self) -> None:
        self.thread.start()

    def _loop(self, thread) -> None:
        from stele.download.queue import Queue

        queue: Queue = self.queue
        while not self.stop.is_set():
            kind, job, file_row = queue.db.claim_next_file()
            if kind in ("empty", "paused"):
                self.wake.wait(0.4)
                self.wake.clear()
                continue
            if kind == "idle":
                try:
                    queue.finish_if_ready(int(job["id"]), thread.message.emit)
                except Exception as exc:
                    log.exception("Could not finish job %s", job.get("id"))
                    thread.message.emit(str(exc))
                    queue.db.mark_job_finished(int(job["id"]), "failed", None, str(exc))
                thread.changed.emit()
                self.wake.wait(0.2)
                self.wake.clear()
                continue
            if file_row is None:
                continue
            try:
                self._one_file(thread, job, file_row)
            except Cancelled as exc:
                queue.db.mark_file_pending(int(file_row["id"]))
                if exc.kind == "cancelled":
                    queue.db.cancel_job(int(job["id"]))
                elif exc.kind == "shutdown":
                    # Closing the window is not Cancel. Leave the partial and the slot.
                    current = queue.db.get_job(int(job["id"]))
                    if current and current["status"] == "active":
                        queue.db.pause_holding()
                thread.changed.emit()
            except DiskFull:
                queue.db.mark_file_pending(int(file_row["id"]))
                queue.db.set_job_status(int(job["id"]), "paused", MSG_DISK)
                thread.message.emit(MSG_DISK)
                thread.changed.emit()
            except AuthRefused:
                queue.db.mark_file_failed(int(file_row["id"]), MSG_AUTH)
                queue.db.mark_job_finished(int(job["id"]), "failed", None, MSG_AUTH)
                thread.message.emit(MSG_AUTH)
                thread.changed.emit()
            except Exception as exc:
                if _win_disk_full(exc):
                    queue.db.mark_file_pending(int(file_row["id"]))
                    queue.db.set_job_status(int(job["id"]), "paused", MSG_DISK)
                    thread.message.emit(MSG_DISK)
                else:
                    log.exception("file failed")
                    queue.db.mark_file_failed(int(file_row["id"]), str(exc))
                    thread.message.emit(str(exc))
                thread.changed.emit()

    def _stop_check(self, job_id: int):
        def check() -> str | None:
            job = self.queue.db.get_job(job_id)
            status = None if job is None else str(job["status"])
            return transfer_stop_reason(status, self.stop.is_set())

        return check

    def _backoff_sleep(self, attempt: int, filename: str, thread, job_id: int) -> None:
        """Cooperative exponential backoff sleeping in small increments while checking stop/pause."""
        delay = min(30.0, (1.5 ** attempt) * 2.0)
        thread.message.emit(
            f"Network retry for {filename} in {delay:.1f}s (attempt {attempt + 1}/{NETWORK_TRIES})..."
        )
        stop_fn = self._stop_check(job_id)
        deadline = time.monotonic() + delay
        while time.monotonic() < deadline:
            how = stop_fn()
            if how:
                raise Cancelled(how)
            time.sleep(min(0.25, max(0.01, deadline - time.monotonic())))

    def _one_file(self, thread, job: dict, file_row: dict) -> None:
        from stele.credentials import get_token

        file_id = int(file_row["id"])
        job_id = int(job["id"])
        relative = str(file_row["relative_path"])
        dest = Path(str(file_row["local_path"]))
        dest.parent.mkdir(parents=True, exist_ok=True)
        filename = Path(relative).name

        def emit(done: int, total: int | None) -> None:
            job_done = self.queue.db.update_file_progress(file_id, done, job_id)
            now = time.monotonic()
            state = getattr(thread, "_rate", None)
            if state is None or state[0] != file_id:
                thread._rate = (file_id, now, done)
                rate = 0.0
            else:
                elapsed = max(0.001, now - state[1])
                rate = max(0.0, (done - state[2]) / elapsed)
                if elapsed > 2:
                    thread._rate = (file_id, now, done)
            job_total = int(job["bytes_total"] or 0)
            thread.progress.emit(
                {
                    "filename": filename,
                    "file_done": done,
                    "file_total": total if total is not None else file_row.get("size"),
                    "rate": rate,
                    "job_done": job_done,
                    "job_total": job_total,
                }
            )

        last_error = "Download failed."
        for attempt in range(NETWORK_TRIES):
            try:
                from stele.db import loads_meta

                meta = loads_meta(job.get("meta_json"))
                if job["kind"] == "runtime":
                    download_runtime_file(
                        str(meta["url"]),
                        dest,
                        list(meta.get("allow") or []),
                        expected_size=file_row.get("size"),
                        progress=emit,
                        stop_check=self._stop_check(job_id),
                    )
                    etag = meta.get("sha256")
                elif meta.get("source") == "civitai":
                    from stele.credentials import get_civitai_key

                    download_civitai_file(
                        str((meta.get("download_urls") or {})[relative]),
                        dest,
                        get_civitai_key(),
                        progress=emit,
                        stop_check=self._stop_check(job_id),
                        expected_size=file_row.get("size"),
                    )
                    etag = file_row.get("etag")
                else:
                    _size, etag = download_hub_file(
                        str(job["repo_id"]),
                        relative,
                        str(job["commit_sha"] or job["revision"] or "main"),
                        dest,
                        get_token(),
                        progress=emit,
                        stop_check=self._stop_check(job_id),
                        expected_size=file_row.get("size"),
                    )
                self.queue.db.set_file_local(file_id, str(dest), etag, dest.stat().st_size)
                break
            except Cancelled:
                raise
            except (DiskFull, AuthRefused):
                raise
            except TransferError as exc:
                last_error = str(exc)
                if exc.kind in ("auth", "disk", "source"):
                    raise
                log.warning("network attempt %s for %s failed: %s", attempt + 1, filename, exc)
                if attempt + 1 >= NETWORK_TRIES:
                    raise TransferError(last_error) from exc
                self._backoff_sleep(attempt, filename, thread, job_id)
            except Exception as exc:
                if _win_disk_full(exc):
                    raise DiskFull() from exc
                last_error = str(exc)
                log.warning("unexpected error on attempt %s for %s: %s", attempt + 1, filename, exc)
                if attempt + 1 >= NETWORK_TRIES:
                    raise TransferError(last_error) from exc
                self._backoff_sleep(attempt, filename, thread, job_id)

        self._hash_and_finish(thread, job, file_id, dest, relative)

    def _hash_and_finish(self, thread, job: dict, file_id: int, dest: Path, relative: str) -> None:
        from stele.db import loads_meta

        self.queue.db.mark_file_hashing(file_id)
        thread.changed.emit()
        row = next(item for item in self.queue.db.list_files(int(job["id"])) if int(item["id"]) == file_id)
        expected = row.get("etag")
        if job["kind"] == "runtime":
            expected = loads_meta(job.get("meta_json")).get("sha256") or expected
        actual = hash_file(dest)
        decision = evaluate_hash(expected, actual, int(row.get("hash_attempts") or 0))
        if decision == "retry":
            self.queue.db.bump_hash_attempt(file_id)
            if dest.exists():
                dest.unlink()
            partial = partial_path(dest)
            if partial.exists():
                partial.unlink()
            self.queue.db.mark_file_pending(file_id, 0)
            thread.message.emit(f"Checksum mismatch for {Path(relative).name}. Retrying once.")
            return
        if decision == "failed":
            self.queue.db.bump_hash_attempt(file_id)
            self.queue.db.mark_file_failed(file_id, "SHA-256 did not match after one retry.")
            thread.message.emit(f"Checksum failed for {Path(relative).name}.")
            return
        self.queue.db.mark_file_done(file_id, actual, dest.stat().st_size)
        self.queue.db.update_file_progress(file_id, dest.stat().st_size, int(job["id"]))
        thread.changed.emit()
