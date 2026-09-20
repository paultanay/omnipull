# OmniPull - One-click startup for Windows
# Starts Redis + Web in Docker, then starts the Celery worker on the HOST
# so yt-dlp can access your browser cookies automatically.
#
# Usage: .\start.ps1
# Stop:  Ctrl+C  (stops worker), then: docker compose down

param(
    [string]$Browser = "",        # Override browser: chrome, brave, firefox, edge
    [switch]$NoCookies            # Skip cookie auto-detection
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot "backend"
$VenvDir = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvCelery = Join-Path $VenvDir "Scripts\celery.exe"

Write-Host ""
Write-Host "  OmniPull" -ForegroundColor Cyan
Write-Host "  Universal media downloader" -ForegroundColor Gray
Write-Host ""

# --- Check Docker is running --------------------------------------------------
Write-Host "[1/4] Checking Docker..." -ForegroundColor Yellow
try {
    docker info *>$null 2>&1
    if ($LASTEXITCODE -ne 0) { throw }
    Write-Host "      Docker is running." -ForegroundColor Green
} catch {
    Write-Host "      ERROR: Docker Desktop is not running. Please start it first." -ForegroundColor Red
    exit 1
}

# --- Check virtual environment ------------------------------------------------
Write-Host "[2/4] Checking virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path $VenvPython)) {
    Write-Host "      Creating virtual environment at .venv ..." -ForegroundColor Cyan
    python -m venv $VenvDir
    & $VenvPython -m pip install --quiet --upgrade pip
    Write-Host "      Installing dependencies from requirements.txt ..." -ForegroundColor Cyan
    & $VenvPython -m pip install --quiet -r (Join-Path $BackendDir "requirements.txt")
    Write-Host "      Dependencies installed." -ForegroundColor Green
} else {
    Write-Host "      Virtual environment found." -ForegroundColor Green
}

# --- Start Docker services (Redis + Web) --------------------------------------
Write-Host "[3/4] Starting Redis + Web server (Docker)..." -ForegroundColor Yellow
Set-Location $ProjectRoot
docker compose up -d --build
if ($LASTEXITCODE -ne 0) {
    Write-Host "      ERROR: docker compose failed." -ForegroundColor Red
    exit 1
}

# Wait for web to be healthy
Write-Host "      Waiting for web server to be ready..." -ForegroundColor Gray
$maxWait = 30
$waited = 0
do {
    Start-Sleep -Seconds 2
    $waited += 2
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($resp.StatusCode -eq 200) { break }
    } catch {}
} while ($waited -lt $maxWait)
Write-Host "      Web server ready at http://localhost:8000" -ForegroundColor Green

# --- Build cookie environment for worker --------------------------------------
$env:REDIS_URL = "redis://localhost:6379/0"
$env:TMP_DIR = Join-Path $env:TEMP "omnipull"
New-Item -ItemType Directory -Force -Path $env:TMP_DIR *>$null

if ($Browser) {
    $env:COOKIES_BROWSER = $Browser.ToLower()
    Write-Host "[4/4] Starting worker (cookies from $Browser)..." -ForegroundColor Yellow
} elseif ($NoCookies) {
    Write-Host "[4/4] Starting worker (no cookies)..." -ForegroundColor Yellow
} else {
    Write-Host "[4/4] Starting worker (auto-detecting browser cookies)..." -ForegroundColor Yellow
    Write-Host "      yt-dlp will auto-detect Chrome/Brave/Firefox cookies." -ForegroundColor Gray
    Write-Host "      Make sure you are logged in to YouTube in your browser." -ForegroundColor Gray
}

Write-Host ""
Write-Host "  App running at: http://localhost:8000" -ForegroundColor Cyan
Write-Host "  Press Ctrl+C to stop the worker. Then run: docker compose down" -ForegroundColor Gray
Write-Host ""

# Start Celery worker (blocking - keeps terminal open)
Set-Location $BackendDir
& $VenvCelery -A celery_app worker --loglevel=info --concurrency=4 --queues=celery