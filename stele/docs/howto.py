"""How-to-use guide stored beside the specification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from stele.docs.spec import ModelFacts
from stele.models import DISCLAIMER

VERIFY_PROMPT = "Reply with the single word stele."


@dataclass
class HowtoGuide:
    repo_id: str
    commit_sha: str
    safe_id: str
    profile: str
    license_name: str
    library_name: str
    facts: ModelFacts
    gguf_paths: list[str]
    markdown: str


def build_howto(
    *,
    repo_id: str,
    commit_sha: str,
    safe_id: str,
    profile: str,
    license_name: str,
    library_name: str,
    facts: ModelFacts,
    gguf_paths: list[str],
) -> HowtoGuide:
    gguf = gguf_paths[0] if gguf_paths else ""
    disc_gguf = f"MODELS/{safe_id}/{commit_sha}/{gguf}" if gguf else ""
    if repo_id.startswith("civitai/"):
        order = (
            f"This is a Civitai model for {library_name or 'an undeclared base model'}. Load it in an image "
            "generation front end that supports that base model, such as ComfyUI, Forge, or InvokeAI. "
            "LM Studio, Ollama, and llama.cpp do not load it."
        )
        description = (
            f"This Stele archive holds Civitai model {repo_id} version {commit_sha} as downloaded files. "
            "civitai_model.json beside the weights keeps the description, trigger words, base model, "
            "and the creator's permissions as Civitai showed them."
        )
    elif gguf_paths:
        order = "GGUF files on this disc: use LM Studio first, then Ollama, then llama.cpp."
        description = (
            f"This Stele archive holds {repo_id} at commit {commit_sha[:12]} "
            f"as a {profile}. The GGUF weights are the files you load. "
            "Tokenizer, config, license, and README files sit beside them when the repository published them."
        )
    else:
        order = (
            "These weights are not GGUF. LM Studio, Ollama, and the llama.cpp packs on a Stele disc "
            f"do not load them directly. The Hub library tag is {library_name or 'not declared'}."
        )
        description = (
            f"This Stele archive holds {repo_id} at commit {commit_sha[:12]} as a {profile}. "
            "Use the library named above, pointed at the MODELS folder, if you need to run it."
        )
    lines = [
        f"# How to use {repo_id}",
        "",
        description,
        "",
        "## Recommended runtime order",
        "",
        order,
        "",
        "## LM Studio",
        "",
        "1. Install LM Studio from the copy on this disc if RUNTIME/LMStudio is present, or from your own installer. Stele does not run the installer.",
        "2. Open LM Studio and choose the local model directory.",
        f"3. Point it at `{disc_gguf or 'MODELS/' + safe_id}`." if gguf else "3. LM Studio loads GGUF. This archive has no GGUF file.",
        "4. Load the model and start a new chat.",
        "",
        "## Ollama",
        "",
        "GGUF import varies by Ollama version. The files are under MODELS. Stele does not register a Modelfile for you and does not run OllamaSetup.exe.",
        "If your Ollama build can create a model from a GGUF file, use the GGUF path above and a one-line Modelfile: `FROM <path-to-gguf>`.",
        "",
        "## llama.cpp",
        "",
        "Unpack the official Windows zip from RUNTIME/llama.cpp if you archived it. Then, from that folder:",
        "",
        f"`llama-cli -m {disc_gguf or '<path-to-gguf>'}`" if True else "",
        "",
        "## First verification",
        "",
        f"Ask the model: {VERIFY_PROMPT}",
        "",
        "## Limits",
        "",
        f"- Context: {facts.context}",
        f"- Vision: {facts.vision}",
        f"- Tools: {facts.tools}",
        f"- License: {license_name}",
        "",
        "## Restore from this disc",
        "",
        "The disc does not need a network connection.",
        "",
        "`powershell -ExecutionPolicy Bypass -File .\\RESTORE.ps1 -Destination D:\\Restored`",
        "",
        "The script copies MODELS, DOCS, and RUNTIME (if present) into the destination you pass and checks every file against checksums.sha256.",
        "On a multi-disc set, run it once for each volume into the same destination. VOLUME.json names the other discs.",
        "",
        DISCLAIMER,
        "",
    ]
    return HowtoGuide(
        repo_id=repo_id,
        commit_sha=commit_sha,
        safe_id=safe_id,
        profile=profile,
        license_name=license_name,
        library_name=library_name,
        facts=facts,
        gguf_paths=list(gguf_paths),
        markdown="\n".join(lines),
    )


def write_howto_markdown(guide: HowtoGuide, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(guide.markdown, encoding="utf-8")
