# Stele

Stele is a Windows desktop application that archives Hugging Face and Civitai models, and a short list of official runtimes, onto M-DISC. It searches the Hub, downloads one file at a time, writes a technical specification and a how-to-use guide, and burns a verified UDF disc or exports the same tree as an ISO image.

Carve the model into stone.

Stele does not grant redistribution rights.

## Install

Python 3.12 is required.

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
run_stele.bat
```

`run_stele.bat` creates the virtual environment with Python 3.12 if it is missing, installs dependencies once, and starts the app. It does not download model files by itself.

## First launch

The first run creates:

- `%USERPROFILE%\Stele\staging\` — the active download
- `%USERPROFILE%\Stele\vault\` — finished models and runtimes
- `%LOCALAPPDATA%\Stele\stele.db` — queue, catalog, and burn history
- `%LOCALAPPDATA%\Stele\logs\` — the log file
- `%LOCALAPPDATA%\Stele\burn-work\` — disc trees and ISO images

Vault and staging can be moved in Settings. The database and logs stay under Local AppData.

## Free and Pro

Free covers search, download, the specification and how-to documents, and a single-volume ISO export. Stele Pro adds disc burning, multi-disc sets, PAR2 recovery data, and the Compliance Vault evidence package. Pro is checked where the work happens, not only in the window title.

Activate Pro in Workspace settings with the license key from your Gumroad receipt. One key covers one person on up to three machines. Stele re-checks the key online about once a week. If Gumroad cannot be reached the license stays active, so an offline archive workstation keeps working; only a refund, a dispute, or a rejected key turns Pro off. There are no offline keys in this version.

`GUMROAD_PRODUCT_ID` in `stele/license.py` holds the Stele Pro product ID from the Gumroad product page. Change it only if the product is recreated.

## Hugging Face token

The token is stored in Windows Credential Manager under the name Stele. It is not written to the database, the log, the PDFs, or the disc. The token field is write-only. The window shows Stored or Not set.

A gated repository cannot be queued until a token is saved. You still have to accept the license on the Hub itself. Stele does not grant redistribution rights, and it asks you to acknowledge the model license before a job enters the queue.

## Civitai

Pick Civitai in the source list on Discover to search Civitai by name, model id, or civitai.com link. Stele archives one model version at a time into `MODELS/civitai--<model id>/v<version id>/`, checks each file against the SHA-256 that Civitai publishes, and keeps `civitai_model.json` beside the weights with the description, trigger words, base model, and the creator's permissions. Training-data files are listed but not ticked by default. Search hides NSFW models.

Many Civitai downloads need an API key (civitai.com, Account settings, API keys). Save it in Workspace settings; it is stored in Windows Credential Manager like the Hugging Face token. The key is sent only to civitai.com, never to the storage host a download redirects to.

## Download rules

One model or one runtime pack is the active job. Inside that job, one file is on the wire. Pause keeps the partial file. Quit and relaunch leave the job paused; Resume continues with HTTP Range. Cancel keeps finished files. Purge incomplete deletes only unfinished files, and only after you confirm.

`snapshot_download` is not used. `hf_transfer` is not installed.

## Burn and ISO

The Burn page lists IMAPI2 recorders. An empty tray or a missing drive is a message, not a crash. DVD M-DISC may need an M-DISC-aware drive. BD M-DISC is written as ordinary BD-R.

Burn writes a closed UDF disc at a conservative speed (2x–4x) and, by default, reads the disc back against `checksums.sha256`. Export ISO builds the same `STELE/` tree and writes a UDF image with IMAPI. Use ISO when the drive is a USB enclosure that IMAPI cannot control. The vault is not modified if the burn fails.

A download and a burn of the same tree are refused. A finished vault item can be burned while a different job downloads.

If one file is larger than the blank, Stele stores it as equal numbered parts (`name.part001`, `name.part002`, …) on consecutive discs and records each part's SHA-256 and the whole file's SHA-256 in `VOLUME.json` and `ARCHIVE_MANIFEST.json`. Multi-disc sets need Pro.

## Recovery data (Pro)

With recovery data on (Settings, default 5%), every disc keeps room for a PAR2 recovery set under `RECOVERY/`, made with a standard par2 program. If a disc gets scratched, `RESTORE.ps1` copies past unreadable sectors, then repairs the damaged files when `par2` is on PATH. Without it, the script prints the exact `par2 r` command to run with any PAR2 tool (par2cmdline, MultiPar, QuickPar). Recovery data repairs scattered damage up to roughly its percentage of the disc; it does not replace a second copy.

Stele looks for par2 at the path set in Settings, then `tools\par2.exe` next to the app, then PATH. Release builds bundle `tools\par2.exe` from par2cmdline-turbo (GPL-2.0) when it is present at build time.

## Compliance Vault (Pro)

The Compliance Vault is timestamped evidence of what you archived: where each file came from, its SHA-256, and the license Stele recorded for it. Pick a vault item in Library and choose Export evidence to save one ZIP, by default under `%USERPROFILE%\Stele\vault\EVIDENCE\`. With Pro active, every burn and ISO also gets an evidence ZIP for each model, made when the disc tree is built, under `EVIDENCE/`. RESTORE.ps1 copies it back.

Each ZIP holds:

- `provenance.json`: source page, commit, profile, the license name and when you acknowledged it, and every file with its download URL, the SHA-256 Stele recorded at download, and the SHA-256 measured for this package
- `LICENSES/`: every license, notice, or use-policy file published with the model, Civitai permissions when the model came from Civitai, and `LICENSE_SUMMARY.txt`, which flags a missing or unknown license
- `sbom.cdx.json`: a CycloneDX 1.6 SBOM with the model as a machine-learning-model component and each file with its SHA-256
- `checksums.sha256`, the spec and how-to documents, and the `SOURCE.txt` Stele kept with the files
- `ZIP_CONTENTS.sha256`: the SHA-256 of every other file in the ZIP

Every file is hashed again when the package is made. A file that is missing or no longer matches is listed in `README.txt` and in `provenance.json`, and Stele warns you; it does not hide the mismatch.

Times come from this PC's own clock. Stele does not contact a time server or a timestamp authority, so the timestamp is only as good as the clock.

Stele records timestamped evidence of what you archived. It is not legal advice; ask a lawyer about your obligations.

## Disc layout

```
STELE/
  README_FIRST.txt
  ARCHIVE_MANIFEST.json
  checksums.sha256
  RESTORE.ps1
  VOLUME.json
  DOCS/
  MODELS/<org>--<repo>/<commit>/
  RUNTIME/    (optional)
  EVIDENCE/   (Pro, Compliance Vault ZIP per model)
  RECOVERY/   (optional, PAR2)
```

`RESTORE.ps1` copies MODELS, DOCS, RUNTIME, and EVIDENCE to a folder you choose and checks every copy against `checksums.sha256`. It stops with an error and a list of files if anything does not match. Run it from each disc of a set with the same `-Destination`; after the last part of a split file arrives, it joins the parts and checks the whole-file SHA-256. It does not use the network and it does not run installers.

## Tests

```bat
.venv\Scripts\python -m pytest
```

The tests do not download from the Hub and do not need a disc drive.

## Known limits

IMAPI2 is unreliable on some USB optical enclosures. Export ISO is the supported path there. A DVD M-DISC written on a drive that is not M-DISC-aware can fail or produce a disc that does not last. Stele cannot always tell M-DISC dye from a normal BD-R; confirm the blank yourself. Runtime packs are the official Windows files pinned in `stele/runtime/manifest.json`. Stele archives them and does not execute them.
