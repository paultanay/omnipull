"""
Celery tasks for OmniPull.
- fetch_info: extract media metadata and available formats
- download_file: download a specific format to /tmp
"""
from __future__ import annotations

import ast
import json
import os

import redis as redis_client

from celery_app import celery_app
from utils import (
    detect_platform,
    download_media,
    extract_instagram_instaloader,
    extract_media_info,
    validate_url,
)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_redis = redis_client.from_url(REDIS_URL, decode_responses=True)


@celery_app.task(bind=True, name="fetch_info")
def fetch_info(self, url: str) -> dict:
    """Extract media info from URL. Returns normalized metadata + format list."""
    self.update_state(state="STARTED", meta={"status": "Fetching media info..."})

    if not validate_url(url):
        raise ValueError("Invalid URL. Please provide a full URL starting with http:// or https://")

    try:
        result = extract_media_info(url)
        return {"status": "success", "data": result}
    except ValueError as e:
        # Pass the raw yt-dlp error through - it's descriptive enough
        # Strip the verbose "ERROR: " prefix yt-dlp adds
        error_msg = str(e).replace("ERROR: ", "").strip()
        raise ValueError(error_msg)


@celery_app.task(bind=True, name="download_file")
def download_file(self, url: str, format_id: str, file_id: str) -> dict:
    """Download media to /tmp/omnipull/{file_id}/. Reports progress to Redis."""
    self.update_state(state="STARTED", meta={"status": "Starting download...", "percent": 0})

    platform = detect_platform(url)

    def progress_hook(d: dict) -> None:
        if d["status"] == "downloading":
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            percent = (downloaded / total * 100) if total else 0
            speed = d.get("speed")
            eta = d.get("eta")

            speed_str = None
            if speed:
                if speed > 1_048_576:
                    speed_str = f"{speed / 1_048_576:.1f} MB/s"
                elif speed > 1024:
                    speed_str = f"{speed / 1024:.1f} KB/s"
                else:
                    speed_str = f"{speed:.0f} B/s"

            eta_str = None
            if eta:
                m, s = divmod(int(eta), 60)
                eta_str = f"{m}m {s}s" if m else f"{s}s"

            progress_data = {
                "percent": round(percent, 1),
                "speed": speed_str,
                "eta": eta_str,
                "status": "downloading",
            }
            _redis.setex(f"progress:{file_id}", 600, str(progress_data))
            self.update_state(state="PROGRESS", meta=progress_data)

        elif d["status"] == "finished":
            done_data = {"percent": 100, "speed": None, "eta": None, "status": "processing"}
            _redis.setex(f"progress:{file_id}", 600, str(done_data))
            self.update_state(state="PROGRESS", meta=done_data)

    try:
        if platform == "instagram":
            try:
                result = download_media(url, format_id, file_id, progress_hook)
            except ValueError:
                self.update_state(
                    state="STARTED",
                    meta={"status": "Trying Instagram fallback...", "percent": 0},
                )
                result = extract_instagram_instaloader(url, file_id)
        else:
            result = download_media(url, format_id, file_id, progress_hook)

        complete_data = {"percent": 100, "speed": None, "eta": None, "status": "complete"}
        _redis.setex(f"progress:{file_id}", 600, str(complete_data))

        return {"status": "success", "data": result}

    except ValueError as e:
        error_data = {"status": "error", "message": str(e)}
        _redis.setex(f"progress:{file_id}", 60, str(error_data))
        raise