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
from app.yt_info import extract_video_id
from app.services.gemini_service import (
    find_highlights_with_gemini_transcript,
    generate_clip_metadata,
    process_audio_with_gemini,
)
from app.yt_utils import (
    get_cookies_path,
    get_yt_dlp_cookies_args,
    get_yt_dlp_proxy_args,
    normalize_youtube_url,
)


_AI_DEPS_READY = False
_AI_DEPS_LOCK = threading.Lock()


def _ensure_ai_deps():
    global _AI_DEPS_READY
    if _AI_DEPS_READY:
        return
    with _AI_DEPS_LOCK:
        if _AI_DEPS_READY:
            return
        cek_dependensi(install_whisper=False)
        _AI_DEPS_READY = True


def _download_audio_to_temp(url: str) -> tuple[str, tempfile.TemporaryDirectory]:
    tmpdir = tempfile.TemporaryDirectory(prefix="ytclipper_ai_")
    out_tpl = os.path.join(tmpdir.name, "audio.%(ext)s")

    u = normalize_youtube_url(url)

    format_candidates = [
        "139", # m4a 48k (paling kecil)
        "140", # m4a 128k
        "249", # webm 50k
        "250", # webm 70k
        "wa",  # worst audio
        "ba/b",
    ]

    cookies_present = bool(get_cookies_path())
    if cookies_present:
        player_client_candidates = [
            "web_creator,mweb",
            "",
            "ios",
            "android",
            "tv_embedded,mweb",
        ]
    else:
        player_client_candidates = [
            "web_creator,tv_embedded,mweb",
            "ios",
            "android",
            "tv_simply,mweb",
            "",  # Empty means don't pass --extractor-args, use yt-dlp default
        ]

    try:
        last_error = None
        downloaded = False
        for player_client in player_client_candidates:
            for fmt in format_candidates:
                cmd = [
                    sys.executable,
                    "-m",
                    "yt_dlp",
                    "--force-ipv4",
                    "--quiet",
                    "--no-warnings",
                    "--no-playlist",
                    "--js-runtimes",
                    "node",
                ]
                if player_client:
                    cmd.extend(["--extractor-args", f"youtube:player_client={player_client}"])
                cmd.extend([
                    "-f",
                    fmt,
                ])
                cmd.extend(get_yt_dlp_cookies_args())
                cmd.extend(get_yt_dlp_proxy_args())
                cmd.extend([
                    "-o",
                    out_tpl,
                    u,
                ])
                try:
                    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    last_error = None
                    downloaded = True
                    break
                except subprocess.CalledProcessError as e:
                    last_error = e
            if downloaded:
                break
        if last_error and not downloaded:
            raise last_error
    except subprocess.CalledProcessError as e:
        err = (e.stderr or "").strip() or (e.stdout or "").strip()
        tmpdir.cleanup()
        if "Sign in to confirm you’re not a bot" in err or "Sign in to confirm you're not a bot" in err:
            err_msg = (
                "YouTube memblokir request (Bot Detection / IP Datacenter).\n"
                "Solusi: Pasang file cookies.txt YouTube dari browser di menu YouTube Cookies atau letakkan di /data/cookies.txt pada server production.\n\n"
                f"Detail: {err}"
            )
            raise ValueError(err_msg)
        raise ValueError("Gagal download audio untuk backup AI." + (f"\n\nDetail: {err}" if err else ""))

    hits = sorted(glob.glob(os.path.join(tmpdir.name, "audio.*")))
    audio_path = hits[0] if hits else None
    if not audio_path or not os.path.exists(audio_path):
        tmpdir.cleanup()
        raise ValueError("Gagal download audio untuk backup AI (file audio tidak ditemukan).")

    return audio_path, tmpdir


