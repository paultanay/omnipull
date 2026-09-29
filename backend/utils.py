"""
Media extraction and download utilities.
"""
from __future__ import annotations

import ipaddress
import os
import re
import socket
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

import yt_dlp

# --- Platform detection -------------------------------------------------------

YOUTUBE_RE = re.compile(
    r"(https?://)?(www\.)?(youtube\.com|youtu\.be|music\.youtube\.com)/",
    re.IGNORECASE,
)
INSTAGRAM_RE = re.compile(
    r"(https?://)?(www\.)?instagram\.com/",
    re.IGNORECASE,
)
TWITTER_RE = re.compile(
    r"(https?://)?(www\.)?(twitter\.com|x\.com)/",
    re.IGNORECASE,
)

SUPPORTED_PLATFORMS = {
    "youtube": YOUTUBE_RE,
    "instagram": INSTAGRAM_RE,
    "twitter": TWITTER_RE,
}


def detect_platform(url: str) -> str:
    for name, pattern in SUPPORTED_PLATFORMS.items():
        if pattern.search(url):
            return name
    return "other"


MAX_URL_LENGTH = 2_048


def _is_public_address(address: str) -> bool:
    """Return whether an address is globally routable.

    This deliberately rejects loopback, private, link-local, multicast and
    documentation ranges.  OmniPull fetches user-provided URLs, so accepting
    an internal address would turn it into a local-network request proxy.
    """
    try:
        return ipaddress.ip_address(address).is_global
    except ValueError:
        return False


def _host_resolves_publicly(hostname: str, port: int) -> bool:
    """Require every current DNS answer for a hostname to be public.

    DNS can change after this check, so this is defence in depth rather than a
    substitute for network-level egress restrictions in a public deployment.
    """
    try:
        answers = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except OSError:
        return False
    return bool(answers) and all(_is_public_address(answer[4][0]) for answer in answers)


def validate_url(url: str) -> bool:
    """Validate an HTTP(S) URL that may be fetched by yt-dlp.

    URLs with credentials, unusual ports, malformed hosts, or internal
    destinations are rejected before they reach a worker.
    """
    if not isinstance(url, str) or not url or len(url) > MAX_URL_LENGTH:
        return False

    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        return False

    if parsed.scheme.lower() not in {"http", "https"}:
        return False
    if not parsed.netloc or parsed.username or parsed.password:
        return False

    hostname = parsed.hostname
    if not hostname or any(char.isspace() for char in hostname):
        return False

    expected_port = 443 if parsed.scheme.lower() == "https" else 80
    if port is not None and port != expected_port:
        return False

    if _is_public_address(hostname):
        return True
    if hostname.replace(".", "").isdigit():
        return False
    return _host_resolves_publicly(hostname, expected_port)


# --- Format helpers -----------------------------------------------------------

def _human_size(size_bytes):
    if not size_bytes:
        return None
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def _quality_label(fmt):
    height = fmt.get("height")
    if height:
        label = f"{height}p"
        fps = fmt.get("fps")
        if fps and fps > 30:
            label += f"{int(fps)}"
        return label
    abr = fmt.get("abr")
    if abr:
        return f"{int(abr)}kbps"
    return fmt.get("format_note") or fmt.get("format_id", "unknown")


def _has_video(fmt):
    v = fmt.get("vcodec", "none")
    return bool(v and v != "none")


def _has_audio(fmt):
    a = fmt.get("acodec", "none")
    return bool(a and a != "none")


