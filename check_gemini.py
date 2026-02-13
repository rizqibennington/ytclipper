import os
from dotenv import load_dotenv

from google import genai

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("API Key not found")
else:
    try:
        client = genai.Client(api_key=api_key)
        print("Listing models...")
        for m in client.models.list():
            name = getattr(m, "name", None)
            print(name if name else str(m))
    except Exception as e:
        print(f"Error: {e}")
