# Stele 1.0 — verified facts for the sales listing

Every line below traces to the code on `claude/activation-licensing` (source in brackets). If a claim is not here, don't put it on the listing without checking first.

## One-line description
Stele is a Windows desktop app that archives Hugging Face AI models, plus a short list of official runtimes, onto M-DISC/BD-R optical discs or ISO images, with documentation and checksums on every disc. [README.md]

## What it does (feature list)
- **Search Hugging Face** by repository id or keywords, filtered by pipeline, library, license, gated status and format. [stele/ui/pages/discover.py]
- **Pick exactly what to archive** with four profiles: GGUF inference pack, Inference pack, Full repo, Runtime kit. A precise revision (commit) is pinned. [stele/models.py PROFILES; stele/hub/planner.py]
- **Safe, resumable downloads**: one job and one file at a time; Pause keeps the partial file and Resume continues it with HTTP Range, even after quitting the app. [stele/download/worker.py; README "Download rules"]
- **Integrity checks**: each downloaded file is hashed (SHA-256) and compared with the Hub's checksum when the Hub provides one; every disc carries a `checksums.sha256`. [stele/download/worker.py; stele/burn/layout.py]
- **Documentation generated for every model**: a technical spec sheet and a how-to-use guide (Markdown and PDF), including a rough hardware class (8 GB / 12 GB / 24 GB / CPU-only) estimated from weight size. [stele/docs/spec.py, howto.py, pdf.py]
- **Printable labels**: a disc face and a US Letter case insert, with your own branding name. [stele/docs/labels.py]
- **Burn a verified disc** (Pro): writes a closed UDF disc at a conservative 2x–4x and, by default, reads it back against the checksums. [stele/burn/imapi.py; stele/settings.py always_verify default on]
- **Span large archives across several discs** (Pro): files are packed across discs and never split; each disc gets VOLUME.json describing the set. [stele/burn/span.py; layout.py]
- **Export ISO** (Free): the same disc layout as .iso files, for USB drives that don't work with Windows burning, or for burning later. [stele/burn/iso.py; burn_page.py]
- **Offline restore**: each disc has RESTORE.ps1, which copies models, docs and runtimes to a folder you choose without network access and without running installers. [stele/restore/restore_ps1.py; README]
- **Runtime packs** archived next to models: Ollama and llama.cpp (CPU and CUDA builds) from a pinned official manifest; LM Studio is optional and off until you accept its terms. Stele archives these files and never runs them. [stele/runtime/manifest.json; stele/legal/__init__.py]
- **Light and dark mode** that follows the Windows setting. [stele/ui/theme.py]
- **Your Hugging Face token stays private**: stored in Windows Credential Manager, never in the database, logs, PDFs or discs. [README "Hugging Face token"; stele/credentials.py]

## Free vs Pro
| | Free | Pro |
|---|---|---|
| Search, download, docs, labels | Yes | Yes |
| Export ISO | Yes | Yes |
| Burn discs | No | Yes |
| Multi-disc spanning | No | Yes |
[stele/license.py PRO_FEATURES; burn_page.py gates]

Pro is a one-time purchase verified through Gumroad. After activation it works offline for 14 days from the last successful check, then needs one online check. Refunded or disabled keys stop unlocking Pro at the next check. [stele/license.py GRACE_DAYS=14; EULA section 3]

## System requirements (what we can actually state)
- Windows PC. Burning uses Windows' built-in IMAPI2 engine. [stele/burn/imapi.py]
- Internet connection for downloads and for Pro activation.
- For burning: an optical writer and BD-R / M-DISC blanks (DVD M-DISC may need an M-DISC-aware drive). [stele/models.py DVD_M_DISC_NOTE]
- Free disk space for the downloaded models (staging + vault folders).
- Portable build: unzip and run Stele.exe, no installer. Not code-signed yet, so SmartScreen may warn on first run. [stele.spec one-folder build]
- NOT verified yet: minimum Windows version and minimum RAM. Don't state them until tested.

## Known limits (be upfront)
- Some USB disc enclosures don't work well with IMAPI2; Export ISO is the dependable path there. [README "Known limits"]
- Stele can't always tell M-DISC blanks from ordinary BD-R; check the blank. [README]
- A single file larger than the disc is never split; use a larger disc or Export ISO. [stele/burn/span.py]
- Stele does not grant redistribution rights; each model keeps its own license, which the user must acknowledge before queueing. [stele/models.py DISCLAIMER; queue.py]
- Optical media can fail; verify discs and keep more than one copy. [EULA section 5]
- Windows only. No macOS or Linux build.

## Support
alexx.forge@proton.me, or reply to the Gumroad receipt. [QUICKSTART]

## Suggested Gumroad category and tags
- Category: Software (or Software Development > Desktop apps, whichever Gumroad offers).
- Tags (pick up to 5 that Gumroad allows): `ai models`, `hugging face`, `local llm`, `archive`, `m-disc`, `backup`, `offline ai`, `gguf`, `windows software`.

## Honest one-paragraph pitch (draft for ChatGPT Sales Lab to edit)
Models disappear, get gated or change. Stele keeps your own copy: pick a Hugging Face model and revision, download it safely one file at a time, and Stele writes a spec sheet, a how-to guide and checksums next to it. Export everything as an ISO for free, or with Pro burn verified M-DISC or BD-R discs, spanning big models across several discs, with an offline restore script on every disc.
