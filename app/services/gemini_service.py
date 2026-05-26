import logging
import json

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

def generate_clip_metadata(transcript_text, api_key):
    """
    Generate saran judul dan caption untuk YouTube Shorts berdasarkan transkrip.
    
    Args:
        transcript_text (str): Teks transkrip dari clip.
        api_key (str): Gemini API Key.
        
    Returns:
        dict: {
            "title": "Judul yang disarankan",
            "caption": "Caption yang disarankan",
            "hashtags": ["#tag1", "#tag2"]
        }
    """
    if not api_key:
        raise ValueError("API Key Gemini belum diset. Cek settings, Bos!")

    if not transcript_text:
        raise ValueError("Transkrip kosong. Gimana mau mikir kalo ga ada bahannya?")

    prompt = f"""
    Kamu adalah asisten kreatif media sosial yang ahli dalam membuat konten viral untuk YouTube Shorts (Indonesia).

    Tugasmu:
    Buatlah 3 opsi JUDUL yang clickbait tapi relevan, dan 1 CAPTION yang engaging untuk video pendek berdasarkan transkrip berikut.
    Sertakan juga 5-7 HASHTAG yang relevan dan trending.

    Format output WAJIB JSON valid seperti ini:
    {{
        "titles": ["Judul 1", "Judul 2", "Judul 3"],
        "caption": "Isi caption yang menarik...",
        "hashtags": ["#tag1", "#tag2", "#tag3"]
    }}

    Transkrip Video:
    "{transcript_text}"
    """

    cfg = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema={
            "type": "OBJECT",
            "required": ["titles", "caption", "hashtags"],
            "properties": {
                "titles": {"type": "ARRAY", "items": {"type": "STRING"}},
                "caption": {"type": "STRING"},
                "hashtags": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
        },
    )

    client = genai.Client(api_key=api_key)
    last_err = None
    for model_name in ("gemini-2.0-flash", "gemini-flash-latest"):
        try:
            response = client.models.generate_content(model=model_name, contents=prompt, config=cfg)
            text_response = (response.text or "").strip()
            if text_response.startswith("```json"):
                text_response = text_response[7:]
            if text_response.endswith("```"):
                text_response = text_response[:-3]
            text_response = text_response.strip()
            if not text_response:
                raise ValueError("Response dari Gemini kosong.")
            return json.loads(text_response)
        except Exception as e:
            last_err = e

    logger.error(f"Gemini Error: {str(last_err)}")
    raise Exception(f"Duh, Gemini lagi ngambek atau ada error: {str(last_err)}")


def process_audio_with_gemini(audio_path, api_key):
    import time
    if not api_key:
        raise ValueError("API Key Gemini belum diset.")
    
    client = genai.Client(api_key=api_key)
    uploaded_file = None
    try:
        uploaded_file = client.files.upload(file=audio_path)
        
        while uploaded_file.state.name == "PROCESSING":
            time.sleep(2)
            uploaded_file = client.files.get(name=uploaded_file.name)
            
        if uploaded_file.state.name == "FAILED":
            raise ValueError("Gagal memproses audio di server Gemini.")
            
        prompt = """
        Dengarkan audio ini. Carikan SATU bagian berdurasi 30-60 detik yang merupakan highlight paling menarik, viral, penting, atau lucu dari keseluruhan audio.
        Format output WAJIB JSON valid:
        {
            "start": 12.5,
            "end": 45.0,
            "text": "Transkrip ringkas dari bagian tersebut..."
        }
        """
        
        cfg = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema={
                "type": "OBJECT",
                "required": ["start", "end", "text"],
                "properties": {
                    "start": {"type": "NUMBER"},
                    "end": {"type": "NUMBER"},
                    "text": {"type": "STRING"}
                }
            }
        )
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[uploaded_file, prompt],
            config=cfg
        )
        
        text_response = (response.text or "").strip()
        if text_response.startswith("```json"):
            text_response = text_response[7:]
        if text_response.endswith("```"):
            text_response = text_response[:-3]
        
        data = json.loads(text_response.strip())
        
        return [{
            "start": float(data.get("start", 0)),
            "end": float(data.get("end", 0)),
            "text": str(data.get("text", "")),
            "score": 1.0,
            "enabled": True
        }]
    except Exception as e:
        logger.error(f"Gemini Audio Error: {str(e)}")
        raise Exception(f"Gagal memproses audio dengan Gemini: {str(e)}")
    finally:
        if uploaded_file:
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception:
                pass
