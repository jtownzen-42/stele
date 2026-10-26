"""Civitai as a second model source.

Models are archived per version. Inside Stele a Civitai model is the repo id
`civitai/<model id>` and a version is the revision `v<version id>`, so the vault
and disc layout stay `MODELS/civitai--<model id>/v<version id>/`.

The API key is an argument, never part of repr, and is sent only to
civitai.com, never to the storage host a download redirects to.
"""

from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from stele.hub.client import HubError
from stele.models import HubFile, PlanResult, RepoDetails, SearchHit

API = "https://civitai.com/api/v1"
SITE = "https://civitai.com"
PREFIX = "civitai/"
CIVITAI_HOSTS = ["civitai.com"]
PROFILE_CIVITAI = "Civitai version"
# Files Stele leaves unticked by default: training sets are large and not needed to run the model.
OPTIONAL_TYPES = {"training data"}

MSG_CIVITAI_AUTH = (
    "Civitai refused the download (401/403). Save a Civitai API key in Workspace settings, "
    "and check the model is not early access or removed."
)

_TAG = re.compile(r"<[^>]+>")
_BLOCK = re.compile(r"(?i)</?(p|br|li|h\d|div)[^>]*>")


def is_civitai(repo_id: str) -> bool:
    return str(repo_id).startswith(PREFIX)


def model_id_of(repo_id: str) -> int:
    return int(str(repo_id)[len(PREFIX):].split("/", 1)[0])


def repo_id_for(model_id: int | str) -> str:
    return f"{PREFIX}{int(model_id)}"


def model_url(repo_id: str, version: str = "") -> str:
    url = f"{SITE}/models/{model_id_of(repo_id)}"
    version_id = version.lstrip("v")
    return f"{url}?modelVersionId={version_id}" if version_id.isdigit() else url


class CivitaiClient:
    def __init__(self, api_key: str | None) -> None:
        self._key = api_key or None

    def __repr__(self) -> str:
        return f"CivitaiClient(key={'stored' if self._key else 'absent'})"

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        import httpx

        headers = {"User-Agent": "Stele/1.0"}
        if self._key:
            headers["Authorization"] = f"Bearer {self._key}"
        try:
            response = httpx.get(f"{API}{path}", params=params, headers=headers, timeout=20.0)
        except httpx.RequestError as exc:
            raise HubError(f"Could not reach Civitai: {exc}") from exc
        if response.status_code in (401, 403):
            raise HubError(MSG_CIVITAI_AUTH)
        if response.status_code == 404:
            raise HubError("Civitai has no model with that id. It may have been removed.")
        if response.status_code != 200:
            raise HubError(f"Civitai returned HTTP {response.status_code}.")
        try:
            return response.json()
        except ValueError as exc:
            raise HubError("Civitai sent an unreadable reply.") from exc

    def search(self, query: str, *, model_type: str = "", limit: int = 20) -> list[SearchHit]:
        query = query.strip()
        model_id = _model_id_in(query)
        if model_id is not None:
            return [to_hit(self._get(f"/models/{model_id}"))]
        params: dict[str, Any] = {"query": query, "limit": limit, "nsfw": "false", "sort": "Most Downloaded"}
        if model_type:
            params["types"] = model_type
        data = self._get("/models", params)
        return [to_hit(item) for item in data.get("items") or []]

    def details(self, repo_id: str, revision: str = "") -> RepoDetails:
        return to_details(self._get(f"/models/{model_id_of(repo_id)}"), revision)


def _model_id_in(query: str) -> int | None:
    """A bare id, `civitai/<id>`, or a civitai.com/models/<id> link."""
    if query.isdigit():
        return int(query)
    if is_civitai(query) and query[len(PREFIX):].isdigit():
        return int(query[len(PREFIX):])
    match = re.search(r"civitai\.com/models/(\d+)", query)
    return int(match.group(1)) if match else None


