"""Paths, the default profile, burn defaults, and the token."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from stele.credentials import clear_token, set_token, token_status
from stele.models import CAPACITY_LABELS, PROFILES


class SettingsPage(QWidget):
    def __init__(self, window) -> None:
        super().__init__()
        self.window = window
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        form = QFormLayout()
        self.vault = QLineEdit()
        self.staging = QLineEdit()
        form.addRow("Vault", _browse_row(self.vault, self))
        form.addRow("Staging", _browse_row(self.staging, self))
        self.profile = QComboBox()
        self.profile.addItems(PROFILES)
        form.addRow("Default profile", self.profile)
        self.capacity = QComboBox()
        for key, label in CAPACITY_LABELS.items():
            self.capacity.addItem(label, key)
        form.addRow("Disc estimate", self.capacity)
        self.custom_bytes = QLineEdit()
        self.custom_bytes.setPlaceholderText("Custom capacity in bytes, used when Disc estimate is Custom")
        form.addRow("Custom bytes", self.custom_bytes)
        self.speed = QSpinBox()
        self.speed.setRange(2, 4)
        form.addRow("Burn speed (2x–4x)", self.speed)
        self.verify = QCheckBox("Always verify after burn")
        form.addRow("", self.verify)
        self.token = QLabel()
        form.addRow("Hugging Face token", self.token)
        root.addLayout(form)
        row = QHBoxLayout()
        save = QPushButton("Save")
        save.setObjectName("primary")
        save.clicked.connect(self._save)
        row.addWidget(save)
        token_save = QPushButton("Save token")
        token_save.clicked.connect(self._save_token)
        token_clear = QPushButton("Clear token")
        token_clear.clicked.connect(self._clear_token)
        logs = QPushButton("Open log folder")
        logs.clicked.connect(self._logs)
        row.addWidget(token_save)
        row.addWidget(token_clear)
        row.addWidget(logs)
        row.addStretch(1)
        root.addLayout(row)
        root.addStretch(1)
        self.load()

    def refresh(self) -> None:
        self.token.setText(token_status())

    def load(self) -> None:
        settings = self.window.settings
        self.vault.setText(str(settings.vault()))
        self.staging.setText(str(settings.staging()))
        self.profile.setCurrentText(settings.default_profile())
        preset = settings.capacity_preset()
        index = self.capacity.findData(preset)
        if index >= 0:
            self.capacity.setCurrentIndex(index)
        self.custom_bytes.setText(settings.db.get_setting("capacity_custom_bytes") or "")
        self.speed.setValue(settings.burn_speed())
        self.verify.setChecked(settings.always_verify())
        self.token.setText(token_status())

    def _save(self) -> None:
        settings = self.window.settings
        preset = str(self.capacity.currentData())
        custom_bytes = None
        if preset == "custom":
            try:
                custom_bytes = int(self.custom_bytes.text().strip())
            except ValueError:
                self.token.setText("Custom capacity must be a whole number of bytes.")
                return
        settings.set_vault(Path(self.vault.text().strip()))
        settings.set_staging(Path(self.staging.text().strip()))
        settings.set_default_profile(self.profile.currentText())
        if custom_bytes is None:
            settings.set_capacity_preset(preset)
        else:
            settings.set_custom_capacity(custom_bytes)
        settings.set_burn_speed(self.speed.value())
        settings.set_always_verify(self.verify.isChecked())
        settings.ensure()

    def _save_token(self) -> None:
        from PySide6.QtWidgets import QInputDialog, QLineEdit as Edit

        token, ok = QInputDialog.getText(
            self, "Hugging Face token", "Token (write-only):", Edit.EchoMode.Password
        )
        if not ok:
            return
        try:
            set_token(token)
        except Exception as exc:
            self.token.setText(str(exc))
            return
        self.token.setText(token_status())

    def _clear_token(self) -> None:
        clear_token()
        self.token.setText(token_status())

    def _logs(self) -> None:
        import os

        path = self.window.settings.log_dir()
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(path)  # noqa: S606 — opens the log folder, not a downloaded installer


def _browse_row(edit: QLineEdit, parent: QWidget) -> QWidget:
    wrap = QWidget()
    row = QHBoxLayout(wrap)
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(edit, 1)
    button = QPushButton("Browse")

    def pick() -> None:
        chosen = QFileDialog.getExistingDirectory(parent, "Stele", edit.text())
        if chosen:
            edit.setText(chosen)

    button.clicked.connect(pick)
    row.addWidget(button)
    return wrap
