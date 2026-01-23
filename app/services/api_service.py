import uuid

import os
import subprocess
import sys
import tempfile
import re

from config_store import default_output_dir, load_config, save_config
from clipper import estimate_total_size_bytes
from core_constants import MAX_DURATION
from ffmpeg_deps import cek_dependensi
from heatmap import ambil_most_replayed
from jobs import create_job, get_job, start_job
from subtitle_ai import get_whisper_model, set_whisper_model, transcribe_timestamped_segments
from yt_info import extract_video_id, get_duration


def _get_url(data):
    url = str((data or {}).get("url", "")).strip()
    if not url:
        raise ValueError("YouTube URL wajib diisi.")
    return url


def get_video_info(data):
    url = _get_url(data)
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError("Link YouTube tidak valid.")
    duration_seconds = int(get_duration(video_id))
    return {"ok": True, "video_id": video_id, "duration_seconds": duration_seconds}


def get_heatmap_segments(data):
    url = _get_url(data)
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError("Link YouTube tidak valid.")

    duration_seconds = (data or {}).get("duration_seconds")
    heatmap = ambil_most_replayed(video_id, duration_seconds=duration_seconds)
    segs = []
    for it in heatmap:
        s = int(float(it.get("start", 0)))
        d = int(float(it.get("duration", 0)))
        if d <= 0:
            continue
        segs.append({"enabled": True, "start": s, "end": s + d, "score": float(it.get("score", 0))})
    segs.sort(key=lambda x: (-(x.get("score") or 0.0), x.get("start") or 0, x.get("end") or 0))
    if not segs:
        raise ValueError(
            "Tidak ada data auto-segmen untuk video ini.\n"
            "- Kemungkinan video tidak punya Most Replayed.\n"
            "- Kalau video ada Chapters, pastikan videonya memang punya chapter dan coba lagi.\n"
            "- Kalau sering gagal di banyak video: YouTube mungkin lagi ubah format halaman (coba beberapa menit lagi).\n"
            "Kamu tetap bisa bikin segmen manual (Start/End) lalu klik Add."
        )
    return {"ok": True, "segments": segs}


def _download_audio_to(video_id, out_dir):
    cek_dependensi(install_whisper=True)
    url = f"https://youtu.be/{video_id}"

    out_tpl = os.path.join(str(out_dir), "audio.%(ext)s")
    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--force-ipv4",
        "--quiet",
        "--no-warnings",
        "-f",
        "bestaudio[ext=m4a]/bestaudio/best",
        "-o",
        out_tpl,
        url,
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)
    files = [os.path.join(str(out_dir), f) for f in os.listdir(str(out_dir)) if f.startswith("audio.")]
    if not files:
        raise ValueError("Gagal download audio untuk analisis.")
    return files[0]


def _download_captions_vtt_to(video_id, out_dir, sub_langs):
    url = f"https://youtu.be/{video_id}"
    langs = []
    for it in (sub_langs or []):
        it = str(it or "").strip()
        if it:
            langs.append(it)
    if not langs:
        langs = ["id", "en"]

    out_tpl = os.path.join(str(out_dir), "video.%(ext)s")
    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--force-ipv4",
        "--quiet",
        "--no-warnings",
        "--skip-download",
        "--write-auto-subs",
        "--sub-format",
        "vtt",
        "--sub-lang",
        ",".join(langs),
        "-o",
        out_tpl,
        url,
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=False)

    files = [os.path.join(str(out_dir), f) for f in os.listdir(str(out_dir)) if f.lower().endswith(".vtt")]
    if not files:
        return None

    def pref_key(p):
        name = os.path.basename(p).lower()
        for i, lang in enumerate(langs):
            if f".{lang.lower()}.vtt" in name:
                return (0, i, name)
        return (1, 999, name)

    files.sort(key=pref_key)
    return files[0]


