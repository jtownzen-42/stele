"""Thin HfApi wrapper. The token is an argument, never part of repr."""

from __future__ import annotations

from stele.models import MSG_AUTH, MSG_GATED, HubFile, RepoDetails, SearchHit


class HubError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class HubClient:
    def __init__(self, token: str | None) -> None:
        self._token = token or None

    def __repr__(self) -> str:
        state = "stored" if self._token else "absent"
        return f"HubClient(token={state})"

    def _api(self):
        from huggingface_hub import HfApi

        return HfApi(token=self._token)

    def search(
        self,
        query: str,
        *,
        pipeline_tag: str = "",
        library: str = "",
        license_id: str = "",
        gated: str = "",
        limit: int = 20,
    ) -> list[SearchHit]:
        api = self._api()
        kwargs: dict = {"search": query or None, "limit": limit, "expand": ["lastModified"]}
        if pipeline_tag:
            kwargs["filter"] = pipeline_tag
        if library:
            kwargs["library"] = library
        try:
            models = list(api.list_models(**kwargs))
        except Exception as exc:
            raise _translate(exc) from exc
        hits: list[SearchHit] = []
        for model in models:
            gated_flag = _is_gated(getattr(model, "gated", False))
            if gated == "gated" and not gated_flag:
                continue
            if gated == "ungated" and gated_flag:
                continue
            card = getattr(model, "card_data", None)
            license_name = ""
            if card is not None:
                license_name = str(getattr(card, "license", "") or "")
                if not license_name and isinstance(card, dict):
                    license_name = str(card.get("license") or "")
            if license_id and license_name and license_name != license_id:
                continue
            repo_id = str(getattr(model, "id", ""))
            author = repo_id.split("/", 1)[0] if "/" in repo_id else repo_id
            modified = getattr(model, "last_modified", None) or getattr(model, "created_at", None)
            hits.append(
                SearchHit(
                    repo_id=repo_id,
                    author=author,
                    last_modified=modified.strftime("%Y-%m-%d") if hasattr(modified, "strftime") else str(modified or ""),
                    downloads=getattr(model, "downloads", None),
                    likes=getattr(model, "likes", None),
                    pipeline_tag=str(getattr(model, "pipeline_tag", "") or ""),
                    library_name=str(getattr(model, "library_name", "") or ""),
                    gated=gated_flag,
                    tags=list(getattr(model, "tags", None) or []),
                )
            )
        self._fill_sizes(api, hits)
        return hits

    @staticmethod
    def _fill_sizes(api, hits: list[SearchHit]) -> None:
        """Total size of every file in each repo, fetched in parallel. Failures leave the size unknown."""
        from concurrent.futures import ThreadPoolExecutor

        def total(hit: SearchHit) -> int | None:
            try:
                info = api.model_info(hit.repo_id, files_metadata=True)
            except Exception:
                return None
            sizes = []
            for sibling in getattr(info, "siblings", None) or []:
                size = getattr(sibling, "size", None)
                lfs = getattr(sibling, "lfs", None)
                if size is None and lfs is not None:
                    size = getattr(lfs, "size", None)
                if size is not None:
                    sizes.append(int(size))
            return sum(sizes) if sizes else None

        if not hits:
            return
        with ThreadPoolExecutor(max_workers=8) as pool:
            for hit, size in zip(hits, pool.map(total, hits)):
                hit.approx_bytes = size

    def details(self, repo_id: str, revision: str = "main") -> RepoDetails:
        api = self._api()
        try:
            info = api.model_info(repo_id, revision=revision, files_metadata=True)
        except Exception as exc:
            raise _translate(exc) from exc
        gated_flag = _is_gated(getattr(info, "gated", False))
        if gated_flag and not self._token:
            raise HubError(MSG_GATED)
        files: list[HubFile] = []
        for sibling in getattr(info, "siblings", None) or []:
            name = getattr(sibling, "rfilename", None) or getattr(sibling, "path", None)
            if not name:
                continue
            size = getattr(sibling, "size", None)
            lfs = getattr(sibling, "lfs", None)
            etag = None
            if lfs is not None:
                etag = getattr(lfs, "sha256", None) or getattr(lfs, "oid", None)
                if size is None:
                    size = getattr(lfs, "size", None)
            files.append(HubFile(path=str(name), size=size, etag=etag))
        card_text = _card_text(repo_id, self._token)
        license_name = _license_of(info) or "unknown"
        sha = str(getattr(info, "sha", "") or "")
        modified = getattr(info, "last_modified", None)
        return RepoDetails(
            repo_id=repo_id,
            sha=sha,
            revision=revision,
            last_modified=modified.strftime("%Y-%m-%d") if hasattr(modified, "strftime") else str(modified or ""),
            pipeline_tag=str(getattr(info, "pipeline_tag", "") or ""),
            library_name=str(getattr(info, "library_name", "") or ""),
            license_name=license_name,
            gated=gated_flag,
            card_excerpt=card_text[:2000],
            files=sorted(files, key=lambda item: item.path),
            private=bool(getattr(info, "private", False)),
        )


def _is_gated(value) -> bool:
    if value is True:
        return True
    if isinstance(value, str) and value and value.lower() != "false":
        return True
    return False


def _license_of(info) -> str:
    card = getattr(info, "card_data", None)
    if card is None:
        return ""
    if isinstance(card, dict):
        return str(card.get("license") or card.get("license_name") or "")
    return str(getattr(card, "license", "") or getattr(card, "license_name", "") or "")


def _card_text(repo_id: str, token: str | None) -> str:
    try:
        from huggingface_hub import ModelCard

        card = ModelCard.load(repo_id, token=token)
        return str(getattr(card, "text", "") or "")
    except Exception:
        return ""


def _translate(exc: Exception) -> HubError:
    status = getattr(exc, "response", None)
    code = getattr(status, "status_code", None) or getattr(exc, "status_code", None)
    text = str(exc).lower()
    if code in (401, 403) or "401" in text or "403" in text:
        return HubError(MSG_AUTH)
    if "gated" in text or "access" in text and "restricted" in text:
        return HubError(MSG_GATED)
    return HubError(str(exc).splitlines()[0][:300])
