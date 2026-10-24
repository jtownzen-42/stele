"""SHA-256, the one automatic retry, log redaction, and the single queue slot."""

import hashlib
import logging
from pathlib import Path

from stele.credentials import RedactionFilter, redact_text
from stele.db import Database, utc_now
from stele.download.queue import Queue
from stele.download.worker import evaluate_hash, format_checksum_line, hash_file
from stele.models import HubFile
from stele.settings import Settings

GOOD = "a" * 64
BAD = "b" * 64


def test_hash_file_matches_known_bytes(tmp_path: Path):
    path = tmp_path / "note.txt"
    path.write_bytes(b"stele")
    assert hash_file(path) == hashlib.sha256(b"stele").hexdigest()


def test_checksum_line_uses_two_spaces():
    line = format_checksum_line(GOOD, "MODELS\\org--repo\\file.gguf")
    assert line == f"{GOOD}  MODELS/org--repo/file.gguf\n"


def test_hash_mismatch_retries_once_then_fails():
    assert evaluate_hash(GOOD, BAD, 0) == "retry"
    assert evaluate_hash(GOOD, BAD, 1) == "failed"
    assert evaluate_hash(GOOD, GOOD, 0) == "done"
    assert evaluate_hash(None, GOOD, 0) == "done"
    assert evaluate_hash("not-a-sha", GOOD, 0) == "done"


def test_redaction_removes_token_and_authorization():
    secret = "hf_abcdefghijklmnopqrstuvwxyz123456"
    text = f"token {secret} Authorization: Bearer {secret}"
    cleaned = redact_text(text)
    assert secret not in cleaned
    assert "hf_" not in cleaned
    assert "Bearer" not in cleaned

    record = logging.LogRecord(
        name="stele",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="header %s",
        args=(f"Authorization: {secret}",),
        exc_info=None,
    )
    assert RedactionFilter().filter(record) is True
    rendered = record.getMessage()
    assert secret not in rendered
    assert "hf_" not in rendered


def test_shutdown_does_not_override_pause():
    from stele.download.worker import partial_path, transfer_stop_reason

    assert transfer_stop_reason("paused", True) == "paused"
    assert transfer_stop_reason("active", True) == "shutdown"
    assert transfer_stop_reason("cancelled", True) == "cancelled"
    assert transfer_stop_reason("active", False) is None
    assert partial_path(Path("model.gguf")) == Path("model.gguf.partial")


def test_range_resume_keeps_one_partial(tmp_path: Path):
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    payload = b"abcdefghij" * 300_000
    state = {"requests": 0}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            state["requests"] += 1
            start = 0
            header = self.headers.get("Range")
            if header and header.startswith("bytes="):
                start = int(header.split("=", 1)[1].split("-", 1)[0] or "0")
                body = payload[start:]
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{len(payload) - 1}/{len(payload)}")
            else:
                body = payload
                self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        from stele.download.worker import Cancelled, hash_file, partial_path, stream_range

        dest = tmp_path / "weights.gguf"
        url = f"http://127.0.0.1:{server.server_port}/weights.gguf"
        seen = {"n": 0}

        def stop():
            seen["n"] += 1
            if seen["n"] >= 2:
                return "paused"
            return None

        try:
            stream_range(url, dest, expected_size=len(payload), progress=lambda done, total: None, stop_check=stop)
            raise AssertionError("transfer should have paused")
        except Cancelled as exc:
            assert exc.kind == "paused"
        partial = partial_path(dest)
        assert partial.exists()
        assert 0 < partial.stat().st_size < len(payload)
        assert not dest.exists()
        written = stream_range(url, dest, expected_size=len(payload))
        assert written == len(payload)
        assert hash_file(dest) == hashlib.sha256(payload).hexdigest()
        assert not partial.exists()
        assert state["requests"] == 2
    finally:
        server.shutdown()
        server.server_close()


