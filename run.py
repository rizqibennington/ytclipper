import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from webapp import app


if __name__ == "__main__":
    debug = str(os.environ.get("FLASK_DEBUG", "1")).lower() not in ("0", "false", "no", "off")
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    print(f"🚀 Server running at http://{host}:{port}")
    print(f"🔥 Hot reload: {'ON' if debug else 'OFF'} (set FLASK_DEBUG=0 to disable)")
    app.run(host=host, port=port, debug=debug, use_reloader=debug)

