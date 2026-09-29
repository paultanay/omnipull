"""
OmniPull API, task queue integration, progress updates, and file serving.
"""
from __future__ import annotations

import ast
import json
import logging
import os
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import redis as redis_client
from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from celery_app import celery_app
from cleanup import start_cleanup_scheduler
from tasks import download_file, fetch_info
from utils import TMP_BASE, validate_url

# --- Logging ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# --- Redis --------------------------------------------------------------------
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_redis = redis_client.from_url(REDIS_URL, decode_responses=True)

# --- Simple in-memory rate limiter --------------------------------------------
# {ip: [timestamp, timestamp, ...]}
_rate_buckets: dict[str, list[float]] = defaultdict(list)
RATE_WINDOW = 60.0  # seconds


def check_rate_limit(ip: str, max_requests: int) -> bool:
    """Return True if allowed, False if rate limited."""
    now = time.time()
    bucket = _rate_buckets[ip]
    # Drop timestamps outside the window
    _rate_buckets[ip] = [t for t in bucket if now - t < RATE_WINDOW]
    if len(_rate_buckets[ip]) >= max_requests:
        return False
    _rate_buckets[ip].append(now)
    return True


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Prepare temporary storage and stop the cleanup scheduler on shutdown."""
    TMP_BASE.mkdir(parents=True, exist_ok=True)
    scheduler = start_cleanup_scheduler()
    logger.info("OmniPull started.")
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


# --- App ----------------------------------------------------------------------
app = FastAPI(
    title="OmniPull",
    description="Local media download service.",
    version="1.0.0",
    lifespan=lifespan,
)

# The bundled frontend is served from this application, so it needs no CORS.
# Opt in explicitly when developing a separate frontend; never use a wildcard
# for an application that can initiate downloads on behalf of its caller.
cors_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip()]
if cors_origins:
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )


# --- Models -------------------------------------------------------------------
class FetchRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


class DownloadRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    format_id: str = Field(min_length=1, max_length=256)
    file_id: str | None = None


# --- Health -------------------------------------------------------------------
@app.get("/health")
@app.get("/healthz")
async def health() -> dict:
    return {"status": "ok", "service": "OmniPull"}


# --- Fetch media info ---------------------------------------------------------
@app.post("/api/fetch")
async def api_fetch(request: Request, body: FetchRequest) -> dict:
    ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(ip, max_requests=20):
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")

    url = body.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required.")
    if not validate_url(url):
        raise HTTPException(
            status_code=400,
            detail="Invalid URL. Please provide a full URL starting with http:// or https://",
        )
    task = fetch_info.delay(url)
    return {"task_id": task.id, "status": "pending"}


# --- Task status polling ------------------------------------------------------
@app.get("/api/task/{task_id}")
async def api_task_status(task_id: str) -> dict:
    result = AsyncResult(task_id, app=celery_app)

    if result.state == "PENDING":
        return {"task_id": task_id, "status": "pending"}
    if result.state == "STARTED":
        meta = result.info or {}
        return {"task_id": task_id, "status": "started", "message": meta.get("status", "")}
    if result.state == "PROGRESS":
        return {"task_id": task_id, "status": "progress", "progress": result.info}
    if result.state == "SUCCESS":
        return {"task_id": task_id, "status": "success", "result": result.result}
    if result.state == "FAILURE":
        # result.info can be an Exception -- always stringify it
        err = result.info
        if isinstance(err, Exception):
            msg = str(err)
        elif isinstance(err, dict):
            msg = err.get("message") or err.get("exc_message") or str(err)
        else:
            msg = str(err) if err else "Unknown error"
        return {"task_id": task_id, "status": "error", "message": msg}

    return {"task_id": task_id, "status": result.state.lower()}


# --- Download -----------------------------------------------------------------
@app.post("/api/download")
async def api_download(request: Request, body: DownloadRequest) -> dict:
    ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(ip, max_requests=10):
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")

    url = body.url.strip()
    if not validate_url(url):
        raise HTTPException(status_code=400, detail="Invalid URL.")
    if body.file_id:
        try:
            file_id = str(uuid.UUID(body.file_id))
        except ValueError as error:
            raise HTTPException(status_code=400, detail="Invalid file ID.") from error
    else:
        file_id = str(uuid.uuid4())
    task = download_file.delay(url, body.format_id, file_id)
    return {"task_id": task.id, "file_id": file_id, "status": "pending"}


# --- SSE Progress -------------------------------------------------------------
@app.get("/api/progress/{file_id}")
async def api_progress(file_id: str) -> StreamingResponse:
    try:
        file_id = str(uuid.UUID(file_id))
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Invalid file ID.") from error
    async def event_stream() -> AsyncGenerator[str, None]:
        import asyncio
        last_data = None
        timeout = 300
        elapsed = 0
        interval = 1.0

        while elapsed < timeout:
            raw = _redis.get(f"progress:{file_id}")
            if raw and raw != last_data:
                last_data = raw
                try:
                    data = ast.literal_eval(raw)
                except Exception:
                    data = {"status": "unknown"}
                yield f"data: {json.dumps(data)}\n\n"
                if data.get("status") in ("complete", "error"):
                    break
            await asyncio.sleep(interval)
            elapsed += interval

        yield 'data: {"status": "done"}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --- File serving -------------------------------------------------------------
@app.get("/api/file/{file_id}")
async def api_serve_file(file_id: str) -> FileResponse:
    try:
        file_id = str(uuid.UUID(file_id))
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Invalid file ID.") from error

    file_dir = TMP_BASE / file_id
    if not file_dir.exists():
        raise HTTPException(status_code=404, detail="File not found or expired.")

    files = [
        f for f in file_dir.iterdir()
        if not f.name.endswith(".json") and not f.name.endswith(".part")
    ]
    if not files:
        raise HTTPException(status_code=404, detail="File not ready yet.")

    zip_files = [f for f in files if f.suffix == ".zip"]
    filepath = zip_files[0] if zip_files else files[0]

    return FileResponse(
        path=str(filepath),
        filename=filepath.name,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filepath.name}"'},
    )


# --- Static frontend ----------------------------------------------------------
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


# --- Entry point --------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
