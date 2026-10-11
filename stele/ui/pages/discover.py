"""Search the Hub, preview a profile, acknowledge the license, queue one job."""

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

from stele.credentials import clear_token, get_token, set_token, token_status
from stele.db import utc_now
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
        for box in (self.pipeline, self.library, self.license, self.gated, self.format_box):
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
        self.title = QLabel("Select a model")
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
        self.ack = QCheckBox("I acknowledge this license. Stele does not grant redistribution rights.")
        self.ack.stateChanged.connect(self._replan)
        detail_layout.addWidget(self.ack)
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

    def search(self) -> None:
        query = self.query.text().strip()
        if not query:
            return
        self.notice.setText("Searching…")
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
        revision = self.revision.currentText() or "main"

        def work():
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
                hit.repo_id,
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
        self.title.setText(f"{details.repo_id}  ·  {details.sha[:12]}  ·  {details.license_name}")
        if details.gated and not get_token():
            self.notice.setText(MSG_GATED)
        else:
            self.notice.setText("")
        self.card.setPlainText(
            f"License: {details.license_name}\n\n{details.card_excerpt or 'No model card text.'}"
        )
        self.revision.blockSignals(True)
        current = details.revision or "main"
        if self.revision.findText(current) < 0:
            self.revision.addItem(current)
        self.revision.setCurrentText(current)
        self.revision.blockSignals(False)
        chosen = default_gguf(details.files)
        self.files.setRowCount(len(details.files))
        for row, hub_file in enumerate(details.files):
            if is_gguf(hub_file.path):
                box = QCheckBox()
                box.setChecked(hub_file.path == chosen)
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
        profile = self.profile.currentText()
        plan = plan_profile(
            profile,
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
            )
        except Exception as exc:
            self.notice.setText(str(exc))
            QMessageBox.warning(self, "Stele", str(exc))
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
