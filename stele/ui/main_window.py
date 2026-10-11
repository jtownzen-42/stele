"""One window. Five sections. Settings sits on the gear, not in the nav list."""

from __future__ import annotations

import threading

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from stele.download.queue import Queue
from stele.download.worker import DownloadWorker
from stele.models import human_bytes
from stele.settings import Settings
from stele.ui.pages.burn_page import BurnPage
from stele.ui.pages.discover import DiscoverPage
from stele.ui.pages.library import LibraryPage
from stele.ui.pages.queue_page import QueuePage
from stele.ui.pages.runtimes import RuntimesPage
from stele.ui.pages.settings_page import SettingsPage

NAV = ("Discover", "Queue", "Library", "Burn", "Runtimes")

STYLESHEET = """
QMainWindow, QWidget { background: #1c1917; color: #fafaf9; font-family: "Segoe UI"; font-size: 13px; }
QListWidget#nav { background: #0c0a09; border: none; outline: none; }
QListWidget#nav::item { padding: 14px 18px; color: #fafaf9; }
QListWidget#nav::item:selected { background: #292524; color: #d97706; }
QPushButton { background: #292524; color: #fafaf9; border: 1px solid #44403c; padding: 6px 12px; }
QPushButton:disabled { color: #78716c; }
QPushButton#primary { background: #d97706; color: #1c1917; border: none; font-weight: 600; }
QPushButton#primary:disabled { background: #44403c; color: #a8a29e; }
QPushButton#gear { background: #0c0a09; border: none; color: #a8a29e; padding: 10px; text-align: left; }
QLineEdit, QComboBox, QPlainTextEdit, QTextEdit, QSpinBox {
    background: #292524; color: #fafaf9; border: 1px solid #44403c; padding: 4px;
    selection-background-color: #d97706; selection-color: #1c1917;
}
QTableWidget { background: #1c1917; color: #fafaf9; gridline-color: #44403c; border: 1px solid #44403c; }
QHeaderView::section { background: #0c0a09; color: #a8a29e; padding: 4px; border: none; }
QTableWidget::item:selected { background: #44403c; color: #fafaf9; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #e7e5e4; background: #292524; }
QCheckBox::indicator:checked { background: #d97706; border: 1px solid #d97706; }
QStatusBar { background: #0c0a09; color: #a8a29e; }
QLabel#muted { color: #a8a29e; }
QLabel#warning { color: #d97706; }
"""


class MainWindow(QMainWindow):
    def __init__(self, db, settings: Settings | None = None, start_worker: bool = True) -> None:
        super().__init__()
        self.db = db
        self.settings = settings or Settings(db)
        self.settings.ensure()
        self.queue = Queue(self.db, self.settings)
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.setWindowTitle("Stele")
        self.resize(1180, 760)
        self.setStyleSheet(STYLESHEET)
        font = QFont("Segoe UI", 10)
        self.setFont(font)

        shell = QWidget()
        row = QHBoxLayout(shell)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        side = QWidget()
        side.setFixedWidth(168)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(0)
        self.mark = QLabel("STELE")
        self.mark.setStyleSheet("background: #0c0a09; color: #fafaf9; padding: 16px 18px; font-size: 16px;")
        side_layout.addWidget(self.mark)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        for name in NAV:
            QListWidgetItem(name, self.nav)
        self.nav.currentRowChanged.connect(self._go)
        side_layout.addWidget(self.nav, 1)
        self.gear = QPushButton("Settings")
        self.gear.setObjectName("gear")
        self.gear.clicked.connect(self._open_settings)
        side_layout.addWidget(self.gear)
        row.addWidget(side)

        self.stack = QStackedWidget()
        self.discover_page = DiscoverPage(self)
        self.queue_page = QueuePage(self)
        self.library_page = LibraryPage(self)
        self.burn_page = BurnPage(self)
        self.runtimes_page = RuntimesPage(self)
        self.settings_page = SettingsPage(self)
        for page in (
            self.discover_page,
            self.queue_page,
            self.library_page,
            self.burn_page,
            self.runtimes_page,
            self.settings_page,
        ):
            self.stack.addWidget(page)
        row.addWidget(self.stack, 1)
        self.setCentralWidget(shell)

        status = QStatusBar()
        self.setStatusBar(status)
        self._status = QLabel("Idle")
        status.addWidget(self._status, 1)

        self.worker = None
        if start_worker:
            self.worker = DownloadWorker(self.queue, self.wake, self.stop)
            self.worker.thread.progress.connect(self._on_progress)
            self.worker.thread.changed.connect(self.refresh_all)
            self.worker.thread.message.connect(self._status.setText)
            self.worker.start()

        self.update_license_display()
        self.nav.setCurrentRow(0)

    def update_license_display(self) -> None:
        from stele.license import is_activated, license_info
        if is_activated(self.db):
            info = license_info(self.db)
            status_text = info.get("status") or "Licensed"
            self.setWindowTitle(f"Stele Studio [{status_text}]")
            self.mark.setText("STELE STUDIO")
            self.mark.setStyleSheet("background: #0c0a09; color: #d97706; padding: 16px 18px; font-size: 15px; font-weight: bold;")
        else:
            self.setWindowTitle("Stele [Unactivated]")
            self.mark.setText("STELE")
            self.mark.setStyleSheet("background: #0c0a09; color: #fafaf9; padding: 16px 18px; font-size: 16px;")

    def nav_labels(self) -> list[str]:
        return [self.nav.item(i).text() for i in range(self.nav.count())]

    def _go(self, index: int) -> None:
        if index < 0:
            return
        self.stack.setCurrentIndex(index)
        self.refresh_all()

    def _open_settings(self) -> None:
        self.nav.clearSelection()
        self.stack.setCurrentWidget(self.settings_page)
        self.settings_page.load()

    def kick(self) -> None:
        self.wake.set()

    def refresh_all(self) -> None:
        current = self.stack.currentWidget()
        for page in (
            self.discover_page,
            self.queue_page,
            self.library_page,
            self.burn_page,
            self.runtimes_page,
            self.settings_page,
        ):
            if page is current and hasattr(page, "refresh"):
                page.refresh()

    def _on_progress(self, payload: dict) -> None:
        file_total = payload.get("file_total")
        file_done = int(payload.get("file_done") or 0)
        rate = float(payload.get("rate") or 0)
        job_done = int(payload.get("job_done") or 0)
        job_total = int(payload.get("job_total") or 0)
        remaining = max(0, job_total - job_done) if job_total else 0
        rate_text = f"{human_bytes(int(rate))}/s" if rate else "…"
        self._status.setText(
            f"{payload.get('filename') or ''}  "
            f"{human_bytes(file_done)} / {human_bytes(file_total)}  "
            f"{rate_text}  remaining {human_bytes(remaining)}"
        )
        self.queue_page.refresh()

    def closeEvent(self, event) -> None:
        self.stop.set()
        self.wake.set()
        if self.worker is not None:
            self.worker.thread.wait(3000)
        super().closeEvent(event)
