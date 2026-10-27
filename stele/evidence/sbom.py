"""CycloneDX 1.6 JSON SBOM for one vault item."""

from __future__ import annotations

import uuid
from urllib.parse import quote

from stele import __version__
from stele.evidence.provenance import EvidenceItem

SPEC_VERSION = "1.6"

# Hub license tags that map to an SPDX id without guessing. Anything else is
# written as a license name, exactly as Stele recorded it.
SPDX_IDS = {
    "apache-2.0": "Apache-2.0",
    "mit": "MIT",
    "bsd-2-clause": "BSD-2-Clause",
    "bsd-3-clause": "BSD-3-Clause",
    "cc0-1.0": "CC0-1.0",
    "cc-by-4.0": "CC-BY-4.0",
    "cc-by-sa-4.0": "CC-BY-SA-4.0",
    "cc-by-nc-4.0": "CC-BY-NC-4.0",
    "cc-by-nc-sa-4.0": "CC-BY-NC-SA-4.0",
    "cc-by-nc-nd-4.0": "CC-BY-NC-ND-4.0",
    "gpl-3.0": "GPL-3.0-only",
    "agpl-3.0": "AGPL-3.0-only",
    "lgpl-3.0": "LGPL-3.0-only",
    "mpl-2.0": "MPL-2.0",
    "unlicense": "Unlicense",
}


def license_choice(name: str) -> list[dict]:
    cleaned = (name or "").strip()
    if not cleaned or cleaned.lower() == "unknown":
        return []
    spdx = SPDX_IDS.get(cleaned.lower())
    return [{"license": {"id": spdx}}] if spdx else [{"license": {"name": cleaned}}]


def purl(item: EvidenceItem) -> str | None:
    if item.source != "huggingface" or "/" not in item.repo_id or not item.commit_sha:
        return None
    namespace, name = item.repo_id.split("/", 1)
    return f"pkg:huggingface/{quote(namespace)}/{quote(name)}@{item.commit_sha.lower()}"


def build_sbom(item: EvidenceItem, stamp: dict[str, str]) -> dict:
    """The SBOM document. Call provenance.measure() first so hashes are current."""
    main: dict = {
        "type": "machine-learning-model" if item.kind == "model" else "application",
        "bom-ref": "item",
        "name": item.repo_id,
        "version": item.commit_sha or item.revision or "unknown",
    }
    item_purl = purl(item)
    if item_purl:
        main["purl"] = item_purl
    licenses = license_choice(item.license_name)
    if licenses:
        main["licenses"] = licenses
    if item.page_url:
        main["externalReferences"] = [{"type": "website", "url": item.page_url}]
    properties = [
        ("stele:source", item.source),
        ("stele:profile", item.profile),
        ("stele:license_acknowledged_utc", item.license_ack_utc),
        ("stele:archived_utc", item.archived_utc),
        ("stele:timestamp_source", stamp["source"]),
    ]
    main["properties"] = [{"name": key, "value": value} for key, value in properties if value]

    components: list[dict] = []
    for entry in item.files:
        component: dict = {"type": "file", "bom-ref": f"file:{entry.path}", "name": entry.path}
        if entry.sha256:
            component["hashes"] = [{"alg": "SHA-256", "content": entry.sha256}]
        if entry.download_url:
            component["externalReferences"] = [{"type": "distribution", "url": entry.download_url}]
        component["properties"] = [
            {"name": "stele:bytes", "value": str(entry.bytes)},
            {"name": "stele:status", "value": entry.status},
        ]
        components.append(component)

    return {
        "bomFormat": "CycloneDX",
        "specVersion": SPEC_VERSION,
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": stamp["utc"],
            "tools": {"components": [{"type": "application", "name": "Stele", "version": __version__}]},
            "component": main,
        },
        "components": components,
        "dependencies": [{"ref": "item", "dependsOn": [component["bom-ref"] for component in components]}],
    }
