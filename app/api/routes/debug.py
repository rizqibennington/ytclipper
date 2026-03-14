import os
from fastapi import APIRouter
from app.yt_utils import get_cookies_path

router = APIRouter(prefix="/debug", tags=["Debug"])

@router.get("/files")
def list_files():
    data_dir = "/data"
    files = []
    if os.path.exists(data_dir):
        try:
            files = os.listdir(data_dir)
        except Exception as e:
            files = [f"Error: {e}"]
    
    return {
        "data_dir_exists": os.path.exists(data_dir),
        "files_in_data": files,
        "cookies_path_detected": get_cookies_path(),
        "env_home": os.environ.get("HOME"),
        "cwd": os.getcwd()
    }
