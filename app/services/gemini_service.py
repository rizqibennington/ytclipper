import logging
import json
import os

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


def get_gemini_client(api_key: str) -> genai.Client:
    """Menginisialisasi Gemini Client dengan opsi proxy/base_url jika tersedia di environment."""
    http_options_kwargs = {}

    base_url = os.environ.get("GEMINI_BASE_URL")
    if base_url:
        http_options_kwargs["base_url"] = base_url.strip().rstrip("/")

    proxy = os.environ.get("GEMINI_PROXY") or os.environ.get("HTTPS_PROXY")
    if proxy:
        http_options_kwargs["client_args"] = {"proxy": proxy.strip()}
        http_options_kwargs["async_client_args"] = {"proxy": proxy.strip()}

    if http_options_kwargs:
        return genai.Client(api_key=api_key, http_options=types.HttpOptions(**http_options_kwargs))
    return genai.Client(api_key=api_key)


def generate_clip_metadata(transcript_text, api_key):
    """
    Generate saran judul dan caption untuk YouTube Shorts berdasarkan transkrip.
    
    Args:
        transcript_text (str): Teks transkrip dari clip.
        api_key (str): Gemini API Key.
        
    Returns:
        dict: {
            "titles": ["Judul 1", "Judul 2", "Judul 3"],
            "caption": "Caption yang disarankan",
            "hashtags": ["#tag1", "#tag2"]
        }
    """
    if not api_key:
        raise ValueError("API Key Gemini belum diset. Cek settings, Bos!")

    if not transcript_text:
        raise ValueError("Transkrip kosong. Gimana mau mikir kalo ga ada bahannya?")

    prompt = f"""
    Kamu adalah asisten kreatif media sosial yang ahli dalam membuat konten viral untuk YouTube Shorts, Instagram Reels, dan TikTok (Indonesia).

    Tugasmu:
    Buatlah 3 opsi JUDUL yang clickbait, berbobot, tapi tetap relevan (hook tinggi).
    Buatlah 1 CAPTION yang engaging untuk memancing komentar dan interaksi audiens.
    Sertakan juga 5-7 HASHTAG yang relevan dan trending untuk video pendek tersebut.

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

    client = get_gemini_client(api_key)
    last_err = None
    for model_name in ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"):
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
    
    client = get_gemini_client(api_key)
    uploaded_file = None
    try:
        uploaded_file = client.files.upload(file=audio_path)
        
        while uploaded_file.state.name == "PROCESSING":
            time.sleep(2)
            uploaded_file = client.files.get(name=uploaded_file.name)
            
        if uploaded_file.state.name == "FAILED":
            raise ValueError("Gagal memproses audio di server Gemini.")
            
        prompt = """
        Dengarkan audio ini dengan teliti. Carikan 3 sampai 5 bagian highlight (masing-masing berdurasi 30-60 detik) yang merupakan bagian paling menarik, penting, lucu, atau memiliki hook emosional kuat untuk YouTube Shorts / TikTok.
        Pastikan waktu start dan end tidak saling bertumpukan.
        Format output WAJIB JSON valid:
        {
            "highlights": [
                {
                    "start": 12.5,
                    "end": 52.0,
                    "text": "Transkrip ringkas atau inti bahasan di bagian ini...",
                    "score": 0.95
                }
            ]
        }
        """
        
        cfg = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema={
                "type": "OBJECT",
                "required": ["highlights"],
                "properties": {
                    "highlights": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "required": ["start", "end", "text"],
                            "properties": {
                                "start": {"type": "NUMBER"},
                                "end": {"type": "NUMBER"},
                                "text": {"type": "STRING"},
                                "score": {"type": "NUMBER"}
                            }
                        }
                    }
                }
            }
        )
        
        last_err = None
        for model_name in ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[uploaded_file, prompt],
                    config=cfg
                )
                
                text_response = (response.text or "").strip()
                if text_response.startswith("```json"):
                    text_response = text_response[7:]
                if text_response.endswith("```"):
                    text_response = text_response[:-3]
                
                parsed = json.loads(text_response.strip())
                items = parsed.get("highlights", []) if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else [])
                
                if not items and isinstance(parsed, dict) and "start" in parsed and "end" in parsed:
                    items = [parsed]
                
                results = []
                for idx, it in enumerate(items):
                    try:
                        st = float(it.get("start", 0))
                        en = float(it.get("end", 0))
                        if en <= st:
                            continue
                        if (en - st) < 15.0:
                            en = st + 35.0
                        tx = str(it.get("text", "")).strip()
                        sc = float(it.get("score", 1.0 - (idx * 0.05)))
                        results.append({
                            "start": int(round(st)),
                            "end": int(round(en)),
                            "text": tx,
                            "score": max(0.1, min(1.0, sc)),
                            "enabled": True
                        })
                    except Exception:
                        continue
                        
                if results:
                    results.sort(key=lambda x: x["start"])
                    return results
            except Exception as e:
                last_err = e
        
        if last_err:
            raise last_err
        raise ValueError("Tidak ada highlight yang terdeteksi oleh Gemini.")
    except Exception as e:
        logger.error(f"Gemini Audio Error: {str(e)}")
        raise Exception(f"Gagal memproses audio dengan Gemini: {str(e)}")
    finally:
        if uploaded_file:
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception:
                pass


def find_highlights_with_gemini_transcript(transcript_segments, api_key, duration_seconds=None, limit=5):
    """
    Menganalisis transkrip bertimestamp menggunakan model Gemini Flash untuk menemukan
    highlight segmen viral terbaik (30-60 detik) dengan hook kuat & punchline utuh.
    100% Gratis di tier free Google AI Studio, super cepat (1-2 detik).
    """
    if not api_key:
        raise ValueError("API Key Gemini belum diset.")
    if not transcript_segments:
        raise ValueError("Transkrip kosong.")

    lines = []
    for s in transcript_segments:
        st = float(s.get("start", 0) or 0)
        tx = str(s.get("text", "") or "").strip()
        if tx:
            m = int(st // 60)
            sec = int(st % 60)
            lines.append(f"[{m:02d}:{sec:02d}] {tx}")

    transcript_text = "\n".join(lines[:1200])
    dur_str = f"Durasi total video: {int(duration_seconds)} detik." if duration_seconds else ""

    prompt = f"""
    Kamu adalah Editor Video Shorts/TikTok profesional.
    {dur_str}
    
    Tugasmu:
    Analisis transkrip bertimestamp berikut, dan pilihlah {limit} bagian highlight terbaik untuk dipotong menjadi video pendek vertikal 9:16 (masing-masing berdurasi 30 sampai 60 detik).

    Kriteria Klip Berkualitas Tinggi:
    1. Hook Kuat: 3-5 detik pertama wajib memancing rasa penasaran, memicu emosi, atau mengangkat pertanyaan menarik.
    2. Alur Utuh: Jangan memotong di tengah kalimat. Klip harus memiliki awal, penjelasan/konflik, dan kesimpulan/punchline.
    3. Non-overlapping: Waktu start dan end antar highlight TIDAK BOLEH saling bertumpukan.
    4. Format Start dan End berupa angka detik.

    Format output WAJIB JSON valid:
    {{
        "highlights": [
            {{
                "start": 15,
                "end": 62,
                "reason": "Alasan klip ini menarik dan berpotensi viral...",
                "score": 0.95
            }}
        ]
    }}

    Transkrip Video:
    {transcript_text}
    """

    cfg = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema={
            "type": "OBJECT",
            "required": ["highlights"],
            "properties": {
                "highlights": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "required": ["start", "end"],
                        "properties": {
                            "start": {"type": "NUMBER"},
                            "end": {"type": "NUMBER"},
                            "reason": {"type": "STRING"},
                            "score": {"type": "NUMBER"},
                        },
                    },
                }
            },
        },
    )

    client = get_gemini_client(api_key)
    last_err = None
    for model_name in ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"):
        try:
            response = client.models.generate_content(model=model_name, contents=prompt, config=cfg)
            text_response = (response.text or "").strip()
            if text_response.startswith("```json"):
                text_response = text_response[7:]
            if text_response.endswith("```"):
                text_response = text_response[:-3]

            parsed = json.loads(text_response.strip())
            items = parsed.get("highlights", []) if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else [])

            results = []
            for it in items:
                try:
                    st = float(it.get("start", 0))
                    en = float(it.get("end", 0))
                    if en <= st:
                        continue
                    # Durasi Shorts wajib minimal 15 detik (optimal 30-60 detik)
                    if (en - st) < 15.0:
                        en = st + 35.0
                    if duration_seconds and en > float(duration_seconds):
                        en = float(duration_seconds)
                        if (en - st) < 15.0 and float(duration_seconds) >= 15.0:
                            st = max(0.0, en - 30.0)
                    sc = float(it.get("score", 0.9))
                    results.append({
                        "start": int(round(st)),
                        "end": int(round(en)),
                        "score": round(max(0.1, min(1.0, sc)), 2),
                        "enabled": True,
                    })
                except Exception:
                    continue

            if results:
                results.sort(key=lambda x: x["start"])
                return results
        except Exception as e:
            last_err = e

    if last_err:
        raise last_err
    raise ValueError("Tidak ada highlight yang terdeteksi.")
