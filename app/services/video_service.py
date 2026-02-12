import json
import os
import time
from pathlib import Path

from app.yt_info import extract_video_id, get_duration


def _heatmap_log_path():
    p = os.environ.get("YTCLIPPER_HEATMAP_LOG")
    if p:
        return str(p)
    base_dir = Path(__file__).resolve().parent.parent.parent
    return str(base_dir / "logs" / "heatmap.jsonl")


def _append_heatmap_log(rec):
    try:
        path = _heatmap_log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")
    except Exception:
        pass


def _get_url(data):
    url = str((data or {}).get("url", "")).strip()
    if not url:
        raise ValueError("YouTube URL wajib diisi.")
    return url


def get_video_info(data):
    url = _get_url(data)
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError("Link YouTube tidak valid.")

    t0 = time.perf_counter()
    duration_seconds = int(get_duration(video_id))
    dt_ms = int((time.perf_counter() - t0) * 1000)
    if dt_ms >= 800:
        _append_heatmap_log({"event": "video_info.done", "video_id": str(video_id), "ms": dt_ms, "duration_seconds": int(duration_seconds)})
    return {"ok": True, "video_id": video_id, "duration_seconds": duration_seconds}
