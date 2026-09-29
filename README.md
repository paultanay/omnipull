# OmniPull

<p align="center"><img src="frontend/logo.svg" width="88" alt="OmniPull logo"></p>

<p align="center"><strong>A local-first media downloader for supported public links.</strong><br>Built with FastAPI, Celery, Redis, yt-dlp, and FFmpeg.</p>

OmniPull turns a supported public media link into a browser download without sending it through a hosted downloader. Paste a URL, inspect available video or audio formats, and follow its progress in a clean local web interface.

> Use OmniPull only for media you are authorized to save and in accordance with applicable law and platform terms.

## Why OmniPull

- **Local-first:** runs on your machine and serves the browser interface locally.
- **Useful format choices:** select a video quality or an audio-only stream before downloading.
- **Visible progress:** downloads run in background workers with live progress updates.
- **Docker-first:** one command starts the default local setup.
- **Temporary by design:** prepared files are removed automatically after the retention period.
- **Windows session support:** optional local mode can use a signed-in browser session without exporting cookie files.

## Quick start

Install and start [Docker Desktop](https://www.docker.com/products/docker-desktop/), then run:

```bash
git clone https://github.com/paultanay/omnipull.git
cd omnipull
docker compose up --build
```

Open [http://localhost:8000](http://localhost:8000). The Compose configuration binds the web service to `127.0.0.1`, keeping it off the local network by default.

Stop it with `Ctrl+C`, or run `docker compose down`. To also remove the temporary download cache, run:

```bash
docker compose down -v
```

## How it works

```text
Browser → FastAPI → Redis queue → Celery worker → yt-dlp + FFmpeg → browser download
```

The worker temporarily writes the prepared file to its private cache. Once ready, your browser downloads it to its configured Downloads folder. A website cannot force the browser's native location picker; enable **Ask where to save each file** in your browser if you want to choose a location every time.

## Sources and compatibility

OmniPull provides a focused interface for public media links. YouTube, Instagram, and X/Twitter are recognised in the interface; the underlying yt-dlp engine supports many more extractors. Actual availability depends on the source and the post, and can change when a source site changes.

Private, paid, age-gated, region-restricted, or otherwise protected content may not be available. OmniPull does not bypass access controls.

## Windows browser-session mode

When a source requires a session from a browser already signed in on Windows, run:

```powershell
.\start.ps1
```

The script starts Redis in Docker and runs the web service and worker on Windows, where they can access your browser's encrypted session. It tries Brave, Chrome, Edge, and Firefox automatically. Select a browser explicitly when needed:

```powershell
.\start.ps1 -Browser brave
```

The session stays on your computer; it is not uploaded or written to a cookie file. FFmpeg is installed through WinGet on first use when necessary.

## Deployment and security

The default setup is intentionally for a single local user. Do **not** expose it directly to the internet: a media-downloading service needs access control, network egress controls, and a reverse proxy appropriate to its environment.

OmniPull rejects non-HTTP(S), credentialed, non-standard-port, and currently non-public URL targets before sending work to a worker. This is a useful guardrail, not a replacement for network-level SSRF protection; see [deployment guidance](docs/deployment.md) before any shared or remote deployment.

To develop a separately served frontend, explicitly set its origin rather than opening CORS to the world:

```env
CORS_ORIGINS=http://localhost:5173
```

## Development

```text
backend/       FastAPI API, Celery tasks, validation, cleanup
frontend/      Static interface and local brand assets
tests/         Fast, isolated API and validation coverage
docs/          Deployment and contributor documentation
```

For non-container development, install Python 3.12+, Redis, and FFmpeg; install `backend/requirements.txt`; then run the API and worker from `backend/` with matching `REDIS_URL` and `TMP_DIR` values.

Run the checks with:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
ruff check backend tests
```

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service health check |
| `POST` | `/api/fetch` | Queue media inspection |
| `GET` | `/api/task/{task_id}` | Read task status or result |
| `POST` | `/api/download` | Queue file preparation |
| `GET` | `/api/progress/{file_id}` | Read download progress |
| `GET` | `/api/file/{file_id}` | Download a prepared file |

## Roadmap

The next product work should earn its complexity: persistent queue/history, cancellation and retry, playlist selection, and a mobile share flow. See [open issues](https://github.com/paultanay/omnipull/issues) for work that has been accepted into the project.

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md), keep pull requests focused, and include verification details. Do not commit downloaded media, credentials, or local environment files.

## Security

Please report vulnerabilities privately as described in [SECURITY.md](SECURITY.md). Do not open a public issue for a suspected vulnerability.

## License

[MIT](LICENSE)
