# Starts OmniPull locally on Windows and reads the signed-in browser session.
# Usage: .\start.ps1

param(
    [ValidateSet("auto", "brave", "chrome", "edge", "firefox")]
    [string]$Browser = "auto"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot "backend"
$VenvDir = Join-Path $ProjectRoot ".venv"
$Python = Join-Path $VenvDir "Scripts\python.exe"
$RuntimeDir = Join-Path $ProjectRoot ".runtime"
$WebPidFile = Join-Path $RuntimeDir "web.pid"

Set-Location $ProjectRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw "Docker Desktop is required for the local Redis service." }
docker info *>$null
if ($LASTEXITCODE -ne 0) { throw "Docker Desktop is not running. Start it and run this command again." }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "FFmpeg is required. Install FFmpeg or install WinGet, then run this command again."
    }
    Write-Host "Installing FFmpeg for local media processing..." -ForegroundColor Gray
    winget install --id Gyan.FFmpeg --exact --accept-package-agreements --accept-source-agreements --disable-interactivity
    $ffmpeg = Get-ChildItem (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages") -Recurse -Filter "ffmpeg.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $ffmpeg) { throw "FFmpeg installation completed, but it was not found. Open a new PowerShell window and run .\start.ps1 again." }
    $env:Path = "$($ffmpeg.DirectoryName);$env:Path"
}

if (-not (Test-Path $Python)) {
    python -m venv $VenvDir
    & $Python -m pip install --upgrade pip
    & $Python -m pip install -r (Join-Path $BackendDir "requirements.txt")
}

New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
docker compose stop web worker 2>$null
docker compose up -d redis
$env:REDIS_URL = "redis://localhost:6379/0"
$env:TMP_DIR = Join-Path $RuntimeDir "downloads"
$env:TMP_RETENTION_SECONDS = "1800"
$env:COOKIES_BROWSER = $Browser
New-Item -ItemType Directory -Force -Path $env:TMP_DIR | Out-Null

if (Test-Path $WebPidFile) {
    $existingPid = Get-Content $WebPidFile -ErrorAction SilentlyContinue
    if ($existingPid -and (Get-Process -Id $existingPid -ErrorAction SilentlyContinue)) { Stop-Process -Id $existingPid -Force }
}

$webProcess = Start-Process -FilePath $Python -ArgumentList "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000" -WorkingDirectory $BackendDir -PassThru -WindowStyle Hidden
$webProcess.Id | Set-Content $WebPidFile
Write-Host "OmniPull is running at http://localhost:8000" -ForegroundColor Cyan
Write-Host "Using local browser sessions: $Browser" -ForegroundColor Gray
Write-Host "Press Ctrl+C to stop OmniPull." -ForegroundColor Gray

try {
    Set-Location $BackendDir
    & $Python -m celery -A celery_app worker --loglevel=info --concurrency=2 --queues=celery
}
finally {
    if (Get-Process -Id $webProcess.Id -ErrorAction SilentlyContinue) { Stop-Process -Id $webProcess.Id -Force }
    Remove-Item $WebPidFile -ErrorAction SilentlyContinue
}
