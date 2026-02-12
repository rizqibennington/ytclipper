import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return bool(default)
    return str(v).strip().lower() not in ("0", "false", "no", "off", "")


class Settings(BaseModel):
    debug: bool = True
    host: str = "127.0.0.1"
    port: int = 5000

    heatmap_debug: bool = False
    heatmap_cache_ttl_s: int = 900
    heatmap_slow_ms: int = 2000

    heatmap_log_path: str | None = None


@lru_cache
def get_settings() -> Settings:
    load_dotenv()

    debug = _env_bool("DEBUG", default=None) if os.environ.get("DEBUG") is not None else None
    if debug is None:
        debug = _env_bool("UVICORN_RELOAD", default=None) if os.environ.get("UVICORN_RELOAD") is not None else None
    if debug is None:
        debug = _env_bool("FLASK_DEBUG", default=True)

    host = os.environ.get("HOST", "127.0.0.1")
    port_raw = os.environ.get("PORT", "5000")
    try:
        port = int(port_raw)
    except Exception:
        port = 5000

    heatmap_debug = _env_bool("YTCLIPPER_HEATMAP_DEBUG", default=False)

    ttl_raw = os.environ.get("YTCLIPPER_HEATMAP_CACHE_TTL_S", "900")
    try:
        ttl_s = int(ttl_raw)
    except Exception:
        ttl_s = 900

    slow_raw = os.environ.get("YTCLIPPER_HEATMAP_SLOW_MS", "2000")
    try:
        slow_ms = int(slow_raw)
    except Exception:
        slow_ms = 2000

    heatmap_log_path = os.environ.get("YTCLIPPER_HEATMAP_LOG")

    return Settings(
        debug=bool(debug),
        host=str(host),
        port=int(port),
        heatmap_debug=bool(heatmap_debug),
        heatmap_cache_ttl_s=int(ttl_s),
        heatmap_slow_ms=int(slow_ms),
        heatmap_log_path=str(heatmap_log_path) if heatmap_log_path else None,
    )

