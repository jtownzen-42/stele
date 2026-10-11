"""Tests for Stele Studio license verification and offline activation."""

from __future__ import annotations

import pytest
import httpx
from unittest.mock import patch, MagicMock

from stele.db import Database
from stele.license import (
    activate_license,
    deactivate_license,
    generate_offline_key,
    is_activated,
    license_info,
    verify_gumroad_license,
    verify_offline_key,
)


@pytest.fixture
def temp_db(tmp_path) -> Database:
    db = Database(tmp_path / "test.db")
    return db


def test_offline_key_generation_and_verification():
    customer = "LAB-STATION-01"
    key = generate_offline_key(customer)
    assert key.startswith(f"STELE-STUDIO-{customer}-")

    valid, msg, info = verify_offline_key(key)
    assert valid is True
    assert "activated" in msg.lower()
    assert info["customer_id"] == customer
    assert info["offline"] is True


def test_offline_key_invalid_cases():
    valid, msg, info = verify_offline_key("INVALID-KEY-FORMAT")
    assert valid is False
    assert "format" in msg.lower()

    valid, msg, info = verify_offline_key("STELE-STUDIO-USER1-BADSIG123456")
    assert valid is False
    assert "mismatch" in msg.lower()


def test_activate_and_deactivate_offline(temp_db):
    assert not is_activated(temp_db)
    key = generate_offline_key("RESEARCH-42")

    with patch("stele.license._keyring") as mock_keyring:
        mock_kr = MagicMock()
        mock_keyring.return_value = mock_kr

        success, msg = activate_license(key, temp_db)
        assert success is True
        assert is_activated(temp_db)
        info = license_info(temp_db)
        assert info["status"] == "Studio (Offline)"
        assert info["email"] == "RESEARCH-42"
        assert info["is_active"] == "Yes"

        deactivate_license(temp_db)
        assert not is_activated(temp_db)
        info2 = license_info(temp_db)
        assert info2["status"] == "Unactivated"
        assert info2["is_active"] == "No"


def test_gumroad_verification_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "success": True,
        "purchase": {
            "email": "customer@example.com",
            "refunded": False,
            "chargebacked": False,
        },
    }

    with patch("httpx.post", return_value=mock_resp):
        valid, msg, info = verify_gumroad_license("DUMMY-GUMROAD-KEY-1234")
        assert valid is True
        assert info["email"] == "customer@example.com"
        assert info["offline"] is False


def test_gumroad_verification_refunded_or_chargeback():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "success": True,
        "purchase": {
            "email": "customer@example.com",
            "refunded": True,
            "chargebacked": False,
        },
    }

    with patch("httpx.post", return_value=mock_resp):
        valid, msg, _ = verify_gumroad_license("REFUNDED-KEY")
        assert valid is False
        assert "refunded" in msg.lower()


def test_gumroad_verification_network_error():
    with patch("httpx.post", side_effect=httpx.ConnectError("Connection failed")):
        valid, msg, _ = verify_gumroad_license("ANY-KEY")
        assert valid is False
        assert "reach license verification server" in msg.lower()