def test_resume_does_not_jump_the_queue(tmp_path: Path):
    db = Database(tmp_path / "stele.db")
    settings = Settings(db)
    settings.set_staging(tmp_path / "staging")
    settings.set_vault(tmp_path / "vault")
    queue = Queue(db, settings)
    common = dict(
        revision="main",
        commit_sha="abc123",
        profile="GGUF inference pack",
        license_name="mit",
        license_excerpt="mit",
        license_ack_utc=utc_now(),
        card_excerpt="",
        pipeline_tag="text-generation",
        library_name="gguf",
    )
    first = queue.enqueue_model(repo_id="org/one", files=[HubFile("a.gguf", 4)], **common)
    second = queue.enqueue_model(repo_id="org/two", files=[HubFile("b.gguf", 4)], **common)
    assert "waiting" in (db.resume_job(second) or "")
    assert db.get_job(second)["status"] == "queued"
    assert db.resume_job(first) is None
    assert db.get_job(first)["status"] == "active"
    assert db.get_job(second)["status"] == "queued"
    db.close()


def test_catalog_search_does_not_confuse_ids(tmp_path: Path):
    db = Database(tmp_path / "stele.db")
    first = db.insert_catalog(
        {
            "kind": "model",
            "repo_id": "org/one",
            "vault_path": str(tmp_path / "one"),
            "bytes": 1,
            "file_count": 1,
        }
    )
    db.insert_burn(
        {
            "disc_label": "STELE_deadbeef_12",
            "verify_status": "full",
            "result": "success",
            "catalog_ids_json": "[12]",
        }
    )
    assert db.search_catalog(verify_status="full") == []
    db.insert_burn(
        {
            "disc_label": "STELE_deadbeef_1",
            "verify_status": "sampled",
            "result": "success",
            "catalog_ids_json": f"[{first}]",
        }
    )
    found = db.search_catalog(verify_status="sampled")
    assert [row["id"] for row in found] == [first]
    assert [row["id"] for row in db.search_catalog(disc_id="STELE_deadbeef_12")] == []
    assert [row["id"] for row in db.search_catalog(disc_id="1")] == [first]
    db.close()


