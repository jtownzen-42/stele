"""Tests for download queue resilience and network retry backoff."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from stele.download.worker import (
    NETWORK_TRIES,
    Cancelled,
    DownloadWorker,
    TransferError,
    transfer_stop_reason,
)


def test_network_tries_count():
    assert NETWORK_TRIES == 5


def test_transfer_stop_reason():
    assert transfer_stop_reason(None, False) == "cancelled"
    assert transfer_stop_reason("paused", False) == "paused"
    assert transfer_stop_reason("cancelled", False) == "cancelled"
    assert transfer_stop_reason("active", True) == "shutdown"
    assert transfer_stop_reason("active", False) is None


def test_backoff_sleep_cancellation():
    mock_queue = MagicMock()
    wake = threading.Event()
    stop = threading.Event()
    worker = DownloadWorker(mock_queue, wake, stop)

    mock_thread = MagicMock()

    # Simulate job paused during backoff
    with patch.object(worker, "_stop_check") as mock_stop_check:
        mock_check = MagicMock(return_value="paused")
        mock_stop_check.return_value = mock_check

        with pytest.raises(Cancelled) as excinfo:
            worker._backoff_sleep(0, "model.safetensors", mock_thread, 1)

        assert excinfo.value.kind == "paused"
        mock_thread.message.emit.assert_called_once()
        assert "Retrying" in mock_thread.message.emit.call_args[0][0] or "retry" in mock_thread.message.emit.call_args[0][0].lower()


def test_backoff_sleep_timing():
    mock_queue = MagicMock()
    wake = threading.Event()
    stop = threading.Event()
    worker = DownloadWorker(mock_queue, wake, stop)

    mock_thread = MagicMock()

    with patch.object(worker, "_stop_check") as mock_stop_check:
        mock_stop_check.return_value = lambda: None

        with patch("time.sleep") as mock_sleep, patch("time.monotonic") as mock_mono:
            mock_mono.side_effect = [0.0, 0.0, 0.1, 5.0]
            worker._backoff_sleep(0, "test.bin", mock_thread, 1)
            mock_sleep.assert_called()
