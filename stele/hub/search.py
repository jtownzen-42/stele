"""Search helpers that sit on HubClient. Format filters need a file list."""

from __future__ import annotations

from stele.hub.client import HubClient
from stele.hub.planner import is_gguf, is_weight
from stele.models import RepoDetails, SearchHit


def search_models(
    client: HubClient,
    query: str,
    *,
    pipeline_tag: str = "",
    library: str = "",
    license_id: str = "",
    gated: str = "",
    format_present: str = "",
) -> list[SearchHit]:
    hits = client.search(
        query,
        pipeline_tag=pipeline_tag,
        library=library,
        license_id=license_id,
        gated=gated,
    )
    if not format_present:
        return hits
    wanted = format_present.lower()
    kept: list[SearchHit] = []
    for hit in hits:
        tags = {tag.lower() for tag in hit.tags}
        if wanted == "gguf" and ("gguf" in tags or hit.library_name.lower() == "gguf"):
            kept.append(hit)
        elif wanted == "safetensors" and "safetensors" in tags:
            kept.append(hit)
        elif wanted == "gguf" and "gguf" not in tags:
            # Tag-less repos still count when the caller already filtered.
            continue
        else:
            continue
    return kept


def repo_has_format(details: RepoDetails, format_present: str) -> bool:
    if not format_present:
        return True
    if format_present.lower() == "gguf":
        return any(is_gguf(item.path) for item in details.files)
    if format_present.lower() == "safetensors":
        return any(item.path.lower().endswith(".safetensors") or is_weight(item.path) for item in details.files)
    return True
