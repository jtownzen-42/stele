"""One-command master builder for all 5 Stele sales videos, covers & posting guide.

Usage:
    .venv\\Scripts\\python.exe videos\\build_all_videos.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", str(Path(__file__).resolve().parent / "assets" / "fonts"))

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PySide6.QtGui import QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from videos.audio_synth import write_soundtrack  # noqa: E402
from videos.config import (  # noqa: E402
    ASSETS_DIR,
    BRAND_EMAIL,
    BRAND_HANDLE,
    BRAND_NAME,
    BRAND_TAGLINE,
    GUMROAD_FREE_URL,
    GUMROAD_PRO_URL,
    OUT_DIR,
    SHORTS_COVERS_DIR,
    STELE_FREE_PRICE,
    STELE_PRO_PRICE,
    UI_CAPTURES_DIR,
    X_COVERS_DIR,
)
from videos.render_engine import (  # noqa: E402
    ensure_brand_fonts,
    render_120px_audit_sheet,
    render_shorts_cover,
    render_video_mp4,
    render_x_cover,
)
from videos.video_specs import VIDEO_SPECS  # noqa: E402

BANNED_WORDS = (
    "guaranteed",
    "100%",
    "never again",
    "ultimate",
    "game-changer",
    "revolutionary",
    "secret",
    "hack",
    "insane",
    "10x",
    "unleash",
    "supercharge",
    "harness the power",
    "next-level",
    "cutting-edge",
    "seamless",
    "alex forge",
    "pi forge",
    "alex.forge@",
    "forgealex4",
    "digital tools. real impact",
)


def audit_brand_compliance() -> None:
    """Fail fast if any headline, caption, cover, or post violates Brand Book rules."""
    for spec in VIDEO_SPECS:
        # 1. Cover <= 4 words and zero prices in cover art
        cover_words = " ".join(spec["cover_lines"]).split()
        if len(cover_words) > 4:
            raise ValueError(f"{spec['slug']} cover has >4 words: {cover_words}")
        for cov_field in (" ".join(spec["cover_lines"]), spec["cover_subhead"]):
            if "$" in cov_field or "29" in cov_field:
                raise ValueError(f"{spec['slug']} cover bakes a price into art: {cov_field}")

        # 2. Check all text fields against banned words
        texts = [
            spec["title"],
            spec["eyebrow"],
            " ".join(spec["cover_lines"]),
            spec["cover_subhead"],
            spec["x_post"],
            spec["x_reply"],
            spec["shorts_title"],
            spec["shorts_desc"],
        ]
        for sc in spec["scenes"]:
            texts.extend(sc.get("headline", []))
            if "caption" in sc:
                texts.append(sc["caption"])
            if "cta_headline" in sc:
                texts.append(sc["cta_headline"])
            if "honest_limit" in sc:
                texts.append(sc["honest_limit"])
        joined = "\n".join(texts).lower()
        for bad in BANNED_WORDS:
            if bad in joined:
                raise ValueError(f"Banned phrase '{bad}' found in {spec['slug']}")


def write_posting_guide(out_md: Path) -> Path:
    lines = [
        f"# {BRAND_NAME} — Stele 5-Video Posting Pack (X.com & YouTube Shorts)",
        "",
        f"- **Account:** `{BRAND_HANDLE}` on X (never post from personal handle) · YouTube Shorts channel",
        f"- **Support Email:** `{BRAND_EMAIL}` (two x's)",
        f"- **Stele Free ({STELE_FREE_PRICE}):** {GUMROAD_FREE_URL}",
        f"- **Stele Pro ({STELE_PRO_PRICE}):** {GUMROAD_PRO_URL}",
        f"- **Tagline:** `{BRAND_TAGLINE}`",
        "",
        "## Platform Posting Rules",
        "1. **X.com:** Upload the `.mp4` natively to Post 1 with **no external URL in Post 1** (avoids link throttling). Immediately post **Reply 1** with the exact Gumroad links below. Attach the `covers_x_16x9/*.png` thumbnail if scheduling via X Media Studio.",
        "2. **YouTube Shorts:** Upload the same `1080x1920` `.mp4` and select/upload the matching `covers_shorts_9x16/*.png` cover. Since Shorts descriptions do not render clickable external URLs, make sure `forgealex0.gumroad.com` is added to your YouTube Channel profile links.",
        "",
        "---",
        "",
    ]
    for idx, spec in enumerate(VIDEO_SPECS, start=1):
        dur = sum(float(s["duration"]) for s in spec["scenes"])
        lines.extend(
            [
                f"## Video {idx}: {spec['title']} (`{spec['slug']}.mp4` · `{dur:.0f}s`)",
                "",
                f"- **Video file:** `videos/out/{spec['slug']}.mp4`",
                f"- **Shorts Cover (`9:16`):** `videos/out/covers_shorts_9x16/{spec['slug']}_shorts_cover.png`",
                f"- **X / YouTube Cover (`16:9`):** `videos/out/covers_x_16x9/{spec['slug']}_x_cover.png`",
                "",
                "### X.com — Main Post (`@Alexxforge`)",
                "```text",
                spec["x_post"],
                "```",
                "",
                "### X.com — Immediate Reply #1",
                "```text",
                spec["x_reply"],
                "```",
                "",
                "### YouTube Shorts — Title",
                "```text",
                spec["shorts_title"],
                "```",
                "",
                "### YouTube Shorts — Description",
                "```text",
                spec["shorts_desc"],
                "```",
                "",
                "---",
                "",
            ]
        )
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines), encoding="utf-8")
    return out_md


def main() -> int:
    t0 = time.perf_counter()
    audit_brand_compliance()
    print("[1/5] Brand Book text & banned-words audit passed.", flush=True)

    regions_file = UI_CAPTURES_DIR / "ui_regions.json"
    if not regions_file.exists():
        print("[2/5] Capturing 2x HiDPI dark-mode Stele UI screens...", flush=True)
        import subprocess as sp

        res = sp.run([sys.executable, str(Path(__file__).resolve().parent / "capture_ui.py")], check=True)
        assert res.returncode == 0
    else:
        print("[2/5] Using fresh 2x HiDPI UI captures in", UI_CAPTURES_DIR, flush=True)

    app = QApplication.instance() or QApplication(["SteleVideoRender"])
    hl_fam, body_fam = ensure_brand_fonts()
    print(f"[3/5] Loaded brand fonts -> Headline: '{hl_fam}', Body: '{body_fam}'", flush=True)

    regions = json.loads(regions_file.read_text(encoding="utf-8"))
    pixmaps: dict[str, QPixmap] = {}
    for png in UI_CAPTURES_DIR.glob("*.png"):
        pix = QPixmap(str(png))
        pix.setDevicePixelRatio(1.0)  # Treat 2720x1800 raw pixels directly for camera math
        pixmaps[png.stem] = pix

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    wav_dir = ASSETS_DIR / "audio"
    shorts_covers: list[Path] = []
    x_covers: list[Path] = []

    print("[4/5] Synthesizing audio & rendering 5 1080x1920 MP4s + 10 covers...", flush=True)
    for idx, spec in enumerate(VIDEO_SPECS, start=1):
        v0 = time.perf_counter()
        slug = spec["slug"]
        total_dur = sum(float(s["duration"]) for s in spec["scenes"])
        cuts = []
        acc = 0.0
        for s in spec["scenes"][:-1]:
            acc += float(s["duration"])
            cuts.append(acc)

        wav_path = write_soundtrack(
            wav_dir / f"{slug}.wav",
            duration_s=total_dur,
            cut_times=cuts,
            tick_windows=spec.get("tick_windows"),
        )
        mp4_path = render_video_mp4(spec, wav_path, OUT_DIR / f"{slug}.mp4", pixmaps, regions)
        sc_path = render_shorts_cover(spec, SHORTS_COVERS_DIR / f"{slug}_shorts_cover.png", pixmaps, regions)
        xc_path = render_x_cover(spec, X_COVERS_DIR / f"{slug}_x_cover.png", pixmaps, regions)
        shorts_covers.append(sc_path)
        x_covers.append(xc_path)
        sz_mb = mp4_path.stat().st_size / (1024 * 1024)
        print(f"      -> [{idx}/5] {mp4_path.name} ({total_dur:.0f}s, {sz_mb:.2f} MB) in {time.perf_counter() - v0:.1f}s", flush=True)

    audit_png = render_120px_audit_sheet(shorts_covers, x_covers, OUT_DIR / "audit_120px_contact_sheet.png")
    guide_md = write_posting_guide(OUT_DIR / "POSTING_GUIDE_X_AND_SHORTS.md")
    print(f"[5/5] Wrote {audit_png.name} and {guide_md.name} in {time.perf_counter() - t0:.1f}s total.", flush=True)
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
