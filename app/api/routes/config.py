from fastapi import APIRouter

from app.config_store import default_output_dir, load_config, save_config
from app.schemas import ConfigResponse, ConfigUpdateRequest, OkResponse


router = APIRouter()


@router.get("/config", response_model=ConfigResponse)
def get_config():
    cfg = load_config()
    if "output_dir" not in cfg:
        cfg["output_dir"] = default_output_dir()
    if "output_mode" not in cfg:
        cfg["output_mode"] = "default"
    if "preview_seconds" not in cfg:
        cfg["preview_seconds"] = 30
    if "subtitle_position" not in cfg:
        cfg["subtitle_position"] = "middle"
    if "subtitle_language" not in cfg:
        cfg["subtitle_language"] = "id"
    if "deps_verbose" not in cfg:
        cfg["deps_verbose"] = False

    gemini_key = cfg.get("gemini_api_key")
    cfg["has_gemini_key"] = bool(gemini_key)
    cfg.pop("gemini_api_key", None)
    return cfg


@router.post("/config", response_model=OkResponse)
def set_config(data: ConfigUpdateRequest):
    cfg = load_config()
    patch = data.model_dump(exclude_unset=True)
    if "gemini_api_key" in patch and not patch.get("gemini_api_key"):
        patch.pop("gemini_api_key", None)
    for k, v in patch.items():
        cfg[k] = v
    save_config(cfg)
    return {"ok": True}
