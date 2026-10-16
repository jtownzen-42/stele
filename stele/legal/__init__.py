"""EULA acceptance, third-party notices and the LM Studio opt-in. No Qt in here, so it is easy to test."""

from __future__ import annotations

from pathlib import Path

from stele.db import Database, utc_now

EULA_VERSION = "1"
KEY_EULA_VERSION = "eula_accepted_version"
KEY_EULA_UTC = "eula_accepted_utc"
KEY_LMSTUDIO_OPTIN_UTC = "lmstudio_optin_utc"

LMSTUDIO_ID = "lmstudio"
LMSTUDIO_TERMS_URL = "https://lmstudio.ai"
LMSTUDIO_NOTICE = (
    "LM Studio is third-party proprietary software, not part of Stele and not covered by the Stele "
    "licence. Stele only downloads and archives its official installer; it never runs it. Using LM Studio "
    "is subject to its own terms at " + LMSTUDIO_TERMS_URL + ". Show LM Studio only if you have read "
    "and accept those terms."
)

_DIR = Path(__file__).resolve().parent


def eula_text() -> str:
    return (_DIR / "EULA.txt").read_text(encoding="utf-8")


def notices_text() -> str:
    return (_DIR / "THIRD_PARTY_NOTICES.txt").read_text(encoding="utf-8")


# ---------------------------------------------------------------- EULA

def eula_accepted(db: Database) -> bool:
    """True when this EULA version was accepted. A new EULA_VERSION asks again."""
    return (db.get_setting(KEY_EULA_VERSION) or "") == EULA_VERSION


def accept_eula(db: Database) -> None:
    db.set_setting(KEY_EULA_VERSION, EULA_VERSION)
    db.set_setting(KEY_EULA_UTC, utc_now())


# ---------------------------------------------------------------- LM Studio (off by default)

def lmstudio_enabled(db: Database) -> bool:
    return bool(db.get_setting(KEY_LMSTUDIO_OPTIN_UTC))


def set_lmstudio_optin(db: Database, accepted_terms: bool) -> None:
    """Turn LM Studio on only with an explicit acknowledgment; turning it off clears the record."""
    db.set_setting(KEY_LMSTUDIO_OPTIN_UTC, utc_now() if accepted_terms else "")


def visible_packs(db: Database, packs) -> list[dict]:
    """Runtime packs to show. LM Studio is hidden until the user opts in."""
    on = lmstudio_enabled(db)
    return [p for p in packs if on or p.get("id") != LMSTUDIO_ID]


def allowed_runtime_ids(db: Database, ids) -> list[str]:
    """Drop LM Studio from a saved selection if the user has not opted in (or has opted out)."""
    on = lmstudio_enabled(db)
    return [i for i in ids if on or i != LMSTUDIO_ID]
