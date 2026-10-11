"""The single active job, the files inside it, and the jobs waiting behind it."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from stele.models import human_bytes


class QueuePage(QWidget):
    def __init__(self, window) -> None:
        super().__init__()
        self.window = window
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.addWidget(QLabel("One job runs. One file transfers. The rest wait."))
        buttons = QHBoxLayout()
        for label, slot in (
            ("Pause", self._pause),
            ("Resume", self._resume),
            ("Cancel", self._cancel),
            ("Purge incomplete", self._purge),
            ("Up", lambda: self._move(-1)),
            ("Down", lambda: self._move(1)),
            ("Retry failed file", self._retry),
        ):
            button = QPushButton(label)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        buttons.addStretch(1)
        root.addLayout(buttons)
        self.jobs = QTableWidget(0, 6)
        self.jobs.setHorizontalHeaderLabels(["#", "Kind", "Name", "Profile", "Status", "Bytes"])
        self.jobs.setSelectionBehavior(QTableWidget.SelectRows)
        self.jobs.itemSelectionChanged.connect(self._show_files)
        root.addWidget(self.jobs, 1)
        self.files = QTableWidget(0, 5)
        self.files.setHorizontalHeaderLabels(["File", "Status", "Bytes", "SHA-256", "Error"])
        root.addWidget(self.files, 1)

    def refresh(self) -> None:
        selected = self._selected_job()
        rows = self.window.db.list_jobs()
        self.jobs.blockSignals(True)
        self.jobs.setRowCount(len(rows))
        for index, job in enumerate(rows):
            values = [
                str(job["position"]),
                job["kind"],
                job["repo_id"],
                job.get("profile") or "",
                job["status"],
                f"{human_bytes(job.get('bytes_done'))} / {human_bytes(job.get('bytes_total'))}",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                item.setData(Qt.UserRole, job["id"])
                self.jobs.setItem(index, col, item)
            if selected is not None and int(job["id"]) == selected:
                self.jobs.selectRow(index)
        self.jobs.blockSignals(False)
        self.jobs.resizeColumnsToContents()
        self._show_files()

    def _selected_job(self) -> int | None:
        row = self.jobs.currentRow()
        item = self.jobs.item(row, 0) if row >= 0 else None
        if item is None:
            return None
        return int(item.data(Qt.UserRole))

    def _show_files(self) -> None:
        job_id = self._selected_job()
        files = self.window.db.list_files(job_id) if job_id else []
        self.files.setRowCount(len(files))
        for index, file_row in enumerate(files):
            values = [
                file_row["relative_path"],
                file_row["status"],
                f"{human_bytes(file_row.get('bytes_downloaded'))} / {human_bytes(file_row.get('size'))}",
                (file_row.get("sha256") or "")[:12],
                file_row.get("error") or "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                item.setData(Qt.UserRole, file_row["id"])
                self.files.setItem(index, col, item)
        self.files.resizeColumnsToContents()

    def _pause(self) -> None:
        self.window.queue.pause()
        self.window.kick()
        self.refresh()

    def _resume(self) -> None:
        job_id = self._selected_job()
        if job_id is None:
            holder = self.window.db.holding_job()
            job_id = int(holder["id"]) if holder else None
        if job_id is None:
            return
        error = self.window.queue.resume(job_id)
        if error:
            QMessageBox.information(self, "Stele", error)
        self.window.kick()
        self.refresh()

    def _cancel(self) -> None:
        job_id = self._selected_job()
        if job_id is None:
            return
        self.window.queue.cancel(job_id)
        self.window.kick()
        self.refresh()

    def _purge(self) -> None:
        job_id = self._selected_job()
        if job_id is None:
            return
        answer = QMessageBox.question(
            self,
            "Purge incomplete",
            "Delete unfinished files for this job? Finished files stay.",
        )
        if answer != QMessageBox.Yes:
            return
        removed = self.window.queue.purge_incomplete(job_id)
        QMessageBox.information(self, "Stele", f"Removed {len(removed)} incomplete file(s).")
        self.refresh()

    def _move(self, direction: int) -> None:
        job_id = self._selected_job()
        if job_id is None:
            return
        self.window.queue.reorder(job_id, direction)
        self.refresh()

    def _retry(self) -> None:
        row = self.files.currentRow()
        item = self.files.item(row, 0) if row >= 0 else None
        if item is None:
            return
        self.window.queue.retry_file(int(item.data(Qt.UserRole)))
        self.window.kick()
        self.refresh()
