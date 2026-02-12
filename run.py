import uvicorn

from app.core.settings import get_settings


if __name__ == "__main__":
    settings = get_settings()
    debug = bool(settings.debug)
    host = str(settings.host)
    port = int(settings.port)
    print(f"🚀 Server running at http://{host}:{port}")
    print(f"🔥 Hot reload: {'ON' if debug else 'OFF'} (set DEBUG=0 to disable)")
    target = "app.main:app" if debug else "app.main:app"
    uvicorn.run(target, host=host, port=port, reload=debug)

