"""Stele Pro activation, re-checks, and Free/Pro gating."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from stele import license as lic
from stele.burn.layout import build_disc_set
from stele.db import Database
from stele.license import (
    FEATURE_BURN,
    ProRequired,
    activate_license,
    deactivate_license,
    is_activated,
    license_info,
    require_pro,
    revalidate,
    verify_gumroad_license,
)
from stele.models import PayloadFile

PRODUCT = "prod_TEST123"


@pytest.fixture(autouse=True)
def product_id(monkeypatch):
    monkeypatch.setattr(lic, "GUMROAD_PRODUCT_ID", PRODUCT)


@pytest.fixture
def temp_db(tmp_path) -> Database:
    db = Database(tmp_path / "test.db")
    yield db
    db.close()


@pytest.fixture
def keyring_store(monkeypatch):
    store: dict[tuple[str, str], str] = {}
    fake = MagicMock()
    fake.set_password.side_effect = lambda s, u, p: store.__setitem__((s, u), p)
    fake.get_password.side_effect = lambda s, u: store.get((s, u))
    fake.delete_password.side_effect = lambda s, u: store.pop((s, u), None)
    monkeypatch.setattr(lic, "_keyring", lambda: fake)
    return store


def _reply(status: int = 200, success: bool = True, uses: int = 1, **purchase) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    body = {"success": success, "uses": uses, "purchase": {"product_id": PRODUCT, "email": "buyer@example.com"}}
    body["purchase"].update(purchase)
    if not success:
        body = {"success": False, "message": "That license does not exist for the provided product."}
    resp.json.return_value = body
    return resp


def test_no_minting_secret_in_source():
    root = Path(__file__).resolve().parents[1] / "stele"
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "_OFFLINE_SECRET" not in text, path
        assert "STONE-COLD-STORAGE" not in text, path
        assert not re.search(r"hmac\.new\(", text), path
    assert not hasattr(lic, "generate_offline_key")


def test_verify_sends_product_id_not_permalink():
    with patch("httpx.post", return_value=_reply()) as post:
        valid, _, info = verify_gumroad_license("KEY-1")
    assert valid is True
    assert info["email"] == "buyer@example.com"
    sent = post.call_args.kwargs["data"]
    assert sent["product_id"] == PRODUCT
    assert "product_permalink" not in sent


def test_unconfigured_build_refuses(monkeypatch):
    monkeypatch.setattr(lic, "GUMROAD_PRODUCT_ID", "")
    with patch("httpx.post") as post:
        valid, msg, _ = verify_gumroad_license("KEY-1")
    assert valid is False
    assert "no gumroad product" in msg.lower()
    post.assert_not_called()


@pytest.mark.parametrize(
    "purchase,needle",
    [
        ({"refunded": True}, "refunded"),
        ({"chargebacked": True}, "charged back"),
        ({"disputed": True}, "dispute"),
        ({"product_id": "prod_OTHER"}, "different product"),
        ({"subscription_cancelled_at": "2026-01-01T00:00:00Z"}, "subscription"),
    ],
)
def test_rejected_purchases(purchase, needle):
    with patch("httpx.post", return_value=_reply(**purchase)):
        valid, msg, _ = verify_gumroad_license("KEY-1")
    assert valid is False
    assert needle in msg.lower()


def test_won_dispute_is_accepted():
    with patch("httpx.post", return_value=_reply(disputed=True, dispute_won=True)):
        valid, _, _ = verify_gumroad_license("KEY-1")
    assert valid is True


def test_unknown_key_is_rejected():
    with patch("httpx.post", return_value=_reply(status=404, success=False)):
        valid, msg, info = verify_gumroad_license("NOPE")
    assert valid is False
    assert "does not exist" in msg
    assert not info.get("network_error")


def test_activation_limit():
    with patch("httpx.post", return_value=_reply(uses=lic.MAX_ACTIVATIONS + 1)):
        valid, msg, _ = verify_gumroad_license("KEY-1")
    assert valid is False
    assert "machines" in msg


def test_network_error_is_flagged():
    with patch("httpx.post", side_effect=httpx.ConnectError("Connection failed")):
        valid, msg, info = verify_gumroad_license("ANY-KEY")
    assert valid is False
    assert info["network_error"] is True
    assert "license server" in msg.lower()


def test_activate_and_deactivate(temp_db, keyring_store):
    assert not is_activated(temp_db)
    with patch("httpx.post", return_value=_reply()):
        ok, _ = activate_license("ABCDEFGH-1234", temp_db)
    assert ok is True
    assert is_activated(temp_db)
    info = license_info(temp_db)
    assert info["status"] == "Pro"
    assert info["email"] == "buyer@example.com"
    assert keyring_store[("Stele", "studio_license")] == "ABCDEFGH-1234"

    deactivate_license(temp_db)
    assert not is_activated(temp_db)
    assert license_info(temp_db)["status"] == "Free"
    assert keyring_store == {}


def test_legacy_offline_status_is_not_pro(temp_db):
    temp_db.set_setting("license_status", "Studio (Offline)")
    assert not is_activated(temp_db)
    with pytest.raises(ProRequired):
        require_pro(temp_db, FEATURE_BURN)


def _activate(db) -> None:
    with patch("httpx.post", return_value=_reply()):
        assert activate_license("ABCDEFGH-1234", db)[0]


def test_revalidate_skips_recent_check(temp_db, keyring_store):
    _activate(temp_db)
    with patch("httpx.post") as post:
        assert revalidate(temp_db) == "skipped"
    post.assert_not_called()


def test_revalidate_revokes_refund(temp_db, keyring_store):
    _activate(temp_db)
    later = datetime.now(timezone.utc) + timedelta(days=30)
    with patch("httpx.post", return_value=_reply(refunded=True)) as post:
        assert revalidate(temp_db, now=later) == "revoked"
    assert post.call_args.kwargs["data"]["increment_uses_count"] == "false"
    assert not is_activated(temp_db)


def test_revalidate_offline_keeps_license(temp_db, keyring_store):
    _activate(temp_db)
    later = datetime.now(timezone.utc) + timedelta(days=365)
    with patch("httpx.post", side_effect=httpx.ConnectError("offline")):
        assert revalidate(temp_db, now=later) == "offline"
    assert is_activated(temp_db)


def test_revalidate_ignores_activation_limit(temp_db, keyring_store):
    _activate(temp_db)
    with patch("httpx.post", return_value=_reply(uses=50)):
        assert revalidate(temp_db, force=True) == "ok"
    assert is_activated(temp_db)


def _payload(tmp_path: Path, sizes: list[int]) -> list[PayloadFile]:
    items = []
    for i, size in enumerate(sizes):
        src = tmp_path / f"f{i}.bin"
        src.write_bytes(b"x" * size)
        items.append(PayloadFile(src, f"MODELS/a--b/c/f{i}.bin", size, "0" * 64, "a--b"))
    return items


def test_free_tier_cannot_span(tmp_path):
    capacity = 32 * 1024 * 1024 + 1500  # 32 MB headroom leaves 1500 bytes per volume
    with pytest.raises(ProRequired) as err:
        build_disc_set(tmp_path / "out", _payload(tmp_path, [1000, 1000]), [], [], capacity, "2026-10-26T00:00:00Z", max_volumes=1)
    assert "Multi-disc spanning" in str(err.value)
    roots = build_disc_set(tmp_path / "out", _payload(tmp_path, [1000, 1000]), [], [], capacity, "2026-10-26T00:00:00Z")
    assert len(roots) == 2


def test_free_tier_single_volume_iso_allowed(tmp_path):
    roots = build_disc_set(
        tmp_path / "out", _payload(tmp_path, [1000]), [], [], 25_025_314_816, "2026-10-26T00:00:00Z", max_volumes=1
    )
    assert len(roots) == 1


def test_release_build_has_a_product_id():
    source = Path(lic.__file__).read_text(encoding="utf-8")
    match = re.search(r'^GUMROAD_PRODUCT_ID = "([^"]+)"$', source, re.MULTILINE)
    assert match and match.group(1).strip()
