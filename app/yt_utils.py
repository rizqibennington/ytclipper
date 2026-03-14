import os
import http.cookiejar
from pathlib import Path

# Default path inside container (mapped to ./ytclip_data on host)
DEFAULT_COOKIES_PATH = "/data/cookies.txt"

def get_cookies_path():
    """
    Returns the path to the cookies file if it exists, otherwise None.
    Checks env var YTCLIPPER_COOKIES_PATH first, then default location.
    """
    env_path = os.environ.get("YTCLIPPER_COOKIES_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path
    
    if os.path.isfile(DEFAULT_COOKIES_PATH):
        return DEFAULT_COOKIES_PATH
    
    # Check if we are in development mode on Windows (local test)
    # Assuming local dev might have cookies.txt in project root or similar
    local_dev_path = "cookies.txt"
    if os.path.isfile(local_dev_path):
        return local_dev_path
        
    return None

def get_yt_dlp_cookies_args():
    """
    Returns a list of arguments for yt-dlp to use cookies if available.
    e.g. ['--cookies', '/path/to/cookies.txt'] or []
    """
    path = get_cookies_path()
    if path:
        return ["--cookies", path]
    return []

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
