"""Licensing tests: Free/Pro gating, Gumroad verification (faked), rejections, grace period, no secret."""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

import stele.license as lic
from stele.db import Database
from stele.license import (
    FeatureLocked,
    activate_license,
    current_tier,
    deactivate_license,
    is_pro,
    license_info,
    refresh_license,
    require_pro,
    verify_gumroad_license,
)

PID = "TEST-PRODUCT-ID=="
KEY = "ABCD1234-EFGH5678-IJKL9012-MNOP3456"


@pytest.fixture
def db(tmp_path) -> Database:
    return Database(tmp_path / "test.db")


@pytest.fixture(autouse=True)
def product_id(monkeypatch):
    monkeypatch.setenv("STELE_GUMROAD_PRODUCT_ID", PID)


@pytest.fixture(autouse=True)
def fake_keyring():
    store: dict = {}
    kr = MagicMock()
    kr.set_password.side_effect = lambda s, u, p: store.__setitem__((s, u), p)
    kr.get_password.side_effect = lambda s, u: store.get((s, u))
    kr.delete_password.side_effect = lambda s, u: store.pop((s, u), None)
    with patch("stele.license._keyring", return_value=kr):
        yield store


def reply(success=True, status=200, message="", **purchase):
    resp = MagicMock()
    resp.status_code = status
    base = {"email": "customer@example.com", "refunded": False, "chargebacked": False}
    base.update(purchase)
    body = {"success": success, "purchase": base}
    if message:
        body["message"] = message
    resp.json.return_value = body
    return resp


# ---------------------------------------------------------------- free tier gating

def test_fresh_install_is_free_and_pro_features_are_locked(db):
    assert not is_pro(db)
    assert current_tier(db) == "Free"
    for feature in ("burn", "span"):
        with pytest.raises(FeatureLocked):
            require_pro(db, feature)
    assert "ISO export" in str(FeatureLocked("burn"))


def test_unknown_feature_is_a_programming_error(db):
    with pytest.raises(ValueError):
        require_pro(db, "iso_export")  # ISO export is free and is never gated


def test_free_status_in_settings_does_not_unlock(db):
    db.set_setting(lic.KEY_LICENSE_STATUS, "Free")
    assert not is_pro(db)


# ---------------------------------------------------------------- pro unlock

def test_pro_unlocks_with_valid_gumroad_response(db):
    with patch("httpx.post", return_value=reply()) as post:
        ok, msg = activate_license(KEY, db)
    assert ok and "active" in msg.lower()
    assert is_pro(db)
    require_pro(db, "burn")
    require_pro(db, "span")
    info = license_info(db)
    assert info["tier"] == "Pro" and info["email"] == "customer@example.com"
    assert KEY not in info["key_masked"]
    sent = post.call_args.kwargs["data"]
    assert sent["product_id"] == PID
    assert "product_permalink" not in sent
    assert sent["license_key"] == KEY


def test_key_is_saved_in_credential_store_not_in_settings(db, fake_keyring):
    with patch("httpx.post", return_value=reply()):
        activate_license(KEY, db)
    assert fake_keyring[("Stele", "studio_license")] == KEY
    for setting in ("license_status", "license_email", "license_key_masked", "license_verified_utc"):
        assert KEY not in (db.get_setting(setting) or "")


def test_deactivate_returns_to_free(db):
    with patch("httpx.post", return_value=reply()):
        activate_license(KEY, db)
    deactivate_license(db)
    assert not is_pro(db)
    assert license_info(db)["is_active"] == "No"


# ---------------------------------------------------------------- rejections

@pytest.mark.parametrize(
    "purchase,word",
    [
        ({"refunded": True}, "refunded"),
        ({"chargebacked": True}, "charged back"),
        ({"disputed": True, "dispute_won": False}, "dispute"),
        ({"subscription_cancelled_at": "2026-10-01T00:00:00Z"}, "no longer active"),
    ],
)
def test_rejected_purchases_do_not_unlock(db, purchase, word):
    with patch("httpx.post", return_value=reply(**purchase)):
        ok, msg = activate_license(KEY, db)
    assert not ok and word in msg.lower()
    assert not is_pro(db)


def test_won_dispute_is_accepted(db):
    with patch("httpx.post", return_value=reply(disputed=True, dispute_won=True)):
        ok, _ = activate_license(KEY, db)
    assert ok


def test_invalid_key(db):
    with patch("httpx.post", return_value=reply(success=False, status=404, message="That license does not exist for the provided product.")):
        ok, msg = activate_license("NOPE", db)
    assert not ok and "does not exist" in msg
    assert not is_pro(db)


def test_empty_key(db):
    ok, msg = activate_license("   ", db)
    assert not ok and "empty" in msg.lower()


