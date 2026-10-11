"""Shared types, profile names, and the sentences the UI and discs must match."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

DISCLAIMER = "Stele does not grant redistribution rights."
FULL_LICENSE_NOTE = "full license file is on this disc"

PROFILE_GGUF = "GGUF inference pack"
PROFILE_FULL = "Full repo"
PROFILE_INFERENCE = "Inference pack"
PROFILE_RUNTIME = "Runtime kit"
PROFILES = (PROFILE_GGUF, PROFILE_FULL, PROFILE_INFERENCE, PROFILE_RUNTIME)

MSG_GATED = (
    "This repository is gated. Save a Hugging Face token in Settings, "
    "accept the license on the Hub, then try again."
)
MSG_AUTH = (
    "Hugging Face refused the download (401/403). The token may be missing, "
    "expired, or not accepted for this model."
)
MSG_DISK = "Staging disk is full. Free space and resume the job. No further files were started."
MSG_EMPTY_TRAY = "No disc in the drive. Insert a blank M-DISC and choose Refresh."
MSG_NO_DRIVE = "No optical drive is connected."
MSG_CANCEL_UNAVAILABLE = (
    "Cancel is not available for this recorder; the burn will finish or fail on its own."
)
DVD_M_DISC_NOTE = (
    "DVD M-DISC write may require an M-DISC-aware drive. "
    "BD M-DISC is written as a standard BD-R."
)

HEADROOM_BYTES = 32 * 1024 * 1024
SAMPLE_LIMIT = 64 * 1024 * 1024
FULL_VERIFY_LIMIT = 8 * 1024 ** 3

# Advertised capacities in bytes (DVD+R and BD-R decimal sizes used by IMAPI).
CAPACITY_PRESETS: dict[str, int] = {
    "dvd47": 4_700_372_992,
    "bd25": 25_025_314_816,
    "bd50": 50_050_629_632,
    "bd100": 100_103_356_416,
}
CAPACITY_LABELS = {
    "dvd47": "DVD 4.7 GB",
    "bd25": "BD 25 GB",
    "bd50": "BD 50 GB",
    "bd100": "BD 100 GB",
    "custom": "Custom",
}


def human_bytes(n: int | None) -> str:
    if n is None:
        return "unknown"
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{int(n)} B"


def msg_file_too_big(name: str, size: int, usable: int) -> str:
    return (
        f"{name} is {human_bytes(size)} and this disc has {human_bytes(usable)} usable. "
        "It was not split. Use larger media or Export ISO."
    )


def msg_imapi(details: str) -> str:
    return (
        "The burn did not start. The vault was not changed. You can Export ISO. "
        f"Details: {details}"
    )


def safe_repo(repo_id: str) -> str:
    return repo_id.replace("\\", "--").replace("/", "--").strip()


@dataclass
class HubFile:
    path: str
    size: int | None = None
    etag: str | None = None

    @property
    def known_size(self) -> int:
        return int(self.size or 0)


@dataclass
class PlanResult:
    profile_requested: str
    profile_used: str
    fallback_note: str | None
    files: list[HubFile]
    total_bytes: int
    disc_estimate: int | None
    blocked_reason: str | None = None


@dataclass
class SearchHit:
    repo_id: str
    author: str
    last_modified: str
    downloads: int | None
    likes: int | None
    pipeline_tag: str
    library_name: str
    gated: bool
    tags: list[str] = field(default_factory=list)
    approx_bytes: int | None = None


@dataclass
class RepoDetails:
    repo_id: str
    sha: str
    revision: str
    last_modified: str
    pipeline_tag: str
    library_name: str
    license_name: str
    gated: bool
    card_excerpt: str
    files: list[HubFile]
    private: bool = False


@dataclass
class SpanFile:
    path: str
    size: int


@dataclass
class VolumePlan:
    index: int
    files: list[SpanFile]
    used_bytes: int


@dataclass
class SpanPlan:
    volumes: list[VolumePlan]
    usable_bytes: int
    capacity_bytes: int
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.volumes or not self.error)


@dataclass
class PayloadFile:
    """A real file copied onto a volume. disc_relative uses forward slashes."""

    source: Path
    disc_relative: str
    size: int
    sha256: str
    owner: str  # safe repo id, runtime pack id, or ""


@dataclass
class ModelDiscMeta:
    repo_id: str
    safe_id: str
    revision: str
    commit_sha: str
    profile: str
    license_name: str
    spec_md: Path | None = None
    spec_pdf: Path | None = None
    howto_md: Path | None = None
    howto_pdf: Path | None = None


@dataclass
class RuntimeDiscMeta:
    pack_id: str
    folder: str
    version: str
    filename: str
    homepage: str
    source: Path
    sha256: str
    size: int
