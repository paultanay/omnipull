#!/usr/bin/env bash
# OmniPull - One-click startup for Linux/macOS
# Starts Redis + Web in Docker, Celery worker on the HOST for browser cookie access.
#
# Usage: ./start.sh
# Stop:  Ctrl+C, then: docker compose down

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
VENV_DIR="$SCRIPT_DIR/.venv"

echo ""
echo "  OmniPull"
echo "  Universal media downloader"
echo ""

# --- Check Docker -------------------------------------------------------------
echo "[1/4] Checking Docker..."
if ! docker info &>/dev/null; then
    echo "  ERROR: Docker is not running. Please start Docker Desktop first."
    exit 1
fi
echo "       Docker is running."

# --- Check virtual environment ------------------------------------------------
echo "[2/4] Checking virtual environment..."
if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "       Creating virtual environment at .venv ..."
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --quiet --upgrade pip
    echo "       Installing dependencies..."
    "$VENV_DIR/bin/pip" install --quiet -r "$BACKEND_DIR/requirements.txt"
    echo "       Dependencies installed."
else
    echo "       Virtual environment found."
fi

# --- Start Docker services (Redis + Web) --------------------------------------
echo "[3/4] Starting Redis + Web server (Docker)..."
cd "$SCRIPT_DIR"
docker compose up -d --build

echo "       Waiting for web server..."
for i in $(seq 1 15); do
    if curl -sf http://localhost:8000/health &>/dev/null; then
        break
    fi
    sleep 2
done
echo "       Web server ready at http://localhost:8000"

# --- Start Celery worker on host (has browser cookie access) ------------------
echo "[4/4] Starting worker (auto-detecting browser cookies)..."
echo "       yt-dlp will auto-detect Chrome/Brave/Firefox cookies."
echo "       Make sure you are logged in to YouTube in your browser."
echo ""
echo "  App running at: http://localhost:8000"
echo "  Press Ctrl+C to stop. Then run: docker compose down"
echo ""

export REDIS_URL="redis://localhost:6379/0"
export TMP_DIR="/tmp/omnipull"
mkdir -p "$TMP_DIR"

cd "$BACKEND_DIR"
"$VENV_DIR/bin/celery" -A celery_app worker --loglevel=info --concurrency=4 --queues=celery