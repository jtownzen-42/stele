"""Persistent queue operations on top of SQLite.

Enqueue never starts a second transfer. The worker is the only thing that
promotes a queued job, and only when nothing is active or paused.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from stele.db import Database, loads_meta, utc_now
from stele.download.worker import hash_file, write_checksum_file
from stele.models import DISCLAIMER, HubFile, safe_repo
from stele.settings import Settings

log = logging.getLogger("stele.queue")


class Queue:
    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    def enqueue_model(
        self,
        *,
        repo_id: str,
        revision: str,
        commit_sha: str,
        profile: str,
        license_name: str,
        license_excerpt: str,
        license_ack_utc: str | None,
        card_excerpt: str,
        pipeline_tag: str,
        library_name: str,
        files: list[HubFile],
        source: str = "huggingface",
        download_urls: dict[str, str] | None = None,
        source_meta: dict | None = None,
    ) -> int:
        if not license_ack_utc:
            raise ValueError("Acknowledge the license before queueing.")
        if not files:
            raise ValueError("Nothing to download for this profile.")
        if not commit_sha:
            raise ValueError("The revision has no commit SHA yet.")
        staging_note = str(self.settings.staging())
        meta = {
            "license_excerpt": license_excerpt,
            "card_excerpt": card_excerpt,
        }
        if source == "civitai":
            urls = download_urls or {}
            missing = [item.path for item in files if item.path not in urls]
            if missing:
                raise ValueError(f"No Civitai download link for {missing[0]}.")
            meta.update(
                {
                    "source": "civitai",
                    "download_urls": {item.path: urls[item.path] for item in files},
                    "civitai": source_meta or {},
                }
            )
        job_id = self.db.insert_job(
            {
                "kind": "model",
                "repo_id": repo_id,
                "revision": revision,
                "commit_sha": commit_sha,
                "profile": profile,
                "license_name": license_name,
                "license_excerpt": license_excerpt,
                "license_ack_utc": license_ack_utc,
                "card_excerpt": card_excerpt,
                "pipeline_tag": pipeline_tag,
                "library_name": library_name,
                "bytes_total": sum(item.known_size for item in files),
                "staging_path": staging_note,
                "meta_json": json.dumps(meta),
            },
            [
                {
                    "relative_path": item.path,
                    "size": item.size,
                    "etag": item.etag,
                    "local_path": "",
                }
                for item in files
            ],
        )
        staging = self.settings.staging() / str(job_id)
        self.db.set_job_staging(job_id, str(staging))
        for row in self.db.list_files(job_id):
            local = staging / str(row["relative_path"])
            self.db.set_file_local(int(row["id"]), str(local), row.get("etag"), row.get("size"))
        return job_id

    def enqueue_runtime(self, pack: dict) -> int:
        filename = str(pack["filename"])
        size = pack.get("size")
        meta = {
            "url": pack["url"],
            "allow": pack["allow"],
            "sha256": pack.get("sha256"),
            "folder": pack["folder"],
            "filename": filename,
            "homepage": pack.get("homepage"),
            "version": pack["version"],
            "pack_id": pack["id"],
        }
        job_id = self.db.insert_job(
            {
                "kind": "runtime",
                "repo_id": pack["id"],
                "revision": pack["version"],
                "commit_sha": pack["version"],
                "profile": "Runtime kit",
                "license_name": pack.get("license_name") or "vendor terms",
                "license_excerpt": pack.get("notes") or "",
                "license_ack_utc": utc_now(),
                "card_excerpt": pack.get("notes") or "",
                "pipeline_tag": "",
                "library_name": "",
                "bytes_total": int(size or 0),
                "staging_path": "",
                "meta_json": json.dumps(meta),
            },
            [{"relative_path": filename, "size": size, "etag": pack.get("sha256"), "local_path": ""}],
        )
        staging = self.settings.staging() / str(job_id)
        self.db.set_job_staging(job_id, str(staging))
        local = staging / filename
        file_row = self.db.list_files(job_id)[0]
        self.db.set_file_local(int(file_row["id"]), str(local), pack.get("sha256"), size)
        return job_id

    def pause(self) -> None:
        self.db.pause_holding()

    def resume(self, job_id: int) -> str | None:
        return self.db.resume_job(job_id)

    def cancel(self, job_id: int) -> None:
        self.db.cancel_job(job_id)

    def purge_incomplete(self, job_id: int) -> list[str]:
        """Delete partials and unfinished files for this job. Finished files stay."""
        removed: list[str] = []
        for row in self.db.list_files(job_id):
            if row["status"] == "done":
                continue
            local = row.get("local_path")
            if not local:
                continue
            path = Path(str(local))
            partial = Path(str(path) + ".partial")
            for candidate in (path, partial):
                if candidate.exists() and candidate.is_file():
                    candidate.unlink()
                    removed.append(str(candidate))
        return removed

    def reorder(self, job_id: int, direction: int) -> None:
        self.db.reorder(job_id, direction)

    def retry_file(self, file_id: int) -> int | None:
        return self.db.requeue_file(file_id)

    def finish_if_ready(self, job_id: int, notify=None) -> None:
        job = self.db.get_job(job_id)
        if job is None or job["status"] != "active":
            return
        counts = self.db.file_counts(job_id)
        pending = counts.get("pending", 0) + counts.get("downloading", 0) + counts.get("hashing", 0)
        if pending:
            return
        failed = counts.get("failed", 0)
        if failed:
            self.db.mark_job_finished(job_id, "failed", None, f"{failed} file(s) failed.")
            return
        if counts.get("done", 0) == 0:
            self.db.mark_job_finished(job_id, "failed", None, "The job had no files.")
            return
        if job["kind"] == "runtime":
            vault_path = self._finalize_runtime(job)
        else:
            vault_path = self._finalize_model(job)
        self.db.mark_job_finished(job_id, "succeeded", vault_path, None)
        if notify:
            notify(f"Archived {job['repo_id']} into the vault.")

    def _finalize_runtime(self, job: dict) -> str:
        meta = loads_meta(job.get("meta_json"))
        folder = str(meta.get("folder") or job["repo_id"])
        version = str(meta.get("version") or job["revision"] or "unknown")
        filename = str(meta.get("filename"))
        dest_dir = self.settings.vault() / "RUNTIME" / folder / version
        dest_dir.mkdir(parents=True, exist_ok=True)
        file_row = self.db.list_files(int(job["id"]))[0]
        source = Path(str(file_row["local_path"]))
        target = dest_dir / filename
        if source.exists():
            if target.exists():
                target.unlink()
            shutil.move(str(source), str(target))
        note = dest_dir / "SOURCE.txt"
        note.write_text(
            "\n".join(
                [
                    f"pack: {job['repo_id']}",
                    f"version: {version}",
                    f"file: {filename}",
                    f"homepage: {meta.get('homepage') or ''}",
                    "Stele archived this file and did not execute it.",
                    DISCLAIMER,
                    "",
                ]
            ),
            encoding="utf-8",
        )
        catalog_id = self.db.insert_catalog(
            {
                "kind": "runtime",
                "repo_id": job["repo_id"],
                "revision": version,
                "commit_sha": version,
                "profile": "Runtime kit",
                "license_name": job.get("license_name"),
                "vault_path": str(dest_dir),
                "bytes": int(file_row.get("size") or 0),
                "file_count": 1,
                "formats_json": json.dumps(["runtime", folder]),
                "job_id": job["id"],
            }
        )
        log.info("runtime catalog %s", catalog_id)
        return str(dest_dir)

    def _finalize_model(self, job: dict) -> str:
        from stele.docs.howto import build_howto, write_howto_markdown
        from stele.docs.labels import write_case_insert, write_disc_face
        from stele.docs.pdf import write_howto_pdf, write_spec_pdf
        from stele.docs.spec import build_spec, write_spec_markdown

        repo_id = str(job["repo_id"])
        sha = str(job["commit_sha"] or job["revision"])
        safe = safe_repo(repo_id)
        revision_dir = self.settings.vault() / "MODELS" / safe / sha
        revision_dir.mkdir(parents=True, exist_ok=True)
        docs_dir = self.settings.vault() / "DOCS"
        docs_dir.mkdir(parents=True, exist_ok=True)

        files = self.db.list_files(int(job["id"]))
        inventory: list[dict] = []
        for row in files:
            source = Path(str(row["local_path"]))
            relative = str(row["relative_path"]).replace("\\", "/")
            target = revision_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.exists():
                if target.exists():
                    target.unlink()
                shutil.move(str(source), str(target))
            sha256 = str(row.get("sha256") or "")
            if target.exists() and not sha256:
                sha256 = hash_file(target)
            size = target.stat().st_size if target.exists() else int(row.get("size") or 0)
            inventory.append({"path": relative, "bytes": size, "sha256": sha256, "abs": target})

        job_meta = loads_meta(job.get("meta_json"))
        civitai = job_meta.get("civitai") if job_meta.get("source") == "civitai" else None
        if civitai is not None:
            from stele.hub.civitai import model_url

            url = model_url(repo_id, sha)
            # Civitai has no model card or license file to download. Keep the
            # description, trigger words, base model, and permissions with the weights.
            record = {key: value for key, value in civitai.items() if key != "file_types"}
            (revision_dir / "civitai_model.json").write_text(
                json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
        else:
            url = f"https://huggingface.co/{repo_id}/tree/{sha}"
        source_txt = revision_dir / "SOURCE.txt"
        source_txt.write_text(
            "\n".join(
                [
                    f"source: {'Civitai' if civitai is not None else 'Hugging Face'}",
                    f"repo: {repo_id}",
                    *([f"name: {civitai.get('name')}"] if civitai is not None else []),
                    f"revision: {job.get('revision') or ''}",
                    f"commit: {sha}",
                    f"downloaded_utc: {utc_now()}",
                    f"url: {url}",
                    f"profile: {job.get('profile') or ''}",
                    DISCLAIMER,
                    "",
                ]
            ),
            encoding="utf-8",
        )
        rows = [(item["sha256"], f"MODELS/{safe}/{sha}/{item['path']}") for item in inventory if item["sha256"]]
        write_checksum_file(revision_dir / "checksums.sha256", [(item["sha256"], item["path"]) for item in inventory if item["sha256"]])
        write_checksum_file(docs_dir / f"{safe}_checksums.sha256", rows)

        config = _read_json(revision_dir / "config.json")
        spec = build_spec(
            repo_id=repo_id,
            revision=str(job.get("revision") or ""),
            commit_sha=sha,
            snapshot_utc=utc_now(),
            license_name=str(job.get("license_name") or "unknown"),
            license_excerpt=_license_excerpt(revision_dir, str(job.get("license_excerpt") or "")),
            card_excerpt=str(job.get("card_excerpt") or ""),
            profile=str(job.get("profile") or ""),
            pipeline_tag=str(job.get("pipeline_tag") or ""),
            library_name=str(job.get("library_name") or ""),
            config=config,
            inventory=[{"path": i["path"], "bytes": i["bytes"], "sha256": i["sha256"]} for i in inventory],
            weight_paths=[i["abs"] for i in inventory],
        )
        howto = build_howto(
            repo_id=repo_id,
            commit_sha=sha,
            safe_id=safe,
            profile=str(job.get("profile") or ""),
            license_name=str(job.get("license_name") or "unknown"),
            library_name=str(job.get("library_name") or ""),
            facts=spec.facts,
            gguf_paths=[i["path"] for i in inventory if i["path"].lower().endswith(".gguf")],
        )
        spec_md = docs_dir / f"{safe}_spec.md"
        spec_pdf = docs_dir / f"{safe}_spec.pdf"
        howto_md = docs_dir / f"{safe}_howto.md"
        howto_pdf = docs_dir / f"{safe}_howto.pdf"
        write_spec_markdown(spec, spec_md)
        write_howto_markdown(howto, howto_md)
        write_spec_pdf(spec, spec_pdf)
        write_howto_pdf(howto, howto_pdf)
        write_disc_face(
            docs_dir / f"{safe}_disc_face.pdf",
            model_ids=[repo_id],
            commit_short=sha[:12],
            when=spec.snapshot_utc[:10],
            volume=1,
            count=1,
            studio_name=self.settings.studio_name(),
        )
        write_case_insert(
            docs_dir / f"{safe}_case_insert.pdf",
            model_ids=[repo_id],
            license_name=spec.license_name,
            summary=spec.summary_line(),
            checksum_prefixes=[item["sha256"][:12] for item in inventory if item["sha256"]][:12],
            studio_name=self.settings.studio_name(),
        )
        formats = spec.format_tags
        self.db.insert_catalog(
            {
                "kind": "model",
                "repo_id": repo_id,
                "revision": job.get("revision"),
                "commit_sha": sha,
                "profile": job.get("profile"),
                "license_name": job.get("license_name"),
                "vault_path": str(revision_dir),
                "bytes": sum(item["bytes"] for item in inventory),
                "file_count": len(inventory),
                "formats_json": json.dumps(formats),
                "job_id": job["id"],
            }
        )
        staging = Path(str(job.get("staging_path") or ""))
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        return str(revision_dir)

    def tree_is_busy(self, vault_path: str, repo_id: str | None = None) -> bool:
        """True when a download still owns this vault item or the same repo staging tree."""
        target = str(Path(vault_path).resolve()) if vault_path else ""
        for job in self.db.list_jobs():
            if job["status"] not in ("active", "paused"):
                continue
            staging = str(job.get("staging_path") or "")
            owned = str(job.get("vault_path") or "")
            if owned and target and Path(owned).resolve() == Path(target):
                return True
            if repo_id and job["repo_id"] == repo_id and job["kind"] == "model":
                return True
            if staging and target.startswith(str(Path(staging).resolve())):
                return True
        return False


def _license_excerpt(revision_dir: Path, fallback: str) -> str:
    """Prefer the license file that was actually archived over the model-card blurb."""
    candidates = sorted(
        (
            path
            for path in revision_dir.rglob("*")
            if path.is_file()
            and path.name.lower().startswith(("license", "licence"))
            and path.stat().st_size <= 1_000_000
        ),
        key=lambda path: path.name.lower(),
    )
    if not candidates:
        return fallback
    text = candidates[0].read_text(encoding="utf-8", errors="replace").strip()
    if len(text) > 500:
        return text[:500].rstrip() + "…"
    return text or fallback


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}
