"""Stele Pro activation through the Gumroad License API.

Free (no key): search, download, docs, and single-volume ISO export.
Pro (activated): disc burning, multi-disc spanning, PAR2 recovery data, and
the Compliance Vault evidence export.

There are no offline keys in v1. The earlier HMAC offline scheme shipped its
secret inside the executable, so anyone could mint keys. Do not bring it back:
any offline scheme must verify a signature with a public key only.

Pro is checked where the work happens (`require_pro`), not only in the UI.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from stele.credentials import _keyring
from stele.db import Database, utc_now

log = logging.getLogger("stele.license")

# Gumroad product_id (Product page → Content → License key → "product_id").
# Gumroad requires product_id for products created after Jan 2023; the
# permalink is not accepted for them.
GUMROAD_PRODUCT_ID = "nyqJsy-BD6Tnu2XO62Tnvw=="
GUMROAD_VERIFY_URL = "https://api.gumroad.com/v2/licenses/verify"

# One Pro purchase covers one person on up to this many machines.
MAX_ACTIVATIONS = 3
# A stored license is re-checked online at most this often. When Gumroad is
# unreachable the license stays active: air-gapped archive stations are a
# supported setup. Only an explicit refund, dispute, or rejection revokes it.
REVALIDATE_AFTER = timedelta(days=7)

TIER_PRO = "Pro"
FEATURE_BURN = "Disc burning"
FEATURE_SPAN = "Multi-disc spanning"
FEATURE_RECOVERY = "PAR2 recovery data"
FEATURE_EVIDENCE = "Compliance Vault evidence export"

SERVICE = "Stele"
USERNAME_LICENSE = "studio_license"
KEY_LICENSE_STATUS = "license_status"
KEY_LICENSE_EMAIL = "license_email"
KEY_LICENSE_KEY = "license_key_masked"
KEY_LICENSE_CHECKED = "license_checked_utc"

UNACTIVATED = "Free"


class ProRequired(PermissionError):
    """Raised when a Pro feature is used without an active license."""

    def __init__(self, feature: str) -> None:
        super().__init__(
            f"{feature} is part of Stele Pro. Activate a license in Workspace settings. "
            "Search, download, documentation, and single-disc ISO export stay free."
        )
        self.feature = feature


def verify_gumroad_license(
    license_key: str,
    *,
    increment_uses: bool = True,
    product_id: str | None = None,
) -> tuple[bool, str, dict[str, Any]]:
    """Verify a key with Gumroad. Returns (valid, message, info).

    info["network_error"] is True when Gumroad could not be reached, so the
    caller can tell "rejected" from "unknown".
    """
    product = GUMROAD_PRODUCT_ID if product_id is None else product_id
    if not product:
        return False, "This build has no Gumroad product configured. Contact support.", {}
    payload = {
        "product_id": product,
        "license_key": license_key.strip(),
        "increment_uses_count": "true" if increment_uses else "false",
    }
    try:
        response = httpx.post(GUMROAD_VERIFY_URL, data=payload, timeout=12.0)
    except httpx.RequestError as exc:
        return False, f"Could not reach the license server: {exc}", {"network_error": True}
    if response.status_code >= 500:
        return False, f"The license server returned {response.status_code}. Try again later.", {"network_error": True}
    try:
        data = response.json()
    except ValueError:
        return False, "The license server sent an unreadable reply. Try again later.", {"network_error": True}

    if not data.get("success"):
        return False, data.get("message") or "That license key was not found.", {}
    purchase = data.get("purchase") or {}
    if purchase.get("product_id") and purchase.get("product_id") != product:
        return False, "That key belongs to a different product.", {}
    if purchase.get("refunded"):
        return False, "This purchase was refunded.", {}
    if purchase.get("chargebacked"):
        return False, "This purchase was charged back.", {}
    if purchase.get("disputed") and not purchase.get("dispute_won"):
        return False, "This purchase is under dispute.", {}
    if any(purchase.get(key) for key in ("subscription_ended_at", "subscription_cancelled_at", "subscription_failed_at")):
        return False, "This subscription is no longer active.", {}
    uses = int(data.get("uses") or 0)
    if increment_uses and uses > MAX_ACTIVATIONS:
        return False, (
            f"This key is already active on {MAX_ACTIVATIONS} machines. "
            "Deactivate an old machine or contact support."
        ), {}
    return True, "Stele Pro activated.", {"tier": TIER_PRO, "email": purchase.get("email", ""), "uses": uses}


def activate_license(key: str, db: Database) -> tuple[bool, str]:
    """Activate Pro with a Gumroad license key."""
    cleaned = key.strip()
    if not cleaned:
        return False, "License key cannot be empty."
    valid, msg, info = verify_gumroad_license(cleaned, increment_uses=True)
    if not valid:
        return False, msg
    _store_active(cleaned, info.get("email") or "", db)
    return True, msg


def revalidate(db: Database, *, now: datetime | None = None, force: bool = False) -> str:
    """Re-check a stored license with Gumroad without using an activation.

    Returns "skipped", "ok", "offline", or "revoked". Network failures never
    revoke a license.
    """
    if not is_activated(db):
        return "skipped"
    now = now or datetime.now(timezone.utc)
    checked = _parse_utc(db.get_setting(KEY_LICENSE_CHECKED))
    if not force and checked is not None and now - checked < REVALIDATE_AFTER:
        return "skipped"
    key = _stored_key()
    if not key:
        # The key lives in Windows Credential Manager. If that store is
        # unavailable we cannot re-check, and that is not proof of abuse.
        return "offline"
    valid, msg, info = verify_gumroad_license(key, increment_uses=False)
    if valid:
        db.set_setting(KEY_LICENSE_CHECKED, utc_now())
        return "ok"
    if info.get("network_error"):
        return "offline"
    log.warning("Stored license was rejected on re-check: %s", msg)
    deactivate_license(db)
    return "revoked"


def _store_active(key: str, email: str, db: Database) -> None:
    db.set_setting(KEY_LICENSE_STATUS, TIER_PRO)
    db.set_setting(KEY_LICENSE_EMAIL, email)
    masked = key[:6] + "..." + key[-4:] if len(key) > 10 else "******"
    db.set_setting(KEY_LICENSE_KEY, masked)
    db.set_setting(KEY_LICENSE_CHECKED, utc_now())
    try:
        _keyring().set_password(SERVICE, USERNAME_LICENSE, key.strip())
    except Exception:
        log.warning("Could not persist license key to Windows Credential Manager.")


def _stored_key() -> str | None:
    try:
        return _keyring().get_password(SERVICE, USERNAME_LICENSE)
    except Exception:
        return None


def is_activated(db: Database) -> bool:
    """True when this install holds an active Pro license."""
    return (db.get_setting(KEY_LICENSE_STATUS) or "") == TIER_PRO


def require_pro(db: Database, feature: str) -> None:
    """Raise ProRequired unless Pro is active. Call this in the code path itself."""
    if not is_activated(db):
        raise ProRequired(feature)


def license_info(db: Database) -> dict[str, str]:
    """Return dictionary with license details."""
    active = is_activated(db)
    return {
        "status": TIER_PRO if active else UNACTIVATED,
        "email": (db.get_setting(KEY_LICENSE_EMAIL) or "") if active else "",
        "key_masked": (db.get_setting(KEY_LICENSE_KEY) or "") if active else "",
        "is_active": "Yes" if active else "No",
    }


def deactivate_license(db: Database) -> None:
    """Clear activation status."""
    db.set_setting(KEY_LICENSE_STATUS, UNACTIVATED)
    db.set_setting(KEY_LICENSE_EMAIL, "")
    db.set_setting(KEY_LICENSE_KEY, "")
    db.set_setting(KEY_LICENSE_CHECKED, "")
    try:
        _keyring().delete_password(SERVICE, USERNAME_LICENSE)
    except Exception:
        pass


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
