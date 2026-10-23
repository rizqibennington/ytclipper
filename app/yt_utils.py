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

def get_cookies_target_path() -> str:
    """Tentukan lokasi file cookies yang tepat untuk ditulis."""
    env_path = os.environ.get("YTCLIPPER_COOKIES_PATH")
    if env_path:
        return env_path

    # Jika berjalan di dalam Docker dengan volume /data
    if os.path.isdir("/data") and os.access("/data", os.W_OK):
        return DEFAULT_COOKIES_PATH

    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        return str(data_dir / "cookies.txt")
    except Exception:
        pass

    return str(base_dir / "cookies.txt")

def get_cookies_path():
    env_path = os.environ.get("YTCLIPPER_COOKIES_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path
    if os.path.isfile(DEFAULT_COOKIES_PATH):
        return DEFAULT_COOKIES_PATH

    base_dir = Path(__file__).resolve().parent.parent
    candidate_data = base_dir / "data" / "cookies.txt"
    if candidate_data.is_file():
        return str(candidate_data)

    candidate_root = base_dir / "cookies.txt"
    if candidate_root.is_file():
        return str(candidate_root)

    if os.path.isfile("cookies.txt"):
        return "cookies.txt"
    return None

def get_cookies_status() -> dict:
    path = get_cookies_path()
    if not path or not os.path.isfile(path):
        return {
            "installed": False,
            "path": None,
            "size_bytes": 0,
            "line_count": 0,
            "has_youtube_cookies": False,
            "error": None,
        }
    try:
        size = os.path.getsize(path)
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
            has_yt = any("youtube.com" in l or ".google.com" in l for l in lines)
        return {
            "installed": True,
            "path": path,
            "size_bytes": size,
            "line_count": len(lines),
            "has_youtube_cookies": has_yt,
            "error": None,
        }
    except Exception as e:
        return {
            "installed": True,
            "path": path,
            "size_bytes": 0,
            "line_count": 0,
            "has_youtube_cookies": False,
            "error": str(e),
        }

def save_cookies(content: str) -> str:
    content = str(content or "").strip()
    if not content:
        raise ValueError("Konten cookies kosong.")
    target = get_cookies_target_path()
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write(content + "\n")
    return target

def delete_cookies() -> bool:
    path = get_cookies_path()
    if path and os.path.isfile(path):
        try:
            os.remove(path)
            return True
        except Exception:
            return False
    return False

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

def get_yt_dlp_proxy_args():
    proxy = (
        os.environ.get("YTCLIPPER_PROXY")
        or os.environ.get("HTTPS_PROXY")
        or os.environ.get("HTTP_PROXY")
    )
    if proxy and str(proxy).strip():
        return ["--proxy", str(proxy).strip()]
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
