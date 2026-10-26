# Stele

Stele is a Windows desktop application that archives Hugging Face models, and a short list of official runtimes, onto M-DISC. It searches the Hub, downloads one file at a time, writes a technical specification and a how-to-use guide, and burns a verified UDF disc or exports the same tree as an ISO image.

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

Free covers search, download, the specification and how-to documents, and a single-volume ISO export. Stele Pro adds disc burning, multi-disc sets, and PAR2 recovery data. Pro is checked where the work happens, not only in the window title.

Activate Pro in Workspace settings with the license key from your Gumroad receipt. One key covers one person on up to three machines. Stele re-checks the key online about once a week. If Gumroad cannot be reached the license stays active, so an offline archive workstation keeps working; only a refund, a dispute, or a rejected key turns Pro off. There are no offline keys in this version.

Before a release build, set `GUMROAD_PRODUCT_ID` in `stele/license.py` to the product ID shown on the Gumroad product page.

## Hugging Face token

The token is stored in Windows Credential Manager under the name Stele. It is not written to the database, the log, the PDFs, or the disc. The token field is write-only. The window shows Stored or Not set.

A gated repository cannot be queued until a token is saved. You still have to accept the license on the Hub itself. Stele does not grant redistribution rights, and it asks you to acknowledge the model license before a job enters the queue.

## Download rules

One model or one runtime pack is the active job. Inside that job, one file is on the wire. Pause keeps the partial file. Quit and relaunch leave the job paused; Resume continues with HTTP Range. Cancel keeps finished files. Purge incomplete deletes only unfinished files, and only after you confirm.

`snapshot_download` is not used. `hf_transfer` is not installed.

## Burn and ISO

The Burn page lists IMAPI2 recorders. An empty tray or a missing drive is a message, not a crash. DVD M-DISC may need an M-DISC-aware drive. BD M-DISC is written as ordinary BD-R.

Burn writes a closed UDF disc at a conservative speed (2x–4x) and, by default, reads the disc back against `checksums.sha256`. Export ISO builds the same `STELE/` tree and writes a UDF image with IMAPI. Use ISO when the drive is a USB enclosure that IMAPI cannot control. The vault is not modified if the burn fails.

A download and a burn of the same tree are refused. A finished vault item can be burned while a different job downloads.

If one file is larger than the blank, Stele will not split it. Use a larger disc or Export ISO.

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
```

`RESTORE.ps1` copies MODELS, DOCS, and RUNTIME to a folder you choose. It does not use the network and it does not run installers.

## Tests

```bat
.venv\Scripts\python -m pytest
```

The tests do not download from the Hub and do not need a disc drive.

## Known limits

IMAPI2 is unreliable on some USB optical enclosures. Export ISO is the supported path there. A DVD M-DISC written on a drive that is not M-DISC-aware can fail or produce a disc that does not last. Stele cannot always tell M-DISC dye from a normal BD-R; confirm the blank yourself. Runtime packs are the official Windows files pinned in `stele/runtime/manifest.json`. Stele archives them and does not execute them.
