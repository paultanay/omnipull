from __future__ import annotations

import socket

import utils


def test_validate_url_accepts_a_public_https_host(monkeypatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))],
    )

    assert utils.validate_url("https://media.example/video?id=1")


def test_validate_url_rejects_internal_and_ambiguous_targets() -> None:
    rejected = (
        "http://127.0.0.1/",
        "http://[::1]/",
        "http://169.254.169.254/latest/meta-data/",
        "http://user:pass@example.com/",
        "https://example.com:8443/",
        "file:///etc/passwd",
        "https://",
    )

    for url in rejected:
        assert not utils.validate_url(url), url


def test_validate_url_rejects_host_with_private_dns_answer(monkeypatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.7", 443))],
    )

    assert not utils.validate_url("https://internal-looking.example/path")
