import json
import os
import threading
import time
from pathlib import Path

from app.core.settings import Settings
from app.heatmap import ambil_most_replayed
from app.yt_info import extract_video_id


_HEATMAP_CACHE = {}
_HEATMAP_CACHE_LOCK = threading.Lock()


def _get_url(data):
    url = str((data or {}).get("url", "")).strip()
    if not url:
        raise ValueError("YouTube URL wajib diisi.")
    return url


def _heatmap_log_path(settings: Settings | None):
    if settings and settings.heatmap_log_path:
        return str(settings.heatmap_log_path)
    p = os.environ.get("YTCLIPPER_HEATMAP_LOG")
    if p:
        return str(p)
    base_dir = Path(__file__).resolve().parent.parent.parent
    return str(base_dir / "logs" / "heatmap.jsonl")


def _append_heatmap_log(rec, settings: Settings | None):
    try:
        path = _heatmap_log_path(settings)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")
    except Exception:
        pass


def _heatmap_cache_key(video_id, duration_seconds):
    try:
        dur = int(duration_seconds) if duration_seconds is not None else None
    except Exception:
        dur = None
    return (str(video_id), dur)


def _heatmap_cache_get(key, ttl_s):
    now = time.time()
    with _HEATMAP_CACHE_LOCK:
        it = _HEATMAP_CACHE.get(key)
        if not it:
            return None
        age = now - float(it.get("ts", 0) or 0)
        if age < 0 or age > ttl_s:
            _HEATMAP_CACHE.pop(key, None)
            return None
        out = dict(it)
        out["age_s"] = age
        return out


def _heatmap_cache_set(key, value):
    with _HEATMAP_CACHE_LOCK:
        _HEATMAP_CACHE[key] = value


def get_heatmap_segments(data, settings: Settings | None = None):
    url = _get_url(data)
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError("Link YouTube tidak valid.")

    duration_seconds = (data or {}).get("duration_seconds")
    debug = bool((data or {}).get("debug"))
    if settings is not None:
        debug = bool(debug or settings.heatmap_debug)
        ttl_s = int(settings.heatmap_cache_ttl_s)
        slow_ms = int(settings.heatmap_slow_ms)
    else:
        debug = bool(debug) or (str(os.environ.get("YTCLIPPER_HEATMAP_DEBUG", "") or "").strip() == "1")
        ttl_s = int(os.environ.get("YTCLIPPER_HEATMAP_CACHE_TTL_S", "900") or "900")
        slow_ms = int(os.environ.get("YTCLIPPER_HEATMAP_SLOW_MS", "2000") or "2000")

    cache_key = _heatmap_cache_key(video_id, duration_seconds)
    t0 = time.perf_counter()
    cached = _heatmap_cache_get(cache_key, ttl_s=ttl_s)
    if cached:
        resp = {"ok": True, "segments": cached.get("segments") or []}
        if debug:
            resp["_meta"] = {"cache": "hit", "cache_age_s": round(float(cached.get("age_s") or 0), 3), "video_id": str(video_id)}
        return resp

    diag = {}
    try:
        heatmap = ambil_most_replayed(video_id, duration_seconds=duration_seconds, diag=diag)
    except Exception as e:
        dt_ms = int((time.perf_counter() - t0) * 1000)
        rec = {
            "event": "heatmap.error",
            "video_id": str(video_id),
            "ms": dt_ms,
            "err": str(e),
            "duration_seconds": duration_seconds,
            "diag": diag,
        }
        _append_heatmap_log(rec, settings=settings)
        raise

    segs = []
    for it in heatmap:
        s = int(float(it.get("start", 0)))
        d = int(float(it.get("duration", 0)))
        if d <= 0:
            continue
        segs.append({"enabled": True, "start": s, "end": s + d, "score": float(it.get("score", 0))})
    segs.sort(key=lambda x: (-(x.get("score") or 0.0), x.get("start") or 0, x.get("end") or 0))

    dt_ms = int((time.perf_counter() - t0) * 1000)
    if segs:
        _heatmap_cache_set(cache_key, {"ts": time.time(), "segments": segs})

    if debug or dt_ms >= slow_ms:
        try:
            payload_bytes = len(json.dumps(segs, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        except Exception:
            payload_bytes = None
        rec = {
            "event": "heatmap.done",
            "video_id": str(video_id),
            "ms": dt_ms,
            "segments": len(segs),
            "duration_seconds": duration_seconds,
            "payload_bytes": payload_bytes,
            "cache": "miss",
        }
        if diag:
            rec["diag"] = diag
        _append_heatmap_log(rec, settings=settings)

    resp = {"ok": True, "segments": segs}
    if debug:
        resp["_meta"] = {"cache": "miss", "video_id": str(video_id), "ms": dt_ms}
        if diag:
            resp["_meta"]["diag"] = diag
    return resp
