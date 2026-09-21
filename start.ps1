# Starts OmniPull with Docker Compose.
# Usage: .\start.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop is required. Install it, start it, then run this command again."
}

docker info *>$null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop is not running. Start it, then run this command again."
}

docker compose up --build
