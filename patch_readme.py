import pathlib
p = pathlib.Path("C:/Users/pault/Desktop/Projects/OmniPull/README.md")
content = p.read_text(encoding="utf-8")

old = (
    "## Quick Start (Docker)\n"
    "\n"
    "The easiest way to run OmniPull locally. Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/).\n"
    "\n"
    "```bash\n"
    "git clone https://github.com/YOUR_USERNAME/OmniPull.git\n"
    "cd OmniPull\n"
    "docker compose up --build\n"
    "```\n"
    "\n"
    "Open **http://localhost:8000** \u2014 that is it.\n"
    "\n"
    "```bash\n"
    "# Stop\n"
    "docker compose down\n"
    "```"
)

new = (
    "## Quick Start\n"
    "\n"
    "Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/) and Python 3.12+.\n"
    "\n"
    "```bash\n"
    "git clone https://github.com/YOUR_USERNAME/OmniPull.git\n"
    "cd OmniPull\n"
    "```\n"
    "\n"
    "**Windows:**\n"
    "```powershell\n"
    ".\\start.ps1\n"
    "```\n"
    "\n"
    "**Linux / macOS:**\n"
    "```bash\n"
    "chmod +x start.sh && ./start.sh\n"
    "```\n"
    "\n"
    "That is it. The script will:\n"
    "1. Create a `.venv` and install Python dependencies automatically\n"
    "2. Start Redis + the web server in Docker\n"
    "3. Start the Celery worker **on your host machine** so yt-dlp can read your browser cookies automatically \u2014 no manual cookie export needed\n"
    "\n"
    "Open **http://localhost:8000**.\n"
    "\n"
    "To stop: press `Ctrl+C` (stops the worker), then `docker compose down`."
)

found = old in content
print("old block found:", found)
if found:
    content = content.replace(old, new)
    p.write_text(content, encoding="utf-8")
    print("STEP 5: README.md patched successfully")
    updated = p.read_text(encoding="utf-8")
    print("new block present:", "start.ps1" in updated)
    print("old header gone:", "Quick Start (Docker)" not in updated)
else:
    print("ERROR: block not found, showing raw bytes around Quick Start:")
    idx = content.find("## Quick Start")
    print(repr(content[idx:idx+400]))