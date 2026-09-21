#!/usr/bin/env bash
# Docker mode for public links. Windows users should use start.ps1 for automatic browser sessions.

set -euo pipefail
cd "$(dirname "$0")"
docker compose up --build
