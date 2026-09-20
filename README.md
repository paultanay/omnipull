<div align="center">
  <h1>⬇ OmniPull</h1>
  <p><strong>Universal media downloader — YouTube, Instagram, Twitter/X and 1000+ more sites.</strong></p>
  <p>No ads. No hidden charges. No tracking. Fully open source.</p>
  <br/>
  <img src="https://img.shields.io/badge/python-3.12+-blue?style=flat-square" alt="Python 3.12+"/>
  <img src="https://img.shields.io/badge/fastapi-0.115-009688?style=flat-square" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/yt--dlp-latest-red?style=flat-square" alt="yt-dlp"/>
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="MIT License"/>
  <img src="https://img.shields.io/badge/docker-ready-2496ED?style=flat-square&logo=docker" alt="Docker"/>
</div>

---

## Features

- **Paste any link** from YouTube, Instagram, Twitter/X or 1000+ other platforms
- **Preview before downloading** — thumbnail, title, uploader, duration
- **Choose your quality** — 4K, 1080p, 720p, 480p, 360p, 144p, or audio-only
- **All video formats include audio** — video+audio streams are merged automatically via ffmpeg
- **Real-time progress** — live download bar with speed and ETA
- **Instagram carousel support** — multiple images/videos download as a single zip
- **Dark & light mode** with system preference detection
- **Fully mobile responsive**
- Zero ads, zero rate limits for self-hosted use

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python) + Uvicorn |
| Task queue | Celery + Redis |
| Media extraction | yt-dlp (latest) + instaloader |
| Video merging | ffmpeg |
| Frontend | Vanilla HTML/CSS/JS + Tailwind CSS CDN |
| Deployment | Docker + Render |

## Quick Start

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/) and Python 3.12+.

```bash
git clone https://github.com/YOUR_USERNAME/OmniPull.git
cd OmniPull
```

**Windows:**
```powershell
.\start.ps1
```

**Linux / macOS:**
```bash
chmod +x start.sh && ./start.sh
```

That is it. The script will:
1. Create a `.venv` and install Python dependencies automatically
2. Start Redis + the web server in Docker
3. Start the Celery worker **on your host machine** so yt-dlp can read your browser cookies automatically — no manual cookie export needed

Open **http://localhost:8000**.

To stop: press `Ctrl+C` (stops the worker), then `docker compose down`.

## Manual Setup (without Docker)

### Prerequisites

- Python 3.12+
- Redis (local install or via Docker)
- ffmpeg installed and on your PATH

### Steps

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/OmniPull.git
cd OmniPull

# 2. Create virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r backend/requirements.txt

# 4. Start Redis (pick one)
redis-server                              # if installed locally
docker run -p 6379:6379 redis:7-alpine   # or via Docker

# 5. Start the API server (terminal 1)
cd backend
uvicorn main:app --reload

# 6. Start the Celery worker (terminal 2, venv active)
cd backend
celery -A celery_app worker --loglevel=info --concurrency=4
```

Open **http://localhost:8000**.

## Deploy to Render (Free)

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → **New** → **Blueprint**
3. Connect your GitHub repo — Render auto-detects `render.yaml`
4. It will provision a web service + free Redis instance automatically
5. Your app is live at `https://omnipull-xxxx.onrender.com`

> **Note:** The Render free tier spins down after 15 min of inactivity. First request after idle takes ~60 seconds to wake up. Upgrade to a paid plan to avoid this.

## Environment Variables

Copy `.env.example` to `.env` for local development:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis broker URL |
| `TMP_DIR` | `/tmp/omnipull` | Temp directory for downloads |
| `PORT` | `8000` | Server port |

## Project Structure

```
OmniPull/
├── backend/
│   ├── main.py           # FastAPI app — all API routes, rate limiting, SSE
│   ├── tasks.py          # Celery tasks — fetch_info, download_file
│   ├── celery_app.py     # Celery + Redis configuration
│   ├── utils.py          # yt-dlp wrapper, format normalizer, instaloader fallback
│   ├── cleanup.py        # APScheduler — deletes temp files after 10 min
│   └── requirements.txt
├── frontend/
│   ├── index.html        # Single-page UI
│   ├── style.css         # Design system — dark/light themes, glassmorphism
│   └── app.js            # Fetch flow, format picker, SSE progress, download
├── Dockerfile            # Production container (Python + ffmpeg + supervisord)
├── docker-compose.yml    # Local dev — web + worker + redis
├── supervisord.conf      # Runs FastAPI + Celery in one container on Render
├── render.yaml           # One-click Render deploy
└── .env.example          # Environment variable template
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/fetch` | Submit URL → returns `task_id` |
| `GET` | `/api/task/{task_id}` | Poll task status and result |
| `POST` | `/api/download` | Start download → returns `task_id` + `file_id` |
| `GET` | `/api/progress/{file_id}` | SSE stream: `{percent, speed, eta, status}` |
| `GET` | `/api/file/{file_id}` | Stream the downloaded file to browser |

## Contributing

Pull requests are welcome. For major changes, open an issue first.

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "feat: add your feature"`
4. Push and open a PR

## Legal

OmniPull is a tool for downloading publicly available media for **personal use**. Always respect copyright law and the Terms of Service of the platforms you use. The developers are not responsible for misuse.

## License

[MIT](LICENSE)