def to_hit(item: dict) -> SearchHit:
    versions = item.get("modelVersions") or []
    latest = versions[0] if versions else {}
    stats = item.get("stats") or {}
    primary = _primary_file(latest.get("files") or [])
    return SearchHit(
        repo_id=repo_id_for(item["id"]),
        author=str((item.get("creator") or {}).get("username") or ""),
        last_modified=str(latest.get("publishedAt") or latest.get("createdAt") or "")[:10],
        downloads=stats.get("downloadCount"),
        likes=stats.get("thumbsUpCount") or stats.get("favoriteCount"),
        pipeline_tag=str(item.get("type") or ""),
        library_name=str(latest.get("baseModel") or ""),
        gated=False,
        tags=[str(tag) for tag in item.get("tags") or []],
        approx_bytes=_file_bytes(primary) if primary else None,
        title=str(item.get("name") or ""),
    )


def to_details(item: dict, revision: str = "") -> RepoDetails:
    versions = item.get("modelVersions") or []
    if not versions:
        raise HubError("This Civitai model has no published versions.")
    wanted = revision.lstrip("v")
    version = next((v for v in versions if str(v.get("id")) == wanted), versions[0])
    version_id = int(version["id"])
    files: list[HubFile] = []
    urls: dict[str, str] = {}
    types: dict[str, str] = {}
    for entry in version.get("files") or []:
        name = str(entry.get("name") or "").replace("\\", "/").strip("/")
        if not name or name in urls:
            continue
        sha = str((entry.get("hashes") or {}).get("SHA256") or "").lower() or None
        files.append(HubFile(path=name, size=_file_bytes(entry), etag=sha))
        urls[name] = str(entry.get("downloadUrl") or f"{SITE}/api/download/models/{version_id}")
        types[name] = str(entry.get("type") or "")
    repo_id = repo_id_for(item["id"])
    meta = {
        "model_id": int(item["id"]),
        "name": item.get("name") or "",
        "type": item.get("type") or "",
        "creator": (item.get("creator") or {}).get("username") or "",
        "tags": item.get("tags") or [],
        "nsfw": bool(item.get("nsfw")),
        "permissions": permissions_of(item),
        "description": _text(item.get("description") or ""),
        "url": model_url(repo_id, f"v{version_id}"),
        "version": {
            "id": version_id,
            "name": version.get("name") or "",
            "base_model": version.get("baseModel") or "",
            "trained_words": version.get("trainedWords") or [],
            "published": version.get("publishedAt") or version.get("createdAt") or "",
            "description": _text(version.get("description") or ""),
        },
        "files": [
            {
                "name": entry.get("name"),
                "type": entry.get("type"),
                "bytes": _file_bytes(entry),
                "sha256": str((entry.get("hashes") or {}).get("SHA256") or "").lower(),
                "metadata": entry.get("metadata") or {},
                "primary": bool(entry.get("primary")),
            }
            for entry in version.get("files") or []
        ],
        "file_types": types,
    }
    return RepoDetails(
        repo_id=repo_id,
        sha=f"v{version_id}",
        revision=f"v{version_id}",
        last_modified=str(meta["version"]["published"])[:10],
        pipeline_tag=str(item.get("type") or ""),
        library_name=str(version.get("baseModel") or ""),
        license_name=license_summary(meta["permissions"]),
        gated=False,
        card_excerpt=card_text(meta)[:2000],
        files=sorted(files, key=lambda f: f.path),
        source="civitai",
        download_urls=urls,
        versions=[(f"{v.get('name') or v['id']} (v{v['id']})", f"v{v['id']}") for v in versions],
        source_meta=meta,
    )


def default_selection(details: RepoDetails) -> list[str]:
    types = details.source_meta.get("file_types") or {}
    return [f.path for f in details.files if str(types.get(f.path, "")).lower() not in OPTIONAL_TYPES]