def normalize_formats(raw_formats: list) -> list:
    """
    Build a clean format list for the frontend.

    Strategy:
    - For each unique video resolution, create ONE merged entry that pairs it
      with the best available audio stream. The format_id is "VIDEO_ID+AUDIO_ID"
      so yt-dlp + ffmpeg will merge them automatically at download time.
    - If a format already has both video and audio, use it directly.
    - Audio-only formats are kept separately (type="audio") for the Audio tab.
    - video_only formats are NEVER shown directly to the user.
    """
    if not raw_formats:
        return []

    # Separate streams
    video_only = [f for f in raw_formats if _has_video(f) and not _has_audio(f)]
    audio_only = [f for f in raw_formats if _has_audio(f) and not _has_video(f)]
    muxed = [f for f in raw_formats if _has_video(f) and _has_audio(f)]

    # Pick best audio stream for merging (highest abr, prefer m4a/mp4 for compatibility)
    best_audio = None
    if audio_only:
        def audio_score(a):
            abr = a.get("abr") or a.get("tbr") or 0
            ext_bonus = 10 if a.get("ext") in ("m4a", "mp4") else 0
            return abr + ext_bonus
        best_audio = max(audio_only, key=audio_score)

    results = []
    seen_heights = set()

    # Build merged entries from video-only + best audio
    for vfmt in sorted(video_only, key=lambda f: -(f.get("height") or 0)):
        height = vfmt.get("height")
        if not height:
            continue
        if height in seen_heights:
            continue
        seen_heights.add(height)

        if best_audio:
            fmt_id = f"{vfmt['format_id']}+{best_audio['format_id']}"
            # Estimate combined size
            vsize = vfmt.get("filesize") or vfmt.get("filesize_approx") or 0
            asize = best_audio.get("filesize") or best_audio.get("filesize_approx") or 0
            total_size = (vsize + asize) if (vsize and asize) else (vsize or asize or None)
        else:
            # No separate audio track -- use the video format as-is
            fmt_id = vfmt["format_id"]
            total_size = vfmt.get("filesize") or vfmt.get("filesize_approx")

        results.append({
            "format_id": fmt_id,
            "ext": "mp4",  # always mp4 after merge
            "quality_label": _quality_label(vfmt),
            "type": "video",
            "filesize": total_size,
            "filesize_human": _human_size(total_size),
            "vcodec": vfmt.get("vcodec"),
            "acodec": best_audio.get("acodec") if best_audio else vfmt.get("acodec"),
            "height": height,
            "fps": vfmt.get("fps"),
            "abr": best_audio.get("abr") if best_audio else None,
            "tbr": vfmt.get("tbr"),
            "has_audio": best_audio is not None,
        })

    # Add muxed formats (already have video+audio), deduplicate by height
    for fmt in sorted(muxed, key=lambda f: -(f.get("height") or 0)):
        height = fmt.get("height")
        if height in seen_heights:
            continue
        if height:
            seen_heights.add(height)
        results.append({
            "format_id": fmt.get("format_id"),
            "ext": fmt.get("ext", "mp4"),
            "quality_label": _quality_label(fmt),
            "type": "video",
            "filesize": fmt.get("filesize") or fmt.get("filesize_approx"),
            "filesize_human": _human_size(fmt.get("filesize") or fmt.get("filesize_approx")),
            "vcodec": fmt.get("vcodec"),
            "acodec": fmt.get("acodec"),
            "height": height,
            "fps": fmt.get("fps"),
            "abr": fmt.get("abr"),
            "tbr": fmt.get("tbr"),
            "has_audio": True,
        })

    # Sort video entries by height descending
    results.sort(key=lambda f: -(f.get("height") or 0))

    # Add audio-only entries (for the Audio Only tab)
    seen_abr = set()
    for afmt in sorted(audio_only, key=lambda f: -(f.get("abr") or f.get("tbr") or 0)):
        abr = int(afmt.get("abr") or afmt.get("tbr") or 0)
        if abr in seen_abr:
            continue
        seen_abr.add(abr)
        results.append({
            "format_id": afmt.get("format_id"),
            "ext": afmt.get("ext", "m4a"),
            "quality_label": _quality_label(afmt),
            "type": "audio",
            "filesize": afmt.get("filesize") or afmt.get("filesize_approx"),
            "filesize_human": _human_size(afmt.get("filesize") or afmt.get("filesize_approx")),
            "vcodec": None,
            "acodec": afmt.get("acodec"),
            "height": None,
            "fps": None,
            "abr": afmt.get("abr"),
            "tbr": afmt.get("tbr"),
            "has_audio": True,
        })

    # Fallback: if nothing worked, return a single best-quality entry
    if not results:
        results.append({
            "format_id": "bestvideo+bestaudio/best",
            "ext": "mp4",
            "quality_label": "Best Quality",
            "type": "video",
            "filesize": None,
            "filesize_human": None,
            "vcodec": None,
            "acodec": None,
            "height": None,
            "fps": None,
            "abr": None,
            "tbr": None,
            "has_audio": True,
        })

    return results


