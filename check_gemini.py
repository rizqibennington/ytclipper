import os
from dotenv import load_dotenv

from google import genai
from google.genai import types

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
base_url = os.environ.get("GEMINI_BASE_URL")
proxy = os.environ.get("GEMINI_PROXY") or os.environ.get("HTTPS_PROXY")

if not api_key:
    print("API Key not found")
else:
    try:
        http_options_kwargs = {}
        if base_url:
            http_options_kwargs["base_url"] = base_url.strip().rstrip("/")
        if proxy:
            http_options_kwargs["client_args"] = {"proxy": proxy.strip()}
            http_options_kwargs["async_client_args"] = {"proxy": proxy.strip()}

        http_options = types.HttpOptions(**http_options_kwargs) if http_options_kwargs else None
        client = genai.Client(api_key=api_key, http_options=http_options)
        print("Listing models...")
        for m in client.models.list():
            name = getattr(m, "name", None)
            print(name if name else str(m))
    except Exception as e:
        print(f"Error: {e}")
