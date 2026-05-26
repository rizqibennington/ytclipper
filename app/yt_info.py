import os
import threading
import time
import subprocess
import sys
from app.yt_utils import extract_youtube_video_id, get_yt_dlp_cookies_args


_DURATION_CACHE = {}
_DURATION_CACHE_LOCK = threading.Lock()


def _duration_cache_ttl_s():
    raw = str((os.environ.get("YTCLIPPER_VIDEO_INFO_CACHE_TTL_S") or "21600")).strip()
    try:
        return max(0, int(raw))
    except Exception:
        return 21600


def extract_video_id(url):
    return extract_youtube_video_id(url)


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
        "--extractor-args",
        "youtube:player_client=ios,android,web_creator",
    ] + get_yt_dlp_cookies_args() + [
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
