"""Search Hugging Face or Civitai, preview the files, acknowledge the license, queue one job."""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from stele.credentials import clear_token, get_civitai_key, get_token, set_token, token_status
from stele.db import utc_now
from stele.hub.civitai import CivitaiClient, default_selection, is_civitai, plan_civitai
from stele.hub.client import HubClient, HubError
from stele.hub.planner import default_gguf, is_gguf, plan_profile
from stele.hub.search import search_models
from stele.models import (
    MSG_GATED,
    PROFILE_GGUF,
    PROFILE_INFERENCE,
    PROFILES,
    HubFile,
    RepoDetails,
    SearchHit,
    human_bytes,
)


class _Call(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, fn) -> None:
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        try:
            self.finished_ok.emit(self._fn())
        except Exception as exc:
            self.failed.emit(str(exc))


class DiscoverPage(QWidget):
    def __init__(self, window) -> None:
        super().__init__()
        self.window = window
        self.hits: list[SearchHit] = []
        self.details: RepoDetails | None = None
        self._thread: _Call | None = None
        self._generation = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(8)

        top = QHBoxLayout()
        self.source = QComboBox()
        self.source.addItem("Hugging Face", "huggingface")
        self.source.addItem("Civitai", "civitai")
        self.source.currentIndexChanged.connect(self._source_changed)
        top.addWidget(self.source)
        self.query = QLineEdit()
        self.query.setPlaceholderText("Repository id or keywords")
        self.query.returnPressed.connect(self.search)
        top.addWidget(self.query, 1)
        search = QPushButton("Search")
        search.setObjectName("primary")
        search.clicked.connect(self.search)
        top.addWidget(search)
        self.token_label = QLabel(token_status())
        self.token_label.setObjectName("muted")
        top.addWidget(self.token_label)
        save = QPushButton("Save token")
        save.clicked.connect(self._save_token)
        clear = QPushButton("Clear token")
        clear.clicked.connect(self._clear_token)
        top.addWidget(save)
        top.addWidget(clear)
        root.addLayout(top)

        filters = QHBoxLayout()
        self.pipeline = _combo(["", "text-generation", "text2text-generation", "image-text-to-text"], "Pipeline")
        self.library = _combo(["", "transformers", "gguf", "diffusers"], "Library")
        self.license = _combo(["", "apache-2.0", "mit", "llama3", "gemma"], "License")
        self.gated = _combo(["", "gated", "ungated"], "Gated")
        self.format_box = _combo(["", "gguf", "safetensors"], "Format")
        self.civitai_type = _combo(
            ["", "Checkpoint", "LORA", "LoCon", "TextualInversion", "VAE", "Controlnet", "Upscaler"], "Type"
        )
        self.civitai_type.setVisible(False)
        for box in (self.pipeline, self.library, self.license, self.gated, self.format_box, self.civitai_type):
            filters.addWidget(box)
        root.addLayout(filters)

        split = QSplitter()
        self.results = QTableWidget(0, 5)
        self.results.setHorizontalHeaderLabels(["Repository", "Author", "Updated", "Size", "Gated"])
        self.results.setSelectionBehavior(QTableWidget.SelectRows)
        self.results.setSelectionMode(QTableWidget.SingleSelection)
        self.results.itemSelectionChanged.connect(self._open_selected)
        split.addWidget(self.results)

        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(8, 0, 0, 0)
        self.title = QLabel("Archive preview")
        self.title.setStyleSheet("font-size: 16px; font-weight: 600;")
        self.title.setWordWrap(True)
        detail_layout.addWidget(self.title)
        self.notice = QLabel("")
        self.notice.setObjectName("warning")
        self.notice.setWordWrap(True)
        detail_layout.addWidget(self.notice)
        self.card = QTextEdit()
        self.card.setReadOnly(True)
        self.card.setPlaceholderText("Model card excerpt and license")
        detail_layout.addWidget(self.card, 1)

        rev_row = QHBoxLayout()
        rev_row.addWidget(QLabel("Revision"))
        self.revision = QComboBox()
        self.revision.addItem("main")
        self.revision.currentTextChanged.connect(self._revision_changed)
        rev_row.addWidget(self.revision, 1)
        rev_row.addWidget(QLabel("Profile"))
        self.profile = QComboBox()
        self.profile.addItems(PROFILES[:3])
        self.profile.setCurrentText(PROFILE_GGUF)
        self.profile.currentTextChanged.connect(self._replan)
        rev_row.addWidget(self.profile, 1)
        detail_layout.addLayout(rev_row)

        self.files = QTableWidget(0, 3)
        self.files.setHorizontalHeaderLabels(["Include", "File", "Size"])
        self.files.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.files.setColumnWidth(0, 72)
        self.files.cellClicked.connect(self._toggle_include)
        detail_layout.addWidget(self.files, 2)

        self.preview = QLabel("File list, total bytes, and disc estimate appear here.")
        self.preview.setWordWrap(True)
        self.preview.setObjectName("muted")
        detail_layout.addWidget(self.preview)
        self.ack = QCheckBox("I acknowledge the model license")
        self.ack.setToolTip("Stele does not grant redistribution rights.")
        self.ack.stateChanged.connect(self._replan)
        detail_layout.addWidget(self.ack)
        disclaimer = QLabel("Stele does not grant redistribution rights.")
        disclaimer.setObjectName("muted")
        disclaimer.setWordWrap(True)
        detail_layout.addWidget(disclaimer)
        self.add_button = QPushButton("Add to Queue")
        self.add_button.setObjectName("primary")
        self.add_button.setEnabled(False)
        self.add_button.clicked.connect(self._enqueue)
        detail_layout.addWidget(self.add_button)
        split.addWidget(detail)
        split.setSizes([420, 640])
        root.addWidget(split, 1)
        self._plan = None

    def refresh(self) -> None:
        self.token_label.setText(token_status())
        preferred = self.window.settings.default_profile()
        if preferred in (PROFILE_GGUF, PROFILE_INFERENCE, "Full repo"):
            self.profile.setCurrentText(preferred)

    def _civitai(self) -> bool:
        return self.source.currentData() == "civitai"

    def _source_changed(self, _index: int) -> None:
        civitai = self._civitai()
        for box in (self.pipeline, self.library, self.license, self.gated, self.format_box):
            box.setVisible(not civitai)
        self.civitai_type.setVisible(civitai)
        self.query.setPlaceholderText(
            "Model name, id, or civitai.com link" if civitai else "Repository id or keywords"
        )
        self.revision.blockSignals(True)
        self.revision.clear()
        if not civitai:
            self.revision.addItem("main")
        self.revision.blockSignals(False)
        self.hits = []
        self.details = None
        self.results.setRowCount(0)
        self.files.setRowCount(0)
        self._replan()

    def search(self) -> None:
        query = self.query.text().strip()
        if not query:
            return
        self.notice.setText("Searching…")
        if self._civitai():
            model_type = str(self.civitai_type.currentData() or "")

            def civitai_work():
                return CivitaiClient(get_civitai_key()).search(query, model_type=model_type)

            self._start(civitai_work, self._show_hits)
            return
        pipeline = str(self.pipeline.currentData() or "")
        library = str(self.library.currentData() or "")
        license_id = str(self.license.currentData() or "")
        gated = str(self.gated.currentData() or "")
        fmt = str(self.format_box.currentData() or "")

        def work():
            client = HubClient(get_token())
            hits = search_models(
                client,
                query,
                pipeline_tag=pipeline,
                library=library,
                license_id=license_id,
                gated=gated,
                format_present=fmt,
            )
            if not hits and "/" in query:
                details = client.details(query)
                hits = [
                    SearchHit(
                        repo_id=details.repo_id,
                        author=details.repo_id.split("/")[0],
                        last_modified=details.last_modified,
                        downloads=None,
                        likes=None,
                        pipeline_tag=details.pipeline_tag,
                        library_name=details.library_name,
                        gated=details.gated,
                        tags=[],
                    )
                ]
            return hits

        self._start(work, self._show_hits)

    def _open_selected(self) -> None:
        row = self.results.currentRow()
        if row < 0 or row >= len(self.hits):
            return
        hit = self.hits[row]
        revision = str(self.revision.currentData() or self.revision.currentText() or "main")

        def work():
            if is_civitai(hit.repo_id):
                return CivitaiClient(get_civitai_key()).details(hit.repo_id, revision)
            return HubClient(get_token()).details(hit.repo_id, revision)

        self.notice.setText("Loading files…")
        self._start(work, self._show_details)

    def _revision_changed(self, _text: str) -> None:
        if self.details is not None and self.sender() is self.revision:
            self._open_selected()

    def _show_hits(self, hits: list[SearchHit]) -> None:
        self.hits = hits
        self.notice.setText("" if hits else "No repositories matched.")
        self.results.setRowCount(len(hits))
        for row, hit in enumerate(hits):
            values = [
                f"{hit.title} ({hit.repo_id})" if hit.title else hit.repo_id,
                hit.author,
                hit.last_modified,
                human_bytes(hit.approx_bytes),
                "gated" if hit.gated else "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                self.results.setItem(row, col, item)
        self.results.resizeColumnsToContents()

    def _show_details(self, details: RepoDetails) -> None:
        self.details = details
        civitai = details.source == "civitai"
        name = details.source_meta.get("name") if civitai else ""
        self.title.setText(
            f"{name}  ·  {details.repo_id}  ·  {details.sha}"
            if civitai
            else f"{details.repo_id}  ·  {details.sha[:12]}  ·  {details.license_name}"
        )
        self.profile.setEnabled(not civitai)
        if details.gated and not get_token():
            self.notice.setText(MSG_GATED)
        else:
            self.notice.setText("")
        self.card.setPlainText(
            f"License: {details.license_name}\n\n{details.card_excerpt or 'No model card text.'}"
        )
        self.revision.blockSignals(True)
        if civitai:
            self.revision.clear()
            for label, value in details.versions:
                self.revision.addItem(label, value)
            index = self.revision.findData(details.revision)
            if index >= 0:
                self.revision.setCurrentIndex(index)
        else:
            current = details.revision or "main"
            if self.revision.findText(current) < 0:
                self.revision.addItem(current)
            self.revision.setCurrentText(current)
        self.revision.blockSignals(False)
        chosen = default_gguf(details.files)
        ticked = set(default_selection(details)) if civitai else set()
        self.files.setRowCount(len(details.files))
        for row, hub_file in enumerate(details.files):
            if civitai or is_gguf(hub_file.path):
                box = QCheckBox()
                box.setChecked(hub_file.path in ticked if civitai else hub_file.path == chosen)
                box.toggled.connect(self._replan)
                self.files.setCellWidget(row, 0, box)
            name = QTableWidgetItem(hub_file.path)
            name.setFlags(name.flags() & ~Qt.ItemIsEditable)
            size = QTableWidgetItem(human_bytes(hub_file.size))
            size.setFlags(size.flags() & ~Qt.ItemIsEditable)
            self.files.setItem(row, 1, name)
            self.files.setItem(row, 2, size)
        self.files.resizeColumnToContents(1)
        self.files.resizeColumnToContents(2)
        self._replan()

    def _selected_gguf(self) -> list[str]:
        chosen = []
        for row in range(self.files.rowCount()):
            box = self.files.cellWidget(row, 0)
            name = self.files.item(row, 1)
            if isinstance(box, QCheckBox) and box.isChecked() and name is not None:
                chosen.append(name.text())
        return chosen

    def _toggle_include(self, row: int, column: int) -> None:
        if column == 0:
            return
        box = self.files.cellWidget(row, 0)
        if isinstance(box, QCheckBox):
            box.toggle()

    def _replan(self, *_args) -> None:
        if self.details is None:
            self.add_button.setEnabled(False)
            return
        if self.details.source == "civitai":
            plan = plan_civitai(
                self.details.files,
                self._selected_gguf(),
                capacity_bytes=self.window.settings.capacity_bytes(),
            )
        else:
            plan = plan_profile(
                self.profile.currentText(),
                self.details.files,
                selected_gguf=self._selected_gguf(),
                capacity_bytes=self.window.settings.capacity_bytes(),
            )
        self._plan = plan
        lines = [f"{human_bytes(item.size):>10}  {item.path}" for item in plan.files]
        head = f"{len(plan.files)} files · {human_bytes(plan.total_bytes)}"
        if plan.disc_estimate:
            head += f" · about {plan.disc_estimate} disc(s)"
        if plan.fallback_note:
            head += f"\n{plan.fallback_note}"
        if plan.blocked_reason and plan.blocked_reason != plan.fallback_note:
            head += f"\n{plan.blocked_reason}"
        self.preview.setText(head + ("\n" + "\n".join(lines[:40]) if lines else ""))
        blocked = bool(plan.blocked_reason) or not plan.files
        gated = bool(self.details.gated and not get_token())
        ready = self.ack.isChecked() and not blocked and not gated and bool(self.details.sha)
        self.add_button.setEnabled(ready)
        if ready:
            self.add_button.setToolTip("")
        elif not self.ack.isChecked():
            self.add_button.setToolTip("Acknowledge the license first.")
        elif gated:
            self.add_button.setToolTip(MSG_GATED)
        elif not self.details.sha:
            self.add_button.setToolTip("This revision has no commit SHA yet.")
        else:
            self.add_button.setToolTip(plan.blocked_reason or "Nothing to queue.")

    def _enqueue(self) -> None:
        if self.details is None or self._plan is None:
            return
        try:
            self.window.queue.enqueue_model(
                repo_id=self.details.repo_id,
                revision=self.details.revision,
                commit_sha=self.details.sha,
                profile=self._plan.profile_used,
                license_name=self.details.license_name,
                license_excerpt=self.card.toPlainText()[:500],
                license_ack_utc=utc_now() if self.ack.isChecked() else None,
                card_excerpt=self.details.card_excerpt,
                pipeline_tag=self.details.pipeline_tag,
                library_name=self.details.library_name,
                files=self._plan.files,
                source=self.details.source,
                download_urls=self.details.download_urls,
                source_meta=self.details.source_meta,
            )
        except Exception as exc:
            self.notice.setText(str(exc))
            QMessageBox.warning(self, "Stele", str(exc))
            return
        if self.details.source == "civitai":
            self.notice.setText(f"Queued {self.details.source_meta.get('name') or self.details.repo_id}.")
            self.window.kick()
            self.window.nav.setCurrentRow(1)
            return
        fmt = "gguf" if any(is_gguf(item.path) for item in self._plan.files) else "other"
        if self._plan.profile_used == PROFILE_INFERENCE:
            fmt = "safetensors"
        if any(is_gguf(item.path) for item in self._plan.files):
            fmt = "gguf"
        self.window.settings.set_last_format(fmt)
        self.notice.setText(f"Queued {self.details.repo_id}.")
        self.window.kick()
        self.window.nav.setCurrentRow(1)

    def _save_token(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        token, ok = QInputDialog.getText(
            self, "Hugging Face token", "Token (write-only):", QLineEdit.EchoMode.Password
        )
        if not ok:
            return
        try:
            set_token(token)
        except Exception as exc:
            self.notice.setText(str(exc))
            return
        self.token_label.setText(token_status())
        self.notice.setText("Token stored in Windows Credential Manager.")

    def _clear_token(self) -> None:
        clear_token()
        self.token_label.setText(token_status())
        self.notice.setText("Token cleared.")

    def _start(self, fn, ok) -> None:
        self._generation += 1
        generation = self._generation
        thread = _Call(fn)

        def accept(value) -> None:
            if generation == self._generation:
                ok(value)

        def fail(message: str) -> None:
            if generation == self._generation:
                self.notice.setText(message)

        thread.finished_ok.connect(accept)
        thread.failed.connect(fail)
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        thread.start()


def _combo(values: list[str], label: str) -> QComboBox:
    box = QComboBox()
    for value in values:
        box.addItem(value or f"Any {label.lower()}", value)
    return box
