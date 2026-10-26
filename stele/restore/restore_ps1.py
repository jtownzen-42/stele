"""Generate the restore script that is copied onto every volume.

The script needs only Windows PowerShell 5.1 and the disc. It copies MODELS,
DOCS, RUNTIME, and RECOVERY file by file, checks each copy against this
volume's checksums.sha256, and joins files that were stored in parts once the
last part has been restored.
"""

from __future__ import annotations

from pathlib import Path

from stele.models import DISCLAIMER

_TEMPLATE = r"""param(
    [Parameter(Mandatory = $true)]
    [string]$Destination
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "__DISCLAIMER__"
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$Destination = (Resolve-Path -LiteralPath $Destination).ProviderPath
$sep = [string][System.IO.Path]::DirectorySeparatorChar

function Get-Sha256([string]$Path) {
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

function Join-Disc([string]$Root, [string]$Relative) {
    return Join-Path $Root ($Relative -replace '/', $sep)
}

$volume = $null
$volumeFile = Join-Path $here "VOLUME.json"
if (Test-Path -LiteralPath $volumeFile) {
    $volume = Get-Content -LiteralPath $volumeFile -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Host ("Disc {0} of {1}" -f $volume.index, $volume.count)
}

# 1. Copy this disc's files and check every copy.
$restoreFolders = @("MODELS", "DOCS", "RUNTIME", "RECOVERY")
$copied = 0
$bad = New-Object System.Collections.Generic.List[string]
foreach ($line in Get-Content -LiteralPath (Join-Path $here "checksums.sha256") -Encoding UTF8) {
    if ($line -notmatch '^([0-9a-fA-F]{64})  (.+)$') { continue }
    $expected = $Matches[1].ToLowerInvariant()
    $relative = $Matches[2]
    if ($restoreFolders -notcontains ($relative -split '/')[0]) { continue }
    $target = Join-Disc $Destination $relative
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
    Copy-Item -LiteralPath (Join-Disc $here $relative) -Destination $target -Force
    $copied++
    if ((Get-Sha256 $target) -ne $expected) {
        $bad.Add($relative)
        Write-Host "MISMATCH: $relative"
    }
}
Write-Host "Copied and checked $copied file(s)."

#__RECOVERY__

if ($bad.Count -gt 0) {
    Write-Host ""
    Write-Host "RESTORE FAILED. These files do not match checksums.sha256:"
    foreach ($item in $bad) { Write-Host "  $item" }
    Write-Host "Clean the disc and run RESTORE.ps1 again. If it fails again, the disc is damaged."
    exit 1
}

# 2. Join files stored in parts once every part is present.
$waiting = @{}
if ($volume -and $volume.split_files) {
    foreach ($split in @($volume.split_files)) {
        $target = Join-Disc $Destination $split.path
        $parts = @($split.parts | Sort-Object { [int]$_.part })
        $present = @($parts | Where-Object { Test-Path -LiteralPath (Join-Disc $Destination $_.path) })
        if (Test-Path -LiteralPath $target) {
            if ($present.Count -eq 0 -or (Get-Sha256 $target) -eq ([string]$split.sha256).ToLowerInvariant()) {
                foreach ($part in $present) { Remove-Item -LiteralPath (Join-Disc $Destination $part.path) -Force }
                Write-Host "Already joined: $($split.path)"
                continue
            }
        }
        if ($present.Count -lt $parts.Count) {
            foreach ($part in $parts) {
                if (-not (Test-Path -LiteralPath (Join-Disc $Destination $part.path))) { $waiting[[int]$part.volume] = $true }
            }
            Write-Host ("Waiting for {0} more part(s) of {1}" -f ($parts.Count - $present.Count), $split.path)
            continue
        }
        Write-Host ("Joining {0} from {1} parts" -f $split.path, $parts.Count)
        $partial = "$target.joining"
        if (Test-Path -LiteralPath $partial) { Remove-Item -LiteralPath $partial -Force }
        # Grow part 1 in place so the join needs one extra part of free space, not a second copy.
        Move-Item -LiteralPath (Join-Disc $Destination $parts[0].path) -Destination $partial
        $out = [System.IO.File]::Open($partial, [System.IO.FileMode]::Append, [System.IO.FileAccess]::Write)
        try {
            for ($i = 1; $i -lt $parts.Count; $i++) {
                $piece = Join-Disc $Destination $parts[$i].path
                $in = [System.IO.File]::OpenRead($piece)
                try { $in.CopyTo($out, 8MB) } finally { $in.Dispose() }
                Remove-Item -LiteralPath $piece -Force
            }
        } finally {
            $out.Dispose()
        }
        if ((Get-Sha256 $partial) -ne ([string]$split.sha256).ToLowerInvariant()) {
            Write-Host "RESTORE FAILED. $($split.path) does not match its SHA-256 after joining."
            Write-Host "Run RESTORE.ps1 again from every disc in the set."
            exit 1
        }
        Move-Item -LiteralPath $partial -Destination $target -Force
        Write-Host "Joined and verified: $($split.path)"
    }
}

if ($waiting.Count -gt 0) {
    $discs = ($waiting.Keys | Sort-Object) -join ", "
    Write-Host ""
    Write-Host "Insert disc(s) $discs and run RESTORE.ps1 from each with the same -Destination."
} else {
    Write-Host "Restore complete. Every file matched its SHA-256."
}
Write-Host "LM Studio: point the app at the GGUF folder under $Destination\MODELS"
Write-Host "Ollama: GGUF import varies by version. The files are under $Destination\MODELS. Stele does not run installers."
Write-Host "llama.cpp example: llama-cli -m <path-to-gguf>"
Write-Host "First check: ask the model to reply with the single word stele."
Write-Host "__DISCLAIMER__"
"""

RESTORE_PS1 = _TEMPLATE.replace("__DISCLAIMER__", DISCLAIMER).replace("#__RECOVERY__\n", "")


def write_restore_script(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(RESTORE_PS1, encoding="utf-8", newline="\r\n")
