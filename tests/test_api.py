from __future__ import annotations

from fastapi.testclient import TestClient

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
