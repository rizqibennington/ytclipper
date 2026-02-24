import os
import subprocess
import sys
import uuid

from app.clipper import estimate_total_size_bytes
from app.config_store import default_output_dir, load_config, save_config
from app.core_constants import MAX_DURATION
from app.jobs import append_job_log, create_job, get_job, start_job
from app.subtitle_ai import get_whisper_model


def _get_url(data):
    url = str((data or {}).get("url", "")).strip()
    if not url:
        raise ValueError("YouTube URL wajib diisi.")
    return url


def _parse_segments(segments):
    cleaned = []
    enabled_segments = []
    total_sec = 0
    warnings = []

    for raw in segments or []:
        if not isinstance(raw, dict):
            continue
        try:
            enabled = bool(raw.get("enabled", True))
            start = float(raw.get("start", 0) or 0)
            end = float(raw.get("end", 0) or 0)
        except Exception:
            continue
        s = {"enabled": enabled, "start": start, "end": end}
        cleaned.append(s)
        if enabled:
            enabled_segments.append(s)

    if not enabled_segments:
        raise ValueError("Pilih minimal 1 segmen.")

    for s in enabled_segments:
        if s["start"] < 0 or s["end"] < 0:
            raise ValueError("Durasi tidak boleh negatif.")
        if s["end"] <= s["start"]:
            raise ValueError("End harus lebih besar dari Start.")
        dur = float(s["end"] - s["start"])
        if dur > float(MAX_DURATION):
            new_end = float(s["start"]) + float(MAX_DURATION)
            warnings.append(
                {
                    "type": "trim",
                    "start": float(s["start"]),
                    "end_before": float(s["end"]),
                    "end_after": float(new_end),
                    "limit_s": int(MAX_DURATION),
                }
            )
            s["end"] = new_end
            dur = float(s["end"] - s["start"])
        total_sec += int(max(0, dur))

    return cleaned, enabled_segments, total_sec, warnings


def start_clip_job(data):
    data = data or {}

    url = _get_url(data)
    crop_mode = str(data.get("crop_mode", "default")).strip() or "default"
    use_subtitle = bool(data.get("use_subtitle", False))
    whisper_model = str(data.get("whisper_model", get_whisper_model())).strip() or get_whisper_model()

    subtitle_language = data.get("subtitle_language")
    if subtitle_language is None or str(subtitle_language).strip() == "":
        try:
            subtitle_language = str((load_config() or {}).get("subtitle_language") or "id")
        except Exception:
            subtitle_language = "id"
    subtitle_language = str(subtitle_language).strip().lower() or "id"
    if subtitle_language not in ("auto", "id", "en"):
        subtitle_language = "id"

    subtitle_position = str(data.get("subtitle_position", "middle")).strip().lower() or "middle"
    if subtitle_position not in ("bottom", "middle", "top"):
        subtitle_position = "middle"

    output_dir = data.get("output_dir")
    if output_dir is None or str(output_dir).strip() == "":
        output_dir = default_output_dir()
    else:
        output_dir = str(output_dir).strip()

    output_dir = normalize_output_dir(output_dir)
    try:
        os.makedirs(output_dir, exist_ok=True)
    except Exception as e:
        raise ValueError(f"Folder output tidak bisa dibuat/diakses: {output_dir}\n\nDetail: {type(e).__name__}: {str(e)}")

    cleaned, enabled_segments, total_sec, warnings = _parse_segments(data.get("segments", []))
    est_bytes = estimate_total_size_bytes(total_sec)

    job_id = uuid.uuid4().hex
    create_job(job_id, output_dir=output_dir)

    if warnings:
        append_job_log(job_id, "\n⏱️ Standar durasi: maksimal 03:00 (180 detik) per klip.\n")
        for w in warnings[:80]:
            try:
                append_job_log(
                    job_id,
                    f"⚠️ Durasi segmen melebihi batas, auto-trim end {w.get('end_before')} → {w.get('end_after')} (limit {w.get('limit_s')}s)\n",
                )
            except Exception:
                continue

    use_gemini_suggestions = bool(data.get("use_gemini_suggestions", False))
    gemini_api_key = None
    if use_gemini_suggestions:
        gemini_api_key = data.get("gemini_api_key")
        if not gemini_api_key:
            cfg_tmp = load_config()
            gemini_api_key = cfg_tmp.get("gemini_api_key")

    payload = {
        "url": url,
        "segments": cleaned,
        "crop_mode": crop_mode if crop_mode in ("default", "fit", "split_left", "split_right") else "default",
        "use_subtitle": use_subtitle,
        "whisper_model": whisper_model,
        "subtitle_language": subtitle_language,
        "subtitle_position": subtitle_position,
        "output_dir": output_dir,
        "apply_padding": False,
        "total_clips": len(enabled_segments),
        "gemini_api_key": gemini_api_key,
    }

    start_job(job_id, payload)

    cfg = load_config()
    cfg["output_dir"] = output_dir
    cfg["output_mode"] = "custom" if data.get("output_dir") else "default"
    cfg["crop_mode"] = payload["crop_mode"]
    cfg["use_subtitle"] = use_subtitle
    cfg["whisper_model"] = whisper_model
    cfg["subtitle_language"] = subtitle_language
    cfg["subtitle_position"] = subtitle_position
    cfg["use_gemini_suggestions"] = use_gemini_suggestions
    save_config(cfg)

    return {"ok": True, "job_id": job_id, "estimated_bytes": est_bytes}


