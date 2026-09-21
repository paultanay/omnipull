#!/usr/bin/env bash
# Starts OmniPull with Docker Compose.
# Usage: ./start.sh

set -euo pipefail
cd "$(dirname "$0")"

if ! docker info >/dev/null 2>&1; then
  echo "Docker is required and must be running." >&2
  exit 1
fi

docker compose up --build
