"""Default locations. Settings may override vault and staging."""

from __future__ import annotations

import os
from pathlib import Path


def _local_appdata() -> Path:
    raw = os.environ.get("LOCALAPPDATA")
    if raw:
        return Path(raw)
    return Path.home() / "AppData" / "Local"


def default_staging() -> Path:
    return Path.home() / "Stele" / "staging"


def default_vault() -> Path:
    return Path.home() / "Stele" / "vault"


def app_data_dir() -> Path:
    return _local_appdata() / "Stele"


def default_db_path() -> Path:
    return app_data_dir() / "stele.db"


def default_log_dir() -> Path:
    return app_data_dir() / "logs"


def default_log_file() -> Path:
    return default_log_dir() / "stele.log"


def default_burn_work() -> Path:
    return app_data_dir() / "burn-work"


def ensure_app_dirs() -> None:
    """Create the directories a first launch needs, using the built-in defaults.

    Vault and staging overrides are created by Settings.ensure once the database exists.
    """
    for path in (default_staging(), default_vault(), app_data_dir(), default_log_dir(), default_burn_work()):
        path.mkdir(parents=True, exist_ok=True)
