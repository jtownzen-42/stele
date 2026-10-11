"""Stele Studio License & Activation System.

Supports online verification via Gumroad License API and offline signed cryptographic
activation for air-gapped M-DISC cold storage workstations.
License tokens are cached in Windows Credential Manager and SQLite.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
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

# Cryptographic salt for offline air-gapped license keys
# Key format: STELE-STUDIO-<CUSTOMER_ID>-<HMAC_SIGNATURE_HEX>
_OFFLINE_SECRET = b"STELE-STUDIO-V1-ARCHIVE-INTO-STONE-COLD-STORAGE-2026"


def verify_offline_key(key: str) -> tuple[bool, str, dict[str, Any]]:
    """Verify an offline signed license key for air-gapped workstations."""
    cleaned = key.strip().upper()
    if not cleaned.startswith("STELE-STUDIO-"):
        return False, "Invalid offline license format.", {}

    prefix = "STELE-STUDIO-"
    remainder = cleaned[len(prefix) :]
    customer_id, sep, provided_sig = remainder.rpartition("-")
    if not sep or not customer_id or not provided_sig:
        return False, "Invalid offline license format.", {}

    expected_sig = hmac.new(
        _OFFLINE_SECRET,
        customer_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:12].upper()

    if hmac.compare_digest(provided_sig, expected_sig):
        return True, "Offline Studio license activated.", {
            "tier": "Studio (Air-Gapped)",
            "customer_id": customer_id,
            "offline": True,
        }
    return False, "Offline license signature mismatch.", {}


def generate_offline_key(customer_id: str) -> str:
    """Helper for generating legitimate offline customer activation keys."""
    cid = customer_id.strip().upper()
    sig = hmac.new(
        _OFFLINE_SECRET,
        cid.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:12].upper()
    return f"STELE-STUDIO-{cid}-{sig}"


def verify_gumroad_license(
    license_key: str,
    permalink: str = "stele-studio",
) -> tuple[bool, str, dict[str, Any]]:
    """Verify a license key against the Gumroad License Verification API."""
    url = "https://api.gumroad.com/v2/licenses/verify"
    payload = {
        "product_permalink": permalink,
        "license_key": license_key.strip(),
        "increment_uses_count": "true",
    }
    try:
        response = httpx.post(url, data=payload, timeout=12.0)
        data = response.json()
        if response.status_code == 200 and data.get("success"):
            purchase = data.get("purchase", {})
            if purchase.get("refunded"):
                return False, "This purchase was refunded.", {}
            if purchase.get("chargebacked"):
                return False, "This purchase was chargebacked.", {}
            email = purchase.get("email", "")
            return True, "Gumroad license verified successfully.", {
                "tier": "Studio",
                "email": email,
                "offline": False,
            }
        message = data.get("message") or "License key not found or expired."
        return False, message, {}
    except httpx.RequestError as exc:
        return False, f"Could not reach license verification server: {exc}", {}
    except Exception as exc:
        return False, f"Verification error: {exc}", {}


def activate_license(key: str, db: Database) -> tuple[bool, str]:
    """Activate Stele with a license key, checking offline signatures first then Gumroad."""
    cleaned = key.strip()
    if not cleaned:
        return False, "License key cannot be empty."

    # 1. Check offline key format
    if cleaned.upper().startswith("STELE-STUDIO-"):
        valid, msg, info = verify_offline_key(cleaned)
        if valid:
            _store_active(cleaned, "Studio (Offline)", info.get("customer_id", "Air-Gapped User"), db)
            return True, msg
        return False, msg

    # 2. Check online Gumroad API
    valid, msg, info = verify_gumroad_license(cleaned)
    if valid:
        email = info.get("email", "Verified Customer")
        _store_active(cleaned, "Studio", email, db)
        return True, msg

    return False, msg


def _store_active(key: str, tier: str, email_or_user: str, db: Database) -> None:
    db.set_setting(KEY_LICENSE_STATUS, tier)
    db.set_setting(KEY_LICENSE_EMAIL, email_or_user)
    masked = key[:6] + "..." + key[-4:] if len(key) > 10 else "******"
    db.set_setting(KEY_LICENSE_KEY, masked)
    try:
        _keyring().set_password(SERVICE, USERNAME_LICENSE, key.strip())
    except Exception:
        log.warning("Could not persist license key to Windows Credential Manager.")


def is_activated(db: Database) -> bool:
    """Returns True if the instance is activated with a valid Studio license."""
    status = db.get_setting(KEY_LICENSE_STATUS) or ""
    return "Studio" in status


def license_info(db: Database) -> dict[str, str]:
    """Return dictionary with license details."""
    return {
        "status": db.get_setting(KEY_LICENSE_STATUS) or "Unactivated (Trial)",
        "email": db.get_setting(KEY_LICENSE_EMAIL) or "",
        "key_masked": db.get_setting(KEY_LICENSE_KEY) or "",
        "is_active": "Yes" if is_activated(db) else "No",
    }


def deactivate_license(db: Database) -> None:
    """Clear activation status."""
    db.set_setting(KEY_LICENSE_STATUS, "Unactivated")
    db.set_setting(KEY_LICENSE_EMAIL, "")
    db.set_setting(KEY_LICENSE_KEY, "")
    try:
        _keyring().delete_password(SERVICE, USERNAME_LICENSE)
    except Exception:
        pass
