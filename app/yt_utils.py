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
    u = re.sub(r"[`\s\"']*(https?://[^`\s\"']+)[`\s\"']*", r"\1", u)
    u = u.strip("` \t\r\n\"'")
    if not u:
        return ""
    m = re.search(r"(?:v=|/)([0-9A-Za-z_-]{11})(?:\?|&|/|$)", u)
    if m:
        video_id = m.group(1)
        return f"https://youtu.be/{video_id}"
    return u

def extract_youtube_video_id(url):
    u = str(url or "").strip()
    u = re.sub(r"[`\s\"']*(https?://[^`\s\"']+)[`\s\"']*", r"\1", u)
    u = u.strip("` \t\r\n\"'")
    m = re.search(r"(?:v=|/)([0-9A-Za-z_-]{11})(?:\?|&|/|$)", u)
    if m:
        return m.group(1)
    if _YOUTUBE_ID_RE.match(u):
        return u
    return None

def get_cookies_path():
    env_path = os.environ.get("YTCLIPPER_COOKIES_PATH")
    if env_path and os.path.isfile(env_path): return env_path
    if os.path.isfile(DEFAULT_COOKIES_PATH): return DEFAULT_COOKIES_PATH
    if os.path.isfile("cookies.txt"): return "cookies.txt"
    return None

def get_yt_dlp_cookies_args():
    path = get_cookies_path()
    if path:
        try:
            tmp = os.path.join(tempfile.gettempdir(), "ytclipper_cookies.txt")
            shutil.copyfile(path, tmp)
            return ["--cookies", tmp]
        except Exception:
            return ["--cookies", path]
    browser = str(os.environ.get("YTCLIPPER_COOKIES_FROM_BROWSER") or "").strip()
    if browser: return ["--cookies-from-browser", browser]
    return []

def load_cookies_into_session(session):
    path = get_cookies_path()
    if not path: return
    try:
        cj = http.cookiejar.MozillaCookieJar(path)
        cj.load(ignore_discard=True, ignore_expires=True)
        session.cookies.update(cj)
    except Exception:
        pass
