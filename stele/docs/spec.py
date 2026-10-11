"""Technical specification sheet for one archived model."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from stele.models import DISCLAIMER, FULL_LICENSE_NOTE, human_bytes

_QUANT = re.compile(
    r"(IQ\d+_[A-Z0-9]+|Q\d+_K_[A-Z0-9]+|Q\d+_\d(?:_[A-Z0-9]+)?|BF16|F16|F32|Q8_0|Q6_K|Q5_K|Q4_K|Q3_K|Q2_K)",
    re.IGNORECASE,
)


@dataclass
class FileRow:
    path: str
    nbytes: int
    sha256: str


@dataclass
class ModelFacts:
    architecture: str
    parameter_count: str
    context: str
    vocab: str
    vision: str
    tools: str


@dataclass
class SpecSheet:
    repo_id: str
    revision: str
    commit_sha: str
    snapshot_utc: str
    license_name: str
    license_excerpt: str
    profile: str
    pipeline_tag: str
    library_name: str
    facts: ModelFacts
    files: list[FileRow]
    quants: list[str]
    safetensors_dtypes: list[str]
    weight_bytes: int
    hardware_class: str
    format_tags: list[str] = field(default_factory=list)

    def summary_line(self) -> str:
        return (
            f"{self.repo_id} @ {self.commit_sha[:12]} · {self.profile} · "
            f"{self.facts.architecture} · {self.hardware_class}"
        )


def parse_facts(config: dict | None, card: str | None) -> ModelFacts:
    config = config or {}
    card = card or ""
    architectures = config.get("architectures")
    architecture = None
    if isinstance(architectures, list) and architectures:
        architecture = str(architectures[0])
    architecture = architecture or config.get("model_type") or _first(card, r"architecture[:\s]+([A-Za-z0-9_\-]+)")
    params = config.get("num_parameters") or config.get("n_params")
    if params is None:
        match = re.search(r"(\d+(?:\.\d+)?)\s*[Bb](?:illion)?\b", card)
        params_text = f"{match.group(1)}B" if match else "not declared on this disc"
    else:
        params_text = str(params)
    text_config = config.get("text_config") if isinstance(config.get("text_config"), dict) else {}
    context = (
        config.get("max_position_embeddings")
        or config.get("max_sequence_length")
        or config.get("n_ctx")
        or config.get("model_max_length")
        or text_config.get("max_position_embeddings")
    )
    vocab = config.get("vocab_size") or text_config.get("vocab_size")
    blob = json.dumps(config).lower()
    if "vision_config" in config or "vision" in str(architecture or "").lower() or "image-text" in blob:
        vision = "declared in config"
    elif re.search(r"\bvision\b|\bmultimodal\b", card, re.I):
        vision = "mentioned on the model card"
    else:
        vision = "not declared on this disc"
    if config.get("tool_call") or "tools" in blob:
        tools = "declared in config"
    elif re.search(r"\btool ?calling\b|\bfunction calling\b", card, re.I):
        tools = "mentioned on the model card"
    else:
        tools = "not declared on this disc"
    return ModelFacts(
        architecture=str(architecture or "not declared on this disc"),
        parameter_count=params_text,
        context=str(context) if context else "not declared on this disc",
        vocab=str(vocab) if vocab else "not declared on this disc",
        vision=vision,
        tools=tools,
    )


def _first(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, re.I)
    return match.group(1) if match else None


def quant_tags(paths: list[str]) -> list[str]:
    found: list[str] = []
    for path in paths:
        for match in _QUANT.findall(Path(path).name):
            tag = match.upper()
            if tag not in found:
                found.append(tag)
    return found


def hardware_class(weight_bytes: int) -> str:
    if weight_bytes <= 0:
        return "CPU-only"
    need = (weight_bytes / (1024 ** 3)) * 1.15
    if need <= 8:
        return "8 GB"
    if need <= 12:
        return "12 GB"
    if need <= 24:
        return "24 GB"
    return "CPU-only"


def safetensors_dtype(path: Path) -> str | None:
    try:
        with path.open("rb") as handle:
            raw = handle.read(8)
            if len(raw) < 8:
                return None
            length = int.from_bytes(raw, "little")
            if length <= 0 or length > 8_000_000:
                return None
            header = json.loads(handle.read(length))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(header, dict):
        return None
    for key, value in header.items():
        if key == "__metadata__" or not isinstance(value, dict):
            continue
        dtype = value.get("dtype")
        if dtype:
            return str(dtype)
    return None


def build_spec(
    *,
    repo_id: str,
    revision: str,
    commit_sha: str,
    snapshot_utc: str,
    license_name: str,
    license_excerpt: str,
    card_excerpt: str,
    profile: str,
    pipeline_tag: str,
    library_name: str,
    config: dict | None,
    inventory: list[dict],
    weight_paths: list[Path],
) -> SpecSheet:
    facts = parse_facts(config, card_excerpt)
    rows = [
        FileRow(path=str(item["path"]), nbytes=int(item["bytes"]), sha256=str(item.get("sha256") or ""))
        for item in inventory
    ]
    quants = quant_tags([row.path for row in rows])
    dtypes: list[str] = []
    weight_bytes = 0
    tags: list[str] = []
    for row, path in zip(rows, weight_paths, strict=False):
        name = path.name.lower()
        if name.endswith(".gguf") or name.endswith(".safetensors") or name.endswith(".bin"):
            weight_bytes += row.nbytes
        if name.endswith(".gguf") and "gguf" not in tags:
            tags.append("gguf")
        if name.endswith(".safetensors"):
            if "safetensors" not in tags:
                tags.append("safetensors")
            dtype = safetensors_dtype(path)
            if dtype and dtype not in dtypes:
                dtypes.append(dtype)
    for quant in quants:
        if quant not in tags:
            tags.append(quant)
    gb = weight_bytes / (1024 ** 3) if weight_bytes else 0
    excerpt = (license_excerpt or "").strip()
    if len(excerpt) > 500:
        excerpt = excerpt[:500].rstrip() + "…"
    return SpecSheet(
        repo_id=repo_id,
        revision=revision,
        commit_sha=commit_sha,
        snapshot_utc=snapshot_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        license_name=license_name or "unknown",
        license_excerpt=excerpt,
        profile=profile,
        pipeline_tag=pipeline_tag,
        library_name=library_name,
        facts=facts,
        files=rows,
        quants=quants,
        safetensors_dtypes=dtypes,
        weight_bytes=weight_bytes,
        hardware_class=hardware_class(weight_bytes),
        format_tags=tags,
    )


def render_spec_markdown(spec: SpecSheet) -> str:
    lines = [
        f"# {spec.repo_id}",
        "",
        "Technical specification generated by Stele.",
        "",
        f"- Repository: `{spec.repo_id}`",
        f"- Revision: `{spec.revision}`",
        f"- Commit: `{spec.commit_sha}`",
        f"- Snapshot UTC: {spec.snapshot_utc}",
        f"- Profile: {spec.profile}",
        f"- Pipeline: {spec.pipeline_tag or 'not declared'}",
        f"- Library: {spec.library_name or 'not declared'}",
        "",
        "## License",
        "",
        f"Name: {spec.license_name}",
        "",
        spec.license_excerpt or "(no excerpt captured)",
        "",
        f"{FULL_LICENSE_NOTE}.",
        "",
        DISCLAIMER,
        "",
        "## Architecture",
        "",
        f"- Architecture: {spec.facts.architecture}",
        f"- Parameter count: {spec.facts.parameter_count}",
        f"- Context: {spec.facts.context}",
        f"- Vocab: {spec.facts.vocab}",
        "",
        "## Format",
        "",
        f"- GGUF quants: {', '.join(spec.quants) if spec.quants else 'none'}",
        f"- Safetensors dtype: {', '.join(spec.safetensors_dtypes) if spec.safetensors_dtypes else 'none'}",
        (
            f"- Weights about {spec.weight_bytes / (1024 ** 3):.2f} GB. "
            "Plan headroom for the KV cache on top of that."
            if spec.weight_bytes
            else "- Weights: none measured."
        ),
        f"- Hardware class hint: {spec.hardware_class}",
        "",
        "## Files",
        "",
        "| Path | Bytes | SHA-256 |",
        "| --- | ---: | --- |",
    ]
    for row in spec.files:
        lines.append(f"| `{row.path}` | {human_bytes(row.nbytes)} | `{row.sha256}` |")
    lines.append("")
    return "\n".join(lines)


def write_spec_markdown(spec: SpecSheet, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_spec_markdown(spec), encoding="utf-8")
