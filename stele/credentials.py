"""Hugging Face token in Windows Credential Manager, plus log redaction.

The token is never written to SQLite, logs, manifests, PDFs, or disc files.
"""

from __future__ import annotations

import logging
import re

SERVICE = "Stele"
USERNAME = "huggingface"

_HF_TOKEN = re.compile(r"hf_[A-Za-z0-9]{8,}")
_AUTH = re.compile(r"(?i)(authorization\s*[:=]\s*)(?:bearer\s+)?\S+")


def redact_text(text: str, extra: str | None = None) -> str:
    cleaned = _HF_TOKEN.sub("[redacted]", text)
    cleaned = _AUTH.sub(r"\1[redacted]", cleaned)
    if extra:
        cleaned = cleaned.replace(extra, "[redacted]")
    return cleaned


class RedactionFilter(logging.Filter):
    """Strip tokens from log records before they reach a handler."""

    def __init__(self, extra: str | None = None) -> None:
        super().__init__()
        self.extra = extra

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg, self.extra)
        args = record.args
        if isinstance(args, dict):
            record.args = {
                key: redact_text(value, self.extra) if isinstance(value, str) else value
                for key, value in args.items()
            }
        elif isinstance(args, tuple):
            record.args = tuple(
                redact_text(value, self.extra) if isinstance(value, str) else value for value in args
            )
        return True


def _keyring():
    import keyring

    return keyring


def token_status() -> str:
    return "Stored" if get_token() else "Not set"


def get_token() -> str | None:
    try:
        value = _keyring().get_password(SERVICE, USERNAME)
    except Exception:
        logging.getLogger("stele.credentials").warning("Credential Manager could not be read")
        return None
    if not value:
        return None
    return value


def set_token(token: str) -> None:
    cleaned = token.strip()
    if not cleaned:
        raise ValueError("Token is empty.")
    _keyring().set_password(SERVICE, USERNAME, cleaned)


def clear_token() -> None:
    try:
        _keyring().delete_password(SERVICE, USERNAME)
    except Exception:
        # keyring raises if the entry is already gone. That is a successful clear.
        return
