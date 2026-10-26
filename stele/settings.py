"""User-overridable paths and burn defaults, stored in SQLite."""

from __future__ import annotations

import json
from pathlib import Path

from stele.db import Database
from stele.models import CAPACITY_PRESETS, PROFILE_GGUF
from stele.paths import default_burn_work, default_log_dir, default_staging, default_vault

KEY_VAULT = "vault_path"
KEY_STAGING = "staging_path"
KEY_PROFILE = "default_profile"
KEY_SPEED = "burn_speed"
KEY_VERIFY = "always_verify"
KEY_CAPACITY = "capacity_preset"
KEY_CAPACITY_CUSTOM = "capacity_custom_bytes"
KEY_BURN_RUNTIMES = "burn_runtime_ids"
KEY_LAST_FORMAT = "last_model_format"
KEY_BRANDING = "branding_studio_name"
KEY_RECOVERY = "recovery_percent"
KEY_PAR2 = "par2_path"


class Settings:
    def __init__(self, db: Database) -> None:
        self.db = db

    def staging(self) -> Path:
        return Path(self.db.get_setting(KEY_STAGING) or default_staging())

    def vault(self) -> Path:
        return Path(self.db.get_setting(KEY_VAULT) or default_vault())

    def log_dir(self) -> Path:
        return default_log_dir()

    def burn_work(self) -> Path:
        return default_burn_work()

    def default_profile(self) -> str:
        return self.db.get_setting(KEY_PROFILE) or PROFILE_GGUF

    def set_default_profile(self, profile: str) -> None:
        self.db.set_setting(KEY_PROFILE, profile)

    def burn_speed(self) -> int:
        raw = self.db.get_setting(KEY_SPEED) or "4"
        try:
            speed = int(raw)
        except ValueError:
            speed = 4
        return min(4, max(2, speed))

    def set_burn_speed(self, speed: int) -> None:
        self.db.set_setting(KEY_SPEED, str(min(4, max(2, int(speed)))))

    def always_verify(self) -> bool:
        return (self.db.get_setting(KEY_VERIFY) or "1") == "1"

    def set_always_verify(self, enabled: bool) -> None:
        self.db.set_setting(KEY_VERIFY, "1" if enabled else "0")

    def capacity_preset(self) -> str:
        return self.db.get_setting(KEY_CAPACITY) or "bd25"

    def set_capacity_preset(self, preset: str) -> None:
        self.db.set_setting(KEY_CAPACITY, preset)

    def capacity_bytes(self) -> int:
        preset = self.capacity_preset()
        if preset == "custom":
            raw = self.db.get_setting(KEY_CAPACITY_CUSTOM) or str(CAPACITY_PRESETS["bd25"])
            try:
                return max(1, int(raw))
            except ValueError:
                return CAPACITY_PRESETS["bd25"]
        return CAPACITY_PRESETS.get(preset, CAPACITY_PRESETS["bd25"])

    def set_custom_capacity(self, nbytes: int) -> None:
        self.db.set_setting(KEY_CAPACITY, "custom")
        self.db.set_setting(KEY_CAPACITY_CUSTOM, str(int(nbytes)))

    def set_staging(self, path: Path) -> None:
        self.db.set_setting(KEY_STAGING, str(path))

    def set_vault(self, path: Path) -> None:
        self.db.set_setting(KEY_VAULT, str(path))

    def burn_runtime_ids(self) -> list[str]:
        raw = self.db.get_setting(KEY_BURN_RUNTIMES) or "[]"
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(value, list):
            return []
        return [str(item) for item in value]

    def set_burn_runtime_ids(self, pack_ids: list[str]) -> None:
        self.db.set_setting(KEY_BURN_RUNTIMES, json.dumps(list(pack_ids)))

    def last_format(self) -> str:
        return self.db.get_setting(KEY_LAST_FORMAT) or ""

    def set_last_format(self, fmt: str) -> None:
        self.db.set_setting(KEY_LAST_FORMAT, fmt)

    def studio_name(self) -> str:
        return self.db.get_setting(KEY_BRANDING) or "STELE"

    def set_studio_name(self, name: str) -> None:
        self.db.set_setting(KEY_BRANDING, name.strip() or "STELE")

    def recovery_percent(self) -> int:
        """PAR2 redundancy for burned and exported volumes. 0 turns it off."""
        from stele.burn.par2 import DEFAULT_PERCENT, MAX_PERCENT

        raw = self.db.get_setting(KEY_RECOVERY) or str(DEFAULT_PERCENT)
        try:
            return min(MAX_PERCENT, max(0, int(raw)))
        except ValueError:
            return DEFAULT_PERCENT

    def set_recovery_percent(self, percent: int) -> None:
        from stele.burn.par2 import MAX_PERCENT

        self.db.set_setting(KEY_RECOVERY, str(min(MAX_PERCENT, max(0, int(percent)))))

    def par2_path(self) -> str:
        return self.db.get_setting(KEY_PAR2) or ""

    def set_par2_path(self, path: str) -> None:
        self.db.set_setting(KEY_PAR2, path.strip())

    def ensure(self) -> None:
        for path in (self.staging(), self.vault(), self.log_dir(), self.burn_work()):
            path.mkdir(parents=True, exist_ok=True)
