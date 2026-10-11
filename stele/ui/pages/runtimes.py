"""Official packs only. Add to the same serial queue. Never execute."""

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
from stele.runtime.catalog import load_packs, recommend


class RuntimesPage(QWidget):
    def __init__(self, window) -> None:
        super().__init__()
        self.window = window
        self.packs = list(load_packs())
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        self.recommend_label = QLabel("")
        self.recommend_label.setWordWrap(True)
        root.addWidget(self.recommend_label)
        note = QLabel("These files are archived and never executed. Sources are the frozen official manifest.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        root.addWidget(note)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Include", "Pack", "Version", "Size", "File"])
        self.table.itemChanged.connect(self._toggle)
        root.addWidget(self.table, 1)
        self.notes = QLabel("")
        self.notes.setWordWrap(True)
        self.notes.setObjectName("muted")
        root.addWidget(self.notes)
        row = QHBoxLayout()
        add = QPushButton("Add to Queue")
        add.setObjectName("primary")
        add.clicked.connect(self._enqueue)
        row.addWidget(add)
        row.addStretch(1)
        root.addLayout(row)
        self._fill()

    def refresh(self) -> None:
        fmt = self.window.settings.last_format()
        order = recommend(fmt)
        if order:
            names = [pack["display"] for pack in self.packs if pack["id"] in order]
            self.recommend_label.setText(
                "Last model format was GGUF. Recommended order: " + ", ".join(names) + "."
            )
        else:
            self.recommend_label.setText(
                "No runtime is recommended until you queue a GGUF model. Packs stay selectable."
            )

    def _fill(self) -> None:
        included = set(self.window.settings.burn_runtime_ids())
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.packs))
        for row, pack in enumerate(self.packs):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            check.setCheckState(Qt.Checked if pack["id"] in included else Qt.Unchecked)
            check.setData(Qt.UserRole, pack["id"])
            self.table.setItem(row, 0, check)
            for col, value in enumerate(
                (pack["display"], pack["version"], human_bytes(pack.get("size")), pack["filename"]),
                start=1,
            ):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                item.setData(Qt.UserRole, pack["id"])
                self.table.setItem(row, col, item)
        self.table.blockSignals(False)
        self.table.resizeColumnsToContents()
        self.refresh()

    def _selected_pack(self) -> dict | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        pack_id = self.table.item(row, 1).data(Qt.UserRole)
        return next(pack for pack in self.packs if pack["id"] == pack_id)

    def _toggle(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        chosen = []
        for row in range(self.table.rowCount()):
            check = self.table.item(row, 0)
            if check and check.checkState() == Qt.Checked:
                chosen.append(str(check.data(Qt.UserRole)))
        self.window.settings.set_burn_runtime_ids(chosen)

    def _enqueue(self) -> None:
        pack = self._selected_pack()
        if pack is None:
            QMessageBox.information(self, "Stele", "Select a pack first.")
            return
        self.notes.setText(pack.get("notes") or "")
        self.window.queue.enqueue_runtime(pack)
        self.window.kick()
        self.window.nav.setCurrentRow(1)
