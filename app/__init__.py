import json
import os
import time
import traceback
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import router as api_router
from app.web.routes import router as pages_router


def create_app():
    app = FastAPI(title="YTClipper")

    base_dir = Path(__file__).resolve().parent.parent
    static_dir = base_dir / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.exception_handler(StarletteHTTPException)
    async def _http_exc_handler(request, exc):
        msg = str(exc.detail) if exc.detail is not None else "Error"
        return JSONResponse(status_code=int(exc.status_code), content={"ok": False, "error": msg})

    @app.exception_handler(RequestValidationError)
    async def _validation_exc_handler(request, exc):
        return JSONResponse(status_code=422, content={"ok": False, "error": "Request body tidak valid."})

    @app.exception_handler(Exception)
    async def _unhandled_exc_handler(request, exc):
        err_id = uuid.uuid4().hex[:10]
        try:
            log_path = os.environ.get("YTCLIPPER_SERVER_ERROR_LOG") or str(base_dir / "logs" / "server_errors.jsonl")
            log_dir = os.path.dirname(log_path)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            rec = {
                "ts": float(time.time()),
                "id": err_id,
                "method": getattr(request, "method", None),
                "path": str(getattr(getattr(request, "url", None), "path", "")),
                "query": str(getattr(getattr(request, "url", None), "query", "")),
                "client": str(getattr(getattr(request, "client", None), "host", "")),
                "err_type": type(exc).__name__,
                "err": str(exc),
                "traceback": traceback.format_exc(limit=30),
            }
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")
        except Exception:
            pass
        return JSONResponse(status_code=500, content={"ok": False, "error": f"Internal server error. (ref: {err_id})"})

    app.include_router(pages_router)
    app.include_router(api_router)
    return app


