"""Generate the restore script that is copied onto every volume."""

from __future__ import annotations

from pathlib import Path

from stele.models import DISCLAIMER

RESTORE_PS1 = f"""param(
    [Parameter(Mandatory = $true)]
    [string]$Destination
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "{DISCLAIMER}"
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
foreach ($name in @("MODELS", "DOCS", "RUNTIME")) {{
    $src = Join-Path $here $name
    if (Test-Path $src) {{
        $dest = Join-Path $Destination $name
        Copy-Item -Path $src -Destination $dest -Recurse -Force
        Write-Host "Copied $name"
    }}
}}
Write-Host "LM Studio: point the app at the GGUF folder under $Destination\\MODELS"
Write-Host "Ollama: GGUF import varies by version. The files are under $Destination\\MODELS. Stele does not run installers."
Write-Host "llama.cpp example: llama-cli -m <path-to-gguf>"
Write-Host "First check: ask the model to reply with the single word stele."
Write-Host "{DISCLAIMER}"
"""


def write_restore_script(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(RESTORE_PS1, encoding="utf-8", newline="\r\n")