def _get_cookie_opts() -> dict:
    """Return cookie options for the local browser selected by Windows mode."""
    browser = os.getenv("COOKIES_BROWSER", "").strip().lower()
    if browser and browser != "auto":
        return {"cookiesfrombrowser": (browser, None, None, None)}
    if browser == "auto":
        return {"cookiesfrombrowser": ("brave", None, None, None)}
    return {}


def _browser_cookie_options() -> list[dict]:
    """List local browser cookie options when host mode requests auto-detection."""
    if os.getenv("COOKIES_BROWSER", "").strip().lower() != "auto":
        return []
    return [
        {"cookiesfrombrowser": (browser, None, None, None)}
        for browser in ("brave", "chrome", "edge", "firefox")
    ]


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
    opts.update(_get_cookie_opts())
    return opts


def extract_media_info(url: str) -> dict:
    """
    Extract media metadata and available formats from a URL.
    Returns a normalized dict ready to send to the frontend.
    """
    platform = detect_platform(url)

    options = [_ydl_opts_info(), *_browser_cookie_options()]
    last_error = None
    for cookie_opts in options:
        opts = _ydl_opts_info()
        opts.update(cookie_opts)
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                break
            except yt_dlp.utils.DownloadError as error:
                last_error = error
                info = None
    else:
        if last_error:
            raise ValueError(str(last_error)) from last_error
        raise ValueError("Could not extract media info from this URL.")

    if info is None:
        raise ValueError("Could not extract media info from this URL.")

    if info.get("_type") == "playlist":
        entries = info.get("entries") or []
        if not entries:
            raise ValueError("Playlist is empty.")
        info = entries[0]

    raw_formats = info.get("formats") or []
    formats = normalize_formats(raw_formats)

    if not formats and info.get("url"):
        formats = [{
            "format_id": "bestvideo+bestaudio/best",
            "ext": "mp4",
            "quality_label": "Best Quality",
            "type": "video",
            "filesize": None,
            "filesize_human": None,
            "vcodec": None,
            "acodec": None,
            "height": None,
            "fps": None,
            "abr": None,
            "tbr": None,
            "has_audio": True,
        }]

    thumbnails = info.get("thumbnails") or []
    thumbnail = None
    if thumbnails:
        sorted_thumbs = sorted(
            thumbnails,
            key=lambda t: (t.get("width") or 0) * (t.get("height") or 0),
            reverse=True,
        )
        thumbnail = sorted_thumbs[0].get("url")
    if not thumbnail:
        thumbnail = info.get("thumbnail")

    duration = info.get("duration")
    duration_str = None
    if duration:
        mins, secs = divmod(int(duration), 60)
        hrs, mins = divmod(mins, 60)
        if hrs:
            duration_str = f"{hrs}:{mins:02d}:{secs:02d}"
        else:
            duration_str = f"{mins}:{secs:02d}"

    return {
        "title": info.get("title") or "Untitled",
        "thumbnail": thumbnail,
        "duration": duration_str,
        "uploader": info.get("uploader") or info.get("channel"),
        "platform": platform,
        "original_url": url,
        "formats": formats,
        "webpage_url": info.get("webpage_url") or url,
    }


