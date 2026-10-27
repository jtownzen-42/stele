"""Completed vault items and past burns."""

from __future__ import annotations

import json
import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from stele.db import utc_now
from stele.docs.howto import build_howto, write_howto_markdown
from stele.docs.labels import write_case_insert, write_disc_face
from stele.docs.pdf import write_howto_pdf, write_spec_pdf
from stele.docs.spec import build_spec, write_spec_markdown
from stele.download.worker import hash_file
from stele.evidence.package import export_evidence
from stele.license import FEATURE_EVIDENCE, ProRequired, is_activated
from stele.models import NOT_LEGAL_ADVICE, human_bytes, safe_repo
from stele.ui.pages.burn_page import _Job


class LibraryPage(QWidget):
    def __init__(self, window) -> None:
        super().__init__()
        self.window = window
        self.rows: list[dict] = []
        self._evidence_job: _Job | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        filters = QHBoxLayout()
        self.text = QLineEdit()
        self.text.setPlaceholderText("Name")
        self.license = QLineEdit()
        self.license.setPlaceholderText("License")
        self.fmt = QLineEdit()
        self.fmt.setPlaceholderText("Format")
        self.disc = QLineEdit()
        self.disc.setPlaceholderText("Disc id")
        self.verify = QLineEdit()
        self.verify.setPlaceholderText("Verify status")
        for box in (self.text, self.license, self.fmt, self.disc, self.verify):
            box.returnPressed.connect(self.refresh)
            filters.addWidget(box)
        apply = QPushButton("Filter")
        apply.clicked.connect(self.refresh)
        filters.addWidget(apply)
        root.addLayout(filters)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Name", "Revision", "License", "Format", "Bytes", "When"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        root.addWidget(self.table, 2)

        actions = QHBoxLayout()
        for label, slot in (
            ("Open folder", self._open),
            ("Regenerate docs", self._regenerate),
            ("Add to burn set", self._add_burn),
            ("Export ISO", self._export),
            ("Export evidence", self._export_evidence),
        ):
            button = QPushButton(label)
            button.clicked.connect(slot)
            actions.addWidget(button)
        actions.addStretch(1)
        root.addLayout(actions)
        self.evidence_status = QLabel(NOT_LEGAL_ADVICE)
        self.evidence_status.setWordWrap(True)
        root.addWidget(self.evidence_status)

        root.addWidget(QLabel("Past burns"))
        self.burns = QTableWidget(0, 6)
        self.burns.setHorizontalHeaderLabels(["When", "Label", "Media", "Verify", "Result", "ISO"])
        root.addWidget(self.burns, 1)

    def refresh(self) -> None:
        self.rows = self.window.db.search_catalog(
            self.text.text(),
            self.license.text(),
            self.fmt.text(),
            self.disc.text(),
            self.verify.text(),
        )
        self.table.setRowCount(len(self.rows))
        for index, row in enumerate(self.rows):
            formats = row.get("formats_json") or ""
            values = [
                row["repo_id"],
                (row.get("commit_sha") or row.get("revision") or "")[:12],
                row.get("license_name") or "",
                formats,
                human_bytes(row.get("bytes")),
                row.get("created_utc") or "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                item.setData(Qt.UserRole, row["id"])
                self.table.setItem(index, col, item)
        self.table.resizeColumnsToContents()
        burns = self.window.db.list_burns()
        self.burns.setRowCount(len(burns))
        for index, burn in enumerate(burns):
            values = [
                burn.get("created_utc") or "",
                burn.get("disc_label") or "",
                burn.get("media_type") or "",
                burn.get("verify_status") or "",
                burn.get("result") or "",
                burn.get("iso_path") or "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                self.burns.setItem(index, col, item)
        self.burns.resizeColumnsToContents()

    def _selected(self) -> dict | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.rows):
            return None
        return self.rows[row]

    def _open(self) -> None:
        row = self._selected()
        if row is None:
            return
        path = Path(row["vault_path"])
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(path)  # noqa: S606 — opens the vault folder

    def _add_burn(self) -> None:
        row = self._selected()
        if row is None:
            return
        self.window.burn_page.add_catalog(int(row["id"]))
        self.window.nav.setCurrentRow(3)

    def _export(self) -> None:
        row = self._selected()
        if row is None:
            return
        self.window.burn_page.add_catalog(int(row["id"]))
        self.window.nav.setCurrentRow(3)
        self.window.burn_page.export_iso()

    def _export_evidence(self) -> None:
        row = self._selected()
        if row is None:
            QMessageBox.information(self, "Stele", "Select an item in the vault.")
            return
        if not is_activated(self.window.db):
            QMessageBox.information(self, "Stele", str(ProRequired(FEATURE_EVIDENCE)))
            return
        if self._evidence_job is not None and self._evidence_job.isRunning():
            QMessageBox.information(self, "Stele", "An evidence export is already running.")
            return
        default = self.window.settings.vault() / "EVIDENCE"
        default.mkdir(parents=True, exist_ok=True)
        chosen = QFileDialog.getExistingDirectory(self, "Save evidence ZIP to", str(default))
        if not chosen:
            return
        db = self.window.db
        vault = self.window.settings.vault()
        catalog_id = int(row["id"])
        self.evidence_status.setText(f"Hashing {row['repo_id']} for the evidence package...")
        job = _Job(lambda: export_evidence(db, vault, catalog_id, Path(chosen)))
        job.succeeded.connect(self._evidence_done)
        job.failed.connect(self._evidence_failed)
        job.blocked.connect(self._evidence_failed)
        self._evidence_job = job
        job.start()

    def _evidence_done(self, result) -> None:
        self.evidence_status.setText(NOT_LEGAL_ADVICE)
        if result.problems:
            QMessageBox.warning(
                self,
                "Stele",
                f"Evidence saved to {result.path}\n\n"
                "These files no longer match what Stele recorded when it archived them:\n"
                + "\n".join(result.problems[:20]),
            )
            return
        QMessageBox.information(
            self,
            "Stele",
            f"Timestamped evidence saved to {result.path}\n\nThe time comes from this PC's clock.\n{NOT_LEGAL_ADVICE}",
        )

    def _evidence_failed(self, text: str) -> None:
        self.evidence_status.setText(NOT_LEGAL_ADVICE)
        QMessageBox.warning(self, "Stele", text.splitlines()[0] if text else "Evidence export failed.")

    def _regenerate(self) -> None:
        row = self._selected()
        if row is None or row["kind"] != "model":
            QMessageBox.information(self, "Stele", "Select a model in the vault.")
            return
        revision_dir = Path(row["vault_path"])
        if not revision_dir.exists():
            QMessageBox.warning(self, "Stele", "The vault folder is missing.")
            return
        inventory = []
        weight_paths = []
        for path in sorted(revision_dir.rglob("*")):
            if not path.is_file() or path.name in ("SOURCE.txt", "checksums.sha256"):
                continue
            relative = path.relative_to(revision_dir).as_posix()
            digest = hash_file(path)
            inventory.append({"path": relative, "bytes": path.stat().st_size, "sha256": digest})
            weight_paths.append(path)
        config_path = revision_dir / "config.json"
        config = {}
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                config = {}
        safe = safe_repo(row["repo_id"])
        sha = str(row.get("commit_sha") or "")
        docs = self.window.settings.vault() / "DOCS"
        docs.mkdir(parents=True, exist_ok=True)
        spec = build_spec(
            repo_id=row["repo_id"],
            revision=str(row.get("revision") or ""),
            commit_sha=sha,
            snapshot_utc=utc_now(),
            license_name=str(row.get("license_name") or "unknown"),
            license_excerpt="",
            card_excerpt="",
            profile=str(row.get("profile") or ""),
            pipeline_tag="",
            library_name="",
            config=config if isinstance(config, dict) else {},
            inventory=inventory,
            weight_paths=weight_paths,
        )
        howto = build_howto(
            repo_id=row["repo_id"],
            commit_sha=sha,
            safe_id=safe,
            profile=str(row.get("profile") or ""),
            license_name=spec.license_name,
            library_name="",
            facts=spec.facts,
            gguf_paths=[item["path"] for item in inventory if item["path"].lower().endswith(".gguf")],
        )
        write_spec_markdown(spec, docs / f"{safe}_spec.md")
        write_howto_markdown(howto, docs / f"{safe}_howto.md")
        write_spec_pdf(spec, docs / f"{safe}_spec.pdf")
        write_howto_pdf(howto, docs / f"{safe}_howto.pdf")
        write_disc_face(
            docs / f"{safe}_disc_face.pdf",
            model_ids=[row["repo_id"]],
            commit_short=sha[:12],
            when=spec.snapshot_utc[:10],
            volume=1,
            count=1,
        )
        write_case_insert(
            docs / f"{safe}_case_insert.pdf",
            model_ids=[row["repo_id"]],
            license_name=spec.license_name,
            summary=spec.summary_line(),
            checksum_prefixes=[item["sha256"][:12] for item in inventory if item["sha256"]][:12],
        )
        QMessageBox.information(self, "Stele", f"Docs rewritten in {docs}")
