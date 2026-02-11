from flask import Blueprint, jsonify, request

from config_store import default_output_dir, load_config, save_config
from jobs import get_job
from app.services.api_service import get_ai_segments, get_heatmap_segments, get_video_info, open_output_folder, start_clip_job


api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.get("/config")
def api_get_config():
    cfg = load_config()
    if "output_dir" not in cfg:
        cfg["output_dir"] = default_output_dir()
    if "output_mode" not in cfg:
        cfg["output_mode"] = "default"
    if "preview_seconds" not in cfg:
        cfg["preview_seconds"] = 30
    if "subtitle_position" not in cfg:
        cfg["subtitle_position"] = "middle"
    if "deps_verbose" not in cfg:
        cfg["deps_verbose"] = False
    return jsonify(cfg)


@api_bp.post("/config")
def api_set_config():
    data = request.get_json(silent=True) or {}
    cfg = load_config()
    for k in (
        "output_mode",
        "output_dir",
        "crop_mode",
        "use_subtitle",
        "whisper_model",
        "subtitle_position",
        "preview_seconds",
        "deps_verbose",
    ):
        if k in data:
            cfg[k] = data[k]
    save_config(cfg)
    return jsonify({"ok": True})


@api_bp.post("/video_info")
def api_video_info():
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(get_video_info(data))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@api_bp.post("/heatmap")
def api_heatmap():
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(get_heatmap_segments(data))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@api_bp.post("/ai_segments")
def api_ai_segments():
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(get_ai_segments(data))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@api_bp.post("/start")
def api_start():
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(start_clip_job(data))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@api_bp.get("/status/<job_id>")
def api_status(job_id):
    job = get_job(job_id)
    if not job:
        return jsonify({"ok": False})
    logs = "".join(job.get("logs", [])[-2500:])
    return jsonify(
        {
            "ok": True,
            "running": bool(job.get("running", False)),
            "done": bool(job.get("done", False)),
            "percent": float(job.get("percent", 0.0)),
            "status": str(job.get("status", "")),
            "stage": str(job.get("stage", "")),
            "eta": str(job.get("eta", "")),
            "error": job.get("error"),
            "output_dir": job.get("output_dir"),
            "success_count": int(job.get("success_count", 0)),
            "logs": logs,
        }
    )


@api_bp.post("/open_output/<job_id>")
def api_open_output(job_id):
    try:
        return jsonify(open_output_folder(job_id))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})
