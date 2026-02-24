import os
import re
import subprocess
import tempfile

from app.core_constants import DEFAULT_WHISPER_MODEL


_WHISPER_MODEL = DEFAULT_WHISPER_MODEL
_FASTER_WHISPER_MODEL = None
_FASTER_WHISPER_MODEL_KEY = None


def _env_bool(name, default=False):
    v = os.environ.get(name)
    if v is None:
        return bool(default)
    return str(v).strip().lower() not in ("0", "false", "no", "off", "")


def _env_int(name, default):
    v = os.environ.get(name)
    if v is None:
        return int(default)
    try:
        return int(str(v).strip())
    except Exception:
        return int(default)


def _env_float(name, default):
    v = os.environ.get(name)
    if v is None:
        return float(default)
    try:
        return float(str(v).strip())
    except Exception:
        return float(default)


def _env_str(name, default=None):
    v = os.environ.get(name)
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


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
    global _FASTER_WHISPER_MODEL, _FASTER_WHISPER_MODEL_KEY

    device = _env_str("YTCLIPPER_WHISPER_DEVICE", "cpu")
    compute_type = _env_str("YTCLIPPER_WHISPER_COMPUTE_TYPE", "int8")
    key = (str(_WHISPER_MODEL), str(device), str(compute_type))

    if _FASTER_WHISPER_MODEL is not None and _FASTER_WHISPER_MODEL_KEY == key:
        return _FASTER_WHISPER_MODEL

    from faster_whisper import WhisperModel

    _FASTER_WHISPER_MODEL = WhisperModel(_WHISPER_MODEL, device=device, compute_type=compute_type)
    _FASTER_WHISPER_MODEL_KEY = key
    return _FASTER_WHISPER_MODEL


def _run_ffmpeg(cmd):
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return
    except subprocess.CalledProcessError as e:
        err = (e.stderr or "").strip() or (e.stdout or "").strip()
        raise ValueError("FFmpeg gagal saat preprocessing audio." + (f"\n\nDetail: {err}" if err else ""))


def _preprocess_audio(input_path: str, tmpdir: tempfile.TemporaryDirectory) -> str:
    out_wav = os.path.join(tmpdir.name, "audio.wav")

    audio_filter = _env_str("YTCLIPPER_ASR_AUDIO_FILTER")
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(input_path),
        "-map",
        "0:a:0?",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
    ]
    if audio_filter:
        cmd += ["-af", audio_filter]
    cmd.append(out_wav)

    _run_ffmpeg(cmd)
    if not os.path.exists(out_wav):
        raise ValueError("Preprocessing audio gagal (file output tidak ditemukan).")
    return out_wav


def _resolve_language(language):
    lang = (language if language is not None else _env_str("YTCLIPPER_ASR_LANGUAGE", "id"))
    if lang is None:
        return None
    lang = str(lang).strip().lower()
    if not lang or lang == "auto":
        return None
    return lang


def _transcribe(model, audio_path: str, language=None, word_timestamps=None):
    task = _env_str("YTCLIPPER_ASR_TASK", "transcribe")
    beam_size = _env_int("YTCLIPPER_ASR_BEAM_SIZE", 5)
    best_of = _env_int("YTCLIPPER_ASR_BEST_OF", 5)
    patience = _env_float("YTCLIPPER_ASR_PATIENCE", 1.0)
    temperature = _env_float("YTCLIPPER_ASR_TEMPERATURE", 0.0)
    compression_ratio_threshold = _env_float("YTCLIPPER_ASR_COMPRESSION_RATIO_THRESHOLD", 2.4)
    log_prob_threshold = _env_float("YTCLIPPER_ASR_LOG_PROB_THRESHOLD", -1.0)
    no_speech_threshold = _env_float("YTCLIPPER_ASR_NO_SPEECH_THRESHOLD", 0.6)
    condition_on_previous_text = _env_bool("YTCLIPPER_ASR_CONDITION_ON_PREVIOUS_TEXT", True)
    initial_prompt = _env_str("YTCLIPPER_ASR_INITIAL_PROMPT")

    vad_filter = _env_bool("YTCLIPPER_ASR_VAD_FILTER", True)
    vad_min_silence_ms = _env_int("YTCLIPPER_ASR_VAD_MIN_SILENCE_MS", 300)
    vad_speech_pad_ms = _env_int("YTCLIPPER_ASR_VAD_SPEECH_PAD_MS", 200)

    if word_timestamps is None:
        word_timestamps = _env_bool("YTCLIPPER_ASR_WORD_TIMESTAMPS", False)

    segments, info = model.transcribe(
        audio_path,
        language=_resolve_language(language),
        task=str(task),
        beam_size=int(max(1, beam_size)),
        best_of=int(max(1, best_of)),
        patience=float(max(0.1, patience)),
        temperature=float(max(0.0, temperature)),
        compression_ratio_threshold=float(compression_ratio_threshold),
        log_prob_threshold=float(log_prob_threshold),
        no_speech_threshold=float(no_speech_threshold),
        condition_on_previous_text=bool(condition_on_previous_text),
        initial_prompt=initial_prompt,
        vad_filter=bool(vad_filter),
        vad_parameters={"min_silence_duration_ms": int(max(0, vad_min_silence_ms)), "speech_pad_ms": int(max(0, vad_speech_pad_ms))},
        word_timestamps=bool(word_timestamps),
    )
    return segments, info