def _open_folder(path):
    if not os.path.isdir(path):
        raise ValueError("Folder output tidak ditemukan di komputer ini.")

    if sys.platform.startswith("win"):
        try:
            os.startfile(path)
            return "os.startfile"
        except Exception:
            pass
        try:
            subprocess.Popen(["explorer", path])
            return "explorer"
        except Exception as e:
            raise ValueError("Gagal membuka folder di Windows: " + str(e))
    if sys.platform == "darwin":
        subprocess.Popen(["open", path])
        return "open"
    subprocess.Popen(["xdg-open", path])
    return "xdg-open"


def normalize_output_dir(path: str) -> str:
    p = str(path or "").strip()
    p = os.path.expandvars(os.path.expanduser(p))
    p = os.path.abspath(p)
    return p


def inspect_output_dir(path: str) -> dict:
    p = normalize_output_dir(path)
    if not p:
        return {"ok": False, "path": p, "error": "Output folder tidak tersedia."}
    if not os.path.isdir(p):
        return {"ok": False, "path": p, "error": f"Folder output tidak ditemukan: {p}"}
    try:
        os.listdir(p)
    except PermissionError:
        return {"ok": False, "path": p, "error": f"Tidak punya akses ke folder output: {p}"}
    except Exception as e:
        return {"ok": False, "path": p, "error": f"Folder output tidak bisa diakses: {p}\n\nDetail: {type(e).__name__}: {str(e)}"}
    return {"ok": True, "path": p, "error": None}


def open_output_folder(job_id):
    job = get_job(job_id)
    if not job:
        raise ValueError("Job tidak ditemukan.")

    output_dir = job.get("output_dir")
    if not output_dir:
        raise ValueError("Output folder tidak tersedia.")

    output_dir = str(output_dir)
    inspected = inspect_output_dir(output_dir)
    output_dir = inspected.get("path") or output_dir
    if not inspected.get("ok"):
        msg = str(inspected.get("error") or "Folder output tidak bisa diakses.")
        try:
            append_job_log(job_id, f"\n❌ {msg}\n")
        except Exception:
            pass
        raise ValueError(msg)

    append_job_log(job_id, f"\n📁 Membuka folder output: {output_dir}\n")
    try:
        method = _open_folder(output_dir)
        append_job_log(job_id, f"✅ Folder dibuka ({method}).\n")
        return {"ok": True, "output_dir": output_dir, "method": method}
    except Exception as e:
        append_job_log(job_id, f"❌ Gagal membuka folder: {type(e).__name__}: {str(e)}\n")
        raise
