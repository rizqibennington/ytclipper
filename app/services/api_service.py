import uuid

from config_store import default_output_dir, load_config, save_config
from clipper import estimate_total_size_bytes
from heatmap import ambil_most_replayed
from jobs import create_job, start_job
from subtitle_ai import get_whisper_model
from yt_info import extract_video_id, get_duration


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
    duration_seconds = int(get_duration(video_id))
    return {"ok": True, "video_id": video_id, "duration_seconds": duration_seconds}


def get_heatmap_segments(data):
    url = _get_url(data)
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError("Link YouTube tidak valid.")

    heatmap = ambil_most_replayed(video_id)
    segs = []
    for it in heatmap:
        s = int(float(it.get("start", 0)))
        d = int(float(it.get("duration", 0)))
        if d <= 0:
            continue
        segs.append({"enabled": True, "start": s, "end": s + d, "score": float(it.get("score", 0))})
    if not segs:
        raise ValueError(
            "Heatmap tidak ditemukan untuk video ini. Bisa jadi videonya memang tidak punya Most Replayed, atau YouTube lagi ganti format halaman."
        )
    return {"ok": True, "segments": segs}


def _parse_segments(segments):
    if not isinstance(segments, list):
        raise ValueError("segments harus array.")

    cleaned = []
    for s in segments:
        if not isinstance(s, dict):
            continue
        enabled = bool(s.get("enabled", True))
        try:
            start = float(s.get("start", 0))
            end = float(s.get("end", 0))
        except Exception:
            raise ValueError("start/end harus angka.")
        cleaned.append({"enabled": enabled, "start": start, "end": end})

    enabled_segments = [s for s in cleaned if s.get("enabled", True)]
    if not enabled_segments:
        raise ValueError("Minimal 1 segmen harus aktif.")

    total_sec = 0
    for s in enabled_segments:
        if s["start"] < 0 or s["end"] < 0:
            raise ValueError("Durasi tidak boleh negatif.")
        if s["end"] <= s["start"]:
            raise ValueError("End harus lebih besar dari Start.")
        total_sec += int(max(0, s["end"] - s["start"]))

    return cleaned, enabled_segments, total_sec


def start_clip_job(data):
    data = data or {}

    url = _get_url(data)
    crop_mode = str(data.get("crop_mode", "default")).strip() or "default"
    use_subtitle = bool(data.get("use_subtitle", False))
    whisper_model = str(data.get("whisper_model", get_whisper_model())).strip() or get_whisper_model()

    subtitle_position = str(data.get("subtitle_position", "middle")).strip().lower() or "middle"
    if subtitle_position not in ("bottom", "middle", "top"):
        subtitle_position = "middle"

    output_dir = data.get("output_dir")
    if output_dir is None or str(output_dir).strip() == "":
        output_dir = default_output_dir()
    else:
        output_dir = str(output_dir).strip()

    cleaned, enabled_segments, total_sec = _parse_segments(data.get("segments", []))
    est_bytes = estimate_total_size_bytes(total_sec)

    job_id = uuid.uuid4().hex
    create_job(job_id, output_dir=output_dir)

    payload = {
        "url": url,
        "segments": cleaned,
        "crop_mode": crop_mode if crop_mode in ("default", "split_left", "split_right") else "default",
        "use_subtitle": use_subtitle,
        "whisper_model": whisper_model,
        "subtitle_position": subtitle_position,
        "output_dir": output_dir,
        "apply_padding": False,
        "total_clips": len(enabled_segments),
    }

    start_job(job_id, payload)

    cfg = load_config()
    cfg["output_dir"] = output_dir
    cfg["output_mode"] = "custom" if data.get("output_dir") else "default"
    cfg["crop_mode"] = payload["crop_mode"]
    cfg["use_subtitle"] = use_subtitle
    cfg["whisper_model"] = whisper_model
    cfg["subtitle_position"] = subtitle_position
    save_config(cfg)

    return {"ok": True, "job_id": job_id, "estimated_bytes": est_bytes}

