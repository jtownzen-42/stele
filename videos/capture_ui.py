"""Capture 2x HiDPI dark-mode Stele UI screens + exact widget regions offscreen.

Runs against the real PySide6 MainWindow in `stele/ui/main_window.py` without
network requests or optical drive hardware probes.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# Headless 2x HiDPI rendering must be set before importing QtWidgets
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QPA_FONTDIR"] = str(Path(__file__).resolve().parent / "assets" / "fonts")
os.environ["QT_SCALE_FACTOR"] = "2"

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtGui import QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

import stele.burn.imapi as imapi_mod  # noqa: E402
import stele.burn.par2 as par2_mod  # noqa: E402
import stele.credentials as creds_mod  # noqa: E402
import stele.ui.pages.burn_page as burn_page_mod  # noqa: E402
import stele.ui.pages.discover as discover_mod  # noqa: E402
import stele.ui.pages.settings_page as settings_page_mod  # noqa: E402
from stele.db import Database  # noqa: E402
from stele.models import HubFile, PROFILE_GGUF, RepoDetails, SearchHit  # noqa: E402
from stele.settings import Settings  # noqa: E402
from stele.ui.main_window import MainWindow  # noqa: E402
from videos.config import UI_CAPTURES_DIR  # noqa: E402


def _rect_in_window(window: MainWindow, widget: QWidget, dpr: float) -> dict[str, int]:
    top_left = widget.mapTo(window, QPoint(0, 0))
    return {
        "x": int(round(top_left.x() * dpr)),
        "y": int(round(top_left.y() * dpr)),
        "w": int(round(widget.width() * dpr)),
        "h": int(round(widget.height() * dpr)),
    }


def _grab(window: MainWindow, app: QApplication, filename: str) -> tuple[Path, float]:
    app.processEvents()
    app.processEvents()
    pix = window.grab()
    out = UI_CAPTURES_DIR / filename
    pix.save(str(out), "PNG")
    return out, float(pix.devicePixelRatio())


def capture_all() -> dict:
    UI_CAPTURES_DIR.mkdir(parents=True, exist_ok=True)

    # Patch hardware & credential stores so captures are deterministic and safe
    fake_drives = [
        {
            "id": "mock-recorder-0",
            "name": "E: Pioneer BDR-S13U-X",
            "media_type": "BD-R M-DISC 25 GB",
            "free_bytes": 25_025_314_816,
            "blank": True,
            "note": "",
            "warning": (
                "DVD M-DISC write may require an M-DISC-aware drive. "
                "BD M-DISC is written as a standard BD-R."
            ),
        }
    ]
    imapi_mod.enumerate_recorders = lambda: list(fake_drives)
    burn_page_mod.enumerate_recorders = lambda: list(fake_drives)
    imapi_mod.probe = lambda: None
    burn_page_mod.probe = lambda: None

    fake_par2 = REPO_ROOT / "tools" / "par2.exe"
    par2_mod.find_par2 = lambda _p="": fake_par2
    burn_page_mod.find_par2 = lambda _p="": fake_par2

    creds_mod.get_token = lambda: "hf_stored_in_credential_manager"
    discover_mod.get_token = lambda: "hf_stored_in_credential_manager"
    creds_mod.token_status = lambda: "Token: Stored"
    discover_mod.token_status = lambda: "Token: Stored"
    settings_page_mod.token_status = lambda: "Stored (Windows Credential Manager)"

    creds_mod.civitai_key_status = lambda: "API key: Stored"
    discover_mod.civitai_key_status = lambda: "API key: Stored"
    settings_page_mod.civitai_key_status = lambda: "Stored (Windows Credential Manager)"

    app = QApplication.instance() or QApplication(["SteleCapture"])
    for win_font in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf"):
        fp = Path(r"C:\Windows\Fonts") / win_font
        if fp.exists():
            QFontDatabase.addApplicationFont(str(fp))
    app.setStyle("Fusion")

    regions: dict[str, dict] = {}

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        os.environ["LOCALAPPDATA"] = str(tmp_path / "local")
        db = Database(tmp_path / "stele.sqlite")
        settings = Settings(db)
        settings.set_vault(Path(r"C:\Users\Alexx\Stele\vault"))
        settings.set_staging(Path(r"C:\Users\Alexx\Stele\staging"))
        settings.set_capacity_preset("bd25")
        settings.set_burn_speed(4)
        settings.set_always_verify(True)
        settings.set_recovery_percent(5)
        settings.set_studio_name("ALEXX FORGE")
        settings.set_last_format("gguf")
        settings.set_burn_runtime_ids(["lmstudio", "llama-cpp-cpu", "llama-cpp-cuda"])

        # Seed Pro license active first
        db.set_setting("license_status", "Pro")
        db.set_setting("license_email", "alexx.forge@proton.me")
        db.set_setting("license_key_masked", "STELE8...4F9A")

        # Seed Catalog + Burns
        cat_qwen = db.insert_catalog(
            {
                "kind": "model",
                "repo_id": "Qwen/Qwen2.5-7B-Instruct-GGUF",
                "revision": "main",
                "commit_sha": "dd98b7684b25f1e09a41c8810bc3f4e2a701d9e0",
                "profile": PROFILE_GGUF,
                "license_name": "apache-2.0",
                "vault_path": r"C:\Users\Alexx\Stele\vault\MODELS\Qwen--Qwen2.5-7B-Instruct-GGUF\dd98b7684b25",
                "bytes": 5_026_119_680,
                "file_count": 4,
                "formats_json": "gguf, Q4_K_M",
            }
        )
        cat_phi = db.insert_catalog(
            {
                "kind": "model",
                "repo_id": "microsoft/Phi-3.5-mini-instruct-gguf",
                "revision": "main",
                "commit_sha": "4979126c438b910aa34f0192b281c1a9f440e821",
                "profile": PROFILE_GGUF,
                "license_name": "mit",
                "vault_path": r"C:\Users\Alexx\Stele\vault\MODELS\microsoft--Phi-3.5-mini-instruct-gguf\4979126c438b",
                "bytes": 2_568_421_120,
                "file_count": 3,
                "formats_json": "gguf, Q4_K_M",
            }
        )
        db.insert_catalog(
            {
                "kind": "model",
                "repo_id": "civitai/842109",
                "revision": "v918204",
                "commit_sha": "v918204",
                "profile": "Civitai version",
                "license_name": "Civitai creator permissions",
                "vault_path": r"C:\Users\Alexx\Stele\vault\MODELS\civitai--842109\v918204",
                "bytes": 644_245_094,
                "file_count": 2,
                "formats_json": "safetensors, LoRA",
            }
        )
        db.insert_burn(
            {
                "drive_name": "E: Pioneer BDR-S13U-X",
                "media_type": "BD-R M-DISC 25 GB",
                "disc_label": "STELE_QWEN25_7B_01",
                "volume_index": 1,
                "volume_count": 1,
                "set_id": "set-01",
                "verify_status": "verified (SHA-256)",
                "verify_note": "All 11 files matched checksums.sha256",
                "iso_path": "",
                "result": "ok",
                "catalog_ids_json": json.dumps([cat_qwen, cat_phi]),
            }
        )

        # Seed Queue job (1 file done + verified SHA-256, 1 file HTTP Range downloading, 1 runtime waiting)
        job1 = db.insert_job(
            {
                "kind": "model",
                "repo_id": "Qwen/Qwen2.5-7B-Instruct-GGUF",
                "revision": "main",
                "commit_sha": "dd98b7684b25f1e09a41c8810bc3f4e2a701d9e0",
                "profile": PROFILE_GGUF,
                "license_name": "apache-2.0",
                "bytes_total": 5_026_119_680,
                "staging_path": r"C:\Users\Alexx\Stele\staging\job-1",
            },
            [
                {
                    "relative_path": "qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf",
                    "size": 4_284_229_120,
                    "etag": "e1",
                },
                {
                    "relative_path": "qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf",
                    "size": 737_696_256,
                    "etag": "e2",
                },
                {
                    "relative_path": "config.json",
                    "size": 1_248,
                    "etag": "e3",
                },
                {
                    "relative_path": "LICENSE",
                    "size": 11_357,
                    "etag": "e4",
                },
            ],
        )
        with db._lock:
            files_rows = db._all("SELECT id FROM job_files WHERE job_id = ? ORDER BY id ASC", (job1,))
            db._conn.execute(
                "UPDATE jobs SET status = 'active', bytes_done = ? WHERE id = ?",
                (4_695_270_912, job1),
            )
            db._conn.execute(
                "UPDATE job_files SET status = 'done', bytes_downloaded = 4284229120, "
                "sha256 = '4ab19c80f7d2e6019b4ab14ab19c80f7d2e6019b4ab14ab19c80f7d2e6019b4a' WHERE id = ?",
                (files_rows[0]["id"],),
            )
            db._conn.execute(
                "UPDATE job_files SET status = 'downloading', bytes_downloaded = 411041792 WHERE id = ?",
                (files_rows[1]["id"],),
            )
            db._conn.commit()

        db.insert_job(
            {
                "kind": "runtime",
                "repo_id": "llama.cpp Windows x64 CUDA",
                "revision": "b11146",
                "commit_sha": "b11146",
                "profile": "Runtime kit",
                "license_name": "MIT",
                "bytes_total": 253_869_799,
            },
            [
                {
                    "relative_path": "llama-b11146-bin-win-cuda-12.4-x64.zip",
                    "size": 253_869_799,
                    "etag": "r1",
                }
            ],
        )

        window = MainWindow(db, settings, start_worker=False)
        window.resize(1360, 900)
        window.show()
        app.processEvents()

        # -------------------------------------------------------------------
        # 1. Discover Page — Hugging Face
        # -------------------------------------------------------------------
        window.nav.setCurrentRow(0)
        dp = window.discover_page
        dp.query.setText("Qwen2.5-7B-Instruct-GGUF")
        dp._show_hits(
            [
                SearchHit(
                    repo_id="Qwen/Qwen2.5-7B-Instruct-GGUF",
                    author="Qwen",
                    last_modified="2026-09-18",
                    downloads=412000,
                    likes=1480,
                    pipeline_tag="text-generation",
                    library_name="gguf",
                    gated=False,
                    approx_bytes=5_026_119_680,
                ),
                SearchHit(
                    repo_id="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
                    author="Qwen",
                    last_modified="2026-09-21",
                    downloads=289000,
                    likes=980,
                    pipeline_tag="text-generation",
                    library_name="gguf",
                    gated=False,
                    approx_bytes=5_026_119_680,
                ),
                SearchHit(
                    repo_id="bartowski/Mistral-Small-24B-Instruct-GGUF",
                    author="bartowski",
                    last_modified="2026-10-04",
                    downloads=164000,
                    likes=620,
                    pipeline_tag="text-generation",
                    library_name="gguf",
                    gated=False,
                    approx_bytes=14_892_100_000,
                ),
            ]
        )
        dp.results.blockSignals(True)
        dp.results.selectRow(0)
        dp.results.blockSignals(False)
        dp._show_details(
            RepoDetails(
                repo_id="Qwen/Qwen2.5-7B-Instruct-GGUF",
                sha="dd98b7684b25f1e09a41c8810bc3f4e2a701d9e0",
                revision="main",
                last_modified="2026-09-18",
                pipeline_tag="text-generation",
                library_name="gguf",
                license_name="apache-2.0",
                gated=False,
                card_excerpt=(
                    "Instruction-tuned 7B parameter model in GGUF format. "
                    "Pinned by commit SHA for reproducible local inference with "
                    "LM Studio, Ollama, or llama.cpp."
                ),
                files=[
                    HubFile("qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf", 4_284_229_120),
                    HubFile("qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf", 737_696_256),
                    HubFile("config.json", 1_248),
                    HubFile("LICENSE", 11_357),
                ],
            )
        )
        # Ensure second shard checkbox is also checked for realism
        box1 = dp.files.cellWidget(1, 0)
        if box1 is not None:
            box1.setChecked(True)
        dp.ack.setChecked(True)
        dp._replan()
        _, dpr = _grab(window, app, "ui_discover_hf.png")
        regions["ui_discover_hf"] = {
            "window_w": int(round(window.width() * dpr)),
            "window_h": int(round(window.height() * dpr)),
            "top_search": _rect_in_window(window, dp.query, dpr),
            "source_combo": _rect_in_window(window, dp.source, dpr),
            "detail_title": _rect_in_window(window, dp.title, dpr),
            "files_table": _rect_in_window(window, dp.files, dpr),
            "ack_checkbox": _rect_in_window(window, dp.ack, dpr),
            "add_button": _rect_in_window(window, dp.add_button, dpr),
        }

        # -------------------------------------------------------------------
        # 2. Queue Page — Active HTTP Range Download + Verified SHA-256
        # -------------------------------------------------------------------
        window.nav.setCurrentRow(1)
        qp = window.queue_page
        qp.refresh()
        qp.jobs.selectRow(0)
        qp._show_files()
        window._status.setText(
            "qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf  "
            "392.0 MB / 703.5 MB  48.4 MB/s  remaining 311.5 MB"
        )
        _grab(window, app, "ui_queue_active.png")
        regions["ui_queue_active"] = {
            "jobs_table": _rect_in_window(window, qp.jobs, dpr),
            "files_table": _rect_in_window(window, qp.files, dpr),
        }
        window._status.setText("Idle · Ready for your next archive")

        # -------------------------------------------------------------------
        # 3. Burn Page (Pro) — UDF Burn + 5% PAR2 + Verify After Burn
        # -------------------------------------------------------------------
        window.nav.setCurrentRow(3)
        bp = window.burn_page
        bp.selected_ids = [cat_qwen, cat_phi]
        bp._refresh_drives()
        bp.refresh()
        bp.log.setPlainText(
            "[09:14:02] Assembled volume_01/STELE (7.1 GB payload + 5% PAR2 recovery set)\n"
            "[09:14:05] Wrote Spec PDF, How-To PDF, 140mm Disc Label, and RESTORE.ps1\n"
            "[09:14:06] Ready: Blank BD-R M-DISC 25 GB · Burn speed 4x · Readback verify ON"
        )
        _grab(window, app, "ui_burn_pro.png")
        regions["ui_burn_pro"] = {
            "edition_badge": _rect_in_window(window, window.edition, dpr),
            "drives_box": _rect_in_window(window, bp.drives_box, dpr),
            "recovery_check": _rect_in_window(window, bp.recovery, dpr),
            "verify_check": _rect_in_window(window, bp.verify, dpr),
            "burn_button": _rect_in_window(window, bp.burn_button, dpr),
            "iso_button": _rect_in_window(window, bp.iso_button, dpr),
            "log_box": _rect_in_window(window, bp.log, dpr),
        }

        # -------------------------------------------------------------------
        # 4. Discover Page — Civitai Checkpoint / LoRA + Trigger Words
        # -------------------------------------------------------------------
        window.nav.setCurrentRow(0)
        dp.source.setCurrentIndex(1)  # Civitai
        dp.civitai_type.setCurrentIndex(2)  # LORA
        dp.query.setText("Architectural Linework Flux LoRA")
        dp._show_hits(
            [
                SearchHit(
                    repo_id="civitai/842109",
                    title="Architectural Linework Flux",
                    author="atelier_ink",
                    last_modified="2026-10-12",
                    downloads=18420,
                    likes=940,
                    pipeline_tag="LORA",
                    library_name="Flux.1 D",
                    gated=False,
                    approx_bytes=644_245_094,
                ),
                SearchHit(
                    repo_id="civitai/791044",
                    title="Technical Cutaway Illustration",
                    author="draftsman_ai",
                    last_modified="2026-09-29",
                    downloads=11200,
                    likes=610,
                    pipeline_tag="LORA",
                    library_name="SDXL 1.0",
                    gated=False,
                    approx_bytes=228_170_137,
                ),
            ]
        )
        dp.results.blockSignals(True)
        dp.results.selectRow(0)
        dp.results.blockSignals(False)
        dp._show_details(
            RepoDetails(
                repo_id="civitai/842109",
                sha="v918204",
                revision="918204",
                last_modified="2026-10-12",
                pipeline_tag="LORA",
                library_name="Flux.1 D",
                license_name="Civitai creator permissions (saved to civitai_model.json)",
                gated=False,
                card_excerpt=(
                    "Base model: Flux.1 D  ·  Trigger words: arch_linework, blueprint_etching\n"
                    "SHA-256 published by Civitai: 9f40c2b81e77...  ·  "
                    "Stele saves civitai_model.json beside the weights."
                ),
                files=[
                    HubFile("arch_linework_flux_v2.safetensors", 612_368_384),
                    HubFile("training_captions_sample.zip", 31_876_710),
                ],
                source="civitai",
                versions=[("v2.0 — Flux.1 D (918204)", "918204"), ("v1.0 — SDXL (804112)", "804112")],
                source_meta={
                    "name": "Architectural Linework Flux",
                    "training_files": ["training_captions_sample.zip"],
                },
            )
        )
        # Keep weights checked, training data unchecked (Stele default)
        c0 = dp.files.cellWidget(0, 0)
        c1 = dp.files.cellWidget(1, 0)
        if c0 is not None:
            c0.setChecked(True)
        if c1 is not None:
            c1.setChecked(False)
        dp.ack.setChecked(True)
        dp._replan()
        _grab(window, app, "ui_discover_civitai.png")
        regions["ui_discover_civitai"] = {
            "source_combo": _rect_in_window(window, dp.source, dpr),
            "civitai_type": _rect_in_window(window, dp.civitai_type, dpr),
            "detail_title": _rect_in_window(window, dp.title, dpr),
            "card_box": _rect_in_window(window, dp.card, dpr),
            "files_table": _rect_in_window(window, dp.files, dpr),
            "add_button": _rect_in_window(window, dp.add_button, dpr),
        }

        # -------------------------------------------------------------------
        # 5. Runtimes Page — Official Pinned Offline Packs
        # -------------------------------------------------------------------
        window.nav.setCurrentRow(4)
        rp = window.runtimes_page
        rp._fill()
        rp.table.selectRow(2)
        rp.notes.setText(
            "Official ggml-org/llama.cpp Windows x64 zip from GitHub release b11146. "
            "Archive only — Stele never executes installers."
        )
        _grab(window, app, "ui_runtimes.png")
        regions["ui_runtimes"] = {
            "table": _rect_in_window(window, rp.table, dpr),
            "recommend": _rect_in_window(window, rp.recommend_label, dpr),
        }

        # -------------------------------------------------------------------
        # 6. Settings Page (Pro) — Credential Manager + 3-Machine Offline-Safe License
        # -------------------------------------------------------------------
        window._open_settings()
        sp = window.settings_page
        sp.load()
        app.processEvents()
        # Scroll to bottom so Disc/PAR2 + Connections & License are centered
        bar = sp.sections_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
        _grab(window, app, "ui_settings_pro.png")
        regions["ui_settings_pro"] = {
            "edition_badge": _rect_in_window(window, window.edition, dpr),
            "license_status": _rect_in_window(window, sp.license_status, dpr),
            "recovery_spin": _rect_in_window(window, sp.recovery, dpr),
        }

        # -------------------------------------------------------------------
        # 7. Burn Page (Free Tier) — Single-Disc UDF ISO Export Unlocked
        # -------------------------------------------------------------------
        db.set_setting("license_status", "Free")
        window.update_license_display()
        window.nav.setCurrentRow(3)
        bp.selected_ids = [cat_qwen]
        bp.refresh()
        bp.log.setPlainText(
            "[Free tier] Search, SHA-256 download, Spec & How-To PDFs, and single-disc UDF ISO export are free.\n"
            "[Free tier] Export ISO also supports USB optical enclosures that Windows IMAPI2 cannot control."
        )
        _grab(window, app, "ui_burn_free.png")
        regions["ui_burn_free"] = {
            "edition_badge": _rect_in_window(window, window.edition, dpr),
            "iso_button": _rect_in_window(window, bp.iso_button, dpr),
            "burn_button": _rect_in_window(window, bp.burn_button, dpr),
            "log_box": _rect_in_window(window, bp.log, dpr),
        }

        window.close()
        db.close()

    meta_path = UI_CAPTURES_DIR / "ui_regions.json"
    meta_path.write_text(json.dumps(regions, indent=2), encoding="utf-8")
    print(f"Captured 7 HiDPI dark-mode Stele screens to {UI_CAPTURES_DIR}")
    return regions


if __name__ == "__main__":
    capture_all()
