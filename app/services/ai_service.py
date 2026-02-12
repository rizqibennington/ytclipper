import glob
import os
import re
import subprocess
import sys
import tempfile
import threading

from app.config_store import load_config
from app.core_constants import MAX_DURATION
from app.ffmpeg_deps import cek_dependensi
from app.subtitle_ai import set_whisper_model, transcribe_timestamped_segments
from app.yt_info import extract_video_id
from app.services.gemini_service import generate_clip_metadata


_AI_DEPS_READY = False
_AI_DEPS_LOCK = threading.Lock()


def _ensure_ai_deps():
    global _AI_DEPS_READY
    if _AI_DEPS_READY:
        return
    with _AI_DEPS_LOCK:
        if _AI_DEPS_READY:
            return
        cek_dependensi(install_whisper=True)
        _AI_DEPS_READY = True


def _download_audio_to_temp(url: str) -> tuple[str, tempfile.TemporaryDirectory]:
    tmpdir = tempfile.TemporaryDirectory(prefix="ytclipper_ai_")
    out_tpl = os.path.join(tmpdir.name, "audio.%(ext)s")

    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--force-ipv4",
        "--quiet",
        "--no-warnings",
        "--no-playlist",
        "-f",
        "bestaudio[ext=m4a]/bestaudio/best",
        "-o",
        out_tpl,
        str(url),
    ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except subprocess.CalledProcessError as e:
        err = (e.stderr or "").strip() or (e.stdout or "").strip()
        tmpdir.cleanup()
        raise ValueError("Gagal download audio untuk backup AI." + (f"\n\nDetail: {err}" if err else ""))

    hits = sorted(glob.glob(os.path.join(tmpdir.name, "audio.*")))
    audio_path = hits[0] if hits else None
    if not audio_path or not os.path.exists(audio_path):
        tmpdir.cleanup()
        raise ValueError("Gagal download audio untuk backup AI (file audio tidak ditemukan).")

    return audio_path, tmpdir


def _get_url(data):
    url = str((data or {}).get("url", "")).strip()
    if not url:
        raise ValueError("YouTube URL wajib diisi.")
    return url


def _word_tokens(text):
    return re.findall(r"[0-9A-Za-zÀ-ÿ]+", (text or "").lower())


def _build_ai_segments(transcript_segments, duration_seconds, limit=10):
    if not transcript_segments:
        return []

    try:
        dur_total = float(duration_seconds) if duration_seconds is not None else None
    except Exception:
        dur_total = None
    if dur_total is None:
        dur_total = max((float(s.get("end", 0) or 0) for s in transcript_segments), default=0.0)

    dur_total = max(0.0, float(dur_total))
    if dur_total <= 0:
        return []

    max_len = float(MAX_DURATION)
    duration_options = [20.0, 30.0, 45.0, 60.0, 90.0, 120.0, 179.0]

    keywords = {
        "intinya",
        "jadi",
        "pokoknya",
        "kesimpulannya",
        "serius",
        "gila",
        "parah",
        "wkwk",
        "haha",
        "anjir",
        "buset",
        "plot",
        "twist",
        "ending",
        "ternyata",
        "finally",
        "beneran",
        "nggak",
        "gak",
        "kok",
        "lah",
    }

    segs = []
    for s in transcript_segments:
        try:
            st = float(s.get("start", 0) or 0)
            en = float(s.get("end", st) or st)
            tx = str(s.get("text", "") or "")
        except Exception:
            continue
        if en <= st:
            continue

        toks = _word_tokens(tx)
        kw = sum(1 for t in toks if t in keywords)
        density = float(kw) / max(1.0, float(len(toks)))
        score = density + (0.25 if any(t in {"plot", "twist", "ending", "ternyata"} for t in toks) else 0.0)

        segs.append({"start": st, "end": en, "text": tx, "_score": score})

    if not segs:
        return []

    segs.sort(key=lambda x: (-(x.get("_score") or 0.0), x.get("start") or 0.0))

    out = []
    for it in segs:
        st = float(it["start"])
        en = float(it["end"])
        chosen_len = None
        for d in duration_options:
            if d <= max_len:
                chosen_len = float(d)
                break
        if chosen_len is None:
            chosen_len = min(60.0, max_len)

        if (en - st) > chosen_len:
            en = st + chosen_len
        if (en - st) > max_len:
            en = st + max_len
        if en <= st:
            continue

        out.append({"enabled": True, "start": int(max(0, round(st))), "end": int(max(round(st) + 1, round(en))), "score": float(it.get("_score") or 0.0)})
        if len(out) >= int(limit or 10):
            break

    max_score = max((p["score"] for p in out), default=1.0) or 1.0
    for p in out:
        p["score"] = float(p["score"] / max_score)
    return out


def get_ai_segments(data):
    data = data or {}
    url = _get_url(data)
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError("Link YouTube tidak valid.")

    language = str(data.get("language", "id") or "id")
    whisper_model = data.get("whisper_model")
    limit = int(data.get("limit", 10) or 10)
    duration_seconds = data.get("duration_seconds")

    try:
        _ensure_ai_deps()
        if whisper_model:
            set_whisper_model(whisper_model)
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Gagal menyiapkan dependency backup AI: {type(e).__name__}: {str(e)}")

    audio_path = None
    tmpdir = None
    try:
        audio_path, tmpdir = _download_audio_to_temp(url)
        try:
            transcript_segments = transcribe_timestamped_segments(audio_path, language=language)
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Gagal transcribe audio untuk backup AI: {type(e).__name__}: {str(e)}")
        segs = _build_ai_segments(transcript_segments, duration_seconds=duration_seconds, limit=limit)
        return {"ok": True, "segments": segs}
    finally:
        try:
            if tmpdir is not None:
                tmpdir.cleanup()
        except Exception:
            pass


def generate_ai_suggestions(data):
    text = (data or {}).get("text", "")
    if not text:
        raise ValueError("Teks transkrip kosong.")

    api_key = (data or {}).get("gemini_api_key")
    if not api_key:
        cfg = load_config()
        api_key = cfg.get("gemini_api_key")
    if not api_key:
        raise ValueError("Gemini API Key belum diset. Masukkan di Settings atau kirim langsung.")

    result = generate_clip_metadata(text, api_key)
    return {"ok": True, "data": result}
