"""Pack files onto volumes.

plan_volumes never slices a file. Callers split files larger than one volume
first (see part_sizes and stele.burn.layout.split_oversized).
"""

from __future__ import annotations

import math

from stele.models import HEADROOM_BYTES, SpanFile, SpanPlan, VolumePlan, msg_file_too_big


def usable_bytes(capacity_bytes: int, headroom: int = HEADROOM_BYTES) -> int:
    return max(0, int(capacity_bytes) - int(headroom))


PART_ALIGN = 1024 * 1024


def part_sizes(size: int, usable: int) -> list[int]:
    """Sizes of equal parts that each fit `usable`, aligned to 1 MiB when possible.

    40 GB on 25 GB blanks becomes two 20 GB parts, which leaves room on each
    disc for other files. A file that already fits is one part.
    """
    if size <= usable or usable <= 0:
        return [size]
    align = PART_ALIGN if usable >= 2 * PART_ALIGN else 1
    count = math.ceil(size / usable)
    part = math.ceil(math.ceil(size / count) / align) * align
    if part > usable:
        part = usable // align * align
    count = math.ceil(size / part)
    return [min(part, size - index * part) for index in range(count)]


def estimate_volumes(sizes: list[int], capacity_bytes: int, headroom: int = HEADROOM_BYTES) -> SpanPlan:
    """plan_volumes after splitting files that are larger than one volume."""
    usable = usable_bytes(capacity_bytes, headroom)
    files: list[SpanFile] = []
    for index, size in enumerate(sizes):
        for part, part_size in enumerate(part_sizes(size, usable)):
            files.append(SpanFile(f"{index}.{part}", part_size))
    return plan_volumes(files, capacity_bytes, headroom)


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
