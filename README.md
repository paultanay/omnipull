# OmniPull

<p align="center"><img src="frontend/logo.svg" width="88" alt="OmniPull logo"></p>

OmniPull is a local web application for saving media from supported public links. Paste a link, choose an available format, and let your browser save the completed file.

## Run locally

Install and start Docker Desktop, then run:

```bash
docker compose up --build
```

Open [http://localhost:8000](http://localhost:8000). The first start builds the image; later starts are faster. Stop the application with `Ctrl+C`, or run `docker compose down` from another terminal.

PowerShell users can also run `./start.ps1`. macOS and Linux users can run `./start.sh`.

## Downloads and storage

The application temporarily stores a file inside its private Docker volume while it is being prepared. Once it is ready, the browser receives it as a normal attachment download. The file is saved to the browser's configured Downloads folder.

Websites cannot force a browser's native folder picker. To choose a location for every download, turn on the browser setting usually named **Ask where to save each file before downloading**. This is a browser privacy restriction, not a Docker limitation.

Temporary files are retained for 30 minutes and are cleaned up automatically. The only Docker volume created by this project is named `omnipull_download_cache`.

To remove the application and its temporary cache:

```bash
docker compose down -v
```

## Supported content

Availability depends on the source site and the specific post. Public, non-restricted media works without account configuration. Private, paid, age-gated, region-restricted, or protected media may be unavailable. Use OmniPull only for content you have permission to save and in accordance with applicable laws and platform terms.

## Development

The project has three small parts:

```text
backend/                API, queue tasks, download handling, and cleanup
frontend/               Static browser interface and local brand assets
docker-compose.yml      Local services and shared temporary storage
```

For a non-container development environment, install Python 3.12+, Redis, and FFmpeg; install `backend/requirements.txt`; then run the API and worker from `backend/` with the same `REDIS_URL` and `TMP_DIR` values.

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service health check |
| `POST` | `/api/fetch` | Queue link inspection |
| `GET` | `/api/task/{task_id}` | Read task status or result |
| `POST` | `/api/download` | Queue file preparation |
| `GET` | `/api/progress/{file_id}` | Read download progress |
| `GET` | `/api/file/{file_id}` | Download the prepared file |

## Contributing

Open an issue before substantial changes, keep pull requests focused, and include verification details. Do not commit downloaded media, credentials, or local environment files.

## License

[MIT](LICENSE)
