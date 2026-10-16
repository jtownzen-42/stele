"""One window. Five sections. Settings sits on the gear, not in the nav list."""

from __future__ import annotations

import threading

from PySide6.QtCore import Qt, QSize
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
    QScrollArea,
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

from stele.ui.theme import STYLESHEET, PAGE_INFO, nav_icon, polish_tables


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
        self.resize(1360, 900)
        self.setMinimumSize(1100, 760)
        self.setStyleSheet(STYLESHEET)
        font = QFont("Segoe UI", 10)
        self.setFont(font)

        shell = QWidget()
        row = QHBoxLayout(shell)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(220)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 28, 0, 16)
        side_layout.setSpacing(6)
        brand = QWidget()
        brand_layout = QVBoxLayout(brand)
        brand_layout.setContentsMargins(26, 0, 20, 28)
        self.mark = QLabel("STELE")
        self.mark.setObjectName("brand")
        brand_layout.addWidget(self.mark)
        tagline = QLabel("Carve the model into stone.")
        tagline.setObjectName("brandNote")
        brand_layout.addWidget(tagline)
        side_layout.addWidget(brand)
        workspace_label = QLabel("   ARCHIVE WORKSPACE")
        workspace_label.setObjectName("eyebrow")
        workspace_label.setContentsMargins(14, 0, 0, 8)
        side_layout.addWidget(workspace_label)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setIconSize(QSize(20, 20))
        self.nav.setSpacing(2)
        for index, name in enumerate(NAV):
            item = QListWidgetItem(nav_icon(index), name, self.nav)
            item.setToolTip(PAGE_INFO[index][1])
        self.nav.currentRowChanged.connect(self._go)
        side_layout.addWidget(self.nav, 1)
        footer = QLabel("MODEL ARCHIVING\nBuilt for the long term.")
        footer.setObjectName("brandNote")
        footer.setContentsMargins(26, 10, 14, 10)
        side_layout.addWidget(footer)
        self.gear = QPushButton("Workspace settings")
        self.gear.setObjectName("gear")
        self.gear.clicked.connect(self._open_settings)
        side_layout.addWidget(self.gear)
        row.addWidget(side)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        header = QWidget()
        header.setObjectName("pageHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(28, 24, 28, 22)
        headings = QVBoxLayout()
        headings.setSpacing(5)
        self.breadcrumb = QLabel("WORKSPACE / DISCOVER")
        self.breadcrumb.setObjectName("eyebrow")
        self.page_title = QLabel()
        self.page_title.setObjectName("pageTitle")
        self.page_subtitle = QLabel()
        self.page_subtitle.setObjectName("pageSubtitle")
        self.page_subtitle.setWordWrap(True)
        for label in (self.breadcrumb, self.page_title, self.page_subtitle):
            headings.addWidget(label)
        header_layout.addLayout(headings, 1)
        self.edition = QLabel("Unactivated")
        self.edition.setObjectName("edition")
        self.edition.setToolTip("Activation status. Manage your existing license in Workspace settings.")
        header_layout.addWidget(self.edition, 0, Qt.AlignTop)
        content_layout.addWidget(header)
        self.stack = QStackedWidget()
        self.discover_page = DiscoverPage(self)
        self.queue_page = QueuePage(self)
        self.library_page = LibraryPage(self)
        self.burn_page = BurnPage(self)
        self.runtimes_page = RuntimesPage(self)
        self.settings_page = SettingsPage(self)
        for page in (
            self.discover_page, self.queue_page, self.library_page,
            self.burn_page, self.runtimes_page,
        ):
            page.layout().setContentsMargins(28, 22, 28, 24)
            page.layout().setSpacing(14)
            self.stack.addWidget(page)
        self.settings_scroll = QScrollArea()
        self.settings_scroll.setWidgetResizable(True)
        self.settings_scroll.setFrameShape(QScrollArea.NoFrame)
        self.settings_page.layout().setContentsMargins(28, 22, 28, 24)
        self.settings_scroll.setWidget(self.settings_page)
        self.stack.addWidget(self.settings_scroll)
        polish_tables(self.discover_page, {
            "results": "Find your next archive\nSearch by repository or keyword above.",
            "files": "Choose a model to inspect its files.",
        })
        polish_tables(self.queue_page, {
            "jobs": "Your queue is clear\nAdd a model from Discover or a pack from Runtimes.",
            "files": "Select a queued job to inspect file progress.",
        })
        polish_tables(self.library_page, {
            "table": "No archives match this view\nCompleted downloads appear here. Check your filters or start in Discover.",
            "burns": "No burns recorded yet.",
        })
        polish_tables(self.runtimes_page, {})
        content_layout.addWidget(self.stack, 1)
        row.addWidget(content, 1)
        self.setCentralWidget(shell)

        status = QStatusBar()
        self.setStatusBar(status)
        self._status = QLabel("Idle · Ready for your next archive")
        status.addWidget(self._status, 1)
        policy = QLabel("One file at a time  /  SHA-256 integrity")
        policy.setObjectName("brandNote")
        status.addPermanentWidget(policy)

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
            status_text = license_info(self.db).get("status") or "Licensed"
            self.setWindowTitle(f"Stele Studio [{status_text}]")
            self.edition.setText(status_text)
        else:
            self.setWindowTitle("Stele [Unactivated]")
            self.edition.setText("Unactivated")

    def _set_heading(self, index: int) -> None:
        title, subtitle = PAGE_INFO[index]
        self.page_title.setText(title)
        self.page_subtitle.setText(subtitle)
        name = NAV[index].upper() if index < len(NAV) else "SETTINGS"
        self.breadcrumb.setText(f"WORKSPACE / {name}")

    def nav_labels(self) -> list[str]:
        return [self.nav.item(i).text() for i in range(self.nav.count())]

    def _go(self, index: int) -> None:
        if index < 0:
            return
        self._set_heading(index)
        self.stack.setCurrentIndex(index)
        self.refresh_all()

    def _open_settings(self) -> None:
        self.nav.setCurrentRow(-1)
        self._set_heading(5)
        self.stack.setCurrentWidget(self.settings_scroll)
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
            if (page is current or (page is self.settings_page and current is self.settings_scroll)) and hasattr(page, "refresh"):
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
