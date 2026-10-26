"""Generate the restore script that is copied onto every volume.

The script needs only Windows PowerShell 5.1 and the disc. It copies MODELS,
DOCS, RUNTIME, and RECOVERY file by file, keeps going past unreadable sectors
(they are written as zeros), checks each copy against this volume's
checksums.sha256, repairs damage with the PAR2 data in RECOVERY when a par2
program is on PATH, and joins files that were stored in parts once the last
part has been restored.
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

# .NET instead of Get-FileHash: a PowerShell 7 terminal can leak its module
# path into Windows PowerShell 5.1, which then cannot find Get-FileHash.
function Get-Sha256([string]$Path) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        return ([System.BitConverter]::ToString($sha.ComputeHash($stream)) -replace '-', '').ToLowerInvariant()
    } finally {
        $stream.Dispose()
        $sha.Dispose()
    }
}

function Join-Disc([string]$Root, [string]$Relative) {
    return Join-Path $Root ($Relative -replace '/', $sep)
}

# Copy a file and keep going past unreadable sectors. Returns the number of
# bytes that could not be read; they are written as zeros so PAR2 can repair them.
function Copy-Tolerant([string]$Source, [string]$Target) {
    $lost = 0
    $in = [System.IO.File]::Open($Source, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
    try {
        $out = [System.IO.File]::Open($Target, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write)
        try {
            $buffer = New-Object byte[] (1MB)
            $length = $in.Length
            $pos = [long]0
            while ($pos -lt $length) {
                $want = [int][Math]::Min([long]1MB, $length - $pos)
                $got = 0
                try {
                    $in.Position = $pos
                    $got = $in.Read($buffer, 0, $want)
                } catch {
                    $got = 0
                }
                if ($got -gt 0) {
                    $out.Write($buffer, 0, $got)
                    $pos += $got
                    continue
                }
                # Retry this window in 64 KB steps and zero-fill what cannot be read.
                $end = $pos + $want
                while ($pos -lt $end) {
                    $step = [int][Math]::Min([long]64KB, $end - $pos)
                    $got = 0
                    try {
                        $in.Position = $pos
                        $got = $in.Read($buffer, 0, $step)
                    } catch {
                        $got = 0
                    }
                    if ($got -le 0) {
                        [Array]::Clear($buffer, 0, $step)
                        $got = $step
                        $lost += $step
                    }
                    $out.Write($buffer, 0, $got)
                    $pos += $got
                }
            }
        } finally {
            $out.Dispose()
        }
    } finally {
        $in.Dispose()
    }
    return $lost
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
$kept = 0
$expectedBy = @{}
$bad = New-Object System.Collections.Generic.List[string]
$badRecovery = New-Object System.Collections.Generic.List[string]
foreach ($line in Get-Content -LiteralPath (Join-Path $here "checksums.sha256") -Encoding UTF8) {
    if ($line -notmatch '^([0-9a-fA-F]{64})  (.+)$') { continue }
    $expected = $Matches[1].ToLowerInvariant()
    $relative = $Matches[2]
    $top = ($relative -split '/')[0]
    if ($restoreFolders -notcontains $top) { continue }
    $expectedBy[$relative] = $expected
    $target = Join-Disc $Destination $relative
    if ((Test-Path -LiteralPath $target) -and (Get-Sha256 $target) -eq $expected) {
        $kept++
        continue
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
    $problem = $null
    try {
        $lost = Copy-Tolerant (Join-Disc $here $relative) $target
        if ($lost -gt 0) { $problem = "UNREADABLE ($lost bytes)" }
    } catch {
        $problem = "UNREADABLE (could not open)"
    }
    $copied++
    if (-not $problem -and (Get-Sha256 $target) -ne $expected) { $problem = "MISMATCH" }
    if ($problem) {
        Write-Host "${problem}: $relative"
        if ($top -eq "RECOVERY") { $badRecovery.Add($relative) } else { $bad.Add($relative) }
    }
}
Write-Host "Copied and checked $copied file(s). $kept file(s) were already restored and matched."
if ($badRecovery.Count -gt 0) {
    Write-Host "Some recovery files are damaged. PAR2 can still use the readable parts."
}

# PAR2 repair of damaged files, when this disc carries recovery data.
if ($bad.Count -gt 0 -and $volume) {
    $index = Join-Disc $Destination ("RECOVERY/" + $volume.label + ".par2")
    if (Test-Path -LiteralPath $index) {
        $par2 = Get-Command par2 -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($par2) {
            Write-Host "Repairing with the PAR2 recovery data on this disc."
            & $par2.Path r -q -p "-B$Destination" $index | Out-Host
            $still = New-Object System.Collections.Generic.List[string]
            foreach ($relative in $bad) {
                $target = Join-Disc $Destination $relative
                if ((Test-Path -LiteralPath $target) -and (Get-Sha256 $target) -eq $expectedBy[$relative]) {
                    Write-Host "Repaired: $relative"
                } else {
                    $still.Add($relative)
                }
            }
            $bad = $still
        } else {
            Write-Host ""
            Write-Host "This disc carries PAR2 recovery data. Install par2cmdline or MultiPar, then run:"
            Write-Host "  par2 r -p `"-B$Destination`" `"$index`""
            Write-Host "and run RESTORE.ps1 again. Files that already match are kept."
        }
    }
}

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
            # Always check the hash: a file left by an earlier, broken run must not count as joined.
            if ((Get-Sha256 $target) -eq ([string]$split.sha256).ToLowerInvariant()) {
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

RESTORE_PS1 = _TEMPLATE.replace("__DISCLAIMER__", DISCLAIMER)


def write_restore_script(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(RESTORE_PS1, encoding="utf-8", newline="\r\n")
