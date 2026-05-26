import os
import http.cookiejar
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

DEFAULT_COOKIES_PATH = "/data/cookies.txt"
_YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def normalize_youtube_url(url):
    u = str(url or "").strip()
    u = re.sub(r"[`\\s\"']*(https?://[^`\\s\"']+)[`\\s\"']*", r"\1", u)
    u = u.strip("` \\t\\r\\n\"'")
    if not u:
        return ""
    parsed = urlparse(u)
    video_id = None
    if parsed.hostname in ("youtu.be", "www.youtu.be"):
        video_id = parsed.path.strip("/").split("/")[0]
    elif parsed.hostname in ("youtube.com", "www.youtube.com", "m.youtube.com"):
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [None])[0]
        elif parsed.path.startswith("/shorts/") or parsed.path.startswith("/embed/"):
            parts = [p for p in parsed.path.split("/") if p]
            if len(parts) >= 2:
                video_id = parts[1]
    elif _YOUTUBE_ID_RE.match(u):
        video_id = u
    if video_id:
        video_id = str(video_id).strip().strip("` \\t\\r\\n\"'")
        if _YOUTUBE_ID_RE.match(video_id):
            return f"https://youtu.be/{video_id}"
    return u


def extract_youtube_video_id(url):
    normalized = normalize_youtube_url(url)
    parsed = urlparse(normalized)
    if parsed.hostname in ("youtu.be", "www.youtu.be"):
        video_id = parsed.path.strip("/").split("/")[0]
        if _YOUTUBE_ID_RE.match(video_id or ""):
            return video_id
    return None

def get_cookies_path():
    """
    Returns the path to the cookies file if it exists, otherwise None.
    Checks env var YTCLIPPER_COOKIES_PATH first, then default location.
    """
    env_path = os.environ.get("YTCLIPPER_COOKIES_PATH")
    if env_path:
        if os.path.isfile(env_path):
            return env_path
        else:
            print(f"WARNING: YTCLIPPER_COOKIES_PATH set to {env_path} but file not found.")

    if os.path.isfile(DEFAULT_COOKIES_PATH):
        return DEFAULT_COOKIES_PATH
    else:
        # Debug: list files in /data to help troubleshoot
        data_dir = os.path.dirname(DEFAULT_COOKIES_PATH)
        if os.path.exists(data_dir):
            try:
                files = os.listdir(data_dir)
                print(f"DEBUG: Files in {data_dir}: {files}")
                if "cookies.txt" not in files:
                     print(f"WARNING: cookies.txt not found in {data_dir}")
            except Exception as e:
                print(f"WARNING: Could not list files in {data_dir}: {e}")
        else:
            print(f"WARNING: Directory {data_dir} does not exist.")
    
    # Check if we are in development mode on Windows (local test)
    # Assuming local dev might have cookies.txt in project root or similar
    local_dev_path = "cookies.txt"
    if os.path.isfile(local_dev_path):
        return local_dev_path
        
    return None

def get_yt_dlp_cookies_args():
    # Gunakan OAuth2 secara default, karena ini paling stabil di VPS / Datacenter.
    # Token akan dibaca dari cache (biasanya /data/.cache/yt-dlp)
    return ["--username", "oauth2", "--password", ""]

def load_cookies_into_session(session):
    """
    Loads Netscape-formatted cookies from the cookies file into a requests.Session.
    """
    path = get_cookies_path()
    if not path:
        return

    try:
        cj = http.cookiejar.MozillaCookieJar(path)
        cj.load(ignore_discard=True, ignore_expires=True)
        session.cookies.update(cj)
        print(f"INFO: Successfully loaded cookies from {path}")
    except Exception as e:
        print(f"WARNING: Failed to load cookies from {path}: {e}")
