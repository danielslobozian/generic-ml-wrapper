# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
#
# Install gmlw (generic-ml-wrapper) on Windows:
#
#   irm https://raw.githubusercontent.com/danielslobozian/generic-ml-wrapper/main/install.ps1 | iex
#
# Ensures uv is present (installing it via Astral's own installer if not), then runs
# `uv tool install generic-ml-wrapper`. No Python prerequisite -- uv fetches its own
# interpreter, so there is nothing to detect or branch on there. Checks the install
# actually landed on PATH and says so loudly rather than exiting silently successful.

$ErrorActionPreference = "Stop"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "gmlw: uv not found, installing it first..."
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    # uv's installer updates the persisted user PATH, not this session's -- extend it here.
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Error "gmlw: uv install did not put 'uv' on PATH. See https://docs.astral.sh/uv/getting-started/installation/ and try again."
        exit 1
    }
}

Write-Host "gmlw: installing generic-ml-wrapper..."
uv tool install generic-ml-wrapper

$binDir = (uv tool dir --bin 2>$null)
if (-not $binDir) { $binDir = "$env:USERPROFILE\.local\bin" }

$onPath = ($env:Path -split ";") -contains $binDir
if (-not $onPath) {
    Write-Host ""
    Write-Host "-------------------------------------------------------------------"
    Write-Host "gmlw is installed, but $binDir is not on your PATH yet."
    Write-Host "Open a new PowerShell window, or add it to this one:"
    Write-Host ""
    Write-Host "  `$env:Path = `"$binDir;`$env:Path`""
    Write-Host ""
    Write-Host "-------------------------------------------------------------------"
}

Write-Host ""
Write-Host "gmlw installed. Try:  gmlw --version"
