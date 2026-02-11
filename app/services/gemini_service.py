import google.generativeai as genai
import logging
import json

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

    try:
        genai.configure(api_key=api_key)
        # Gunakan model yang lebih baru (gemini-2.0-flash atau fallback ke yang ada)
        # Kita coba pake gemini-2.0-flash karena lebih cepat dan murah (biasanya gratis di tier tertentu)
        # Kalau error, user bisa ganti model di kode ini, tapi for now kita hardcode ke yang modern.
        model_name = 'gemini-2.0-flash' 
        try:
             model = genai.GenerativeModel(model_name)
        except:
             # Fallback ke flash latest kalo 2.0 belum rilis stable (jaga-jaga)
             model = genai.GenerativeModel('gemini-flash-latest')

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

        response = model.generate_content(prompt)
        
        # Bersihin response text dari markdown formatting ```json ... ```
        text_response = response.text.strip()
        if text_response.startswith("```json"):
            text_response = text_response[7:]
        if text_response.endswith("```"):
            text_response = text_response[:-3]
        
        return json.loads(text_response.strip())

    except Exception as e:
        logger.error(f"Gemini Error: {str(e)}")
        # Fallback error message yang ga bikin panic
        raise Exception(f"Duh, Gemini lagi ngambek atau ada error: {str(e)}")
