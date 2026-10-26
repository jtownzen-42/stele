"""Civitai as a second source: parsing, planning, downloading, and finishing a job.

The fixture follows the public Civitai REST API (GET /api/v1/models/:id).
These tests never touch the network.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from stele.credentials import redact_text
from stele.db import Database, utc_now
from stele.download.queue import Queue
from stele.hub import civitai
from stele.hub.civitai import (
    MSG_CIVITAI_AUTH,
    PROFILE_CIVITAI,
    CivitaiClient,
    default_selection,
    is_civitai,
    plan_civitai,
    to_details,
    to_hit,
)
from stele.hub.client import HubError
from stele.models import CAPACITY_PRESETS, safe_repo
from stele.settings import Settings

WEIGHTS = b"safetensors weights"
TRAINING = b"training images"
MODEL = {
    "id": 4201,
    "name": "Stone Carver XL",
    "description": "<p>A <b>granite</b> style.</p><p>Use at 0.8 weight &amp; up.</p>",
    "type": "LORA",
    "nsfw": False,
    "tags": ["style", "stone"],
    "allowNoCredit": False,
    "allowCommercialUse": ["Image", "Rent"],
    "allowDerivatives": True,
    "allowDifferentLicense": False,
    "creator": {"username": "mason"},
    "stats": {"downloadCount": 1234, "thumbsUpCount": 99},
    "modelVersions": [
        {
            "id": 9902,
            "name": "v2.0",
            "baseModel": "SDXL 1.0",
            "trainedWords": ["carved stone", "granite"],
            "publishedAt": "2026-09-01T10:00:00.000Z",
            "description": "<p>Sharper edges.</p>",
            "files": [
                {
                    "name": "stone_carver_xl_v2.safetensors",
                    "sizeKB": 1024.0,
                    "type": "Model",
                    "primary": True,
                    "metadata": {"format": "SafeTensor", "fp": "fp16"},
                    "hashes": {"SHA256": hashlib.sha256(WEIGHTS).hexdigest().upper()},
                    "downloadUrl": "https://civitai.com/api/download/models/9902",
                },
                {
                    "name": "training_set.zip",
                    "sizeKB": 2048.5,
                    "type": "Training Data",
                    "hashes": {"SHA256": hashlib.sha256(TRAINING).hexdigest().upper()},
                    "downloadUrl": "https://civitai.com/api/download/models/9902?type=Training%20Data",
                },
            ],
        },
        {
            "id": 9801,
            "name": "v1.0",
            "baseModel": "SDXL 1.0",
            "trainedWords": [],
            "publishedAt": "2026-06-01T10:00:00.000Z",
            "files": [
                {
                    "name": "stone_carver_xl_v1.safetensors",
                    "sizeKB": 900,
                    "type": "Model",
                    "hashes": {"SHA256": "AB" * 32},
                    "downloadUrl": "https://civitai.com/api/download/models/9801",
                }
            ],
        },
    ],
}


def test_ids_and_safe_folder():
    hit = to_hit(MODEL)
    assert hit.repo_id == "civitai/4201"
    assert is_civitai(hit.repo_id)
    assert not is_civitai("org/repo")
    assert safe_repo(hit.repo_id) == "civitai--4201"
    assert hit.title == "Stone Carver XL"
    assert hit.author == "mason"
    assert hit.pipeline_tag == "LORA"
    assert hit.library_name == "SDXL 1.0"
    assert hit.approx_bytes == 1024 * 1024
    assert hit.downloads == 1234


def test_details_pick_latest_version_by_default():
    details = to_details(MODEL)
    assert details.source == "civitai"
    assert details.sha == "v9902"
    assert details.revision == "v9902"
    assert [f.path for f in details.files] == ["stone_carver_xl_v2.safetensors", "training_set.zip"]
    weights = details.files[0]
    assert weights.etag == hashlib.sha256(WEIGHTS).hexdigest()
    assert details.download_urls["training_set.zip"].endswith("type=Training%20Data")
    assert details.versions == [("v2.0 (v9902)", "v9902"), ("v1.0 (v9801)", "v9801")]
    assert "commercial use Image, Rent" in details.license_name
    assert "credit required" in details.license_name
    meta = details.source_meta
    assert meta["version"]["trained_words"] == ["carved stone", "granite"]
    assert meta["description"] == "A granite style.\n\nUse at 0.8 weight & up."
    assert "Trigger words: carved stone, granite" in details.card_excerpt


def test_details_pick_requested_version():
    details = to_details(MODEL, "v9801")
    assert details.sha == "v9801"
    assert [f.path for f in details.files] == ["stone_carver_xl_v1.safetensors"]


def test_training_data_is_not_ticked_by_default():
    details = to_details(MODEL)
    assert default_selection(details) == ["stone_carver_xl_v2.safetensors"]
    plan = plan_civitai(details.files, default_selection(details), CAPACITY_PRESETS["bd25"])
    assert plan.profile_used == PROFILE_CIVITAI
    assert plan.disc_estimate == 1
    assert [f.path for f in plan.files] == ["stone_carver_xl_v2.safetensors"]
    empty = plan_civitai(details.files, [], CAPACITY_PRESETS["bd25"])
    assert empty.blocked_reason


def _response(status: int, body: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = body or {}
    return resp


def test_client_search_hides_nsfw_and_sends_key():
    with patch("httpx.get", return_value=_response(200, {"items": [MODEL]})) as get:
        hits = CivitaiClient("secret-key").search("stone", model_type="LORA")
    assert [hit.repo_id for hit in hits] == ["civitai/4201"]
    params = get.call_args.kwargs["params"]
    assert params["nsfw"] == "false"
    assert params["types"] == "LORA"
    assert get.call_args.kwargs["headers"]["Authorization"] == "Bearer secret-key"
    assert "secret-key" not in repr(CivitaiClient("secret-key"))


@pytest.mark.parametrize("query", ["4201", "civitai/4201", "https://civitai.com/models/4201/stone-carver"])
def test_client_search_by_id_or_link(query):
    with patch("httpx.get", return_value=_response(200, MODEL)) as get:
        hits = CivitaiClient(None).search(query)
    assert get.call_args.args[0].endswith("/models/4201")
    assert "Authorization" not in get.call_args.kwargs["headers"]
    assert hits[0].repo_id == "civitai/4201"


def test_client_maps_auth_errors():
    with patch("httpx.get", return_value=_response(401)):
        with pytest.raises(HubError) as err:
            CivitaiClient(None).details("civitai/4201")
    assert err.value.message == MSG_CIVITAI_AUTH


def test_redaction_covers_query_tokens():
    text = "GET https://civitai.com/api/download/models/1?type=Model&token=abcdef0123456789 failed"
    assert "abcdef0123456789" not in redact_text(text)


def test_download_sends_key_to_civitai_only(tmp_path: Path):
    from stele.download import worker

    calls = {}

    def fake_resolve(url, key):
        calls["resolve"] = (url, key)
        return "https://bucket.r2.cloudflarestorage.com/model.safetensors?X-Amz-Signature=abc"

    def fake_stream(url, dest, *, headers, allow_hosts, **_kwargs):
        calls["stream"] = (url, headers, allow_hosts)
        dest.write_bytes(WEIGHTS)
        return len(WEIGHTS)

    with patch.object(civitai, "resolve_download", fake_resolve), patch.object(worker, "stream_range", fake_stream):
        worker.download_civitai_file("https://civitai.com/api/download/models/9902", tmp_path / "w", "secret-key")
    assert calls["resolve"] == ("https://civitai.com/api/download/models/9902", "secret-key")
    url, headers, allow = calls["stream"]
    assert "Authorization" not in headers
    assert "bucket.r2.cloudflarestorage.com" in allow


def test_download_refuses_non_civitai_links(tmp_path: Path):
    from stele.download.worker import TransferError, download_civitai_file

    with pytest.raises(TransferError) as err:
        download_civitai_file("https://evil.example/model", tmp_path / "w", None)
    assert err.value.kind == "source"


def test_auth_failure_is_reported_as_civitai(tmp_path: Path):
    from stele.download.worker import TransferError, download_civitai_file

    def refuse(url, key):
        raise HubError(MSG_CIVITAI_AUTH)

    with patch.object(civitai, "resolve_download", refuse):
        with pytest.raises(TransferError) as err:
            download_civitai_file("https://civitai.com/api/download/models/1", tmp_path / "w", None)
    assert err.value.kind == "auth"
    assert "Civitai" in str(err.value)


def test_resolve_stops_at_storage_host():
    redirect = MagicMock(status_code=307, headers={"location": "https://bucket.example-storage.com/f?sig=1"})
    client = MagicMock()
    client.__enter__.return_value = client
    client.send.return_value = redirect
    with patch("httpx.Client", return_value=client):
        assert civitai.resolve_download("https://civitai.com/api/download/models/1", "k") == (
            "https://bucket.example-storage.com/f?sig=1"
        )
    sent = client.build_request.call_args
    assert sent.kwargs["headers"]["Authorization"] == "Bearer k"
    assert client.send.call_count == 1


def test_queue_and_finish_a_civitai_version(tmp_path: Path):
    db = Database(tmp_path / "stele.db")
    settings = Settings(db)
    settings.set_staging(tmp_path / "staging")
    settings.set_vault(tmp_path / "vault")
    queue = Queue(db, settings)
    details = to_details(MODEL)
    plan = plan_civitai(details.files, default_selection(details))
    with pytest.raises(ValueError):
        queue.enqueue_model(
            repo_id=details.repo_id, revision=details.revision, commit_sha=details.sha, profile=PROFILE_CIVITAI,
            license_name=details.license_name, license_excerpt="", license_ack_utc=utc_now(),
            card_excerpt="", pipeline_tag="", library_name="", files=plan.files,
            source="civitai", download_urls={},
        )
    job_id = queue.enqueue_model(
        repo_id=details.repo_id,
        revision=details.revision,
        commit_sha=details.sha,
        profile=plan.profile_used,
        license_name=details.license_name,
        license_excerpt=details.card_excerpt[:500],
        license_ack_utc=utc_now(),
        card_excerpt=details.card_excerpt,
        pipeline_tag=details.pipeline_tag,
        library_name=details.library_name,
        files=plan.files,
        source="civitai",
        download_urls=details.download_urls,
        source_meta=details.source_meta,
    )
    meta = json.loads(db.get_job(job_id)["meta_json"])
    assert meta["source"] == "civitai"
    assert list(meta["download_urls"]) == ["stone_carver_xl_v2.safetensors"]
    db.set_job_status(job_id, "active")
    for row in db.list_files(job_id):
        path = Path(row["local_path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(WEIGHTS)
        db.mark_file_done(int(row["id"]), hashlib.sha256(WEIGHTS).hexdigest(), len(WEIGHTS))
    queue.finish_if_ready(job_id)
    assert db.get_job(job_id)["status"] == "succeeded"
    folder = settings.vault() / "MODELS" / "civitai--4201" / "v9902"
    assert (folder / "stone_carver_xl_v2.safetensors").read_bytes() == WEIGHTS
    record = json.loads((folder / "civitai_model.json").read_text(encoding="utf-8"))
    assert record["version"]["trained_words"] == ["carved stone", "granite"]
    assert record["permissions"]["credit_required"] is True
    source = (folder / "SOURCE.txt").read_text(encoding="utf-8")
    assert "source: Civitai" in source
    assert "url: https://civitai.com/models/4201?modelVersionId=9902" in source
    howto = (settings.vault() / "DOCS" / "civitai--4201_howto.md").read_text(encoding="utf-8")
    assert "ComfyUI" in howto
    assert "civitai_model.json" in howto
    db.close()


def test_discover_page_queues_a_civitai_version(tmp_path: Path, monkeypatch):
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr("stele.ui.pages.discover.get_token", lambda: None)
    monkeypatch.setattr("stele.burn.imapi.enumerate_recorders", lambda: [])
    monkeypatch.setattr("stele.burn.imapi.probe", lambda: None)
    from PySide6.QtWidgets import QApplication, QCheckBox

    from stele.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "db.sqlite")
    settings = Settings(db)
    settings.set_vault(tmp_path / "vault")
    settings.set_staging(tmp_path / "staging")
    window = MainWindow(db, settings, start_worker=False)
    page = window.discover_page
    page.source.setCurrentIndex(page.source.findData("civitai"))
    assert page.civitai_type.isVisibleTo(page) and not page.pipeline.isVisibleTo(page)
    page._show_hits([to_hit(MODEL)])
    assert page.results.item(0, 0).text() == "Stone Carver XL (civitai/4201)"
    page._show_details(to_details(MODEL))
    assert page.revision.count() == 2 and page.revision.currentData() == "v9902"
    boxes = [page.files.cellWidget(row, 0) for row in range(page.files.rowCount())]
    assert all(isinstance(box, QCheckBox) for box in boxes)
    assert [box.isChecked() for box in boxes] == [True, False]
    assert not page.add_button.isEnabled()
    page.ack.setChecked(True)
    assert page.add_button.isEnabled()
    page._enqueue()
    jobs = db.list_jobs()
    assert [job["repo_id"] for job in jobs] == ["civitai/4201"]
    assert jobs[0]["profile"] == PROFILE_CIVITAI
    window.close()
    db.close()
    assert app is not None
