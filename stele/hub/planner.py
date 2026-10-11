"""Turn a Hub file listing and a profile into the exact file set to archive."""

from __future__ import annotations

from pathlib import Path

from stele.burn.span import plan_volumes
from stele.models import (
    PROFILE_FULL,
    PROFILE_GGUF,
    PROFILE_INFERENCE,
    PROFILE_RUNTIME,
    HubFile,
    PlanResult,
    SpanFile,
)

_ANCILLARY_NAMES = {
    "tokenizer.json",
    "tokenizer.model",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "config.json",
    "generation_config.json",
}


def is_ancillary(path: str) -> bool:
    name = Path(path).name.lower()
    if name in _ANCILLARY_NAMES:
        return True
    if name.startswith("chat_template"):
        return True
    if name.startswith("readme"):
        return True
    if name.startswith("license") or name.startswith("licence"):
        return True
    return False


def is_gguf(path: str) -> bool:
    return Path(path).name.lower().endswith(".gguf")


def default_gguf(files: list[HubFile]) -> str | None:
    """One sensible GGUF so Add to Queue is not stuck waiting on a hidden checkbox.

    Prefer a Q4_K_M file when the repo has one. Otherwise the smallest GGUF.
    """
    ggufs = [item for item in files if is_gguf(item.path)]
    if not ggufs:
        return None
    for item in ggufs:
        if "Q4_K_M" in Path(item.path).name.upper():
            return item.path
    return min(ggufs, key=lambda item: item.size if item.size is not None else 10**18).path


def is_weight(path: str) -> bool:
    name = Path(path).name.lower()
    if name.endswith(".pt"):
        return False
    if name.startswith("optimizer") or "optimizer" in name:
        return False
    if name.startswith("training_args"):
        return False
    if name.endswith(".safetensors") or name.endswith(".bin"):
        return True
    return False


def _index(files: list[HubFile]) -> dict[str, HubFile]:
    return {item.path: item for item in files}


def _take(index: dict[str, HubFile], paths: list[str]) -> list[HubFile]:
    chosen: list[HubFile] = []
    seen: set[str] = set()
    for path in paths:
        if path in seen or path not in index:
            continue
        seen.add(path)
        chosen.append(index[path])
    return chosen


def plan_profile(
    profile: str,
    files: list[HubFile],
    *,
    selected_gguf: list[str] | None = None,
    capacity_bytes: int | None = None,
) -> PlanResult:
    """Build the download set.

    GGUF with no .gguf files falls back to Inference pack and says so.
    Runtime kit plans no model files; the pack is a separate job.
    """
    index = _index(files)
    requested = profile
    note: str | None = None
    used = profile
    selected = list(selected_gguf or [])

    if profile == PROFILE_RUNTIME:
        planned: list[HubFile] = []
    elif profile == PROFILE_FULL:
        planned = list(files)
    elif profile == PROFILE_GGUF:
        ggufs = [item.path for item in files if is_gguf(item.path)]
        if not ggufs:
            used = PROFILE_INFERENCE
            note = (
                "This repository has no GGUF files. Stele switched the profile to "
                "Inference pack and will queue those weights instead."
            )
            planned = _inference_files(index)
        else:
            wanted = [path for path in selected if path in index and is_gguf(path)]
            if not wanted:
                note = "Select at least one GGUF file before queueing this profile."
                planned = _take(index, [item.path for item in files if is_ancillary(item.path)])
            else:
                ancillary = [item.path for item in files if is_ancillary(item.path)]
                planned = _take(index, wanted + ancillary)
    elif profile == PROFILE_INFERENCE:
        planned = _inference_files(index)
    else:
        used = PROFILE_INFERENCE
        note = f"Unknown profile {profile!r}. Stele used Inference pack."
        planned = _inference_files(index)

    total = sum(item.known_size for item in planned)
    estimate: int | None = None
    blocked: str | None = None
    if profile == PROFILE_GGUF and used == PROFILE_GGUF and note and note.startswith("Select at least"):
        blocked = note
    if capacity_bytes and planned and blocked is None:
        span = plan_volumes(
            [SpanFile(item.path, item.known_size) for item in planned],
            capacity_bytes,
        )
        if span.error:
            blocked = span.error
            estimate = None
        else:
            estimate = len(span.volumes)
    elif planned and blocked is None:
        estimate = 1

    return PlanResult(
        profile_requested=requested,
        profile_used=used,
        fallback_note=note,
        files=planned,
        total_bytes=total,
        disc_estimate=estimate,
        blocked_reason=blocked,
    )


def _inference_files(index: dict[str, HubFile]) -> list[HubFile]:
    paths = [path for path in index if is_weight(path) or is_ancillary(path)]
    return _take(index, paths)
