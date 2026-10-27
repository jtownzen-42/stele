"""The one place evidence timestamps come from: this PC's clock."""

from __future__ import annotations

from datetime import datetime, timezone

from stele.models import CLOCK_NOTE

CLOCK_SOURCE = "local system clock"


def local_timestamp(now: datetime | None = None) -> dict[str, str]:
    """UTC time, local time, offset, and zone name, labelled as unverified.

    `now` must be timezone-aware when given (tests pass a fixed time).
    """
    local = (now or datetime.now(timezone.utc)).astimezone()
    offset = local.strftime("%z")
    offset = f"{offset[:3]}:{offset[3:]}" if offset else "+00:00"
    return {
        "utc": local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "local": local.isoformat(timespec="seconds"),
        "utc_offset": offset,
        "time_zone": local.tzname() or "",
        "source": CLOCK_SOURCE,
        "note": CLOCK_NOTE,
    }
