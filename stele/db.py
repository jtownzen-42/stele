"""SQLite catalog, queue, and settings. One connection, one lock."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    position INTEGER NOT NULL,
    repo_id TEXT NOT NULL,
    revision TEXT,
    commit_sha TEXT,
    profile TEXT,
    license_name TEXT,
    license_excerpt TEXT,
    license_ack_utc TEXT,
    card_excerpt TEXT,
    pipeline_tag TEXT,
    library_name TEXT,
    bytes_total INTEGER NOT NULL DEFAULT 0,
    bytes_done INTEGER NOT NULL DEFAULT 0,
    staging_path TEXT,
    vault_path TEXT,
    error TEXT,
    meta_json TEXT,
    created_utc TEXT NOT NULL,
    updated_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS job_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    relative_path TEXT NOT NULL,
    size INTEGER,
    etag TEXT,
    sha256 TEXT,
    status TEXT NOT NULL,
    bytes_downloaded INTEGER NOT NULL DEFAULT 0,
    local_path TEXT,
    hash_attempts INTEGER NOT NULL DEFAULT 0,
    error TEXT
);
CREATE TABLE IF NOT EXISTS catalog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    repo_id TEXT NOT NULL,
    revision TEXT,
    commit_sha TEXT,
    profile TEXT,
    license_name TEXT,
    vault_path TEXT NOT NULL,
    bytes INTEGER NOT NULL DEFAULT 0,
    file_count INTEGER NOT NULL DEFAULT 0,
    formats_json TEXT,
    created_utc TEXT NOT NULL,
    job_id INTEGER
);
CREATE TABLE IF NOT EXISTS burns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_utc TEXT NOT NULL,
    drive_name TEXT,
    media_type TEXT,
    disc_label TEXT,
    volume_index INTEGER,
    volume_count INTEGER,
    set_id TEXT,
    verify_status TEXT,
    verify_note TEXT,
    iso_path TEXT,
    result TEXT,
    com_error TEXT,
    catalog_ids_json TEXT
);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        cur = self._conn.execute(sql, params)
        return cur.fetchone()

    def _all(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        cur = self._conn.execute(sql, params)
        return list(cur.fetchall())

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        with self._lock:
            row = self._one("SELECT value FROM settings WHERE key = ?", (key,))
        if row is None:
            return default
        return str(row["value"])

    def set_setting(self, key: str, value: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            self._conn.commit()

    def recover_on_startup(self) -> None:
        """A killed process must not leave a stuck active job or a half-hashed file.

        Partials stay on disk. Downloading files return to pending so Range can continue.
        The job becomes paused so a relaunch does not surprise-start the transfer.
        """
        now = utc_now()
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET status = 'paused', updated_utc = ? WHERE status = 'active'",
                (now,),
            )
            self._conn.execute(
                "UPDATE job_files SET status = 'pending' WHERE status IN ('downloading', 'hashing')"
            )
            self._conn.commit()

    def next_position(self) -> int:
        row = self._one("SELECT COALESCE(MAX(position), 0) + 1 AS n FROM jobs")
        return int(row["n"]) if row else 1

    def insert_job(
        self,
        fields: dict[str, Any],
        files: list[dict[str, Any]],
        staging_root: str | Path | None = None,
    ) -> int:
        now = utc_now()
        with self._lock:
            position = int(self._one("SELECT COALESCE(MAX(position), 0) + 1 AS n FROM jobs")["n"])
            cur = self._conn.execute(
                """
                INSERT INTO jobs (
                    kind, status, position, repo_id, revision, commit_sha, profile,
                    license_name, license_excerpt, license_ack_utc, card_excerpt,
                    pipeline_tag, library_name, bytes_total, bytes_done, staging_path,
                    vault_path, error, meta_json, created_utc, updated_utc
                ) VALUES (
                    ?, 'queued', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, NULL, NULL, ?, ?, ?
                )
                """,
                (
                    fields["kind"],
                    position,
                    fields["repo_id"],
                    fields.get("revision"),
                    fields.get("commit_sha"),
                    fields.get("profile"),
                    fields.get("license_name"),
                    fields.get("license_excerpt"),
                    fields.get("license_ack_utc"),
                    fields.get("card_excerpt"),
                    fields.get("pipeline_tag"),
                    fields.get("library_name"),
                    int(fields.get("bytes_total") or 0),
                    fields.get("staging_path"),
                    fields.get("meta_json"),
                    now,
                    now,
                ),
            )
            job_id = int(cur.lastrowid)
            # The worker may promote this job the instant it is committed, so
            # the staging folder and every file's local path must be written
            # in this same transaction. Setting them afterwards left a window
            # where the first file was claimed with an empty path (Path("") is
            # "."), which failed at the hash step with "Permission denied: '.'".
            staging_dir = None
            if staging_root:
                staging_dir = Path(staging_root) / str(job_id)
                self._conn.execute(
                    "UPDATE jobs SET staging_path = ? WHERE id = ?",
                    (str(staging_dir), job_id),
                )
            for item in files:
                local_path = item.get("local_path")
                if staging_dir is not None and not local_path:
                    local_path = str(staging_dir / str(item["relative_path"]))
                self._conn.execute(
                    """
                    INSERT INTO job_files (
                        job_id, relative_path, size, etag, status, bytes_downloaded, local_path
                    ) VALUES (?, ?, ?, ?, 'pending', 0, ?)
                    """,
                    (
                        job_id,
                        item["relative_path"],
                        item.get("size"),
                        item.get("etag"),
                        local_path,
                    ),
                )
            self._conn.commit()
            return job_id

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._all("SELECT * FROM jobs ORDER BY position ASC, id ASC")
        return [dict(row) for row in rows]

    def get_job(self, job_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._one("SELECT * FROM jobs WHERE id = ?", (job_id,))
        return dict(row) if row else None

    def list_files(self, job_id: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._all(
                "SELECT * FROM job_files WHERE job_id = ? ORDER BY id ASC",
                (job_id,),
            )
        return [dict(row) for row in rows]

    def holding_job(self) -> dict[str, Any] | None:
        """The job that owns the single slot: active, or paused (pause is not cancel)."""
        with self._lock:
            row = self._one(
                "SELECT * FROM jobs WHERE status IN ('active', 'paused') "
                "ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, position ASC LIMIT 1"
            )
        return dict(row) if row else None

    def reorder(self, job_id: int, direction: int) -> None:
        """Move a queued job up (-1) or down (+1). Active and paused jobs stay put."""
        if direction not in (-1, 1):
            raise ValueError("direction must be -1 or +1")
        with self._lock:
            job = self._one("SELECT * FROM jobs WHERE id = ?", (job_id,))
            if job is None or job["status"] != "queued":
                return
            if direction < 0:
                other = self._one(
                    "SELECT * FROM jobs WHERE status = 'queued' AND position < ? "
                    "ORDER BY position DESC LIMIT 1",
                    (job["position"],),
                )
            else:
                other = self._one(
                    "SELECT * FROM jobs WHERE status = 'queued' AND position > ? "
                    "ORDER BY position ASC LIMIT 1",
                    (job["position"],),
                )
            if other is None:
                return
            self._conn.execute("UPDATE jobs SET position = ? WHERE id = ?", (other["position"], job["id"]))
            self._conn.execute("UPDATE jobs SET position = ? WHERE id = ?", (job["position"], other["id"]))
            self._conn.commit()

    def set_job_status(self, job_id: int, status: str, error: str | None = None) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET status = ?, error = ?, updated_utc = ? WHERE id = ?",
                (status, error, utc_now(), job_id),
            )
            self._conn.commit()

    def pause_holding(self) -> None:
        now = utc_now()
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET status = 'paused', updated_utc = ? WHERE status = 'active'",
                (now,),
            )
            self._conn.commit()

    def resume_job(self, job_id: int) -> str | None:
        """Return an error string when another job still holds the slot."""
        with self._lock:
            holder = self._one(
                "SELECT * FROM jobs WHERE status IN ('active', 'paused') AND id != ?",
                (job_id,),
            )
            if holder is not None:
                return "Another job still holds the queue. Finish or cancel it before starting this one."
            job = self._one("SELECT * FROM jobs WHERE id = ?", (job_id,))
            if job is None:
                return "That job is gone."
            if job["status"] == "failed":
                return "Retry the failed file instead of resuming the whole job."
            if job["status"] == "queued":
                front = self._one(
                    "SELECT id FROM jobs WHERE status = 'queued' ORDER BY position ASC, id ASC LIMIT 1"
                )
                if front is None or int(front["id"]) != int(job_id):
                    return "That job is still waiting. Move it to the front, or let the active job finish."
            elif job["status"] != "paused":
                return None
            self._conn.execute(
                "UPDATE jobs SET status = 'active', error = NULL, updated_utc = ? WHERE id = ?",
                (utc_now(), job_id),
            )
            self._conn.commit()
        return None

    def cancel_job(self, job_id: int) -> None:
        now = utc_now()
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET status = 'cancelled', updated_utc = ? WHERE id = ? "
                "AND status IN ('queued', 'active', 'paused', 'failed')",
                (now, job_id),
            )
            self._conn.commit()

    def claim_next_file(self) -> tuple[str, dict[str, Any], dict[str, Any] | None]:
        """Return ('file', job, file), ('idle', job, None), or ('empty', {}, None).

        Promotes the next queued job only when nothing is active or paused.
        """
        with self._lock:
            holder = self._one(
                "SELECT * FROM jobs WHERE status IN ('active', 'paused') "
                "ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END LIMIT 1"
            )
            if holder is None:
                holder = self._one(
                    "SELECT * FROM jobs WHERE status = 'queued' ORDER BY position ASC, id ASC LIMIT 1"
                )
                if holder is None:
                    return ("empty", {}, None)
                self._conn.execute(
                    "UPDATE jobs SET status = 'active', updated_utc = ? WHERE id = ?",
                    (utc_now(), holder["id"]),
                )
                self._conn.commit()
                holder = self._one("SELECT * FROM jobs WHERE id = ?", (holder["id"],))
            assert holder is not None
            if holder["status"] == "paused":
                return ("paused", dict(holder), None)
            pending = self._one(
                "SELECT * FROM job_files WHERE job_id = ? AND status = 'pending' ORDER BY id ASC LIMIT 1",
                (holder["id"],),
            )
            if pending is None:
                return ("idle", dict(holder), None)
            self._conn.execute(
                "UPDATE job_files SET status = 'downloading', error = NULL WHERE id = ?",
                (pending["id"],),
            )
            self._conn.commit()
            pending = self._one("SELECT * FROM job_files WHERE id = ?", (pending["id"],))
            return ("file", dict(holder), dict(pending) if pending else None)

    def update_file_progress(self, file_id: int, bytes_downloaded: int, job_id: int) -> int:
        """Store this file's bytes, then recompute the job total from the table.

        The caller used to pass a sum taken before the write, so the status bar
        lagged one chunk behind the file that was actually on disk.
        """
        with self._lock:
            self._conn.execute(
                "UPDATE job_files SET bytes_downloaded = ? WHERE id = ?",
                (bytes_downloaded, file_id),
            )
            row = self._one(
                """
                SELECT COALESCE(SUM(
                    CASE WHEN status = 'done' THEN COALESCE(size, bytes_downloaded)
                         ELSE bytes_downloaded END
                ), 0) AS n
                FROM job_files WHERE job_id = ?
                """,
                (job_id,),
            )
            done = int(row["n"]) if row else 0
            self._conn.execute(
                "UPDATE jobs SET bytes_done = ?, updated_utc = ? WHERE id = ?",
                (done, utc_now(), job_id),
            )
            self._conn.commit()
        return done

    def mark_file_pending(self, file_id: int, bytes_downloaded: int | None = None) -> None:
        with self._lock:
            if bytes_downloaded is None:
                self._conn.execute(
                    "UPDATE job_files SET status = 'pending' WHERE id = ?",
                    (file_id,),
                )
            else:
                self._conn.execute(
                    "UPDATE job_files SET status = 'pending', bytes_downloaded = ? WHERE id = ?",
                    (bytes_downloaded, file_id),
                )
            self._conn.commit()

    def mark_file_hashing(self, file_id: int) -> None:
        with self._lock:
            self._conn.execute("UPDATE job_files SET status = 'hashing' WHERE id = ?", (file_id,))
            self._conn.commit()

    def mark_file_done(self, file_id: int, sha256: str, size: int) -> None:
        with self._lock:
            self._conn.execute(
                """
                UPDATE job_files
                SET status = 'done', sha256 = ?, size = ?, bytes_downloaded = ?, error = NULL
                WHERE id = ?
                """,
                (sha256, size, size, file_id),
            )
            self._conn.commit()

    def mark_file_failed(self, file_id: int, error: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE job_files SET status = 'failed', error = ? WHERE id = ?",
                (error, file_id),
            )
            self._conn.commit()

    def bump_hash_attempt(self, file_id: int) -> int:
        with self._lock:
            self._conn.execute(
                "UPDATE job_files SET hash_attempts = hash_attempts + 1 WHERE id = ?",
                (file_id,),
            )
            row = self._one("SELECT hash_attempts FROM job_files WHERE id = ?", (file_id,))
            self._conn.commit()
        return int(row["hash_attempts"]) if row else 0

    def set_job_staging(self, job_id: int, staging_path: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET staging_path = ?, updated_utc = ? WHERE id = ?",
                (staging_path, utc_now(), job_id),
            )
            self._conn.commit()

    def set_file_local(self, file_id: int, local_path: str, etag: str | None, size: int | None) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE job_files SET local_path = ?, etag = COALESCE(?, etag), size = COALESCE(?, size) WHERE id = ?",
                (local_path, etag, size, file_id),
            )
            self._conn.commit()

    def requeue_file(self, file_id: int) -> int | None:
        """User retry. Resets the hash counter. Re-opens the job as queued if needed."""
        with self._lock:
            file_row = self._one("SELECT * FROM job_files WHERE id = ?", (file_id,))
            if file_row is None:
                return None
            job = self._one("SELECT * FROM jobs WHERE id = ?", (file_row["job_id"],))
            if job is None:
                return None
            holder = self._one(
                "SELECT id FROM jobs WHERE status IN ('active', 'paused') AND id != ?",
                (job["id"],),
            )
            self._conn.execute(
                """
                UPDATE job_files
                SET status = 'pending', error = NULL, hash_attempts = 0
                WHERE id = ?
                """,
                (file_id,),
            )
            if job["status"] in ("failed", "cancelled", "succeeded"):
                new_status = "queued" if holder is not None else "active"
                self._conn.execute(
                    "UPDATE jobs SET status = ?, error = NULL, updated_utc = ? WHERE id = ?",
                    (new_status, utc_now(), job["id"]),
                )
            elif job["status"] == "queued" and holder is None:
                self._conn.execute(
                    "UPDATE jobs SET status = 'active', updated_utc = ? WHERE id = ?",
                    (utc_now(), job["id"]),
                )
            self._conn.commit()
            return int(job["id"])

    def file_counts(self, job_id: int) -> dict[str, int]:
        with self._lock:
            rows = self._all(
                "SELECT status, COUNT(*) AS n FROM job_files WHERE job_id = ? GROUP BY status",
                (job_id,),
            )
        counts = {row["status"]: int(row["n"]) for row in rows}
        return counts

    def sum_done_bytes(self, job_id: int) -> int:
        with self._lock:
            row = self._one(
                """
                SELECT COALESCE(SUM(
                    CASE WHEN status = 'done' THEN COALESCE(size, bytes_downloaded)
                         ELSE bytes_downloaded END
                ), 0) AS n
                FROM job_files WHERE job_id = ?
                """,
                (job_id,),
            )
        return int(row["n"]) if row else 0

    def mark_job_finished(self, job_id: int, status: str, vault_path: str | None, error: str | None) -> None:
        with self._lock:
            self._conn.execute(
                """
                UPDATE jobs
                SET status = ?, vault_path = COALESCE(?, vault_path), error = ?, updated_utc = ?
                WHERE id = ?
                """,
                (status, vault_path, error, utc_now(), job_id),
            )
            self._conn.commit()

    def insert_catalog(self, fields: dict[str, Any]) -> int:
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO catalog (
                    kind, repo_id, revision, commit_sha, profile, license_name, vault_path,
                    bytes, file_count, formats_json, created_utc, job_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fields["kind"],
                    fields["repo_id"],
                    fields.get("revision"),
                    fields.get("commit_sha"),
                    fields.get("profile"),
                    fields.get("license_name"),
                    fields["vault_path"],
                    int(fields.get("bytes") or 0),
                    int(fields.get("file_count") or 0),
                    fields.get("formats_json"),
                    utc_now(),
                    fields.get("job_id"),
                ),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def list_catalog(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._all("SELECT * FROM catalog ORDER BY created_utc DESC, id DESC")
        return [dict(row) for row in rows]

    def get_catalog(self, catalog_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._one("SELECT * FROM catalog WHERE id = ?", (catalog_id,))
        return dict(row) if row else None

    def search_catalog(
        self,
        text: str = "",
        license_name: str = "",
        fmt: str = "",
        disc_id: str = "",
        verify_status: str = "",
    ) -> list[dict[str, Any]]:
        clauses = ["1 = 1"]
        params: list[Any] = []
        if text.strip():
            clauses.append("(c.repo_id LIKE ? OR c.revision LIKE ? OR c.commit_sha LIKE ?)")
            like = f"%{text.strip()}%"
            params.extend([like, like, like])
        if license_name.strip():
            clauses.append("c.license_name LIKE ?")
            params.append(f"%{license_name.strip()}%")
        if fmt.strip():
            clauses.append("IFNULL(c.formats_json, '') LIKE ?")
            params.append(f"%{fmt.strip()}%")
        disc = disc_id.strip()
        ver = verify_status.strip()
        sql = f"SELECT c.* FROM catalog c WHERE {' AND '.join(clauses)} ORDER BY c.created_utc DESC"
        with self._lock:
            rows = [dict(row) for row in self._all(sql, tuple(params))]
            burns = [dict(row) for row in self._all("SELECT * FROM burns")] if disc or ver else []
        if not disc and not ver:
            return rows
        kept: list[dict[str, Any]] = []
        for row in rows:
            matched = [burn for burn in burns if int(row["id"]) in _burn_catalog_ids(burn.get("catalog_ids_json"))]
            if disc and not any(_burn_matches_disc(burn, disc) for burn in matched):
                continue
            if ver and not any((burn.get("verify_status") or "") == ver for burn in matched):
                continue
            kept.append(row)
        return kept

    def insert_burn(self, fields: dict[str, Any]) -> int:
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO burns (
                    created_utc, drive_name, media_type, disc_label, volume_index, volume_count,
                    set_id, verify_status, verify_note, iso_path, result, com_error, catalog_ids_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    utc_now(),
                    fields.get("drive_name"),
                    fields.get("media_type"),
                    fields.get("disc_label"),
                    fields.get("volume_index"),
                    fields.get("volume_count"),
                    fields.get("set_id"),
                    fields.get("verify_status"),
                    fields.get("verify_note"),
                    fields.get("iso_path"),
                    fields.get("result"),
                    fields.get("com_error"),
                    fields.get("catalog_ids_json"),
                ),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def list_burns(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._all("SELECT * FROM burns ORDER BY id DESC")
        return [dict(row) for row in rows]

    def active_tree_paths(self) -> list[str]:
        with self._lock:
            rows = self._all(
                "SELECT staging_path, vault_path, repo_id FROM jobs WHERE status IN ('active', 'paused')"
            )
        found: list[str] = []
        for row in rows:
            for key in ("staging_path", "vault_path"):
                if row[key]:
                    found.append(str(row[key]))
            found.append(str(row["repo_id"]))
        return found


def _burn_catalog_ids(raw: str | None) -> set[int]:
    if not raw:
        return set()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return set()
    if not isinstance(value, list):
        return set()
    found: set[int] = set()
    for item in value:
        try:
            found.add(int(item))
        except (TypeError, ValueError):
            continue
    return found


def _burn_matches_disc(burn: dict[str, Any], disc: str) -> bool:
    label = str(burn.get("disc_label") or "")
    set_id = str(burn.get("set_id") or "")
    return disc == str(burn.get("id")) or disc == label or disc == set_id or label.endswith("_" + disc)


def loads_meta(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}