def test_missing_product_id_fails_closed(db, monkeypatch):
    monkeypatch.setenv("STELE_GUMROAD_PRODUCT_ID", "")
    monkeypatch.setattr(lic, "GUMROAD_PRODUCT_ID", "")
    with patch("httpx.post") as post:
        ok, msg = activate_license(KEY, db)
    assert not ok and "not configured" in msg.lower()
    post.assert_not_called()


def test_network_error_does_not_activate(db):
    with patch("httpx.post", side_effect=httpx.ConnectError("down")):
        ok, msg = activate_license(KEY, db)
    assert not ok and "reach" in msg.lower()
    assert not is_pro(db)


def test_garbled_and_server_error_replies_do_not_activate(db):
    bad = MagicMock(status_code=200)
    bad.json.side_effect = ValueError("not json")
    with patch("httpx.post", return_value=bad):
        assert not activate_license(KEY, db)[0]
    srv = reply(success=False, status=503)
    with patch("httpx.post", return_value=srv):
        assert not activate_license(KEY, db)[0]


def test_success_flag_false_with_200_does_not_unlock(db):
    with patch("httpx.post", return_value=reply(success=False, status=200)):
        assert not verify_gumroad_license(KEY)[0]


# ---------------------------------------------------------------- cached result and grace period

def test_pro_stays_within_grace_when_offline(db):
    with patch("httpx.post", return_value=reply()):
        activate_license(KEY, db)
    with patch("httpx.post", side_effect=httpx.ConnectError("offline")):
        pro, msg = refresh_license(db)
    assert pro and "offline" in msg.lower()
    assert is_pro(db)


def test_pro_expires_after_grace_when_never_reverified(db):
    with patch("httpx.post", return_value=reply()):
        activate_license(KEY, db)
    old = lic._now() - timedelta(days=lic.GRACE_DAYS + 1)
    db.set_setting(lic.KEY_LICENSE_VERIFIED, lic._stamp(old))
    assert not is_pro(db)
    with patch("httpx.post", side_effect=httpx.ConnectError("offline")):
        pro, msg = refresh_license(db)
    assert not pro and "online" in msg.lower()
    # Still stored as Pro, so a later online check restores it without retyping the key.
    with patch("httpx.post", return_value=reply()):
        pro, _ = refresh_license(db)
    assert pro and is_pro(db)


def test_refund_after_activation_removes_pro_on_next_check(db):
    with patch("httpx.post", return_value=reply()):
        activate_license(KEY, db)
    with patch("httpx.post", return_value=reply(refunded=True)) as post:
        pro, msg = refresh_license(db)
    assert not pro and "refunded" in msg.lower()
    assert not is_pro(db)
    assert post.call_args.kwargs["data"]["increment_uses_count"] == "false"


def test_refresh_without_license_is_a_noop(db):
    with patch("httpx.post") as post:
        pro, _ = refresh_license(db)
    assert not pro
    post.assert_not_called()


def test_missing_verified_timestamp_is_not_pro(db):
    db.set_setting(lic.KEY_LICENSE_STATUS, "Pro")
    assert not is_pro(db)


# ---------------------------------------------------------------- no secret in source

def test_no_embedded_secret_or_offline_key_path():
    package = Path(lic.__file__).resolve().parent
    root = package.parent
    burned = "ARCHIVE-INTO" + "-STONE"  # fragment of the old secret, split so this file does not contain it
    source = Path(lic.__file__).read_text(encoding="utf-8")
    assert "_OFFLINE_SECRET" not in source
    assert "generate_offline_key" not in source and "verify_offline_key" not in source
    assert not hasattr(lic, "generate_offline_key")
    assert "STELE-STUDIO-V1" not in source
    assert "product_permalink" not in source
    # No old burned secret anywhere in the shipped package.
    for path in [*package.rglob("*.py"), *root.glob("*.py"), *root.glob("*.spec"), *root.glob("*.txt")]:
        assert burned not in path.read_text(encoding="utf-8", errors="ignore"), path
    # No long hex / base64-looking literal assigned to a name that sounds secret.
    assert not re.search(r"(?i)(secret|private_key|signing_key)\s*=\s*b?[\"'][A-Za-z0-9+/=_-]{16,}", source)


# ---------------------------------------------------------------- burn page wiring

def test_burn_page_gates_burn_and_span_but_not_iso_export():
    source = (Path(lic.__file__).resolve().parent / "ui" / "pages" / "burn_page.py").read_text(encoding="utf-8")
    burn = source.split("def burn(self)")[1].split("def _pro_allowed")[0]
    assert '_pro_allowed("burn")' in burn
    assert '_pro_allowed("span")' in source.split("def _planned")[1].split("def _burn_current")[0]
    assert '_pro_allowed("burn")' in source.split("def _burn_current")[1].split("self._set_busy")[0]
    export = source.split("def export_iso(self)")[1].split("def _exported")[0]
    assert "_pro_allowed" not in export and "require_pro" not in export
