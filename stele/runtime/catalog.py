"""Read the frozen runtime manifest and recommend a pack for a model format."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from stele.download.worker import assert_url_allowed

_MANIFEST = Path(__file__).with_name("manifest.json")

GGUF_ORDER = ("lmstudio", "ollama", "llama-cpp-cpu", "llama-cpp-cuda")


@lru_cache(maxsize=1)
def load_packs() -> tuple[dict, ...]:
    raw = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    packs = tuple(raw["packs"])
    for pack in packs:
        assert_url_allowed(str(pack["url"]), list(pack["allow"]))
    return packs


def get_pack(pack_id: str) -> dict:
    for pack in load_packs():
        if pack["id"] == pack_id:
            return pack
    raise KeyError(pack_id)


def recommend(model_format: str) -> list[str]:
    """Pack ids in the order Stele suggests. Empty when the model is not GGUF."""
    if model_format.lower() != "gguf":
        return []
    return list(GGUF_ORDER)
