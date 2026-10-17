"""Render 1280x720 listing screenshots with a throwaway demo database (sample data, no network).

    python scripts/make_listing_screenshots.py OUT_DIR

The model names are real public Hugging Face repositories; sizes, dates and history are sample data
for illustration. Run it on Windows for native fonts; headless Linux renders use fallback fonts.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QTableWidgetItem  # noqa: E402

import stele.license as lic  # noqa: E402
from stele.db import Database  # noqa: E402
from stele.ui.main_window import MainWindow  # noqa: E402

GB = 1024 ** 3
MODELS = [
    ("Qwen/Qwen2.5-7B-Instruct-GGUF", "apache-2.0", "gguf", int(4.68 * GB), 3),
    ("microsoft/Phi-3-mini-4k-instruct-gguf", "mit", "gguf", int(2.39 * GB), 2),
    ("bartowski/Meta-Llama-3.1-8B-Instruct-GGUF", "llama3.1", "gguf", int(4.92 * GB), 3),
    ("mistralai/Mistral-7B-Instruct-v0.3", "apache-2.0", "safetensors", int(14.5 * GB), 7),
]


def seed(db: Database, vault: Path) -> list[int]:
    ids = []
    for i, (repo, lic_name, fmt, size, count) in enumerate(MODELS):
        ids.append(db.insert_catalog({
            "kind": "model", "repo_id": repo, "revision": "main",
            "commit_sha": hashlib.sha1(repo.encode()).hexdigest(), "profile": "GGUF inference pack" if fmt == "gguf" else "Inference pack",
            "license_name": lic_name, "vault_path": str(vault / repo.replace("/", "--")),
            "bytes": size, "file_count": count, "formats_json": fmt,
        }))
    db.insert_burn({"drive_name": "BD-RE BH16NS40", "media_type": "BD-R M-DISC 25 GB", "disc_label": "STELE_QWEN25_7B",
                    "volume_index": 1, "volume_count": 1, "verify_status": "full", "result": "ok",
                    "catalog_ids_json": json.dumps([ids[0]])})
    job = db.insert_job({"kind": "model", "repo_id": "google/gemma-2-9b-it", "revision": "main",
                         "commit_sha": "11c9b309abf73637e4b6f9a3fa1e92e615547819", "profile": "Inference pack",
                         "license_name": "gemma", "license_ack_utc": "2026-10-17T10:00:00Z",
                         "bytes_total": int(18.5 * GB)},
                        [{"relative_path": f"model-0000{n}-of-00004.safetensors", "size": int(4.9 * GB)} for n in range(1, 5)]
                        + [{"relative_path": "config.json", "size": 857}, {"relative_path": "tokenizer.json", "size": 17_525_357}])
    files = db.list_files(job)
    with db._lock:
        db._conn.execute("UPDATE jobs SET status='downloading', bytes_done=? WHERE id=?", (int(7.3 * GB), job))
        db._conn.execute("UPDATE job_files SET status='done', bytes_downloaded=size, sha256=? WHERE id IN (?, ?)",
                         ("9f2c" * 16, files[4]["id"], files[5]["id"]))
        db._conn.execute("UPDATE job_files SET status='done', bytes_downloaded=size, sha256=? WHERE id=?", ("4ab1" * 16, files[0]["id"]))
        db._conn.execute("UPDATE job_files SET status='downloading', bytes_downloaded=? WHERE id=?", (int(2.4 * GB), files[1]["id"]))
        db._conn.commit()
    db.insert_job({"kind": "runtime", "repo_id": "llama.cpp Windows x64 CPU", "profile": "Runtime kit",
                   "license_ack_utc": "2026-10-17T10:00:00Z", "bytes_total": 17_700_000},
                  [{"relative_path": "llama-b11146-bin-win-cpu-x64.zip", "size": 17_700_000}])
    return ids


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    db = Database(tmp / "demo.db")
    ids = seed(db, tmp / "vault")
    db.set_setting(lic.KEY_LICENSE_STATUS, "Pro")
    db.set_setting(lic.KEY_LICENSE_VERIFIED, lic._stamp(lic._now()))
    db.set_setting(lic.KEY_LICENSE_EMAIL, "you@example.com")
    db.set_setting(lic.KEY_LICENSE_KEY, "ABCD...F00D")

    app = QApplication(["Stele"])
    app.setStyle("Fusion")
    w = MainWindow(db, start_worker=False)
    w.setMinimumSize(1100, 700)  # listing images are 1280x720
    w.resize(1280, 720)
    w.show()
    app.processEvents()
    w.update_license_display()
    for cid in ids[:2]:
        w.burn_page.add_catalog(cid)

    d = w.discover_page
    hits = [("Qwen/Qwen2.5-7B-Instruct-GGUF", "Qwen", "2025-01-08", "60.3 GB", "no"),
            ("Qwen/Qwen2.5-14B-Instruct-GGUF", "Qwen", "2025-01-08", "136 GB", "no"),
            ("Qwen/Qwen2.5-3B-Instruct-GGUF", "Qwen", "2025-01-08", "27.1 GB", "no"),
            ("Qwen/Qwen2.5-Coder-7B-Instruct-GGUF", "Qwen", "2025-01-08", "60.3 GB", "no")]

    def fill_discover():
        d.query.setText("Qwen2.5 Instruct GGUF")
        for splitter in d.findChildren(__import__("PySide6.QtWidgets", fromlist=["QSplitter"]).QSplitter):
            splitter.setSizes([470, 530])
        d.results.setColumnWidth(0, 230)
        d.files.setColumnWidth(1, 330)
        d.results.setRowCount(len(hits))
        for r, row in enumerate(hits):
            for c, v in enumerate(row):
                d.results.setItem(r, c, QTableWidgetItem(v))
        d.results.selectRow(0) if False else None
        d.title.setText("Qwen/Qwen2.5-7B-Instruct-GGUF")
        d.card.setPlainText("Qwen2.5 is the latest series of Qwen large language models. This repo contains the "
                            "instruction-tuned 7B model in GGUF format.\n\nLicense: apache-2.0")
        files = [("qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf", "3.99 GB"),
                 ("qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf", "687 MB"), ("README.md", "6.2 KB")]
        d.files.setRowCount(len(files))
        for r, (name, size) in enumerate(files):
            chk = QTableWidgetItem("Yes")
            d.files.setItem(r, 0, chk)
            d.files.setItem(r, 1, QTableWidgetItem(name))
            d.files.setItem(r, 2, QTableWidgetItem(size))
        d.preview.setText("3 files, 4.68 GB. Fits on one BD 25 GB disc.")
        d.ack.setChecked(True)
        d.add_button.setEnabled(True)

    shots = [("1-discover", 0, "light", fill_discover), ("2-queue", 1, "dark", None),
             ("3-library", 2, "light", None), ("4-burn", 3, "dark", None)]
    for name, index, scheme, prep in shots:
        w.apply_scheme(scheme)
        w.nav.setCurrentRow(index)
        app.processEvents()
        if prep:
            prep()
        if index == 1:
            w.queue_page.refresh()
            w.queue_page.jobs.selectRow(0)
        if index == 2:
            w.library_page.refresh()
        if index == 3:
            b = w.burn_page
            b.refresh()
            b.drives_box.blockSignals(True)
            b.drives_box.clear()
            b.drives_box.addItem("E:  BD-RE writer (sample)")
            b.drives_box.setCurrentIndex(0)
            b.drives_box.blockSignals(False)
            b.media.setText("Blank BD-R in drive. 25.0 GB available; this set needs 7.1 GB on 1 disc.")
            b.log.clear()
            b.log.setPlainText("Ready. 2 vault items selected.")
        for size in ((1281, 720), (1280, 720)):
            w.resize(*size)
            app.processEvents()
        w.grab().save(str(out / f"stele-{name}-{scheme}.png"))
    w.apply_scheme("light")
    w.gear.click()
    app.processEvents()
    sp = w.settings_page
    sp.vault.setText(r"C:\Users\you\Stele\vault")
    sp.staging.setText(r"C:\Users\you\Stele\staging")
    for size in ((1281, 720), (1280, 720)):
        w.resize(*size)
        app.processEvents()
    w.grab().save(str(out / "stele-5-settings-light.png"))
    print("saved", sorted(p.name for p in out.glob("*.png")))


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "listing-screenshots"))
