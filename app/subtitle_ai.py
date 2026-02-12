from app.core_constants import DEFAULT_WHISPER_MODEL


_WHISPER_MODEL = DEFAULT_WHISPER_MODEL
_FASTER_WHISPER_MODEL = None
_FASTER_WHISPER_MODEL_NAME = None


def set_whisper_model(name):
    global _WHISPER_MODEL
    if name is None:
        return
    name = str(name).strip()
    if not name:
        return
    _WHISPER_MODEL = name


def get_whisper_model():
    return _WHISPER_MODEL


def get_faster_whisper_model():
    global _FASTER_WHISPER_MODEL, _FASTER_WHISPER_MODEL_NAME

    if _FASTER_WHISPER_MODEL is not None and _FASTER_WHISPER_MODEL_NAME == _WHISPER_MODEL:
        return _FASTER_WHISPER_MODEL

    from faster_whisper import WhisperModel

    _FASTER_WHISPER_MODEL = WhisperModel(_WHISPER_MODEL, device="cpu", compute_type="int8")
    _FASTER_WHISPER_MODEL_NAME = _WHISPER_MODEL
    return _FASTER_WHISPER_MODEL


def format_timestamp(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_subtitle(video_file, subtitle_file):
    try:
        model = get_faster_whisper_model()
        segments, info = model.transcribe(video_file, language="id")

        with open(subtitle_file, "w", encoding="utf-8") as f:
            for i, segment in enumerate(segments, start=1):
                start_time = format_timestamp(segment.start)
                end_time = format_timestamp(segment.end)
                text = segment.text.strip()
                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{text}\n\n")

        return True
    except Exception:
        return False


def transcribe_timestamped_segments(audio_file, language="id"):
    model = get_faster_whisper_model()
    segments, info = model.transcribe(audio_file, language=language)
    out = []
    for s in segments:
        try:
            out.append({"start": float(s.start), "end": float(s.end), "text": str(s.text or "").strip()})
        except Exception:
            continue
    return out

