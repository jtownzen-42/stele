"""Paths, the default profile, burn defaults, and the token."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from stele.credentials import (
    civitai_key_status,
    clear_civitai_key,
    clear_token,
    set_civitai_key,
    set_token,
    token_status,
)
from stele.models import CAPACITY_LABELS, PROFILES


class SettingsPage(QWidget):
    def __init__(self, window) -> None:
        super().__init__()
        self.window = window
        outer = QVBoxLayout(self)
        self.sections_scroll = QScrollArea()
        self.sections_scroll.setWidgetResizable(True)
        self.sections_scroll.setFrameShape(QScrollArea.NoFrame)
        body = QWidget()
        root = QVBoxLayout(body)
        root.setContentsMargins(0, 0, 8, 0)
        root.setSpacing(16)
        self.sections_scroll.setWidget(body)
        outer.addWidget(self.sections_scroll, 1)
        def section(title, description):
            card = QGroupBox(title)
            layout = QVBoxLayout(card)
            layout.setContentsMargins(18, 24, 18, 18)
            layout.setSpacing(12)
            hint = QLabel(description)
            hint.setObjectName("muted")
            hint.setWordWrap(True)
            layout.addWidget(hint)
            form = QFormLayout()
            form.setHorizontalSpacing(20)
            form.setVerticalSpacing(12)
            form.setRowWrapPolicy(QFormLayout.WrapLongRows)
            form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
            layout.addLayout(form)
            root.addWidget(card)
            return form

        form = section("Storage and identity", "Choose where your archives live and how your discs are labeled.")
        self.vault = QLineEdit()
        self.staging = QLineEdit()
        form.addRow("Vault", _browse_row(self.vault, self))
        form.addRow("Staging", _browse_row(self.staging, self))
        self.profile = QComboBox()
        self.profile.addItems(PROFILES)
        form.addRow("Default profile", self.profile)
        self.studio_name = QLineEdit()
        self.studio_name.setPlaceholderText("Organization or studio name (default: STELE)")
        form.addRow("Disc branding", self.studio_name)
        form = section("Disc and recovery defaults", "Set disc capacity, verification and recovery preferences.")
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
        self.recovery = QSpinBox()
        self.recovery.setRange(0, 30)
        self.recovery.setSuffix(" %")
        self.recovery.setToolTip(
            "PAR2 recovery data written to each disc (Pro). 0 turns it off. "
            "5% repairs scattered damage and costs about 5% of each disc."
        )
        form.addRow("Recovery data", self.recovery)
        self.par2 = QLineEdit()
        self.par2.setPlaceholderText("Optional path to par2.exe. Leave empty to use the bundled copy or PATH.")
        form.addRow("PAR2 program", self.par2)
        form = section("Connections and license", "Keys stay in Windows Credential Manager. Manage each connection separately.")
        self.token = QLabel()
        form.addRow("Hugging Face token", self.token)
        self.civitai = QLabel()
        form.addRow("Civitai API key", self.civitai)
        self.license_status = QLabel()
        form.addRow("License status", self.license_status)
        self.license_key = QLineEdit()
        self.license_key.setPlaceholderText("Paste the Stele Pro license key from your Gumroad receipt")
        self.license_key.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        form.addRow("License key", self.license_key)
        def actions(*items):
            wrap = QWidget()
            row = QHBoxLayout(wrap)
            row.setContentsMargins(0, 0, 0, 0)
            for title, callback in items:
                button = QPushButton(title)
                button.clicked.connect(callback)
                row.addWidget(button)
            row.addStretch(1)
            return wrap

        form.insertRow(1, "", actions(("Save token", self._save_token), ("Clear token", self._clear_token)))
        form.insertRow(3, "", actions(("Save Civitai key", self._save_civitai), ("Clear Civitai key", self._clear_civitai)))
        form.addRow("", actions(("Activate license", self._activate_license), ("Deactivate license", self._deactivate_license)))
        row = QHBoxLayout()
        save = QPushButton("Save workspace")
        save.setObjectName("primary")
        save.clicked.connect(self._save)
        row.addWidget(save)
        self.feedback = QLabel("Changes apply when you save.")
        self.feedback.setObjectName("muted")
        self.feedback.setWordWrap(True)
        row.addWidget(self.feedback, 1)
        logs = QPushButton("Open log folder")
        logs.clicked.connect(self._logs)
        row.addWidget(logs)
        outer.addLayout(row)
        root.addStretch(1)
        self.load()

    def refresh(self) -> None:
        self.token.setText(token_status())
        self.civitai.setText(civitai_key_status())
        self._refresh_license()

    def _refresh_license(self) -> None:
        from stele.license import license_info
        info = license_info(self.window.db)
        if info["is_active"] == "Yes":
            email_part = f" ({info['email']})" if info["email"] else ""
            self.license_status.setText(f"Stele Pro{email_part}")
            self.license_status.setStyleSheet("color: #22c55e; font-weight: 600;")
        else:
            self.license_status.setText("Free: burning, multi-disc sets, and recovery data need Pro")
            self.license_status.setStyleSheet("color: #d97706;")
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
        self.recovery.setValue(settings.recovery_percent())
        self.par2.setText(settings.par2_path())
        self.token.setText(token_status())
        self.civitai.setText(civitai_key_status())
        self.studio_name.setText(settings.studio_name())
        self._refresh_license()

    def _activate_license(self) -> None:
        from stele.license import activate_license
        key = self.license_key.text().strip()
        if not key:
            self.license_status.setText("Please enter a license key.")
            self.license_status.setStyleSheet("color: #ef4444;")
            return
        success, msg = activate_license(key, self.window.db)
        if success:
            self.license_key.clear()
            self._refresh_license()
            if hasattr(self.window, "update_license_display"):
                self.window.update_license_display()
        else:
            self.license_status.setText(f"Activation failed: {msg}")
            self.license_status.setStyleSheet("color: #ef4444;")

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
                self.feedback.setText("Custom capacity must be a whole number of bytes.")
                self.custom_bytes.setFocus()
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
        settings.set_recovery_percent(self.recovery.value())
        settings.set_par2_path(self.par2.text())
        settings.set_studio_name(self.studio_name.text())
        settings.ensure()
        self.feedback.setText("Workspace saved.")

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

    def _save_civitai(self) -> None:
        from PySide6.QtWidgets import QInputDialog, QLineEdit as Edit

        key, ok = QInputDialog.getText(
            self, "Civitai API key", "API key from civitai.com/user/account (write-only):", Edit.EchoMode.Password
        )
        if not ok:
            return
        try:
            set_civitai_key(key)
        except Exception as exc:
            self.civitai.setText(str(exc))
            return
        self.civitai.setText(civitai_key_status())

    def _clear_civitai(self) -> None:
        clear_civitai_key()
        self.civitai.setText(civitai_key_status())

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
