from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

import main
from main import app


def test_health_check() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "OmniPull"}


def test_file_endpoint_requires_a_uuid() -> None:
    with TestClient(app) as client:
        response = client.get("/api/file/not-a-uuid")

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid file ID."


def test_default_app_does_not_emit_wildcard_cors() -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers={"Origin": "https://untrusted.example"})

    assert "access-control-allow-origin" not in response.headers


def test_file_download_supports_a_unicode_filename(tmp_path, monkeypatch) -> None:
    """Starlette must generate an RFC 5987 header for non-Latin filenames."""
    file_id = str(uuid.uuid4())
    download_dir = tmp_path / file_id
    download_dir.mkdir()
    (download_dir / "নিয়তি ｜ episode.mp4").write_bytes(b"media")
    monkeypatch.setattr(main, "TMP_BASE", tmp_path)

    with TestClient(app) as client:
        response = client.get(f"/api/file/{file_id}")

    assert response.status_code == 200
    assert response.content == b"media"
    assert "filename*=" in response.headers["content-disposition"]
