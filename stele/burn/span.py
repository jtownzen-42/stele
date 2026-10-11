"""Pack files onto volumes. A file is never split across discs."""

from __future__ import annotations

from stele.models import HEADROOM_BYTES, SpanFile, SpanPlan, VolumePlan, msg_file_too_big


def usable_bytes(capacity_bytes: int, headroom: int = HEADROOM_BYTES) -> int:
    return max(0, int(capacity_bytes) - int(headroom))


def plan_volumes(files: list[SpanFile], capacity_bytes: int, headroom: int = HEADROOM_BYTES) -> SpanPlan:
    """Largest-first, then best-fit into volumes of `capacity_bytes - headroom`.

    `capacity_bytes` is the raw media size. The headroom stays empty for UDF
    metadata, README, manifest, and labels.
    """
    usable = usable_bytes(capacity_bytes, headroom)
    if usable <= 0:
        return SpanPlan([], 0, capacity_bytes, error="Disc capacity is smaller than the 32 MB headroom.")

    ordered = sorted(files, key=lambda item: (-item.size, item.path))
    for item in ordered:
        if item.size > usable:
            return SpanPlan(
                [],
                usable,
                capacity_bytes,
                error=msg_file_too_big(item.path, item.size, usable),
            )

    volumes: list[dict] = []
    for item in ordered:
        best_index = None
        best_remaining = None
        for index, volume in enumerate(volumes):
            remaining = usable - volume["used"]
            if item.size <= remaining and (best_remaining is None or remaining < best_remaining):
                best_index = index
                best_remaining = remaining
        if best_index is None:
            volumes.append({"used": item.size, "files": [item]})
        else:
            volumes[best_index]["files"].append(item)
            volumes[best_index]["used"] += item.size

    planned = [
        VolumePlan(index=i + 1, files=list(volume["files"]), used_bytes=int(volume["used"]))
        for i, volume in enumerate(volumes)
    ]
    return SpanPlan(planned, usable, capacity_bytes, error=None)