def _fetch_youtube_subtitle(url: str, language: str) -> list[dict]:
    import json
    import glob
    with tempfile.TemporaryDirectory(prefix="ytclipper_sub_") as tmpdir:
        out_tpl = os.path.join(tmpdir, "sub.%(ext)s")
        cmd = [
            sys.executable,
            "-m",
            "yt_dlp",
            "--quiet",
            "--no-warnings",
            "--no-playlist",
            "--js-runtimes",
            "node",
            "--extractor-args",
            "youtube:player_client=web_creator,mweb,android",
            "--write-auto-sub",
            "--write-sub",
            "--sub-lang", f"{language},en,id",
            "--sub-format", "json3",
            "--skip-download",
        ] + get_yt_dlp_cookies_args() + get_yt_dlp_proxy_args() + [
            "-o", out_tpl,
            normalize_youtube_url(url)
        ]
        
        try:
            res = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        except Exception as e:
            print("Yt-dlp error:", e)
            
        hits = glob.glob(os.path.join(tmpdir, "*.json3"))
        if not hits:
            return []
            
        target_file = None
        for h in hits:
            if f".{language}.json3" in h:
                target_file = h
                break
        if not target_file:
            for h in hits:
                if ".id.json3" in h or ".en.json3" in h:
                    target_file = h
                    break
        if not target_file:
            target_file = hits[0]
            
        try:
            with open(target_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            return []
            
        segments = []
        events = data.get('events', [])
        
        # Consolidate short events into ~5 second chunks for better scoring
        current_chunk = []
        chunk_start = -1.0
        chunk_end = 0.0
        
        for ev in events:
            start_ms = ev.get('tStartMs', 0)
            duration_ms = ev.get('dDurationMs', 0)
            if duration_ms == 0:
                continue
            segs = ev.get('segs', [])
            text = "".join([s.get('utf8', '') for s in segs if 'utf8' in s]).replace("\n", " ").strip()
            if not text:
                continue
                
            st = float(start_ms) / 1000.0
            en = float(start_ms + duration_ms) / 1000.0
            
            if chunk_start < 0:
                chunk_start = st
            chunk_end = max(chunk_end, en)
            current_chunk.append(text)
            
            if (chunk_end - chunk_start) >= 5.0:
                segments.append({
                    "start": chunk_start,
                    "end": chunk_end,
                    "text": " ".join(current_chunk)
                })
                current_chunk = []
                chunk_start = -1.0
                
        if current_chunk:
            segments.append({
                "start": max(0.0, chunk_start),
                "end": max(chunk_start + 1.0, chunk_end),
                "text": " ".join(current_chunk)
            })
            
        return segments


def _get_url(data):
    url = normalize_youtube_url((data or {}).get("url", ""))
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
    target_len = min(60.0, max_len)
    min_len = 25.0

    keywords = {
        # Indonesian high-engagement & viral hook keywords
        "intinya", "jadi", "pokoknya", "kesimpulannya", "serius", "gila", "parah",
        "wkwk", "haha", "anjir", "buset", "plot", "twist", "ending", "ternyata",
        "finally", "beneran", "nggak", "gak", "kok", "lah", "rahasia", "tips",
        "trik", "penting", "menurut", "alasan", "karena", "faktanya", "kenapa",
        "bayangkan", "masalahnya", "solusinya", "kuncinya", "tahukah", "pernah",
        "bongkar", "waspada", "jangan", "wajib", "ajaib", "terbukti", "kocak",
        # English high-engagement & viral hook keywords
        "secret", "truth", "revealed", "insane", "crazy", "unbelievable", "shocking",
        "mistake", "warning", "never", "always", "how", "why", "best", "worst",
        "hack", "key", "solution", "actually", "plot", "twist", "climax", "genius",
    }

    # 1. Score each raw subtitle chunk
    scored_items = []
    for s in transcript_segments:
        try:
            st = float(s.get("start", 0) or 0)
            en = float(s.get("end", st) or st)
            tx = str(s.get("text", "") or "").strip()
        except Exception:
            continue
        if en <= st or not tx:
            continue

        toks = _word_tokens(tx)
        kw = sum(1 for t in toks if t in keywords)
        density = float(kw) / max(1.0, float(len(toks)))
        # Bonus for high-impact hook keywords or questions
        is_question = "?" in tx or any(tx.lower().startswith(q) for q in ("kenapa", "mengapa", "bagaimana", "tahukah", "why", "how", "what if", "pernah"))
        q_bonus = 0.25 if is_question else 0.0
        kw_bonus = 0.3 if any(t in {"plot", "twist", "ending", "ternyata", "rahasia", "faktanya", "kuncinya", "secret", "truth", "insane", "revealed"} for t in toks) else 0.0
        score = density + kw_bonus + q_bonus
        scored_items.append({"start": st, "end": en, "text": tx, "score": score, "tokens": len(toks)})

    if not scored_items:
        return []

    # 2. Find high-interest anchor points (sorted by score descending)
    anchors = sorted(scored_items, key=lambda x: (-x["score"], x["start"]))

    candidates = []
    for anchor in anchors:
        a_st = anchor["start"]
        a_en = anchor["end"]

        # Expand anchor to reach optimal Shorts duration (target_len ~45-60s)
        # Give context before the hook (e.g. 6s before anchor start)
        win_start = max(0.0, a_st - 6.0)
        win_end = min(dur_total, win_start + target_len)

        # Ensure duration is at least min_len (if video length permits)
        if (win_end - win_start) < min_len and dur_total >= min_len:
            win_start = max(0.0, win_end - min_len)

        win_dur = win_end - win_start
        if win_dur < 10.0:
            continue
        if win_dur > max_len:
            win_end = win_start + max_len

        # Snap to nearest sentence boundaries so we never cut speech mid-sentence
        best_st = win_start
        min_diff_st = 999.0
        for it in scored_items:
            diff = abs(it["start"] - win_start)
            if diff < min_diff_st and diff < 6.0:
                min_diff_st = diff
                best_st = it["start"]

        best_en = win_end
        min_diff_en = 999.0
        for it in scored_items:
            diff = abs(it["end"] - win_end)
            if diff < min_diff_en and diff < 6.0:
                min_diff_en = diff
                best_en = it["end"]

        if best_en - best_st >= min_len and best_en - best_st <= max_len:
            win_start = best_st
            win_end = best_en

        # Calculate window cumulative score & text summary
        win_score = 0.0
        win_texts = []
        for it in scored_items:
            if it["end"] >= win_start and it["start"] <= win_end:
                win_score += it["score"]
                win_texts.append(it["text"])

        candidates.append({
            "start": round(win_start, 1),
            "end": round(win_end, 1),
            "score": win_score,
            "text": " ".join(win_texts[:6]),
        })

    # 3. Non-Maximum Suppression (Deduplication of overlapping windows)
    candidates.sort(key=lambda x: -x["score"])
    selected = []
    for cand in candidates:
        overlap = False
        c_st = cand["start"]
        c_en = cand["end"]
        for s in selected:
            s_st = s["start"]
            s_en = s["end"]
            inter_st = max(c_st, s_st)
            inter_en = min(c_en, s_en)
            inter_dur = max(0.0, inter_en - inter_st)
            if inter_dur > 0.35 * (c_en - c_st):
                overlap = True
                break
        if not overlap:
            selected.append(cand)
            if len(selected) >= int(limit or 10):
                break

    # 4. Normalize scores and format output (Pastikan durasi Shorts minimal 15 detik)
    max_score = max((p["score"] for p in selected), default=1.0) or 1.0
    out = []
    for p in selected:
        st = int(max(0, round(p["start"])))
        en = int(max(st + 15, round(p["end"])))
        if dur_total and en > dur_total:
            en = int(dur_total)
            if (en - st) < 15 and dur_total >= 15:
                st = max(0, en - 15)
        out.append({
            "enabled": True,
            "start": st,
            "end": en,
            "score": round(float(p["score"] / max_score), 2),
        })

    out.sort(key=lambda x: x["start"])
    return out


def get_ai_segments(data, on_progress=None):
    def report(pct, msg, stage="process"):
        if callable(on_progress):
            try:
                on_progress(pct, msg, stage)
            except Exception:
                pass

    data = data or {}
    url = _get_url(data)
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError("Link YouTube tidak valid.")

    language = str(data.get("language", "id") or "id")
    whisper_model = data.get("whisper_model")
    limit = int(data.get("limit", 10) or 10)
    duration_seconds = data.get("duration_seconds")

    report(10.0, "Memeriksa ketersediaan dependency...")
    try:
        _ensure_ai_deps()
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Gagal menyiapkan dependency backup AI: {type(e).__name__}: {str(e)}")

    api_key = data.get("gemini_api_key") or load_config().get("gemini_api_key")

    audio_path = None
    tmpdir = None

    # Method 1: Subtitle YouTube (sangat cepat, 100% hemat CPU)
    print("Mencoba mengambil subtitle dari YouTube...")
    report(20.0, "Memeriksa transkrip subtitle YouTube...")
    try:
        sub_segments = _fetch_youtube_subtitle(url, language)
        if sub_segments and len(sub_segments) > 5:
            print(f"Sukses mendapatkan {len(sub_segments)} segmen subtitle otomatis!")
            report(45.0, f"Membaca {len(sub_segments)} baris transkrip...")
            # Jika user memasukkan Gemini API Key, gunakan analisis semantik Gemini (100% Free Tier)
            if api_key:
                try:
                    print("Menggunakan Gemini Semantic Highlight pada transkrip...")
                    report(65.0, "Mencari highlight viral dengan Gemini AI...")
                    gemini_segs = find_highlights_with_gemini_transcript(
                        sub_segments, api_key, duration_seconds=duration_seconds, limit=limit
                    )
                    if gemini_segs:
                        report(95.0, "Menyusun klip Shorts...")
                        return {"ok": True, "segments": gemini_segs}
                except Exception as ge:
                    print(f"Gemini transcript analysis error, fallback ke local heuristic: {ge}")

            report(65.0, "Menganalisis hook & punchline transkrip...")
            segs = _build_ai_segments(sub_segments, duration_seconds=duration_seconds, limit=limit)
            report(95.0, "Menyusun klip Shorts...")
            return {"ok": True, "segments": segs}
    except Exception as e:
        print(f"Gagal mengambil subtitle otomatis: {e}")

    # Method 2: Download Audio & Analisis (Gemini atau Local Whisper)
    print("Subtitle tidak tersedia, mengunduh audio untuk analisis...")
    report(30.0, "Mengunduh audio video untuk dianalisis...")
    try:
        audio_path, tmpdir = _download_audio_to_temp(url)
        report(55.0, "Audio siap, menyiapkan model transkripsi...")

        # Jika ada API Key Gemini, coba gunakan Gemini Audio
        if api_key:
            try:
                print("Menganalisis audio dengan Gemini...")
                report(70.0, "Mengunggah audio & menganalisis dengan Gemini...")
                segs = process_audio_with_gemini(audio_path, api_key)
                if segs:
                    report(95.0, "Menyusun klip Shorts...")
                    return {"ok": True, "segments": segs}
            except Exception as e:
                print(f"Gemini audio processing gagal: {e}. Mengalihkan ke Faster-Whisper offline...")

        # Method 3: Fallback ke Faster-Whisper Lokal (100% Offline & Gratis)
        print("Menganalisis audio secara lokal menggunakan Faster-Whisper (100% Gratis)...")
        report(60.0, "Mentranskripsi audio secara lokal (Faster-Whisper)...")
        try:
            from app.subtitle_ai import get_faster_whisper_model
            model = get_faster_whisper_model()
            lang_param = language if language and language != "auto" else None
            report(70.0, "Memproses transkripsi speech-to-text...")
            segments_gen, _ = model.transcribe(audio_path, language=lang_param, beam_size=1)
            whisper_subs = []
            for s in segments_gen:
                whisper_subs.append({"start": float(s.start), "end": float(s.end), "text": str(s.text)})

            if whisper_subs:
                if api_key:
                    try:
                        report(85.0, "Mencari highlight viral dengan Gemini AI...")
                        gemini_segs = find_highlights_with_gemini_transcript(
                            whisper_subs, api_key, duration_seconds=duration_seconds, limit=limit
                        )
                        if gemini_segs:
                            report(95.0, "Menyusun klip Shorts...")
                            return {"ok": True, "segments": gemini_segs}
                    except Exception:
                        pass
                report(85.0, "Menganalisis hook & punchline transkrip...")
                segs = _build_ai_segments(whisper_subs, duration_seconds=duration_seconds, limit=limit)
                report(95.0, "Menyusun klip Shorts...")
                return {"ok": True, "segments": segs}
        except Exception as we:
            print(f"Faster-Whisper offline transcribing error: {we}")

        raise ValueError("Tidak dapat mengekstrak segmen dari audio video ini.")
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
