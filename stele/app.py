"""Launch Stele. One process, one download thread, no hf_transfer."""

from __future__ import annotations

import logging
import os
import sys

from stele.credentials import RedactionFilter
from stele.db import Database
from stele.paths import default_db_path, default_log_file, ensure_app_dirs


def configure_logging() -> None:
    ensure_app_dirs()
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    handler = logging.FileHandler(default_log_file(), encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(RedactionFilter())
    root.addHandler(handler)
    # httpx and huggingface must not log request headers.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("huggingface_hub").setLevel(logging.WARNING)


def main() -> int:
    if "--smoke" in sys.argv:
        from PySide6.QtWidgets import QApplication
        from stele.ui.main_window import MainWindow

        # Load the native Qt platform plugin and all UI imports without
        # opening a vault, starting downloads or probing optical hardware.
        app = QApplication(["Stele", "--smoke"])
        app.setStyle("Fusion")
        print("Stele smoke test OK (Qt and UI imports loaded)")
        app.quit()
        return 0
    if "--version" in sys.argv:
        print("Stele 1.0.0")
        return 0

    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    configure_logging()
    from PySide6.QtWidgets import QApplication

    from stele.ui.main_window import MainWindow

    db = Database(default_db_path())
    db.recover_on_startup()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    from stele.legal import accept_eula, eula_accepted

    if not eula_accepted(db):
        from stele.ui.legal_dialogs import EulaDialog

        if EulaDialog().exec() != EulaDialog.DialogCode.Accepted:
            db.close()
            return 0
        accept_eula(db)
    window = MainWindow(db)
    window.show()
    code = app.exec()
    db.close()
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
