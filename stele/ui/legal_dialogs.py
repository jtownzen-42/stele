"""First-run EULA and the About / Licenses window."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QTabWidget,
    QVBoxLayout,
)

from stele.legal import eula_text, notices_text


def _reader(text: str) -> QPlainTextEdit:
    box = QPlainTextEdit()
    box.setReadOnly(True)
    box.setPlainText(text)
    box.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
    return box


class EulaDialog(QDialog):
    """Shown on first run (and when the EULA version changes). Accept continues; Decline quits."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Stele license agreement")
        self.resize(640, 560)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Please read and accept the license agreement to use Stele."))
        layout.addWidget(_reader(eula_text()), 1)
        buttons = QDialogButtonBox()
        accept = buttons.addButton("Accept", QDialogButtonBox.ButtonRole.AcceptRole)
        accept.setDefault(True)
        buttons.addButton("Decline", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class AboutDialog(QDialog):
    """Edition, agreement and open-source notices."""

    def __init__(self, db, parent=None) -> None:
        super().__init__(parent)
        from stele.license import license_info

        self.setWindowTitle("About Stele")
        self.resize(660, 560)
        info = license_info(db)
        layout = QVBoxLayout(self)
        edition = info["tier"]
        extra = f" ({info['email']})" if info.get("email") else ""
        layout.addWidget(QLabel(f"Stele {edition}{extra}"))
        tabs = QTabWidget()
        tabs.addTab(_reader(eula_text()), "License agreement")
        tabs.addTab(_reader(notices_text()), "Open-source notices")
        layout.addWidget(tabs, 1)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        close.accepted.connect(self.accept)
        layout.addWidget(close)