def test_finished_model_reads_the_license_file(tmp_path: Path):
    from stele.models import DISCLAIMER

    db = Database(tmp_path / "stele.db")
    settings = Settings(db)
    settings.set_staging(tmp_path / "staging")
    settings.set_vault(tmp_path / "vault")
    queue = Queue(db, settings)
    job_id = queue.enqueue_model(
        repo_id="org/repo",
        revision="main",
        commit_sha="abc123",
        profile="GGUF inference pack",
        license_name="apache-2.0",
        license_excerpt="this is the model card, not the license",
        license_ack_utc=utc_now(),
        card_excerpt="A tiny model.",
        pipeline_tag="text-generation",
        library_name="gguf",
        files=[HubFile("weights.gguf", 5), HubFile("LICENSE", 20), HubFile("config.json", 2)],
    )
    db.set_job_status(job_id, "active")
    config = '{"model_type": "qwen2", "vocab_size": 32, "max_position_embeddings": 128}'
    bodies = {"weights.gguf": b"gguf", "LICENSE": b"Apache License, Version 2.0. Permission is granted.", "config.json": config.encode()}
    for row in db.list_files(job_id):
        path = Path(row["local_path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(bodies[row["relative_path"]])
        db.mark_file_done(int(row["id"]), hashlib.sha256(bodies[row["relative_path"]]).hexdigest(), path.stat().st_size)
    queue.finish_if_ready(job_id)
    job = db.get_job(job_id)
    assert job["status"] == "succeeded"
    spec = (settings.vault() / "DOCS" / "org--repo_spec.md").read_text(encoding="utf-8")
    assert "Apache License, Version 2.0" in spec
    assert "this is the model card, not the license" not in spec
    assert DISCLAIMER in spec
    assert (settings.vault() / "MODELS" / "org--repo" / "abc123" / "SOURCE.txt").exists()
    assert (settings.vault() / "DOCS" / "org--repo_spec.pdf").stat().st_size > 100
    db.close()


def test_queue_does_not_start_the_second_job(tmp_path: Path):
    db = Database(tmp_path / "stele.db")
    settings = Settings(db)
    settings.set_staging(tmp_path / "staging")
    settings.set_vault(tmp_path / "vault")
    queue = Queue(db, settings)
    common = dict(
        revision="main",
        commit_sha="abc123",
        profile="GGUF inference pack",
        license_name="mit",
        license_excerpt="mit",
        license_ack_utc=utc_now(),
        card_excerpt="",
        pipeline_tag="text-generation",
        library_name="gguf",
    )
    first = queue.enqueue_model(repo_id="org/one", files=[HubFile("a.gguf", 4)], **common)
    second = queue.enqueue_model(repo_id="org/two", files=[HubFile("b.gguf", 4)], **common)
    kind, job, _file = db.claim_next_file()
    assert kind == "file"
    assert job["id"] == first
    kind, job, _file = db.claim_next_file()
    assert kind == "idle"
    assert job["id"] == first
    assert db.get_job(second)["status"] == "queued"
    db.pause_holding()
    kind, paused, _file = db.claim_next_file()
    assert kind == "paused"
    assert paused["id"] == first
    assert db.get_job(second)["status"] == "queued"
    db.close()


def test_enqueue_sets_local_paths_before_the_job_is_visible(tmp_path: Path):
    """The worker can claim a queued job the moment it is committed. Every file
    must already have its real local path then, not '' (which Path() turns into
    '.' and fails the hash step with Permission denied)."""
    db = Database(tmp_path / "stele.db")
    settings = Settings(db)
    settings.set_staging(tmp_path / "staging")
    settings.set_vault(tmp_path / "vault")
    queue = Queue(db, settings)

    def forbidden(*_a, **_k):
        raise AssertionError("local paths must be written inside insert_job, not afterwards")

    db.set_file_local = forbidden
    db.set_job_staging = forbidden
    job_id = queue.enqueue_model(
        repo_id="org/one",
        revision="main",
        commit_sha="abc123",
        profile="Inference pack",
        license_name="mit",
        license_excerpt="mit",
        license_ack_utc=utc_now(),
        card_excerpt="",
        pipeline_tag="text-generation",
        library_name="transformers",
        files=[HubFile("config.json", 4), HubFile("sub/model.bin", 8)],
    )
    staging = tmp_path / "staging" / str(job_id)
    assert db.get_job(job_id)["staging_path"] == str(staging)
    paths = {row["relative_path"]: row["local_path"] for row in db.list_files(job_id)}
    assert paths == {
        "config.json": str(staging / "config.json"),
        "sub/model.bin": str(staging / "sub/model.bin"),
    }
    status, job, file_row = db.claim_next_file()
    assert status == "file" and file_row["local_path"] == str(staging / "config.json")

def test_delete_job_removes_staging_and_rows(tmp_path: Path):
    db = Database(tmp_path / "stele.db")
    settings = Settings(db)
    settings.set_staging(tmp_path / "staging")
    settings.set_vault(tmp_path / "vault")
    queue = Queue(db, settings)
    job_id = queue.enqueue_model(
        repo_id="org/one", revision="main", commit_sha="abc123", profile="Inference pack",
        license_name="mit", license_excerpt="mit", license_ack_utc=utc_now(), card_excerpt="",
        pipeline_tag="text-generation", library_name="transformers",
        files=[HubFile("config.json", 4)],
    )
    staging = tmp_path / "staging" / str(job_id)
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "config.json.partial").write_bytes(b"xx")
    queue.delete_job(job_id)
    assert db.get_job(job_id) is None
    assert db.list_files(job_id) == []
    assert not staging.exists()