def _parse_vtt_ts(ts):
    s = str(ts or "").strip()
    if not s:
        return None
    if "." in s:
        main, ms = s.split(".", 1)
    else:
        main, ms = s, "0"
    parts = main.split(":")
    try:
        if len(parts) == 3:
            h = int(parts[0])
            m = int(parts[1])
            sec = int(parts[2])
        elif len(parts) == 2:
            h = 0
            m = int(parts[0])
            sec = int(parts[1])
        else:
            return None
        ms_i = int(re.sub(r"[^0-9]", "", ms)[:3] or "0")
        return float(h * 3600 + m * 60 + sec) + (ms_i / 1000.0)
    except Exception:
        return None


def _parse_vtt_segments(vtt_path):
    try:
        raw = open(vtt_path, "r", encoding="utf-8", errors="ignore").read()
    except Exception:
        return []

    lines = [ln.rstrip("\n\r") for ln in raw.splitlines()]
    out = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "-->" not in line:
            i += 1
            continue
        left, right = line.split("-->", 1)
        start = _parse_vtt_ts(left.strip())
        right = right.strip()
        end_part = right.split()[0] if right else ""
        end = _parse_vtt_ts(end_part)
        i += 1
        texts = []
        while i < len(lines) and lines[i].strip() != "":
            t = lines[i].strip()
            if t and not t.isdigit() and not t.startswith("NOTE"):
                texts.append(t)
            i += 1
        if start is not None and end is not None and end > start and texts:
            out.append({"start": float(start), "end": float(end), "text": " ".join(texts).strip()})
        i += 1
    return out


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
    step = 10.0
    min_len = 20.0
    duration_options = [20.0, 30.0, 45.0, 60.0, 90.0, 120.0, 180.0]

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
        segs.append({"start": st, "end": en, "words": len(toks), "kw": kw})

    if not segs:
        return []

    cand_starts = {0.0}
    for s in segs:
        cand_starts.add(float(int(s["start"] // step) * step))
    cand_starts = sorted(x for x in cand_starts if 0 <= x < dur_total)

    candidates = []
    for ws in cand_starts:
        for dlen in duration_options:
            dlen = float(dlen)
            if dlen < min_len:
                continue
            if dlen > max_len:
                continue
            we = min(dur_total, ws + dlen)
            if we - ws < min_len:
                continue
            words = 0.0
            kw = 0.0
            for s in segs:
                os_ = max(ws, s["start"])
                oe = min(we, s["end"])
                if oe <= os_:
                    continue
                frac = (oe - os_) / max(1e-6, (s["end"] - s["start"]))
                words += float(s["words"]) * frac
                kw += float(s["kw"]) * frac
            density = words / max(1e-6, (we - ws))
            score = density + (0.8 * kw)
            candidates.append({"start": ws, "end": we, "score": float(score)})

    candidates.sort(key=lambda x: x["score"], reverse=True)

    picked = []
    for c in candidates:
        if len(picked) >= int(limit):
            break
        ok = True
        for p in picked:
            inter = max(0.0, min(c["end"], p["end"]) - max(c["start"], p["start"]))
            if inter <= 0:
                continue
            union = max(c["end"], p["end"]) - min(c["start"], p["start"])
            if union > 0 and (inter / union) > 0.55:
                ok = False
                break
        if ok:
            picked.append(c)

    if not picked:
        return []

    max_score = max((p["score"] for p in picked), default=1.0) or 1.0
    out = []
    for p in picked:
        s = int(max(0, round(p["start"])))
        e = int(max(s + 1, round(p["end"])))
        out.append({"enabled": True, "start": s, "end": e, "score": float(p["score"] / max_score)})
    out.sort(key=lambda x: (-(x.get("score") or 0.0), x.get("start") or 0, x.get("end") or 0))
    return out


def get_ai_segments(data):
    url = _get_url(data)
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError("Link YouTube tidak valid.")

    duration_seconds = (data or {}).get("duration_seconds")
    lang = str((data or {}).get("language") or "id").strip() or "id"
    whisper_model = (data or {}).get("whisper_model")
    if whisper_model:
        set_whisper_model(whisper_model)
    limit = int((data or {}).get("limit") or 10)
    limit = max(1, min(20, limit))

    with tempfile.TemporaryDirectory() as td:
        vtt_langs = [lang, "id", "en"]
        vtt_path = _download_captions_vtt_to(video_id, td, vtt_langs)
        transcript = _parse_vtt_segments(vtt_path) if vtt_path else []
        if not transcript:
            audio_file = _download_audio_to(video_id, td)
            transcript = transcribe_timestamped_segments(audio_file, language=lang)

    segs = _build_ai_segments(transcript, duration_seconds=duration_seconds, limit=limit)
    if not segs:
        raise ValueError("AI tidak menemukan segmen yang cukup jelas dari transcript video ini.")
    return {"ok": True, "segments": segs}


def _parse_segments(segments):
    if not isinstance(segments, list):
        raise ValueError("segments harus array.")

    cleaned = []
    for s in segments:
        if not isinstance(s, dict):
            continue
        enabled = bool(s.get("enabled", True))
        try:
            start = float(s.get("start", 0))
            end = float(s.get("end", 0))
        except Exception:
            raise ValueError("start/end harus angka.")
        cleaned.append({"enabled": enabled, "start": start, "end": end})

    enabled_segments = [s for s in cleaned if s.get("enabled", True)]
    if not enabled_segments:
        raise ValueError("Minimal 1 segmen harus aktif.")

    total_sec = 0
    for s in enabled_segments:
        if s["start"] < 0 or s["end"] < 0:
            raise ValueError("Durasi tidak boleh negatif.")
        if s["end"] <= s["start"]:
            raise ValueError("End harus lebih besar dari Start.")
        total_sec += int(max(0, s["end"] - s["start"]))

    return cleaned, enabled_segments, total_sec


def start_clip_job(data):
    data = data or {}

    url = _get_url(data)
    crop_mode = str(data.get("crop_mode", "default")).strip() or "default"
    use_subtitle = bool(data.get("use_subtitle", False))
    whisper_model = str(data.get("whisper_model", get_whisper_model())).strip() or get_whisper_model()

    subtitle_position = str(data.get("subtitle_position", "middle")).strip().lower() or "middle"
    if subtitle_position not in ("bottom", "middle", "top"):
        subtitle_position = "middle"

    output_dir = data.get("output_dir")
    if output_dir is None or str(output_dir).strip() == "":
        output_dir = default_output_dir()
    else:
        output_dir = str(output_dir).strip()

    cleaned, enabled_segments, total_sec = _parse_segments(data.get("segments", []))
    est_bytes = estimate_total_size_bytes(total_sec)

    job_id = uuid.uuid4().hex
    create_job(job_id, output_dir=output_dir)

    payload = {
        "url": url,
        "segments": cleaned,
        "crop_mode": crop_mode if crop_mode in ("default", "split_left", "split_right") else "default",
        "use_subtitle": use_subtitle,
        "whisper_model": whisper_model,
        "subtitle_position": subtitle_position,
        "output_dir": output_dir,
        "apply_padding": False,
        "total_clips": len(enabled_segments),
    }

    start_job(job_id, payload)

    cfg = load_config()
    cfg["output_dir"] = output_dir
    cfg["output_mode"] = "custom" if data.get("output_dir") else "default"
    cfg["crop_mode"] = payload["crop_mode"]
    cfg["use_subtitle"] = use_subtitle
    cfg["whisper_model"] = whisper_model
    cfg["subtitle_position"] = subtitle_position
    save_config(cfg)

    return {"ok": True, "job_id": job_id, "estimated_bytes": est_bytes}


def _open_folder(path):
    if not os.path.isdir(path):
        raise ValueError("Folder output tidak ditemukan di komputer ini.")

    if sys.platform.startswith("win"):
        os.startfile(path)
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", path])
        return
    subprocess.Popen(["xdg-open", path])


def open_output_folder(job_id):
    job = get_job(job_id)
    if not job:
        raise ValueError("Job tidak ditemukan.")

    output_dir = job.get("output_dir")
    if not output_dir:
        raise ValueError("Output folder tidak tersedia.")

    _open_folder(str(output_dir))
    return {"ok": True}
