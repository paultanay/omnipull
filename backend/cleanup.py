"""
Background scheduler that cleans up old temp download files.
Runs every 5 minutes, deletes dirs older than 10 minutes.
"""
from __future__ import annotations

import logging
import os
import shutil
import time
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

TMP_BASE = Path(os.getenv("TMP_DIR", "/tmp/omnipull"))
MAX_AGE_SECONDS = int(os.getenv("TMP_RETENTION_SECONDS", "1800"))


def cleanup_old_files() -> None:
    if not TMP_BASE.exists():
        return

    now = time.time()
    cleaned = 0

    for entry in TMP_BASE.iterdir():
        if not entry.is_dir():
            continue
        try:
            age = now - entry.stat().st_mtime
            if age > MAX_AGE_SECONDS:
                shutil.rmtree(entry, ignore_errors=True)
                cleaned += 1
        except OSError:
            pass

    if cleaned:
        logger.info(f"Cleaned up {cleaned} expired download directories.")


def start_cleanup_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(cleanup_old_files, "interval", minutes=5, id="file_cleanup")
    scheduler.start()
    logger.info("File cleanup scheduler started.")
    return scheduler