TMP_BASE = Path(os.getenv("TMP_DIR", "/tmp/omnipull"))


def get_download_dir(file_id: str) -> Path:
    d = TMP_BASE / file_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def download_media(url: str, format_id: str, file_id: str, progress_callback=None) -> dict:
    """
    Download and merge selected video and audio streams.
    format_id can be:
      - "137+140"  (video+audio merge, from our normalize_formats)
      - "bestvideo+bestaudio/best"  (fallback)
      - a plain audio format_id for audio-only downloads
    """
    out_dir = get_download_dir(file_id)
    outtmpl = str(out_dir / "%(title)s.%(ext)s")

    # Use exactly what was requested - format_ids already have +audio baked in
    # from normalize_formats. For safety, fall back to best if empty.
    fmt = format_id if format_id else "bestvideo+bestaudio/best"

    ydl_opts = {
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
    if progress_callback:
        ydl_opts["progress_hooks"] = [progress_callback]

    cookie_options = [_get_cookie_opts(), *_browser_cookie_options()]
    last_error = None
    for cookie_opts in cookie_options:
        options = dict(ydl_opts)
        options.update(cookie_opts)
        with yt_dlp.YoutubeDL(options) as ydl:
            try:
                ydl.download([url])
                break
            except yt_dlp.utils.DownloadError as error:
                last_error = error
    else:
        if last_error:
            raise ValueError(str(last_error)) from last_error
        raise ValueError("Could not download this URL.")

    # Find the downloaded file (exclude .part files)
    files = [f for f in out_dir.iterdir() if not f.suffix == ".part" and not f.name.endswith(".json")]
    if not files:
        raise ValueError("Download completed but no file was found.")

    # Prefer .mp4 if multiple files
    mp4_files = [f for f in files if f.suffix == ".mp4"]
    filepath = mp4_files[0] if mp4_files else files[0]
    size_bytes = filepath.stat().st_size

    return {
        "file_id": file_id,
        "filename": filepath.name,
        "filepath": str(filepath),
        "size_human": _human_size(size_bytes),
        "size_bytes": size_bytes,
    }


# --- Instaloader fallback -----------------------------------------------------

def extract_instagram_instaloader(url: str, file_id: str) -> dict:
    """
    Fallback for Instagram using instaloader when yt-dlp fails.
    Handles single posts, carousels, and reels.
    """
    try:
        import instaloader
    except ImportError:
        raise ValueError("instaloader is not installed.")

    shortcode_match = re.search(
        r"instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)", url
    )
    if not shortcode_match:
        raise ValueError("Could not extract Instagram shortcode from URL.")

    shortcode = shortcode_match.group(1)
    out_dir = get_download_dir(file_id)

    L = instaloader.Instaloader(
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        post_metadata_txt_pattern="",
        dirname_pattern=str(out_dir),
        filename_pattern="{shortcode}_{mediaid}",
        quiet=True,
    )

    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        L.download_post(post, target=out_dir)
    except Exception as e:
        raise ValueError(f"Instagram download failed: {e}") from e

    media_files = [
        f for f in out_dir.iterdir()
        if f.suffix.lower() in (".mp4", ".jpg", ".jpeg", ".png", ".webp")
    ]

    if not media_files:
        raise ValueError("No media files downloaded from Instagram.")

    if len(media_files) > 1:
        zip_path = out_dir / f"{shortcode}_carousel.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for mf in sorted(media_files):
                zf.write(mf, mf.name)
        return {
            "file_id": file_id,
            "filename": zip_path.name,
            "filepath": str(zip_path),
            "size_human": _human_size(zip_path.stat().st_size),
            "size_bytes": zip_path.stat().st_size,
        }

    filepath = media_files[0]
    return {
        "file_id": file_id,
        "filename": filepath.name,
        "filepath": str(filepath),
        "size_human": _human_size(filepath.stat().st_size),
        "size_bytes": filepath.stat().st_size,
    }
