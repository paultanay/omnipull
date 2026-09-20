import pathlib, re, sys

ROOT = pathlib.Path("C:/Users/pault/Desktop/Projects/OmniPull")

# ============================================================
# STEP 1: docker-compose.yml  (add COOKIES_FILE + volume mount)
# ============================================================
dc = ROOT / "docker-compose.yml"
txt = dc.read_text(encoding="utf-8")

# ---- web service: add env var after TMP_DIR line ----
old_web_env = "      - TMP_DIR=/tmp/omnipull\n    volumes:\n      - tmp_downloads:/tmp/omnipull\n    depends_on:\n      redis:\n        condition: service_healthy\n    restart: unless-stopped\n  worker:"
new_web_env = "      - TMP_DIR=/tmp/omnipull\n      - COOKIES_FILE=/app/cookies.txt\n    volumes:\n      - tmp_downloads:/tmp/omnipull\n      - ./cookies.txt:/app/cookies.txt:ro\n    depends_on:\n      redis:\n        condition: service_healthy\n    restart: unless-stopped\n  worker:"
txt = txt.replace(old_web_env, new_web_env, 1)

# ---- worker service: add env var + volume mount ----
old_wkr_env = "      - TMP_DIR=/tmp/omnipull\n    volumes:\n      - tmp_downloads:/tmp/omnipull\n    depends_on:\n      redis:\n        condition: service_healthy\n    restart: unless-stopped\nvolumes:"
new_wkr_env = "      - TMP_DIR=/tmp/omnipull\n      - COOKIES_FILE=/app/cookies.txt\n    volumes:\n      - tmp_downloads:/tmp/omnipull\n      - ./cookies.txt:/app/cookies.txt:ro\n    depends_on:\n      redis:\n        condition: service_healthy\n    restart: unless-stopped\nvolumes:"
txt = txt.replace(old_wkr_env, new_wkr_env, 1)

dc.write_text(txt, encoding="utf-8")
final = dc.read_text(encoding="utf-8")
print("STEP 1 DONE")
print("COOKIES_FILE in web env:", "COOKIES_FILE=/app/cookies.txt" in final)
print("cookies.txt volume count:", final.count("./cookies.txt:/app/cookies.txt:ro"))
print()

# ============================================================
# STEP 2: utils.py  (add _cookies_file() + inject cookiefile)
# ============================================================
u = ROOT / "backend" / "utils.py"
uc = u.read_text(encoding="utf-8")

# --- inject _cookies_file helper + patch _ydl_opts_info ---
old_info = '''def _ydl_opts_info():
    return {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "skip_download": True,
        "noplaylist": True,
        "age_limit": None,
        "geo_bypass": True,
    }'''

new_info = '''def _cookies_file():
    """Return path to cookies.txt if it exists, else None."""
    import pathlib as _pl
    path = __import__("os").getenv("COOKIES_FILE", "/app/cookies.txt")
    if path and _pl.Path(path).exists():
        return path
    return None


def _ydl_opts_info():
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "skip_download": True,
        "noplaylist": True,
        "age_limit": None,
        "geo_bypass": True,
    }
    cf = _cookies_file()
    if cf:
        opts["cookiefile"] = cf
    return opts'''

uc = uc.replace(old_info, new_info, 1)

# --- patch download_media ydl_opts block ---
old_dl = '''    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "format": fmt,
        "geo_bypass": True,
        "writethumbnail": False,
        "writeinfojson": False,
        # postprocessors ensure audio is re-encoded if needed for compatibility
        "postprocessors": [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4",
        }],
    }'''

new_dl = '''    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "format": fmt,
        "geo_bypass": True,
        "writethumbnail": False,
        "writeinfojson": False,
        "postprocessors": [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4",
        }],
    }
    cf = _cookies_file()
    if cf:
        ydl_opts["cookiefile"] = cf'''

uc = uc.replace(old_dl, new_dl, 1)
u.write_text(uc, encoding="utf-8")
final_u = u.read_text(encoding="utf-8")
print("STEP 2 DONE")
print("_cookies_file present:", "_cookies_file" in final_u)
print('opts["cookiefile"] in info:', 'opts["cookiefile"] = cf' in final_u)
print('ydl_opts["cookiefile"] in download:', 'ydl_opts["cookiefile"] = cf' in final_u)
print()

# ============================================================
# STEP 3: .gitignore + cookies.txt placeholder
# ============================================================
gi = ROOT / ".gitignore"
gi_txt = gi.read_text(encoding="utf-8")
if "cookies.txt" not in gi_txt:
    gi_txt += "\n# YouTube/browser cookies - NEVER commit these\ncookies.txt\n"
    gi.write_text(gi_txt, encoding="utf-8")
    print("STEP 3: cookies.txt added to .gitignore")
else:
    print("STEP 3: cookies.txt already in .gitignore")

ck = ROOT / "cookies.txt"
if not ck.exists():
    ck.write_text(
        "# Netscape HTTP Cookie File\n"
        "# Export your YouTube cookies here using a browser extension\n"
        "# See README for instructions\n",
        encoding="utf-8"
    )
    print("STEP 3: cookies.txt placeholder created")
else:
    print("STEP 3: cookies.txt already exists")
print()

# ============================================================
# STEP 4: .env.example
# ============================================================
env_ex = ROOT / ".env.example"
env_content = (
    "# OmniPull Environment Variables\n"
    "# Copy this file to .env and fill in your values\n"
    "\n"
    "# Redis connection URL\n"
    "# Local development: redis://localhost:6379/0\n"
    "# Docker Compose: redis://redis:6379/0  (set automatically)\n"
    "REDIS_URL=redis://localhost:6379/0\n"
    "\n"
    "# Temporary download directory\n"
    "TMP_DIR=/tmp/omnipull\n"
    "\n"
    "# Server port\n"
    "PORT=8000\n"
    "\n"
    "# Path to Netscape-format cookies file (for YouTube bot detection bypass)\n"
    "# Export from your browser using \"Get cookies.txt LOCALLY\" extension while on youtube.com\n"
    "# Place the file at the project root as cookies.txt\n"
    "# It is gitignored - never commit your cookies\n"
    "COOKIES_FILE=/app/cookies.txt\n"
)
env_ex.write_text(env_content, encoding="utf-8")
print("STEP 4: .env.example updated")
print()

print("ALL FILE STEPS COMPLETE")