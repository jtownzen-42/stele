"""Paths, the default profile, burn defaults, and the token."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
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


from stele.ui.theme import set_status

class SettingsPage(QWidget):
    def __init__(self, window) -> None:
        super().__init__()
        self.window = window
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(6)

        def section(title: str) -> QFormLayout:
            heading = QLabel(title)
            heading.setObjectName("sectionTitle")
            root.addWidget(heading)
            form = QFormLayout()
            form.setHorizontalSpacing(18)
            form.setVerticalSpacing(10)
            form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            root.addLayout(form)
            forms.append(form)
            return form

        forms: list[QFormLayout] = []

        storage = section("Storage")
        self.vault = QLineEdit()
        self.staging = QLineEdit()
        storage.addRow("Vault", _browse_row(self.vault, self))
        storage.addRow("Staging", _browse_row(self.staging, self))

        burning = section("Burning")
        self.profile = QComboBox()
        self.profile.addItems(PROFILES)
        burning.addRow("Default profile", self.profile)
        self.capacity = QComboBox()
        for key, label in CAPACITY_LABELS.items():
            self.capacity.addItem(label, key)
        burning.addRow("Disc estimate", self.capacity)
        self.custom_bytes = QLineEdit()
        self.custom_bytes.setPlaceholderText("Custom capacity in bytes, used when Disc estimate is Custom")
        burning.addRow("Custom bytes", self.custom_bytes)
        self.speed = QSpinBox()
        self.speed.setRange(2, 4)
        burning.addRow("Burn speed (2x–4x)", self.speed)
        self.verify = QCheckBox("Always verify after burn")
        burning.addRow("", self.verify)
        self.studio_name = QLineEdit()
        self.studio_name.setPlaceholderText("Organization or studio name (default: STELE)")
        burning.addRow("Disc label branding", self.studio_name)

        hub = section("Hugging Face")
        self.token = QLabel()
        token_save = QPushButton("Save token")
        token_save.clicked.connect(self._save_token)
        token_clear = QPushButton("Clear token")
        token_clear.clicked.connect(self._clear_token)
        hub.addRow("Access token", _inline(self.token, token_save, token_clear))

        pro = section("Stele Pro")
        self.license_status = QLabel()
        pro.addRow("Edition", self.license_status)
        self.license_key = QLineEdit()
        self.license_key.setPlaceholderText("Enter your Gumroad license key")
        self.license_key.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        license_activate = QPushButton("Activate")
        license_activate.clicked.connect(self._activate_license)
        license_deactivate = QPushButton("Deactivate")
        license_deactivate.clicked.connect(self._deactivate_license)
        pro.addRow("License key", _inline(self.license_key, license_activate, license_deactivate, stretch=False))

        # One label column width for every section, so fields line up down the page.
        for form in forms:
            for index in range(form.rowCount()):
                item = form.itemAt(index, QFormLayout.ItemRole.LabelRole)
                if item is not None and item.widget() is not None:
                    item.widget().setMinimumWidth(150)

        root.addSpacing(14)
        row = QHBoxLayout()
        about = QPushButton("About and licenses")
        about.clicked.connect(self._about)
        logs = QPushButton("Open log folder")
        logs.clicked.connect(self._logs)
        row.addWidget(about)
        row.addWidget(logs)
        row.addStretch(1)
        save = QPushButton("Save settings")
        save.setObjectName("primary")
        save.setToolTip("Saves storage, burning and branding. Token and license buttons act at once.")
        save.clicked.connect(self._save)
        row.addWidget(save)
        root.addLayout(row)
        root.addStretch(1)
        self.load()

    def refresh(self) -> None:
        self.token.setText(token_status())
        self._refresh_license()

    def _refresh_license(self) -> None:
        from stele.license import license_info
        info = license_info(self.window.db)
        if info["is_active"] == "Yes":
            email_part = f" ({info['email']})" if info["email"] else ""
            self.license_status.setText(f"Active: {info['status']}{email_part}")
            set_status(self.license_status, "ok")
        else:
            self.license_status.setText("Free (search, download, docs, ISO export)")
            set_status(self.license_status, "warn")
        if info.get("key_masked"):
            self.license_key.setPlaceholderText(f"Current: {info['key_masked']}")

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
        self.studio_name.setText(settings.studio_name())
        self._refresh_license()

    def _about(self) -> None:
        from stele.ui.legal_dialogs import AboutDialog

        AboutDialog(self.window.db, self).exec()

    def _activate_license(self) -> None:
        from stele.license import activate_license
        key = self.license_key.text().strip()
        if not key:
            self.license_status.setText("Please enter a license key.")
            set_status(self.license_status, "error")
            return
        success, msg = activate_license(key, self.window.db)
        if success:
            self.license_key.clear()
            self._refresh_license()
            if hasattr(self.window, "update_license_display"):
                self.window.update_license_display()
        else:
            self.license_status.setText(f"Activation failed: {msg}")
            set_status(self.license_status, "error")

    def _deactivate_license(self) -> None:
        from stele.license import deactivate_license
        deactivate_license(self.window.db)
        self.license_key.clear()
        self._refresh_license()
        if hasattr(self.window, "update_license_display"):
            self.window.update_license_display()

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
        settings.set_studio_name(self.studio_name.text())
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


def _inline(first: QWidget, *buttons: QPushButton, stretch: bool = True) -> QWidget:
    """A field or label followed by its own action buttons, on one row."""
    box = QWidget()
    lay = QHBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)
    lay.addWidget(first, 0 if stretch else 1)
    for button in buttons:
        lay.addWidget(button)
    if stretch:
        lay.addStretch(1)
    return box
