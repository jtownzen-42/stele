"""Select vault items, span them, burn with IMAPI2, or export the same tree as ISO."""

from __future__ import annotations

import json
import traceback
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from stele.legal import allowed_runtime_ids
from stele.burn.imapi import ImapiError, burn_directory, eject, enumerate_recorders, find_disc_stele_root, probe, verify_volume
from stele.burn.iso import export_iso
from stele.burn.layout import build_disc_set, model_payload, runtime_pack_file
from stele.db import utc_now
from stele.models import DVD_M_DISC_NOTE, MSG_NO_DRIVE, ModelDiscMeta, RuntimeDiscMeta, human_bytes, safe_repo
from stele.runtime.catalog import get_pack


class _Job(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, fn) -> None:
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        try:
            self.succeeded.emit(self._fn())
        except Exception as exc:
            self.failed.emit(f"{exc}\n{traceback.format_exc()}")


class BurnPage(QWidget):
    def __init__(self, window) -> None:
        super().__init__()
        self.window = window
        self.drives: list[dict] = []
        self.selected_ids: list[int] = []
        self._thread: _Job | None = None
        self._volumes: list[Path] = []
        self._volume_index = 0
        self._set_label = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        drive_row = QHBoxLayout()
        self.drives_box = QComboBox()
        self.drives_box.currentIndexChanged.connect(self._show_media)
        drive_row.addWidget(self.drives_box, 1)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._refresh_drives)
        drive_row.addWidget(refresh)
        root.addLayout(drive_row)
        self.media = QLabel(MSG_NO_DRIVE)
        self.media.setWordWrap(True)
        root.addWidget(self.media)
        self.warning = QLabel(DVD_M_DISC_NOTE)
        self.warning.setObjectName("warning")
        self.warning.setWordWrap(True)
        root.addWidget(self.warning)
        self.math = QLabel("No vault items selected.")
        self.math.setWordWrap(True)
        root.addWidget(self.math)

        options = QHBoxLayout()
        self.include_runtime = QCheckBox("Include runtime packs marked on the Runtimes page")
        self.include_runtime.setChecked(True)
        self.verify = QCheckBox("Verify after burn")
        self.close = QCheckBox("Close disc")
        self.close.setChecked(True)
        self.speed = QSpinBox()
        self.speed.setRange(2, 4)
        options.addWidget(self.include_runtime)
        options.addWidget(self.verify)
        options.addWidget(self.close)
        options.addWidget(QLabel("Speed"))
        options.addWidget(self.speed)
        root.addLayout(options)

        actions = QHBoxLayout()
        self.burn_button = QPushButton("Burn")
        self.burn_button.setObjectName("primary")
        self.burn_button.clicked.connect(self.burn)
        self.iso_button = QPushButton("Export ISO")
        self.iso_button.clicked.connect(self.export_iso)
        self.next_button = QPushButton("Disc is inserted — burn next")
        self.next_button.setEnabled(False)
        self.next_button.clicked.connect(self._burn_current)
        actions.addWidget(self.burn_button)
        actions.addWidget(self.iso_button)
        actions.addWidget(self.next_button)
        actions.addStretch(1)
        root.addLayout(actions)
        self.wizard = QLabel("")
        self.wizard.setWordWrap(True)
        root.addWidget(self.wizard)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        root.addWidget(self.log, 1)
        self.refresh()

    def add_catalog(self, catalog_id: int) -> None:
        if catalog_id not in self.selected_ids:
            self.selected_ids.append(catalog_id)
        self.refresh()

    def refresh(self) -> None:
        self.verify.setChecked(self.window.settings.always_verify())
        self.speed.setValue(self.window.settings.burn_speed())
        if not self.drives:
            self._refresh_drives()
        names = []
        for catalog_id in self.selected_ids:
            row = self.window.db.get_catalog(catalog_id)
            if row:
                names.append(row["repo_id"])
        self.math.setText(
            "Burn set: " + (", ".join(names) if names else "nothing selected. Add items from the Library.")
        )

    def _refresh_drives(self) -> None:
        self.drives_box.clear()
        try:
            self.drives = enumerate_recorders()
        except ImapiError as exc:
            self.drives = []
            self.media.setText(str(exc))
            self._log(str(exc))
            return
        if not self.drives:
            problem = probe()
            self.media.setText(MSG_NO_DRIVE if not problem else f"{MSG_NO_DRIVE} {problem}")
            self.drives_box.addItem(MSG_NO_DRIVE, "")
            return
        for drive in self.drives:
            self.drives_box.addItem(drive["name"], drive["id"])
        self._show_media()

    def _show_media(self) -> None:
        index = self.drives_box.currentIndex()
        if index < 0 or index >= len(self.drives):
            self.media.setText(MSG_NO_DRIVE)
            return
        drive = self.drives[index]
        if drive.get("note"):
            self.media.setText(f"{drive['name']}: {drive['note']}")
        else:
            blank = "blank" if drive.get("blank") else "not blank"
            self.media.setText(
                f"{drive['name']} · {drive.get('media_type') or 'no media'} · "
                f"{human_bytes(drive.get('free_bytes'))} free · {blank}"
            )
        if drive.get("warning"):
            self.warning.setText(drive["warning"])

    def _current_drive(self) -> dict | None:
        index = self.drives_box.currentIndex()
        if index < 0 or index >= len(self.drives):
            return None
        return self.drives[index]

    def _log(self, text: str) -> None:
        self.log.appendPlainText(text)

    def _guard_busy(self) -> bool:
        for catalog_id in self.selected_ids:
            row = self.window.db.get_catalog(catalog_id)
            if row and self.window.queue.tree_is_busy(str(row["vault_path"]), row["repo_id"]):
                QMessageBox.warning(
                    self,
                    "Stele",
                    "A download still owns that tree. Wait until the job finishes or cancel it. "
                    "Stele will not burn and download the same tree at once.",
                )
                return True
        return False

    def _snapshot(self, *, use_media_capacity: bool) -> dict:
        drive = self._current_drive()
        capacity = self.window.settings.capacity_bytes()
        # ISO export is a hard-disk image. A half-full blank must not shrink it.
        if use_media_capacity and drive and drive.get("free_bytes"):
            capacity = int(drive["free_bytes"])
        return {
            "ids": list(self.selected_ids),
            "include_runtime": self.include_runtime.isChecked(),
            "runtime_ids": allowed_runtime_ids(self.window.db, self.window.settings.burn_runtime_ids()),
            "capacity": capacity,
            "verify": self.verify.isChecked(),
            "close": self.close.isChecked(),
            "speed": self.speed.value(),
            "recorder": None if drive is None else drive.get("id"),
        }

    def _assemble(self, snap: dict) -> list[Path]:
        payload = []
        models: list[ModelDiscMeta] = []
        runtimes: list[RuntimeDiscMeta] = []
        vault = self.window.settings.vault()
        for catalog_id in snap["ids"]:
            row = self.window.db.get_catalog(catalog_id)
            if row is None or row["kind"] != "model":
                continue
            revision_dir = Path(row["vault_path"])
            sha = str(row.get("commit_sha") or "")
            payload.extend(model_payload(revision_dir, row["repo_id"], sha))
            safe = safe_repo(row["repo_id"])
            docs = vault / "DOCS"
            models.append(
                ModelDiscMeta(
                    repo_id=row["repo_id"],
                    safe_id=safe,
                    revision=str(row.get("revision") or ""),
                    commit_sha=sha,
                    profile=str(row.get("profile") or ""),
                    license_name=str(row.get("license_name") or ""),
                    spec_md=docs / f"{safe}_spec.md",
                    spec_pdf=docs / f"{safe}_spec.pdf",
                    howto_md=docs / f"{safe}_howto.md",
                    howto_pdf=docs / f"{safe}_howto.pdf",
                )
            )
        if snap["include_runtime"]:
            for pack_id in snap["runtime_ids"]:
                try:
                    pack = get_pack(pack_id)
                except KeyError:
                    continue
                folder = vault / "RUNTIME" / pack["folder"] / pack["version"]
                filename = pack["filename"]
                files = runtime_pack_file(folder, pack["folder"], pack["version"], pack["id"], filename)
                if not files:
                    continue
                payload.extend(files)
                source = folder / filename
                runtimes.append(
                    RuntimeDiscMeta(
                        pack_id=pack["id"],
                        folder=pack["folder"],
                        version=pack["version"],
                        filename=filename,
                        homepage=pack.get("homepage") or "",
                        source=source,
                        sha256=str(pack.get("sha256") or ""),
                        size=int(pack.get("size") or 0),
                    )
                )
        work = self.window.settings.burn_work() / utc_now().replace(":", "")
        return build_disc_set(
            work,
            payload,
            models,
            runtimes,
            int(snap["capacity"]),
            utc_now(),
            studio_name=self.window.settings.studio_name(),
        )

    def export_iso(self) -> None:
        if self._guard_busy():
            return
        if not self.selected_ids:
            QMessageBox.information(self, "Stele", "Add a vault item from the Library first.")
            return
        self._set_busy(True)
        self._log("Building the disc tree, then exporting ISO.")
        snap = self._snapshot(use_media_capacity=False)

        def work():
            roots = self._assemble(snap)
            isos = []
            for root in roots:
                manifest = json.loads((root / "ARCHIVE_MANIFEST.json").read_text(encoding="utf-8"))
                label = manifest["volume"]["label"]
                dest = root.parent / f"{label}.iso"
                try:
                    export_iso(root, dest, label)
                    isos.append(str(dest))
                except ImapiError as exc:
                    return {"roots": [str(item) for item in roots], "error": str(exc), "isos": isos}
            return {"roots": [str(item) for item in roots], "isos": isos, "error": ""}

        self._run(work, self._exported)

    def _exported(self, result: dict) -> None:
        self._set_busy(False)
        if result.get("error"):
            self._log(result["error"])
            self._log("The vault was not changed. The disc tree is still in burn-work.")
            self.window.db.insert_burn(
                {
                    "drive_name": "",
                    "media_type": "",
                    "disc_label": "",
                    "volume_index": 1,
                    "volume_count": len(result.get("roots") or []),
                    "set_id": "",
                    "verify_status": "dry_run",
                    "verify_note": result["error"],
                    "iso_path": "",
                    "result": "failed",
                    "com_error": result["error"],
                    "catalog_ids_json": json.dumps(self.selected_ids),
                }
            )
            return
        for iso in result.get("isos") or []:
            self._log(f"ISO written: {iso}")
            self.window.db.insert_burn(
                {
                    "drive_name": "",
                    "media_type": "ISO",
                    "disc_label": Path(iso).stem,
                    "volume_index": 1,
                    "volume_count": len(result["isos"]),
                    "set_id": "",
                    "verify_status": "dry_run",
                    "verify_note": "ISO export. No disc was burned.",
                    "iso_path": iso,
                    "result": "exported",
                    "com_error": None,
                    "catalog_ids_json": json.dumps(self.selected_ids),
                }
            )
        self.window.library_page.refresh()

    def burn(self) -> None:
        if self._guard_busy():
            return
        if not self._pro_allowed("burn"):
            return
        drive = self._current_drive()
        if drive is None or not drive.get("id"):
            self.media.setText(MSG_NO_DRIVE)
            self._log(MSG_NO_DRIVE)
            return
        if drive.get("note"):
            self._log(drive["note"])
            return
        if not self.selected_ids:
            QMessageBox.information(self, "Stele", "Add a vault item from the Library first.")
            return
        self._set_busy(True)
        self._log("Planning volumes.")
        snap = self._snapshot(use_media_capacity=True)

        def work():
            return self._assemble(snap)

        self._run(work, self._planned)

    def _pro_allowed(self, feature: str) -> bool:
        """Free tier: ISO export only. Burning and spanning need Pro.

        Pro is re-checked with Gumroad each time, so a refunded or charged-back key stops working at
        once. If Gumroad cannot be reached, Pro still works inside the 14-day grace period.
        """
        from stele.license import FeatureLocked, refresh_license, require_pro

        refresh_license(self.window.db)
        try:
            require_pro(self.window.db, feature)
            return True
        except FeatureLocked as exc:
            self._log(str(exc))
            QMessageBox.information(self, "Stele Pro", str(exc))
            return False

    def _planned(self, roots: list[Path]) -> None:
        self._set_busy(False)
        if len(roots) > 1 and not self._pro_allowed("span"):
            self._volumes = []
            return
        self._volumes = list(roots)
        self._volume_index = 0
        count = len(roots)
        self.wizard.setText(f"Insert disc 1 of {count}.")
        self._log(f"{count} volume(s) ready.")
        if count == 1:
            self._burn_current()
        else:
            self.next_button.setEnabled(True)
            self._log("This set spans discs. Burn disc 1, then follow the eject prompt.")

    def _burn_current(self) -> None:
        if not self._pro_allowed("burn"):
            return
        if self._volume_index >= len(self._volumes):
            return
        drive = self._current_drive()
        if drive is None or not drive.get("id"):
            self._log(MSG_NO_DRIVE)
            return
        root = self._volumes[self._volume_index]
        manifest = json.loads((root / "ARCHIVE_MANIFEST.json").read_text(encoding="utf-8"))
        label = manifest["volume"]["label"]
        index = manifest["volume"]["index"]
        count = manifest["volume"]["count"]
        self._set_busy(True)
        self._log(f"Burning {label}. {self._cancel_note()}")
        snap = self._snapshot(use_media_capacity=True)
        speed = snap["speed"]
        close = snap["close"]
        verify = snap["verify"]
        recorder = snap["recorder"] or drive["id"]

        def work():
            outcome = burn_directory(recorder, root, label, speed_x=speed, close_disc=close)
            status, note = ("skipped", "Verify was turned off.")
            if verify:
                disc_root = None
                stele_hint = outcome.get("stele_root")
                if stele_hint:
                    candidate = Path(str(stele_hint))
                    if candidate.exists():
                        disc_root = candidate
                if disc_root is None:
                    for path in outcome.get("volume_paths") or []:
                        candidate = Path(path) / "STELE"
                        if candidate.exists():
                            disc_root = candidate
                            break
                if disc_root is None:
                    disc_root = find_disc_stele_root(
                        volume_label=label,
                        volume_paths=list(outcome.get("volume_paths") or []),
                        recorder_id=recorder,
                        settle_seconds=8.0,
                    )
                if disc_root is None:
                    status, note = (
                        "skipped",
                        "The drive did not expose a readable STELE folder after the burn "
                        "(no letter and no Volume GUID match), so Stele did not claim the disc was verified. "
                        "You can Export ISO. The vault was not changed.",
                    )
                else:
                    status, note = verify_volume(disc_root, root)
            return {"outcome": outcome, "status": status, "note": note, "label": label, "index": index, "count": count}

        self._run(work, self._burned)

    def _cancel_note(self) -> str:
        return "Cancel is not available for this recorder; the burn will finish or fail on its own."

    def _burned(self, result: dict) -> None:
        self._set_busy(False)
        outcome = result["outcome"]
        self._log(outcome.get("speed_note") or "")
        if outcome.get("cancel_note"):
            self._log(outcome["cancel_note"])
        self._log(result["note"])
        self.window.db.insert_burn(
            {
                "drive_name": outcome.get("drive_name"),
                "media_type": outcome.get("media_type"),
                "disc_label": result["label"],
                "volume_index": result["index"],
                "volume_count": result["count"],
                "set_id": result["label"],
                "verify_status": result["status"],
                "verify_note": result["note"],
                "iso_path": None,
                "result": "success" if result["status"] != "failed" else "failed",
                "com_error": None,
                "catalog_ids_json": json.dumps(self.selected_ids),
            }
        )
        drive = self._current_drive()
        if drive and result["index"] < result["count"]:
            try:
                eject(drive["id"])
            except Exception as exc:
                self._log(str(exc))
            self._volume_index += 1
            self.wizard.setText(
                f"Eject done. Insert disc {result['index'] + 1} of {result['count']}, then press the next button."
            )
            self.next_button.setEnabled(True)
        else:
            self.wizard.setText("Burn finished.")
            self.next_button.setEnabled(False)
        self.window.library_page.refresh()

    def _set_busy(self, busy: bool) -> None:
        self.burn_button.setEnabled(not busy)
        self.iso_button.setEnabled(not busy)
        if busy:
            self.next_button.setEnabled(False)

    def _run(self, fn, ok) -> None:
        thread = _Job(fn)
        thread.succeeded.connect(ok)
        thread.failed.connect(self._failed)
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        thread.start()

    def _failed(self, text: str) -> None:
        self._set_busy(False)
        self._log(text)
        self.window.db.insert_burn(
            {
                "drive_name": "",
                "media_type": "",
                "disc_label": "",
                "volume_index": None,
                "volume_count": None,
                "set_id": "",
                "verify_status": "failed",
                "verify_note": text.splitlines()[0] if text else "",
                "iso_path": None,
                "result": "failed",
                "com_error": text[:2000],
                "catalog_ids_json": json.dumps(self.selected_ids),
            }
        )
        QMessageBox.warning(self, "Stele", text.splitlines()[0] if text else "Burn failed.")
