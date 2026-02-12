import os
import threading
import time
import subprocess
import sys
from urllib.parse import parse_qs, urlparse


_DURATION_CACHE = {}
_DURATION_CACHE_LOCK = threading.Lock()


def _duration_cache_ttl_s():
    raw = str((os.environ.get("YTCLIPPER_VIDEO_INFO_CACHE_TTL_S") or "21600")).strip()
    try:
        return max(0, int(raw))
    except Exception:
        return 21600


def extract_video_id(url):
    parsed = urlparse(url)

    if parsed.hostname in ("youtu.be", "www.youtu.be"):
        return parsed.path[1:]

    if parsed.hostname in ("youtube.com", "www.youtube.com"):
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        if parsed.path.startswith("/shorts/"):
            parts = parsed.path.split("/")
            if len(parts) >= 3:
                return parts[2]

    return None


def get_duration(video_id):
    ttl_s = _duration_cache_ttl_s()
    key = str(video_id)
    if ttl_s > 0:
        now = time.time()
        with _DURATION_CACHE_LOCK:
            it = _DURATION_CACHE.get(key)
            if it and (now - float(it.get("ts", 0) or 0)) <= ttl_s:
                try:
                    return int(it.get("duration"))
                except Exception:
                    _DURATION_CACHE.pop(key, None)

    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--quiet",
        "--no-warnings",
        "--no-playlist",
        "--force-ipv4",
        "--get-duration",
        f"https://youtu.be/{video_id}",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        time_parts = res.stdout.strip().split(":")

        duration = None
        if len(time_parts) == 2:
            duration = int(time_parts[0]) * 60 + int(time_parts[1])
        if len(time_parts) == 3:
            duration = int(time_parts[0]) * 3600 + int(time_parts[1]) * 60 + int(time_parts[2])

        if duration is not None and ttl_s > 0:
            with _DURATION_CACHE_LOCK:
                _DURATION_CACHE[key] = {"ts": float(time.time()), "duration": int(duration)}
        if duration is not None:
            return int(duration)
    except Exception:
        pass
    return 3600
