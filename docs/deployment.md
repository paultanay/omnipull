# Deployment guidance

OmniPull is designed for a local, single-user installation. Its default Docker binding is loopback-only (`127.0.0.1:8000`) for that reason.

## Do not publish the default stack

Putting a downloader directly on the public internet can let an unauthenticated party consume bandwidth, storage, and worker capacity. It can also increase the impact of bugs in URL-handling or upstream extractors. If you need remote access, use a private network or VPN first.

Any shared deployment needs, at minimum:

- authentication and authorization at a trusted reverse proxy;
- TLS termination and an explicit allowlist of trusted origins;
- firewall and container egress rules that block private networks and cloud metadata addresses;
- CPU, memory, download-size, concurrent-job, and disk quotas;
- monitoring, log retention, and a tested update process for yt-dlp and dependencies.

## URL validation

Before enqueueing work, OmniPull only accepts HTTP(S) URLs without embedded credentials on ports 80 or 443, then rejects destinations that currently resolve to non-public addresses. DNS can change after validation and extractors may follow source-specific requests, so this application-level check is defence in depth only. Network egress controls remain mandatory for a shared deployment.

## Cookies and sessions

Windows browser-session mode is local-only. Do not mount browser profile directories into containers and do not distribute exported cookie files. Use a dedicated account where an authenticated workflow is truly necessary.