def format_timestamp(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_subtitle(video_file, subtitle_file, language=None):
    try:
        model = get_faster_whisper_model()

        with tempfile.TemporaryDirectory(prefix="ytclipper_asr_") as tmp:
            tmpdir = tempfile.TemporaryDirectory(dir=tmp)
            try:
                wav = _preprocess_audio(video_file, tmpdir)
                segments, info = _transcribe(model, wav, language=language, word_timestamps=None)
            finally:
                try:
                    tmpdir.cleanup()
                except Exception:
                    pass

        pad_ms = _env_int("YTCLIPPER_SRT_PAD_MS", 0)
        pad_s = max(0.0, float(pad_ms) / 1000.0)
        min_seg_ms = _env_int("YTCLIPPER_SRT_MIN_SEG_MS", 200)
        min_seg_s = max(0.0, float(min_seg_ms) / 1000.0)

        prev_end = 0.0
        idx = 0

        with open(subtitle_file, "w", encoding="utf-8") as f:
            for segment in segments:
                text = str(getattr(segment, "text", "") or "").strip()
                if not text:
                    continue

                st = float(getattr(segment, "start", 0.0) or 0.0)
                en = float(getattr(segment, "end", st) or st)
                words = getattr(segment, "words", None)
                if words:
                    try:
                        w_st = [float(getattr(w, "start", None)) for w in words if getattr(w, "start", None) is not None]
                        w_en = [float(getattr(w, "end", None)) for w in words if getattr(w, "end", None) is not None]
                        if w_st and w_en:
                            st = min(w_st)
                            en = max(w_en)
                    except Exception:
                        pass

                st = max(0.0, st - pad_s)
                en = max(st, en + pad_s)
                if st < prev_end:
                    st = prev_end
                if en - st < min_seg_s:
                    en = st + min_seg_s
                if en <= st:
                    continue
                prev_end = en

                start_time = format_timestamp(st)
                end_time = format_timestamp(en)
                idx += 1
                f.write(f"{idx}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{text}\n\n")

        return True
    except Exception:
        return False


def transcribe_timestamped_segments(audio_file, language="id"):
    model = get_faster_whisper_model()
    with tempfile.TemporaryDirectory(prefix="ytclipper_asr_") as tmp:
        tmpdir = tempfile.TemporaryDirectory(dir=tmp)
        try:
            wav = _preprocess_audio(audio_file, tmpdir)
            segments, info = _transcribe(model, wav, language=language, word_timestamps=False)
        finally:
            try:
                tmpdir.cleanup()
            except Exception:
                pass

    out = []
    for s in segments:
        try:
            out.append({"start": float(s.start), "end": float(s.end), "text": str(s.text or "").strip()})
        except Exception:
            continue
    return out


def _norm_words(text: str) -> list[str]:
    s = (text or "").lower()
    s = re.sub(r"\s+", " ", s).strip()
    return re.findall(r"[0-9a-zà-ÿ]+", s)


def wer(reference: str, hypothesis: str) -> float:
    ref = _norm_words(reference)
    hyp = _norm_words(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0

    dp = list(range(len(hyp) + 1))
    for i in range(1, len(ref) + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, len(hyp) + 1):
            cur = dp[j]
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + cost)
            prev = cur

    return float(dp[-1]) / float(len(ref))


def match_percent(reference: str, hypothesis: str) -> float:
    return max(0.0, 1.0 - wer(reference, hypothesis)) * 100.0