def permissions_of(item: dict) -> dict:
    commercial = item.get("allowCommercialUse")
    if isinstance(commercial, str):
        commercial = [commercial] if commercial and commercial != "None" else []
    return {
        "commercial_use": list(commercial or []),
        "derivatives": bool(item.get("allowDerivatives", True)),
        "different_license": bool(item.get("allowDifferentLicense", True)),
        "credit_required": not bool(item.get("allowNoCredit", True)),
    }


def license_summary(perms: dict) -> str:
    commercial = ", ".join(perms.get("commercial_use") or []) or "none"
    return (
        f"Civitai permissions: commercial use {commercial}; "
        f"derivatives {'allowed' if perms.get('derivatives') else 'not allowed'}; "
        f"credit {'required' if perms.get('credit_required') else 'not required'}"
    )


def card_text(meta: dict) -> str:
    version = meta.get("version") or {}
    lines = [
        f"{meta.get('name')} by {meta.get('creator') or 'unknown'} on Civitai",
        f"Type: {meta.get('type')} · Base model: {version.get('base_model') or 'not declared'}",
        f"Version: {version.get('name')} (v{version.get('id')})",
    ]
    words = version.get("trained_words") or []
    if words:
        lines.append("Trigger words: " + ", ".join(str(word) for word in words))
    lines.append(license_summary(meta.get("permissions") or {}))
    lines.append("")
    lines.append(meta.get("description") or "No description.")
    return "\n".join(lines)


def resolve_download(url: str, api_key: str | None) -> str:
    """Follow civitai.com redirects with the key and return the storage URL.

    The key never leaves civitai.com. The storage URL is short-lived and
    signed, so each attempt resolves it again; that keeps resume working.
    """
    import httpx

    headers = {"User-Agent": "Stele/1.0"}
    current = url
    with httpx.Client(timeout=httpx.Timeout(30.0), follow_redirects=False) as client:
        for _hop in range(6):
            host = (urlparse(current).hostname or "").lower()
            if host != "civitai.com" and not host.endswith(".civitai.com"):
                return current
            send = dict(headers)
            if api_key:
                send["Authorization"] = f"Bearer {api_key}"
            response = client.send(client.build_request("GET", current, headers=send), stream=True)
            response.close()
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("location")
                if not location:
                    break
                current = urljoin(current, location)
                if "/login" in urlparse(current).path:
                    raise HubError(MSG_CIVITAI_AUTH)
                continue
            if response.status_code in (401, 403):
                raise HubError(MSG_CIVITAI_AUTH)
            if response.status_code == 200:
                # Served directly by civitai.com; stream it from there.
                return current
            raise HubError(f"Civitai returned HTTP {response.status_code} for the download.")
    raise HubError("Civitai did not hand over a download location.")


def _primary_file(files: list[dict]) -> dict | None:
    for entry in files:
        if entry.get("primary"):
            return entry
    return files[0] if files else None


def _file_bytes(entry: dict) -> int | None:
    size = entry.get("sizeKB")
    return int(round(float(size) * 1024)) if size is not None else None


def _text(markup: str) -> str:
    text = _BLOCK.sub("\n", markup)
    text = html.unescape(_TAG.sub("", text))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def plan_civitai(files: list[HubFile], selected: list[str], capacity_bytes: int | None = None) -> PlanResult:
    """The download set for one Civitai version: the files the user ticked."""
    from stele.burn.span import estimate_volumes

    wanted = set(selected)
    planned = [item for item in files if item.path in wanted]
    blocked = None if planned else "Select at least one file to archive."
    estimate: int | None = None
    if planned and capacity_bytes:
        span = estimate_volumes([item.known_size for item in planned], capacity_bytes)
        if span.error:
            blocked = span.error
        else:
            estimate = len(span.volumes)
    elif planned:
        estimate = 1
    return PlanResult(
        profile_requested=PROFILE_CIVITAI,
        profile_used=PROFILE_CIVITAI,
        fallback_note=None,
        files=planned,
        total_bytes=sum(item.known_size for item in planned),
        disc_estimate=estimate,
        blocked_reason=blocked,
    )
