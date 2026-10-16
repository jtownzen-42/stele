"""Stele licensing: Free and Pro tiers, activated online through the Gumroad License API.

Tiers
-----
Free  search, download, docs, ISO export.
Pro   disc burning and multi-disc spanning ($29 one-time).

Design notes
------------
* There are no offline keys and no secret in this file. A key is only ever valid if Gumroad says so.
* The Gumroad lookup uses ``product_id`` (the product's stable ID), never the URL permalink.
* A successful check is cached with a timestamp. Pro keeps working offline for ``GRACE_DAYS`` after
  the last successful check. After that the app must reach Gumroad again (see ``refresh_license``).
* A definitive rejection (refunded, chargebacked, disputed, cancelled, disabled, unknown key) removes
  Pro immediately on the next check. A network failure never removes Pro inside the grace window.
* The cache lives in the local settings table, so a determined user can edit it. This is a licence
  check for honest customers, not copy protection.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from stele.credentials import _keyring
from stele.db import Database

log = logging.getLogger("stele.license")

SERVICE = "Stele"
USERNAME_LICENSE = "studio_license"

KEY_LICENSE_STATUS = "license_status"
KEY_LICENSE_EMAIL = "license_email"
KEY_LICENSE_KEY = "license_key_masked"
KEY_LICENSE_VERIFIED = "license_verified_utc"

TIER_FREE = "Free"
TIER_PRO = "Pro"

# Gumroad "product_id" for the Pro product. It is an identifier, not a secret. It is filled in by the
# release owner (Stele Pro, permalink varuz); STELE_GUMROAD_PRODUCT_ID overrides it. If empty, activation fails closed.
GUMROAD_PRODUCT_ID = "nyqJsy-BD6Tnu2XO62Tnvw=="
GUMROAD_VERIFY_URL = "https://api.gumroad.com/v2/licenses/verify"

GRACE_DAYS = 14

PRO_FEATURES = {
    "burn": "Disc burning",
    "span": "Multi-disc spanning",
}


class FeatureLocked(Exception):
    """Raised when a Pro-only feature is used on the Free tier."""

    def __init__(self, feature: str) -> None:
        self.feature = feature
        super().__init__(
            f"{PRO_FEATURES.get(feature, feature)} is part of Stele Pro. "
            "Free includes search, download, docs and ISO export."
        )


def product_id() -> str:
    return (os.environ.get("STELE_GUMROAD_PRODUCT_ID") or GUMROAD_PRODUCT_ID).strip()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- Gumroad

def _rejection(purchase: dict[str, Any]) -> str | None:
    """Return the reason a purchase must not unlock Pro, or None if it is in good standing."""
    if purchase.get("refunded"):
        return "This purchase was refunded."
    if purchase.get("chargebacked"):
        return "This purchase was charged back."
    if purchase.get("disputed") and not purchase.get("dispute_won"):
        return "This purchase is under dispute."
    if purchase.get("subscription_cancelled_at") or purchase.get("subscription_failed_at"):
        return "This licence is no longer active."
    return None


def verify_gumroad_license(
    license_key: str,
    *,
    count_use: bool = True,
    pid: str | None = None,
) -> tuple[bool, str, dict[str, Any]]:
    """Check a key with Gumroad.

    Returns ``(ok, message, info)``. ``info["reachable"]`` is False only when Gumroad could not be
    reached, so the caller can tell a network failure from a definitive rejection.
    """
    key = (license_key or "").strip()
    if not key:
        return False, "License key cannot be empty.", {"reachable": True}
    pid = (pid if pid is not None else product_id())
    if not pid:
        return False, "Licensing is not configured in this build (no Gumroad product ID).", {"reachable": True}

    payload = {
        "product_id": pid,
        "license_key": key,
        "increment_uses_count": "true" if count_use else "false",
    }
    try:
        response = httpx.post(GUMROAD_VERIFY_URL, data=payload, timeout=12.0)
    except httpx.RequestError as exc:
        return False, f"Could not reach the license server: {exc}", {"reachable": False}
    except Exception as exc:  # defensive: never let a library error unlock or crash
        return False, f"Verification error: {exc}", {"reachable": False}

    try:
        data = response.json()
    except ValueError:
        return False, "The license server sent an unreadable reply.", {"reachable": False}
    if not isinstance(data, dict):
        return False, "The license server sent an unreadable reply.", {"reachable": False}

    if response.status_code >= 500:
        return False, "The license server is having trouble. Try again later.", {"reachable": False}

    if response.status_code == 200 and data.get("success"):
        purchase = data.get("purchase") or {}
        reason = _rejection(purchase)
        if reason:
            return False, reason, {"reachable": True}
        return True, "License verified.", {
            "tier": TIER_PRO,
            "email": str(purchase.get("email") or ""),
            "reachable": True,
        }

    message = str(data.get("message") or "License key not found.")
    return False, message, {"reachable": True}


# ---------------------------------------------------------------- activation and state

def _store_active(key: str, email: str, db: Database) -> None:
    db.set_setting(KEY_LICENSE_STATUS, TIER_PRO)
    db.set_setting(KEY_LICENSE_EMAIL, email)
    db.set_setting(KEY_LICENSE_VERIFIED, _stamp(_now()))
    cleaned = key.strip()
    masked = cleaned[:4] + "..." + cleaned[-4:] if len(cleaned) > 10 else "******"
    db.set_setting(KEY_LICENSE_KEY, masked)
    try:
        _keyring().set_password(SERVICE, USERNAME_LICENSE, cleaned)
    except Exception:
        log.warning("Could not save the license key to the system credential store.")


def activate_license(key: str, db: Database) -> tuple[bool, str]:
    """Activate Pro with a Gumroad license key."""
    ok, message, info = verify_gumroad_license(key, count_use=True)
    if ok:
        _store_active(key, info.get("email", ""), db)
        return True, "Stele Pro is active."
    return False, message


def deactivate_license(db: Database) -> None:
    """Remove Pro from this computer."""
    db.set_setting(KEY_LICENSE_STATUS, TIER_FREE)
    db.set_setting(KEY_LICENSE_EMAIL, "")
    db.set_setting(KEY_LICENSE_KEY, "")
    db.set_setting(KEY_LICENSE_VERIFIED, "")
    try:
        _keyring().delete_password(SERVICE, USERNAME_LICENSE)
    except Exception:
        pass


def _within_grace(db: Database, now: datetime | None = None) -> bool:
    verified = _parse(db.get_setting(KEY_LICENSE_VERIFIED) or "")
    if verified is None:
        return False
    return (now or _now()) - verified <= timedelta(days=GRACE_DAYS)


def is_pro(db: Database) -> bool:
    """True when this install holds a Pro licence that was verified within the grace window."""
    if (db.get_setting(KEY_LICENSE_STATUS) or "") != TIER_PRO:
        return False
    return _within_grace(db)


def current_tier(db: Database) -> str:
    return TIER_PRO if is_pro(db) else TIER_FREE


def require_pro(db: Database, feature: str) -> None:
    """Raise FeatureLocked unless Pro is active. Call this before any Pro-only action."""
    if feature not in PRO_FEATURES:
        raise ValueError(f"Unknown feature: {feature}")
    if not is_pro(db):
        raise FeatureLocked(feature)


def refresh_license(db: Database) -> tuple[bool, str]:
    """Re-check the stored key with Gumroad. Call on startup and before a burn.

    Returns ``(pro_active, message)``. Network trouble keeps Pro inside the grace window and drops it
    after. A definitive rejection drops Pro right away.
    """
    if (db.get_setting(KEY_LICENSE_STATUS) or "") != TIER_PRO:
        return False, "No Pro licence on this computer."
    try:
        key = _keyring().get_password(SERVICE, USERNAME_LICENSE)
    except Exception:
        key = None
    if not key:
        return is_pro(db), "Stored license key not found. Enter it again to re-verify."

    ok, message, info = verify_gumroad_license(key, count_use=False)
    if ok:
        _store_active(key, info.get("email", ""), db)
        return True, "Stele Pro is active."
    if not info.get("reachable", True):
        if _within_grace(db):
            return True, "Offline. Pro stays active until the grace period ends."
        return False, "Pro needs an online check. Connect to the internet and open Settings."
    deactivate_license(db)
    return False, message


def license_info(db: Database) -> dict[str, str]:
    return {
        "tier": current_tier(db),
        "status": current_tier(db),
        "email": db.get_setting(KEY_LICENSE_EMAIL) or "",
        "key_masked": db.get_setting(KEY_LICENSE_KEY) or "",
        "last_verified": db.get_setting(KEY_LICENSE_VERIFIED) or "",
        "is_active": "Yes" if is_pro(db) else "No",
    }


# Back-compat name used by the current UI.
is_activated = is_pro
