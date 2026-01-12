import os
import re
import json
import sys
import time
import uuid
import queue
import shutil
import threading
import subprocess
import contextlib
from datetime import datetime
from urllib.parse import urlparse, parse_qs

import requests
from flask import Flask, request, jsonify, render_template_string


MIN_SCORE = 0.40
MAX_DURATION = 60
PADDING = 10
TOP_HEIGHT = 960
BOTTOM_HEIGHT = 320
WHISPER_MODEL = "small"


def _default_output_dir():
    return os.path.join(os.path.expanduser("~"), "Videos", "ClipAI")


def _config_path():
    return os.path.join(os.path.expanduser("~"), ".ytclipper_web.json")


def _load_config():
    try:
        with open(_config_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        return {}
    return {}


def _save_config(data):
    try:
        with open(_config_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        return


def _unique_path(folder, stem, ext):
    base = f"{stem}{ext}"
    path = os.path.join(folder, base)
    if not os.path.exists(path):
        return path
    for i in range(2, 10000):
        path = os.path.join(folder, f"{stem}_{i}{ext}")
        if not os.path.exists(path):
            return path
    raise RuntimeError("Gagal membuat nama file output unik.")


def _format_hhmmss(seconds):
    seconds = max(0, int(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _estimate_total_size_bytes(total_seconds):
    bitrate_bps = 2_600_000
    return int(max(0, total_seconds) * (bitrate_bps / 8))


def extract_video_id(url):
    parsed = urlparse(url)

    if parsed.hostname in ("youtu.be", "www.youtu.be"):
        return parsed.path[1:]

    if parsed.hostname in ("youtube.com", "www.youtube.com"):
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        if parsed.path.startswith("/shorts/"):
            parts = parsed.path.split("/")
            if len(parts) >= 3:
                return parts[2]

    return None


def get_duration(video_id):
    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--get-duration",
        f"https://youtu.be/{video_id}"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        time_parts = res.stdout.strip().split(":")

        if len(time_parts) == 2:
            return int(time_parts[0]) * 60 + int(time_parts[1])
        if len(time_parts) == 3:
            return (
                int(time_parts[0]) * 3600 +
                int(time_parts[1]) * 60 +
                int(time_parts[2])
            )
    except Exception:
        pass
    return 3600


def _get_ffmpeg_path():
    """Get ffmpeg path - check system PATH first, then local bin folder."""
    # Check system PATH
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    # Check local bin folder
    local_bin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
    local_ffmpeg = os.path.join(local_bin, "ffmpeg.exe")
    if os.path.exists(local_ffmpeg):
        return local_ffmpeg

    return None


def _download_ffmpeg():
    """Download FFmpeg binary untuk Windows."""
    print("📦 FFmpeg tidak ditemukan, downloading...")

    local_bin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
    os.makedirs(local_bin, exist_ok=True)

    # Download dari GitHub release (ffmpeg-essentials)
    url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    zip_path = os.path.join(local_bin, "ffmpeg.zip")

    try:
        print(f"⬇️  Downloading FFmpeg dari {url[:50]}...")
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0

        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    pct = (downloaded / total_size) * 100
                    print(f"\r⬇️  Downloading... {pct:.1f}%", end="", flush=True)

        print("\n📂 Extracting FFmpeg...")

        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Find ffmpeg.exe in the archive
            for name in zip_ref.namelist():
                if name.endswith('ffmpeg.exe'):
                    # Extract just ffmpeg.exe
                    with zip_ref.open(name) as src:
                        ffmpeg_dest = os.path.join(local_bin, "ffmpeg.exe")
                        with open(ffmpeg_dest, 'wb') as dst:
                            dst.write(src.read())
                    print(f"✅ FFmpeg extracted ke {ffmpeg_dest}")
                    break
                if name.endswith('ffprobe.exe'):
                    with zip_ref.open(name) as src:
                        ffprobe_dest = os.path.join(local_bin, "ffprobe.exe")
                        with open(ffprobe_dest, 'wb') as dst:
                            dst.write(src.read())

        # Cleanup zip
        try:
            os.remove(zip_path)
        except:
            pass

        return os.path.join(local_bin, "ffmpeg.exe")

    except Exception as e:
        raise RuntimeError(f"Gagal download FFmpeg: {e}\n\nSolusi manual: install FFmpeg via 'winget install ffmpeg' atau download dari https://ffmpeg.org")


def cek_dependensi(install_whisper=False):
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    if install_whisper:
        try:
            import faster_whisper
        except ImportError:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "faster-whisper"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

    # Check and download FFmpeg if needed
    ffmpeg_path = _get_ffmpeg_path()
    if not ffmpeg_path:
        ffmpeg_path = _download_ffmpeg()

    # Add local bin to PATH for this session
    local_bin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
    if local_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] = local_bin + os.pathsep + os.environ.get("PATH", "")


def _extract_balanced(text, start_index, open_ch, close_ch):
    if start_index < 0 or start_index >= len(text):
        return None
    if text[start_index] != open_ch:
        return None

    depth = 0
    in_str = False
    esc = False
    for i in range(start_index, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue

        if ch == '"':
            in_str = True
            continue

        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start_index:i + 1]
    return None


def _extract_assigned_json(text, var_name):
    m = re.search(rf"(?:var\s+)?{re.escape(var_name)}\s*=\s*", text)
    if not m:
        return None
    start = text.find("{", m.end())
    if start < 0:
        return None
    raw = _extract_balanced(text, start, "{", "}")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _walk_json(obj):
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            yield cur
            for v in cur.values():
                stack.append(v)
        elif isinstance(cur, list):
            for v in cur:
                stack.append(v)


def _collect_heat_markers(root):
    found = []
    for d in _walk_json(root):
        if "heatMarkerRenderer" in d and isinstance(d.get("heatMarkerRenderer"), dict):
            found.append(d["heatMarkerRenderer"])
        markers = d.get("markers")
        if isinstance(markers, list):
            for it in markers:
                if isinstance(it, dict) and "heatMarkerRenderer" in it and isinstance(it.get("heatMarkerRenderer"), dict):
                    found.append(it["heatMarkerRenderer"])
                elif isinstance(it, dict):
                    found.append(it)
        heat_markers = d.get("heatMarkers")
        if isinstance(heat_markers, list):
            for it in heat_markers:
                if isinstance(it, dict) and "heatMarkerRenderer" in it and isinstance(it.get("heatMarkerRenderer"), dict):
                    found.append(it["heatMarkerRenderer"])
    return found


def _norm_score(marker):
    for k in ("intensityScoreNormalized", "heatMarkerIntensityScoreNormalized", "heatMarkerIntensityScore", "intensityScore"):
        try:
            v = marker.get(k)
            if v is None:
                continue
            return float(v)
        except Exception:
            continue
    return 0.0


def _norm_start_duration(marker):
    start_keys = ("startMillis", "timeRangeStartMillis")
    dur_keys = ("durationMillis", "timeRangeDurationMillis")
    start_ms = None
    dur_ms = None
    for k in start_keys:
        if k in marker:
            start_ms = marker.get(k)
            break
    for k in dur_keys:
        if k in marker:
            dur_ms = marker.get(k)
            break
    if start_ms is None or dur_ms is None:
        return None
    try:
        start_s = float(start_ms) / 1000.0
        dur_s = float(dur_ms) / 1000.0
        return start_s, dur_s
    except Exception:
        return None


def ambil_most_replayed(video_id, min_score=None, fallback_limit=10):
    url = f"https://www.youtube.com/watch?v={video_id}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
    }

    html = ""
    try:
        html = requests.get(url, headers=headers, timeout=20).text
        if "consent.youtube.com" in html or "Before you continue to YouTube" in html:
            html = requests.get(url, headers=headers, cookies={"CONSENT": "YES+1"}, timeout=20).text
    except Exception:
        return []

    all_markers = []

    pos = html.find('"markers"')
    if pos >= 0:
        arr_start = html.find("[", pos)
        raw_arr = _extract_balanced(html, arr_start, "[", "]")
        if raw_arr:
            try:
                markers = json.loads(raw_arr)
                if isinstance(markers, list):
                    all_markers.extend(markers)
            except Exception:
                pass

    for var_name in ("ytInitialPlayerResponse", "ytInitialData"):
        root = _extract_assigned_json(html, var_name)
        if root:
            all_markers.extend(_collect_heat_markers(root))

    normalized = {}
    for marker in all_markers:
        if not isinstance(marker, dict):
            continue
        if "heatMarkerRenderer" in marker and isinstance(marker.get("heatMarkerRenderer"), dict):
            marker = marker["heatMarkerRenderer"]

        sd = _norm_start_duration(marker)
        if not sd:
            continue
        start_s, dur_s = sd
        if dur_s <= 0:
            continue
        score = _norm_score(marker)
        key = (int(start_s * 1000), int(dur_s * 1000))
        prev = normalized.get(key)
        if prev is None or score > prev["score"]:
            normalized[key] = {
                "start": start_s,
                "duration": min(dur_s, float(MAX_DURATION)),
                "score": float(score),
            }

    items = list(normalized.values())
    items.sort(key=lambda x: x["score"], reverse=True)

    threshold = MIN_SCORE if min_score is None else float(min_score)
    filtered = [it for it in items if it["score"] >= threshold]
    if filtered:
        return filtered
    return items[: max(1, int(fallback_limit))]


_FASTER_WHISPER_MODEL = None
_FASTER_WHISPER_MODEL_NAME = None


def get_faster_whisper_model():
    global _FASTER_WHISPER_MODEL, _FASTER_WHISPER_MODEL_NAME

    if _FASTER_WHISPER_MODEL is not None and _FASTER_WHISPER_MODEL_NAME == WHISPER_MODEL:
        return _FASTER_WHISPER_MODEL

    from faster_whisper import WhisperModel

    _FASTER_WHISPER_MODEL = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    _FASTER_WHISPER_MODEL_NAME = WHISPER_MODEL
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


def _fmt_time(s):
    """Format seconds ke mm:ss"""
    m = int(s // 60)
    sec = int(s % 60)
    return f"{m}:{sec:02d}"


def proses_satu_clip(video_id, item, index, total_duration, crop_mode="default", use_subtitle=False, subtitle_position="middle", output_dir=None, apply_padding=True, event_cb=None):
    start_original = float(item.get("start", 0))
    if "end" in item:
        end_original = float(item.get("end", start_original))
    else:
        end_original = start_original + float(item.get("duration", 0))

    if apply_padding:
        start = max(0, start_original - PADDING)
        end = min(end_original + PADDING, total_duration)
    else:
        start = max(0, start_original)
        end = min(end_original, total_duration)

    duration = end - start
    print(f"\n{'='*40}")
    print(f"🎬 Clip #{index}: {_fmt_time(start)} → {_fmt_time(end)} ({duration:.0f}s)")

    if duration < 1:
        print(f"⚠️ Skip - durasi terlalu pendek ({duration:.1f}s)")
        return False

    if output_dir is None:
        output_dir = _default_output_dir()
    os.makedirs(output_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = uuid.uuid4().hex[:8]
    stem = f"clip_{index}_{ts}_{tag}"
    temp_file = _unique_path(output_dir, f"temp_{index}_{ts}_{tag}", ".mp4")
    cropped_file = _unique_path(output_dir, f"temp_cropped_{index}_{ts}_{tag}", ".mp4")
    subtitle_file = _unique_path(output_dir, f"temp_{index}_{ts}_{tag}", ".srt")
    output_file = _unique_path(output_dir, stem, ".mp4")

    cmd_download = [
        sys.executable, "-m", "yt_dlp",
        "--force-ipv4",
        "--quiet", "--no-warnings",
        "--downloader", "ffmpeg",
        "--downloader-args",
        f"ffmpeg_i:-ss {start} -to {end} -hide_banner -loglevel error",
        "-f",
        "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "-o", temp_file,
        f"https://youtu.be/{video_id}"
    ]

    try:
        def _clip_text(s, limit=4000):
            s = "" if s is None else str(s)
            if len(s) <= limit:
                return s
            head = s[: int(limit * 0.6)]
            tail = s[-int(limit * 0.4) :]
            return head + "\n... (truncated) ...\n" + tail

        def _run(cmd, label):
            try:
                res = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if res.stderr:
                    err = res.stderr.strip()
                    if err:
                        print(f"[{label}]\n" + _clip_text(err))
                return res
            except subprocess.CalledProcessError as e:
                cmd_text = " ".join(str(x) for x in cmd)
                print(f"[{label}] Command gagal\n{cmd_text}")
                out = (e.stdout or "").strip()
                err = (e.stderr or "").strip()
                if out:
                    print(f"[{label}] stdout\n" + _clip_text(out))
                if err:
                    print(f"[{label}] stderr\n" + _clip_text(err))
                raise

        if event_cb:
            event_cb({"stage": "download", "clip_index": index})
        _run(cmd_download, "download")

        if not os.path.exists(temp_file):
            return False

        if crop_mode == "default":
            cmd_crop = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", temp_file,
                "-vf", "scale=-2:1280,pad=max(iw\\,720):ih:(ow-iw)/2:0,crop=720:1280:(iw-720)/2:(ih-1280)/2",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
                "-c:a", "aac", "-b:a", "128k",
                cropped_file
            ]
        elif crop_mode == "split_left":
            # Split mode: top = main content (center), bottom = left side (facecam)
            # Scale to 1280 height, pad to ensure min 720 width, then crop
            vf = (
                f"scale='max(720,iw*1280/ih)':1280[scaled];"
                f"[scaled]split=2[s1][s2];"
                f"[s1]crop=720:{TOP_HEIGHT}:(iw-720)/2:0[top];"
                f"[s2]crop=720:{BOTTOM_HEIGHT}:0:{TOP_HEIGHT}[bottom];"
                f"[top][bottom]vstack=inputs=2[out]"
            )
            cmd_crop = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
                "-i", temp_file,
                "-filter_complex", vf,
                "-map", "[out]", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
                "-c:a", "aac", "-b:a", "128k",
                cropped_file
            ]
        else:
            # split_right: top = main content (center), bottom = right side (facecam)
            vf = (
                f"scale='max(720,iw*1280/ih)':1280[scaled];"
                f"[scaled]split=2[s1][s2];"
                f"[s1]crop=720:{TOP_HEIGHT}:(iw-720)/2:0[top];"
                f"[s2]crop=720:{BOTTOM_HEIGHT}:iw-720:{TOP_HEIGHT}[bottom];"
                f"[top][bottom]vstack=inputs=2[out]"
            )
            cmd_crop = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
                "-i", temp_file,
                "-filter_complex", vf,
                "-map", "[out]", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
                "-c:a", "aac", "-b:a", "128k",
                cropped_file
            ]

        if event_cb:
            event_cb({"stage": "clip", "clip_index": index})
        _run(cmd_crop, "ffmpeg")

        try:
            os.remove(temp_file)
        except Exception:
            pass

        if use_subtitle:
            if event_cb:
                event_cb({"stage": "subtitle", "clip_index": index})
            ok = generate_subtitle(cropped_file, subtitle_file)
            if ok:
                if event_cb:
                    event_cb({"stage": "subtitle_burn", "clip_index": index})
                abs_subtitle_path = os.path.abspath(subtitle_file)
                subtitle_path = abs_subtitle_path.replace("\\", "/").replace(":", "\\:")
                pos = str(subtitle_position or "middle").strip().lower()
                if pos in ("bottom", "bawah"):
                    alignment = 2
                    margin_v = 60
                elif pos in ("top", "atas"):
                    alignment = 8
                    margin_v = 60
                else:
                    alignment = 5
                    margin_v = 0
                force_style = (
                    "FontName=Arial,"
                    "FontSize=12,"
                    "Bold=1,"
                    "PrimaryColour=&HFFFFFF,"
                    "OutlineColour=&H000000,"
                    "BorderStyle=1,"
                    "Outline=2,"
                    "Shadow=1,"
                    f"Alignment={alignment},"
                    f"MarginV={margin_v}"
                )
                cmd_subtitle = [
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-i", cropped_file,
                    "-vf", f"subtitles='{subtitle_path}':force_style='{force_style}'",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
                    "-c:a", "copy",
                    output_file
                ]
                _run(cmd_subtitle, "subtitle")
                for f in (cropped_file, subtitle_file):
                    try:
                        os.remove(f)
                    except Exception:
                        pass
            else:
                try:
                    os.replace(cropped_file, output_file)
                except Exception:
                    return False
        else:
            try:
                os.replace(cropped_file, output_file)
            except Exception:
                return False

        print(f"✅ Clip #{index} selesai → {os.path.basename(output_file)}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ [ERROR] Clip #{index} gagal (crop_mode={crop_mode})")
        for f in (temp_file, cropped_file, subtitle_file):
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass
        return False
    except Exception as e:
        print(f"❌ [ERROR] Clip #{index} exception: {e}")
        for f in (temp_file, cropped_file, subtitle_file):
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass
        return False


def proses_dengan_segmen(link, segments, crop_mode="default", use_subtitle=False, whisper_model=None, subtitle_position="middle", output_dir=None, apply_padding=False, event_cb=None):
    global WHISPER_MODEL

    if whisper_model:
        WHISPER_MODEL = whisper_model

    if event_cb:
        event_cb({"stage": "dependency"})
    cek_dependensi(install_whisper=use_subtitle)

    video_id = extract_video_id(link)
    if not video_id:
        raise ValueError("Link YouTube tidak valid.")

    if event_cb:
        event_cb({"stage": "duration"})
    total_duration = get_duration(video_id)

    if output_dir is None:
        output_dir = _default_output_dir()
    os.makedirs(output_dir, exist_ok=True)

    enabled_segments = [s for s in segments if s.get("enabled", True)]
    if not enabled_segments:
        raise ValueError("Tidak ada segmen yang aktif.")

    cleaned = []
    for s in enabled_segments:
        start = float(s.get("start", 0))
        end = float(s.get("end", 0))
        if start < 0 or end < 0:
            raise ValueError("Durasi tidak boleh negatif.")
        if end <= start:
            raise ValueError("End harus lebih besar dari Start.")
        cleaned.append({"start": start, "end": end, "enabled": True})

    success = 0
    for seg in cleaned:
        item = {"start": seg["start"], "end": seg["end"]}
        ok = proses_satu_clip(
            video_id=video_id,
            item=item,
            index=success + 1,
            total_duration=total_duration,
            crop_mode=crop_mode,
            use_subtitle=use_subtitle,
            subtitle_position=subtitle_position,
            output_dir=output_dir,
            apply_padding=apply_padding,
            event_cb=event_cb
        )
        if ok:
            success += 1

    if success == 0:
        raise RuntimeError("Semua segmen gagal diproses.")

    return {"success_count": success, "output_dir": output_dir}


class _JobWriter:
    def __init__(self, job_id):
        self.job_id = job_id

    def write(self, s):
        if not s:
            return
        _append_job_log(self.job_id, s)

    def flush(self):
        return


_JOBS_LOCK = threading.Lock()
_JOBS = {}


def _append_job_log(job_id, text):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        job["logs"].append(text)
        if len(job["logs"]) > 6000:
            job["logs"] = job["logs"][-4000:]


def _update_job(job_id, **kwargs):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        job.update(kwargs)


def _get_job(job_id):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return None
        return dict(job)


def _run_job(job_id, payload):
    stage_text = {
        "dependency": "⚙️ Cek dependensi...",
        "duration": "📊 Ambil info video...",
        "download": "⬇️ Download video...",
        "clip": "✂️ Proses clipping...",
        "subtitle": "🤖 AI generating subtitle...",
        "subtitle_burn": "🔥 Burning subtitle...",
    }

    total_clips = max(1, int(payload.get("total_clips", 1)))
    base_percent = 7.0
    per_clip = (100.0 - base_percent) / float(total_clips)
    clip_stage = {"download": 0.55, "clip": 0.35, "subtitle": 0.07, "subtitle_burn": 0.03}
    if not payload.get("use_subtitle", False):
        clip_stage = {"download": 0.60, "clip": 0.40}

    start_ts = time.perf_counter()
    state = {"clip_index": 1, "stage": "dependency"}

    def push(stage, clip_index=None):
        if clip_index is not None:
            state["clip_index"] = int(clip_index)
        state["stage"] = stage
        clip_i = max(1, int(state["clip_index"]))
        done_clips = float(clip_i - 1)
        stage_part = clip_stage.get(stage, 0.0)
        percent = base_percent + (done_clips + stage_part) * per_clip
        percent = max(0.0, min(100.0, percent))

        elapsed = time.perf_counter() - start_ts
        if percent > 0.1:
            remaining = elapsed * (100.0 - percent) / percent
            eta = _format_hhmmss(int(remaining))
        else:
            eta = ""

        status_msg = stage_text.get(stage, stage)
        if stage in ("download", "clip", "subtitle", "subtitle_burn"):
            status_msg = f"[Clip {clip_i}/{total_clips}] {status_msg}"

        _update_job(job_id, percent=percent, stage=stage, status=status_msg, eta=eta)
        # Log ke output juga
        print(f"📍 {status_msg}")

    def event_cb(evt):
        try:
            push(evt.get("stage", ""), clip_index=evt.get("clip_index"))
        except Exception:
            return

    _update_job(job_id, running=True, percent=0.0, stage="dependency", status="🚀 Memulai...", eta="", error=None)

    writer = _JobWriter(job_id)
    with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
        print(f"🎬 Memproses {total_clips} clip...")
        print(f"📁 Output: {payload.get('output_dir', 'default')}")
        print(f"🎨 Crop mode: {payload.get('crop_mode', 'default')}")
        print(f"📝 Subtitle: {'ON' if payload.get('use_subtitle') else 'OFF'}")
        print("-" * 40)
        try:
            segments = payload["segments"]
            result = proses_dengan_segmen(
                link=payload["url"],
                segments=segments,
                crop_mode=payload["crop_mode"],
                use_subtitle=payload["use_subtitle"],
                whisper_model=payload.get("whisper_model"),
                subtitle_position=payload.get("subtitle_position", "middle"),
                output_dir=payload.get("output_dir"),
                apply_padding=payload.get("apply_padding", False),
                event_cb=event_cb
            )
            _update_job(
                job_id,
                running=False,
                done=True,
                percent=100.0,
                stage="done",
                status="Selesai",
                eta="",
                output_dir=result.get("output_dir"),
                success_count=result.get("success_count", 0)
            )
        except Exception as e:
            import traceback
            error_detail = f"{type(e).__name__}: {str(e)}"
            print(f"\n[FATAL ERROR] {error_detail}")
            print(traceback.format_exc())
            _update_job(job_id, running=False, done=True, percent=0.0, stage="error", status="Error", eta="", error=error_detail)


app = Flask(__name__)


HTML = r"""
<!doctype html>
<html lang="id">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>YTClipper</title>
  <meta name="application-name" content="YTClipper" />
  <meta name="apple-mobile-web-app-title" content="YTClipper" />
  <meta name="theme-color" content="#0b0f14" />
  <link rel="icon" href="data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22%20viewBox%3D%220%200%2024%2024%22%3E%3Crect%20x%3D%223%22%20y%3D%225%22%20width%3D%2218%22%20height%3D%2214%22%20rx%3D%223%22%20fill%3D%22%23111824%22%20stroke%3D%22%2348d0ff%22%20stroke-width%3D%221.6%22/%3E%3Cpath%20d%3D%22M10%209v6l6-3z%22%20fill%3D%22%2348d0ff%22/%3E%3C/svg%3E" />
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 0; background: #0b0f14; color: #e8edf2; }
    .wrap { max-width: 920px; margin: 0 auto; padding: 18px; }
    .grid { display: flex; flex-direction: column; gap: 14px; }
    .card { background: #111824; border: 1px solid #1f2a3a; border-radius: 12px; padding: 14px; }
    .card h2 { margin: 0 0 10px 0; font-size: 16px; display: flex; align-items: center; gap: 10px; }
    label { display: block; font-size: 12px; color: #b8c6d6; margin-bottom: 6px; }
    input[type="text"], input[type="number"], select { width: 100%; box-sizing: border-box; padding: 10px 10px; border-radius: 10px; border: 1px solid #253246; background: #0b111a; color: #e8edf2; }
    .row { display: flex; gap: 10px; align-items: flex-start; flex-wrap: wrap; }
    .row > * { flex: 1 1 200px; min-width: 0; }
    .btn { padding: 10px 12px; border-radius: 10px; border: 1px solid #2a3b56; background: #132033; color: #e8edf2; cursor: pointer; transition: background 150ms ease, border-color 150ms ease, transform 150ms ease, box-shadow 150ms ease; }
    .btn:hover { background: #162844; border-color: #3a5378; }
    .btn:active { transform: translateY(1px); }
    .btn:disabled { opacity: 0.55; cursor: not-allowed; }
    .btn.primary { background: linear-gradient(90deg, #2b5cff, #48d0ff); border-color: rgba(72,208,255,0.55); box-shadow: 0 10px 26px rgba(43,92,255,0.18); }
    .btn.primary:hover { box-shadow: 0 10px 30px rgba(72,208,255,0.18); border-color: rgba(72,208,255,0.9); }
    .btn.danger { background: linear-gradient(90deg, #b4232a, #e14a52); border-color: rgba(225,74,82,0.5); box-shadow: 0 10px 26px rgba(225,74,82,0.12); }
    .btn.danger:hover { border-color: rgba(225,74,82,0.9); box-shadow: 0 10px 30px rgba(225,74,82,0.14); }
    .muted { color: #a7b7c9; font-size: 12px; }
    .btnLabel { display: inline-flex; align-items: center; justify-content: center; gap: 10px; }
    .spinner { width: 14px; height: 14px; border-radius: 999px; border: 2px solid #2a3b56; border-top-color: transparent; animation: spin 0.85s linear infinite; display: none; flex: 0 0 auto; }
    .ico { width: 16px; height: 16px; display: inline-block; flex: 0 0 auto; }
    .divider { height: 1px; background: #1f2a3a; margin: 14px 0; }
    .sectionTitle { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #cfe0f1; font-weight: 650; margin: 0 0 8px 0; }
    @keyframes spin { to { transform: rotate(360deg); } }
    input[type="range"] { width: 100%; margin: 0; -webkit-appearance: none; appearance: none; height: 14px; background: transparent; }
    input[type="range"]:focus { outline: none; }
    input[type="range"]::-webkit-slider-runnable-track { height: 14px; border-radius: 999px; background: linear-gradient(90deg, #2b5cff 0%, #2b5cff var(--pct, 0%), #0b111a var(--pct, 0%), #0b111a 100%); border: 1px solid #1f2a3a; }
    input[type="range"]::-webkit-slider-thumb { -webkit-appearance: none; appearance: none; width: 22px; height: 22px; margin-top: -5px; border-radius: 999px; background: #e8edf2; border: 2px solid #2b5cff; box-shadow: 0 0 0 4px rgba(43,92,255,0.18); }
    input[type="range"]::-moz-range-track { height: 14px; border-radius: 999px; background: #0b111a; border: 1px solid #1f2a3a; }
    input[type="range"]::-moz-range-progress { height: 14px; border-radius: 999px; background: #2b5cff; }
    input[type="range"]::-moz-range-thumb { width: 22px; height: 22px; border-radius: 999px; background: #e8edf2; border: 2px solid #2b5cff; box-shadow: 0 0 0 4px rgba(43,92,255,0.18); }
    .player { width: 100%; aspect-ratio: 16/9; border-radius: 12px; overflow: hidden; border: 1px solid #1f2a3a; background: #0b111a; }
    .player iframe { width: 100%; height: 100%; border: 0; }
    .seglist { width: 100%; border-collapse: collapse; font-size: 13px; }
    .seglist th, .seglist td { padding: 8px 6px; border-bottom: 1px solid #1f2a3a; }
    .seglist th { text-align: left; color: #b8c6d6; font-weight: 600; }
    .seglist tr.activeSeg { background: rgba(43, 92, 255, 0.12); }
    .progress { height: 18px; background: #0b111a; border: 1px solid #1f2a3a; border-radius: 999px; overflow: hidden; position: relative; }
    .bar {
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, #2b5cff 0%, #48d0ff 50%, #2b5cff 100%);
      background-size: 200% 100%;
      transition: width 300ms ease;
      position: relative;
    }
    .bar.active {
      animation: wave 1.5s ease-in-out infinite;
    }
    @keyframes wave {
      0% { background-position: 100% 0; }
      100% { background-position: -100% 0; }
    }
    .bar::after {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.2) 50%, transparent 100%);
      background-size: 50% 100%;
      animation: shimmer 1.2s ease-in-out infinite;
    }
    @keyframes shimmer {
      0% { background-position: -100% 0; }
      100% { background-position: 200% 0; }
    }
    .bar:not(.active)::after { animation: none; opacity: 0; }
    #log { margin-top: 10px; }
    #log:empty { display: none; }
    pre { white-space: pre-wrap; word-wrap: break-word; background: #0b111a; border: 1px solid #1f2a3a; border-radius: 12px; padding: 10px; height: 220px; overflow: auto; }
    .modal { position: fixed; inset: 0; display: none; align-items: flex-start; justify-content: center; padding: 16px; background: rgba(0,0,0,0.65); overflow: auto; }
    .modal.on { display: flex; }
    .modal .box { width: min(980px, 100%); background: #111824; border: 1px solid #1f2a3a; border-radius: 14px; padding: 14px; max-height: calc(100vh - 32px); overflow-y: auto; overflow-x: hidden; box-sizing: border-box; }
    .modal .box h3 { margin: 0 0 10px 0; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }
    @media (max-width: 900px) { .wrap { max-width: 100%; } }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="grid">
      <div class="card">
        <h2>
          <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <rect x="3" y="5" width="18" height="14" rx="2"></rect>
            <path d="M10 9l5 3-5 3V9z"></path>
          </svg>
          Video & Heatmap
        </h2>
        <div class="muted" style="margin:-6px 0 12px 0">Tempel URL, lalu ambil Most Replayed untuk auto-segmen (inti auto-clipper).</div>
        <label title="Tempel link YouTube (watch/shorts/youtu.be).">YouTube URL</label>
        <input id="url" type="text" placeholder="https://www.youtube.com/watch?v=..." />
        <div style="height:10px"></div>
        <div class="row">
          <button class="btn" id="openYT" title="Buka link di tab baru.">
            <span class="btnLabel">
              <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M14 3h7v7"></path>
                <path d="M10 14L21 3"></path>
                <path d="M21 14v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h6"></path>
              </svg>
              <span>Open</span>
            </span>
          </button>
          <button class="btn primary" id="loadHeatmap" title="Ambil segmen otomatis dari Most Replayed.">
            <span class="btnLabel">
              <span class="spinner" id="heatmapSpin"></span>
              <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M3 12h6l3-9 3 18 3-9h3"></path>
              </svg>
              <span id="heatmapText">Load Heatmap</span>
            </span>
          </button>
        </div>
        <div style="height:10px"></div>
        <div class="muted" id="info">Durasi: -</div>
        <div style="height:12px"></div>
        <div class="player">
          <div id="player"></div>
        </div>
        <div style="height:10px"></div>
        <div class="row">
          <button class="btn" id="play" title="Play/Pause preview.">
            <span class="btnLabel">
              <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M8 5v14l11-7z"></path>
              </svg>
              <span>Play/Pause</span>
            </span>
          </button>
          <button class="btn" id="stop" title="Stop dan kembali ke 0.">
            <span class="btnLabel">
              <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <rect x="7" y="7" width="10" height="10" rx="2"></rect>
              </svg>
              <span>Stop</span>
            </span>
          </button>
          <input id="previewSecs" type="number" min="5" max="600" step="1" title="Preview pertama N detik." />
          <button class="btn" id="playPreview" title="Mainkan dari 0 sampai preview detik.">
            <span class="btnLabel">
              <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M22 12a10 10 0 1 1-3-7.2"></path>
                <path d="M22 4v6h-6"></path>
              </svg>
              <span>Play Preview</span>
            </span>
          </button>
        </div>
        <div style="height:10px"></div>
        <label title="Timeline untuk navigasi preview.">Timeline</label>
        <input id="timeline" type="range" min="0" max="0" value="0" />
        <div class="muted"><span id="tCur">00:00</span> / <span id="tDur">00:00</span></div>

        <div class="divider"></div>
        <div class="sectionTitle">
          <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M4 19V5"></path>
            <path d="M4 19h16"></path>
            <path d="M7 15l3-3 3 3 6-8"></path>
          </svg>
          Segmen Otomatis (Most Replayed)
        </div>
        <div class="muted" style="margin:-4px 0 10px 0">Preview/edit per segmen sebelum diproses. Tombol Preview akan membuka modal untuk adjust start/end.</div>
        <div class="row" style="margin:0 0 10px 0">
          <button class="btn" id="segSelectAll" title="Aktifkan semua segmen." disabled>
            <span class="btnLabel">
              <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M9 11l3 3L22 4"></path>
                <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
              </svg>
              <span>Select All</span>
            </span>
          </button>
          <button class="btn" id="segDeselectAll" title="Nonaktifkan semua segmen." disabled>
            <span class="btnLabel">
              <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M18 6L6 18"></path>
                <path d="M6 6l12 12"></path>
              </svg>
              <span>Deselect All</span>
            </span>
          </button>
          <div class="muted" id="segPickInfo" style="text-align:right;flex:1"></div>
        </div>
        <table class="seglist" id="segTable">
          <thead><tr><th style="width:40px">On</th><th>Start</th><th>End</th><th>Dur</th><th style="width:64px">Score</th><th style="width:130px">Aksi</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>

      <div class="card">
        <h2>
          <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M12 1v2"></path>
            <path d="M12 21v2"></path>
            <path d="M4.2 4.2l1.4 1.4"></path>
            <path d="M18.4 18.4l1.4 1.4"></path>
            <path d="M1 12h2"></path>
            <path d="M21 12h2"></path>
            <path d="M4.2 19.8l1.4-1.4"></path>
            <path d="M18.4 5.6l1.4-1.4"></path>
            <circle cx="12" cy="12" r="4"></circle>
          </svg>
          Output & Subtitle
        </h2>
        <div class="muted" style="margin:-6px 0 12px 0">Atur folder output, mode crop, dan opsi subtitle.</div>
        <label title="Default: ~/Videos/ClipAI atau custom path di PC ini.">Lokasi Output</label>
        <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;">
          <label style="display:flex;gap:6px;align-items:center;white-space:nowrap;flex:0 0 auto;" title="Pakai default folder."><input type="radio" name="outMode" value="default" checked /> Default</label>
          <label style="display:flex;gap:6px;align-items:center;white-space:nowrap;flex:0 0 auto;" title="Tulis path folder custom."><input type="radio" name="outMode" value="custom" /> Custom</label>
          <input id="outDir" type="text" placeholder="C:\\path\\to\\folder" title="Folder output di mesin ini." style="flex:1;min-width:200px;" />
        </div>
        <div style="height:10px"></div>
        <div class="row" style="align-items:flex-end;">
          <div style="flex:0 0 160px;">
            <label title="default=middle crop, split untuk facecam bawah.">Crop Mode</label>
            <select id="crop">
              <option value="default">default</option>
              <option value="split_left">split_left</option>
              <option value="split_right">split_right</option>
            </select>
          </div>
          <div style="flex:1;min-width:280px;">
            <label title="Aktifkan subtitle AI (butuh download model).">Subtitle</label>
            <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
              <label style="display:flex;gap:6px;align-items:center;white-space:nowrap;"><input id="subOn" type="checkbox" /> ON</label>
              <select id="model" title="Ukuran model Faster-Whisper." style="flex:1;min-width:100px;">
                <option>tiny</option>
                <option>base</option>
                <option selected>small</option>
                <option>medium</option>
                <option>large-v3</option>
              </select>
              <select id="subPos" title="Posisi subtitle: bawah / tengah / atas." style="flex:0 0 90px;">
                <option value="bottom">Bawah</option>
                <option value="middle" selected>Tengah</option>
                <option value="top">Atas</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <div class="card">
        <h2>
          <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M12 5v14"></path>
            <path d="M5 12h14"></path>
          </svg>
          Tambah Segmen Manual
        </h2>
        <div class="muted" style="margin:-6px 0 12px 0">Kalau mau klip bagian tertentu, isi start/end lalu Tambah. Segmen akan muncul di tabel Segmen.</div>
        <label title="Rentang waktu klip manual (detik).">Start / End (manual)</label>
        <div class="row">
          <input id="sStart" type="number" min="0" step="1" title="Start detik." />
          <input id="sEnd" type="number" min="0" step="1" title="End detik." />
        </div>
        <div style="height:10px"></div>
        <div class="row">
          <button class="btn" id="addSeg" title="Tambah segmen manual dari input start/end.">
            <span class="btnLabel">
              <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M12 5v14"></path>
                <path d="M5 12h14"></path>
              </svg>
              <span>Tambah</span>
            </span>
          </button>
          <button class="btn danger" id="clearSeg" title="Hapus semua segmen.">
            <span class="btnLabel">
              <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M3 6h18"></path>
                <path d="M8 6V4h8v2"></path>
                <path d="M19 6l-1 14H6L5 6"></path>
                <path d="M10 11v6"></path>
                <path d="M14 11v6"></path>
              </svg>
              <span>Clear</span>
            </span>
          </button>
        </div>
      </div>

      <div class="card">
        <h2>
          <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M12 2l1.8 5.2L19 9l-5.2 1.8L12 16l-1.8-5.2L5 9l5.2-1.8L12 2z"></path>
            <path d="M19 14l.9 2.6L22 18l-2.1.7L19 21l-.9-2.3L16 18l2.1-.7L19 14z"></path>
          </svg>
          Proses
        </h2>
        <div class="muted" style="margin:-6px 0 12px 0">Review dulu ringkasan, lalu proses. Progress dan log tampil di bawah.</div>
        <div class="row">
          <button class="btn primary" id="review" title="Tampilkan ringkasan dan konfirmasi sebelum proses.">
            <span class="btnLabel">
              <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M9 11l3 3L22 4"></path>
                <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
              </svg>
              <span>Review & Proses</span>
            </span>
          </button>
        </div>
        <div style="height:12px"></div>
        <div class="progress"><div class="bar" id="bar"></div></div>
        <div class="row" style="margin-top:8px">
          <div class="muted" id="status">Idle</div>
          <div class="muted" id="eta" style="text-align:right"></div>
        </div>
        <pre id="log" class="mono"></pre>
      </div>
    </div>
  </div>

  <div class="modal" id="modal">
    <div class="box">
      <h3>Konfirmasi</h3>
      <pre id="summary" class="mono" style="height:260px"></pre>
      <div class="row">
        <button class="btn" id="closeModal">
          <span class="btnLabel">
            <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <path d="M7 10l5 5 5-5"></path>
              <path d="M12 15V3"></path>
            </svg>
            <span>Ubah Settings</span>
          </span>
        </button>
        <button class="btn primary" id="go">
          <span class="btnLabel">
            <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M8 5v14l11-7z"></path>
            </svg>
            <span>Proses Sekarang</span>
          </span>
        </button>
      </div>
    </div>
  </div>

  <div class="modal" id="segModal">
    <div class="box">
      <h3>Preview Heatmap</h3>
      <div class="muted" id="segMeta"></div>
      <div style="height:10px"></div>
      <div class="player">
        <div id="segPlayer"></div>
      </div>
      <div style="height:10px"></div>
      <div class="row">
        <label style="display:flex;gap:8px;align-items:center;justify-content:flex-end" title="Aktif/nonaktif segmen ini untuk diproses.">
          <input id="segEnabled" type="checkbox" />
          Enable segmen
        </label>
      </div>
      <div style="height:12px"></div>
      <h3 style="margin:0 0 10px 0">Edit Segment</h3>
      <div class="row">
        <div>
          <label title="Format: detik (123) atau MM:SS atau HH:MM:SS">Start</label>
          <input id="segEditStart" type="text" placeholder="MM:SS" />
        </div>
        <div>
          <label title="Format: detik (123) atau MM:SS atau HH:MM:SS">End</label>
          <input id="segEditEnd" type="text" placeholder="MM:SS" />
        </div>
      </div>
      <div style="height:10px"></div>
      <div class="row">
        <button class="btn" id="segSetStartNow" title="Set start = posisi player saat ini.">
          <span class="btnLabel">
            <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M12 8v8"></path>
              <path d="M8 12h8"></path>
              <circle cx="12" cy="12" r="10"></circle>
            </svg>
            <span>Set Start = Now</span>
          </span>
        </button>
        <button class="btn" id="segSetEndNow" title="Set end = posisi player saat ini.">
          <span class="btnLabel">
            <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M12 7v10"></path>
              <path d="M8 12h8"></path>
              <path d="M12 2a10 10 0 1 1 0 20"></path>
            </svg>
            <span>Set End = Now</span>
          </span>
        </button>
        <button class="btn primary" id="segApply" title="Terapkan perubahan start/end ke segmen.">
          <span class="btnLabel">
            <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M9 11l3 3L22 4"></path>
              <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
            </svg>
            <span>Apply</span>
          </span>
        </button>
      </div>
      <div style="height:12px"></div>
      <div class="row">
        <button class="btn" id="segClose">
          <span class="btnLabel">
            <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M18 6L6 18"></path>
              <path d="M6 6l12 12"></path>
            </svg>
            <span>Tutup</span>
          </span>
        </button>
        <button class="btn primary" id="segUse" title="Pakai start/end ini ke input manual.">
          <span class="btnLabel">
            <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M12 5v14"></path>
              <path d="M5 12h14"></path>
            </svg>
            <span>Pakai ke Manual</span>
          </span>
        </button>
      </div>
    </div>
  </div>

  <script>
    const $ = (id) => document.getElementById(id);
    const fmt = (sec) => {
      sec = Math.max(0, Math.floor(sec||0));
      const h = Math.floor(sec/3600);
      const m = Math.floor((sec%3600)/60);
      const s = sec%60;
      if (h>0) return String(h).padStart(2,'0')+':'+String(m).padStart(2,'0')+':'+String(s).padStart(2,'0');
      return String(m).padStart(2,'0')+':'+String(s).padStart(2,'0');
    };

    const parseTime = (raw) => {
      const s = String(raw || '').trim();
      if (!s) return null;
      if (/^\d+$/.test(s)) return parseInt(s, 10);
      const parts = s.split(':').map(x => x.trim());
      if (parts.some(p => p === '' || !/^\d+$/.test(p))) return null;
      if (parts.length === 2) {
        const mm = parseInt(parts[0], 10);
        const ss = parseInt(parts[1], 10);
        return mm * 60 + ss;
      }
      if (parts.length === 3) {
        const hh = parseInt(parts[0], 10);
        const mm = parseInt(parts[1], 10);
        const ss = parseInt(parts[2], 10);
        return hh * 3600 + mm * 60 + ss;
      }
      return null;
    };

    const syncRangeFill = (el) => {
      if (!el) return;
      const min = parseFloat(el.min || '0');
      const max = parseFloat(el.max || '0');
      const val = parseFloat(el.value || '0');
      const denom = (max - min);
      const pct = denom > 0 ? ((val - min) / denom) * 100 : 0;
      el.style.setProperty('--pct', String(Math.max(0, Math.min(100, pct))) + '%');
    };

    let durationSec = 0;
    let segments = [];
    let jobId = null;
    let pollTimer = null;
    let player = null;
    let playerReady = false;
    let previewStopAt = null;
    let activeSegIdx = null;
    let currentVideoId = null;

    let segPlayer = null;
    let segStart = 0;
    let segEnd = 0;

    const setHeatmapLoading = (on) => {
      const btn = $('loadHeatmap');
      const spin = $('heatmapSpin');
      const txt = $('heatmapText');
      if (btn) btn.disabled = !!on;
      if (spin) spin.style.display = on ? 'inline-block' : 'none';
      if (txt) txt.textContent = on ? 'Loading...' : 'Load Heatmap';
    };

    const cfgKey = 'ytclipper_web_cfg_v1';
    const loadLocalCfg = () => {
      try { return JSON.parse(localStorage.getItem(cfgKey) || '{}') || {}; } catch { return {}; }
    };
    const saveLocalCfg = (obj) => {
      try { localStorage.setItem(cfgKey, JSON.stringify(obj||{})); } catch {}
    };

    const applyCfg = (cfg) => {
      if (cfg.output_mode) document.querySelectorAll('input[name="outMode"]').forEach(r => r.checked = (r.value === cfg.output_mode));
      if (cfg.output_dir) $('outDir').value = cfg.output_dir;
      if (cfg.crop_mode) $('crop').value = cfg.crop_mode;
      if (cfg.use_subtitle !== undefined) $('subOn').checked = !!cfg.use_subtitle;
      if (cfg.whisper_model) $('model').value = cfg.whisper_model;
      if (cfg.subtitle_position) $('subPos').value = cfg.subtitle_position;
      if (cfg.preview_seconds) $('previewSecs').value = cfg.preview_seconds;
      syncOutMode();
      syncSub();
    };

    const collectCfg = () => ({
      output_mode: document.querySelector('input[name="outMode"]:checked')?.value || 'default',
      output_dir: $('outDir').value.trim(),
      crop_mode: $('crop').value,
      use_subtitle: $('subOn').checked,
      whisper_model: $('model').value,
      subtitle_position: $('subPos').value,
      preview_seconds: parseInt($('previewSecs').value || '30', 10)
    });

    const persistCfg = async () => {
      const cfg = collectCfg();
      saveLocalCfg(cfg);
      try {
        await fetch('/api/config', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(cfg) });
      } catch {}
    };

    const syncOutMode = () => {
      const mode = document.querySelector('input[name="outMode"]:checked')?.value || 'default';
      $('outDir').disabled = (mode === 'default');
      if (mode === 'default') $('outDir').placeholder = 'Default: ~/Videos/ClipAI';
    };

    const syncSub = () => {
      $('model').disabled = !$('subOn').checked;
      $('subPos').disabled = !$('subOn').checked;
    };

    const ensureYTApi = (() => {
      let p = null;
      return () => {
        if (window.YT && window.YT.Player) return Promise.resolve();
        if (p) return p;
        p = new Promise((resolve) => {
          const tag = document.createElement('script');
          tag.src = "https://www.youtube.com/iframe_api";
          document.head.appendChild(tag);
          const t = setInterval(() => {
            if (window.YT && window.YT.Player) { clearInterval(t); resolve(); }
          }, 80);
        });
        return p;
      };
    })();

    const renderSegs = () => {
      const tbody = $('segTable').querySelector('tbody');
      tbody.innerHTML = '';
      segments.forEach((s, idx) => {
        const tr = document.createElement('tr');
        if (activeSegIdx === idx) tr.classList.add('activeSeg');
        const dur = Math.max(0, (s.end|0)-(s.start|0));
        const score = (s.score === undefined || s.score === null) ? '-' : Number(s.score).toFixed(2);
        tr.innerHTML = `
          <td><input type="checkbox" ${s.enabled?'checked':''} data-idx="${idx}" class="segOn" /></td>
          <td>${fmt(s.start)}</td>
          <td>${fmt(s.end)}</td>
          <td>${fmt(dur)}</td>
          <td>${score}</td>
          <td>
            <button class="btn segPrev" data-idx="${idx}" title="Preview segmen (modal).">Preview</button>
            <button class="btn danger segDel" data-idx="${idx}" title="Hapus segmen ini.">Del</button>
          </td>
        `;
        tbody.appendChild(tr);
      });
      const enabledCount = segments.reduce((acc, s) => acc + (s && s.enabled ? 1 : 0), 0);
      const totalCount = segments.length;
      const pickInfo = $('segPickInfo');
      if (pickInfo) pickInfo.textContent = totalCount ? (`Dipilih ${enabledCount} / ${totalCount}`) : '';
      const selAllBtn = $('segSelectAll');
      const deselAllBtn = $('segDeselectAll');
      if (selAllBtn) selAllBtn.disabled = !totalCount || enabledCount === totalCount;
      if (deselAllBtn) deselAllBtn.disabled = !totalCount || enabledCount === 0;
      if (activeSegIdx !== null && segments[activeSegIdx] && $('segEnabled')) {
        $('segEnabled').checked = !!segments[activeSegIdx].enabled;
      }
      tbody.querySelectorAll('.segOn').forEach(cb => cb.addEventListener('change', (e) => {
        const i = parseInt(e.target.dataset.idx, 10);
        segments[i].enabled = !!e.target.checked;
        persistCfg();
      }));
      tbody.querySelectorAll('.segPrev').forEach(btn => btn.addEventListener('click', (e) => {
        const i = parseInt(e.target.dataset.idx, 10);
        openSegPreview(i);
      }));
      tbody.querySelectorAll('.segDel').forEach(btn => btn.addEventListener('click', (e) => {
        const i = parseInt(e.target.dataset.idx, 10);
        segments.splice(i, 1);
        renderSegs();
      }));
    };

    const openSegModal = () => { $('segModal').classList.add('on'); };
    const closeSegModal = () => { $('segModal').classList.remove('on'); };

    const destroySegPlayer = () => {
      try { if (segPlayer && segPlayer.destroy) segPlayer.destroy(); } catch {}
      segPlayer = null;
      const holder = $('segPlayer');
      if (holder) holder.innerHTML = '';
      segStart = 0;
      segEnd = 0;
    };

    const openSegPreview = async (idx) => {
      const s = segments[idx];
      if (!s) return;
      if (!currentVideoId) {
        try {
          await loadInfo();
        } catch (e) {
          alert(e.message);
          return;
        }
      }

      const start = Math.max(0, parseInt(s.start || 0, 10));
      const end = Math.max(0, parseInt(s.end || 0, 10));
      if (end <= start) {
        alert('Segmen tidak valid (end <= start).');
        return;
      }

      activeSegIdx = idx;
      renderSegs();

      $('segEnabled').checked = !!s.enabled;
      $('segMeta').textContent = `Segmen #${idx+1} • ${fmt(start)} - ${fmt(end)} • Dur ${fmt(end-start)} • Score ${s.score === undefined ? '-' : Number(s.score).toFixed(2)}`;

      segStart = start;
      segEnd = end;
      $('segEditStart').value = fmt(start);
      $('segEditEnd').value = fmt(end);

      destroySegPlayer();
      openSegModal();

      await ensureYTApi();
      segPlayer = new YT.Player('segPlayer', {
        height: '100%',
        width: '100%',
        videoId: currentVideoId,
        playerVars: { controls: 1, rel: 0, modestbranding: 1, fs: 1, start: start, end: end },
        events: {
          onReady: (e) => {
            try { e.target.setPlaybackQuality('large'); } catch {}
            try { e.target.seekTo(start, true); } catch {}
          }
        }
      });
    };

    const applySegEdit = async () => {
      if (activeSegIdx === null) return;
      const s = segments[activeSegIdx];
      if (!s) return;

      const rawStart = $('segEditStart').value;
      const rawEnd = $('segEditEnd').value;
      const start = parseTime(rawStart);
      const end = parseTime(rawEnd);

      if (start === null || end === null) {
        alert('Format Start/End tidak valid. Pakai detik (123) atau MM:SS atau HH:MM:SS.');
        return;
      }
      if (start < 0 || end < 0) {
        alert('Durasi tidak boleh negatif.');
        return;
      }
      if (durationSec > 0 && (start > durationSec || end > durationSec)) {
        alert('Start/End melebihi durasi video.');
        return;
      }
      if (end <= start) {
        alert('End harus lebih besar dari Start.');
        return;
      }

      s.start = start;
      s.end = end;
      segments[activeSegIdx] = s;
      renderSegs();
      persistCfg();
      try {
        await openSegPreview(activeSegIdx);
      } catch (e) {
        alert(e && e.message ? e.message : 'Gagal menerapkan perubahan segmen.');
      }
    };

    const validateUrl = () => {
      const u = $('url').value.trim();
      if (!u) throw new Error('YouTube URL wajib diisi.');
      return u;
    };

    const validateOutDir = () => {
      const mode = document.querySelector('input[name="outMode"]:checked')?.value || 'default';
      if (mode === 'default') return null;
      const p = $('outDir').value.trim();
      if (!p) throw new Error('Output folder custom tidak boleh kosong.');
      return p;
    };

    const validateSegments = () => {
      const segs = segments.filter(s => s.enabled);
      if (!segs.length) throw new Error('Minimal 1 segmen harus aktif.');
      for (const s of segs) {
        if (s.start < 0 || s.end < 0) throw new Error('Durasi tidak boleh negatif.');
        if (s.end <= s.start) throw new Error('End harus lebih besar dari Start.');
      }
      return segs;
    };

    const fillSummary = () => {
      const segs = validateSegments();
      const outMode = document.querySelector('input[name="outMode"]:checked')?.value || 'default';
      const outDir = outMode === 'default' ? '{{ default_output_dir }}' : $('outDir').value.trim();
      const crop = $('crop').value;
      const subOn = $('subOn').checked;
      const model = $('model').value;
      let totalSec = 0;
      for (const s of segs) totalSec += Math.max(0, (s.end|0)-(s.start|0));
      const estMB = (totalSec * 2600000 / 8) / (1024*1024);
      const lines = [];
      lines.push('Lokasi output: ' + outDir);
      lines.push('Crop mode: ' + crop);
      lines.push('Subtitle: ' + (subOn ? ('ON (Model: '+model+')') : 'OFF'));
      lines.push('');
      lines.push('Daftar klip:');
      segs.forEach((s, i) => lines.push((i+1)+'. '+fmt(s.start)+' - '+fmt(s.end)));
      lines.push('');
      lines.push('Estimasi ukuran total (kasar): ' + estMB.toFixed(1) + ' MB');
      $('summary').textContent = lines.join('\\n');
    };

    const setLog = (text) => {
      $('log').textContent = text || '';
      $('log').scrollTop = $('log').scrollHeight;
    };

    const setProgress = (p, status, eta, isActive = true) => {
      const pct = Math.max(0, Math.min(100, p||0));
      const bar = $('bar');
      bar.style.width = pct.toFixed(1) + '%';
      $('status').textContent = (status||'') + ' (' + pct.toFixed(0) + '%)';
      $('eta').textContent = eta ? ('ETA ~ ' + eta) : '';
      // Toggle animasi bergelombang
      if (isActive && pct < 100) {
        bar.classList.add('active');
      } else {
        bar.classList.remove('active');
      }
    };

    const poll = async () => {
      if (!jobId) return;
      try {
        const res = await fetch('/api/status/' + jobId);
        const data = await res.json();
        if (!data.ok) return;
        const isRunning = data.running && !data.done;
        setProgress(data.percent, data.status, data.eta, isRunning);
        // Tampilkan error message di log jika ada
        let logText = data.logs || '';
        if (data.error) {
          logText += '\\n\\n❌ ERROR: ' + data.error;
        }
        setLog(logText);
        if (data.done) {
          clearInterval(pollTimer);
          pollTimer = null;
          // Alert jika error
          if (data.error) {
            alert('❌ Proses gagal!\\n\\n' + data.error);
          } else if (data.success_count > 0) {
            alert('✅ Selesai! ' + data.success_count + ' clip berhasil dibuat.\\n\\nOutput: ' + (data.output_dir || ''));
          }
        }
      } catch {}
    };

    const startJob = async () => {
      const url = validateUrl();
      const segs = validateSegments();
      const outMode = document.querySelector('input[name="outMode"]:checked')?.value || 'default';
      const outDir = outMode === 'default' ? null : validateOutDir();
      const payload = {
        url,
        segments: segs,
        crop_mode: $('crop').value,
        use_subtitle: $('subOn').checked,
        whisper_model: $('model').value,
        subtitle_position: $('subPos').value,
        output_dir: outDir
      };
      setLog('🚀 Memulai proses...');
      setProgress(0, 'Memulai...', '', true);
      const res = await fetch('/api/start', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || 'Gagal start job');
      jobId = data.job_id;
      if (pollTimer) clearInterval(pollTimer);
      pollTimer = setInterval(poll, 700);
      await poll();
    };

    const applyVideoInfo = (data) => {
      durationSec = data.duration_seconds|0;
      currentVideoId = data.video_id;
      $('timeline').max = String(durationSec);
      $('tDur').textContent = fmt(durationSec);
      $('info').textContent = 'Durasi: ' + fmt(durationSec);
      $('sStart').value = '0';
      $('sEnd').value = String(Math.min(30, durationSec));
      loadPlayer(data.video_id);
      syncRangeFill($('timeline'));
    };

    const loadInfo = async () => {
      const url = validateUrl();
      const res = await fetch('/api/video_info', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({url}) });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || 'Gagal load info');
      applyVideoInfo(data);
      persistCfg();
    };

    const waitMainPlayer = async () => {
      for (let i = 0; i < 50; i++) {
        if (player && player.getCurrentTime && player.getPlayerState) return true;
        await new Promise(r => setTimeout(r, 80));
      }
      return false;
    };

    const loadHeatmap = async () => {
      const url = validateUrl();

      const infoRes = await fetch('/api/video_info', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({url}) });
      const infoData = await infoRes.json();
      if (!infoData.ok) throw new Error(infoData.error || 'Gagal load info');

      const nextVideoId = infoData.video_id;
      const shouldSwitchVideo = (!currentVideoId) || (String(currentVideoId) !== String(nextVideoId));
      if (shouldSwitchVideo) {
        segments = [];
        activeSegIdx = null;
        renderSegs();
      }
      applyVideoInfo(infoData);
      persistCfg();

      const res = await fetch('/api/heatmap', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({url}) });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || 'Gagal load heatmap');
      segments = data.segments || [];
      if (!segments.length) throw new Error('Heatmap kosong: video ini tidak punya Most Replayed, atau parsing gagal.');
      activeSegIdx = null;
      renderSegs();
    };

    const addSeg = () => {
      const s = parseInt(($('sStart').value||'0'), 10);
      const e = parseInt(($('sEnd').value||'0'), 10);
      if (Number.isNaN(s) || Number.isNaN(e)) throw new Error('Start/End harus angka.');
      if (s < 0 || e < 0) throw new Error('Durasi tidak boleh negatif.');
      if (e <= s) throw new Error('End harus lebih besar dari Start.');
      if (durationSec > 0 && e > durationSec) throw new Error('End melebihi durasi video.');
      segments.push({ enabled:true, start:s, end:e });
      segments.sort((a,b) => (a.start-b.start) || (a.end-b.end));
      renderSegs();
    };

    const openModal = () => { $('modal').classList.add('on'); };
    const closeModal = () => { $('modal').classList.remove('on'); };

    document.querySelectorAll('input[name="outMode"]').forEach(r => r.addEventListener('change', () => { syncOutMode(); persistCfg(); }));
    $('outDir').addEventListener('change', persistCfg);
    $('crop').addEventListener('change', persistCfg);
    $('subOn').addEventListener('change', () => { syncSub(); persistCfg(); });
    $('model').addEventListener('change', persistCfg);
    $('previewSecs').addEventListener('change', persistCfg);

    $('openYT').addEventListener('click', () => window.open($('url').value.trim() || 'https://youtube.com', '_blank'));
    $('loadHeatmap').addEventListener('click', async () => {
      setHeatmapLoading(true);
      try {
        await loadHeatmap();
      } catch(e){
        alert(e.message);
      } finally {
        setHeatmapLoading(false);
      }
    });
    $('segSelectAll').addEventListener('click', () => {
      segments.forEach(s => { if (s) s.enabled = true; });
      renderSegs();
      persistCfg();
    });
    $('segDeselectAll').addEventListener('click', () => {
      segments.forEach(s => { if (s) s.enabled = false; });
      activeSegIdx = null;
      renderSegs();
      persistCfg();
    });
    $('addSeg').addEventListener('click', async () => {
      try {
        if (!durationSec) await loadInfo();
        addSeg();
      } catch(e){
        alert(e.message);
      }
    });
    $('clearSeg').addEventListener('click', () => { segments = []; renderSegs(); });
    $('review').addEventListener('click', () => { try { fillSummary(); openModal(); } catch(e){ alert(e.message); } });
    $('closeModal').addEventListener('click', closeModal);
    $('go').addEventListener('click', async () => {
      try {
        closeModal();
        await startJob();
      } catch(e) {
        alert(e.message);
      }
    });

    $('timeline').addEventListener('input', () => {
      const v = parseInt($('timeline').value || '0', 10);
      $('tCur').textContent = fmt(v);
      syncRangeFill($('timeline'));
      if (playerReady && player) player.seekTo(v, true);
    });

    $('play').addEventListener('click', async () => {
      try {
        if (!currentVideoId) await loadInfo();
        if (!(await waitMainPlayer())) return;
        const st = player.getPlayerState();
        if (st === 1) player.pauseVideo();
        else player.playVideo();
      } catch (e) {
        alert(e.message);
      }
    });
    $('stop').addEventListener('click', async () => {
      try {
        if (!currentVideoId) await loadInfo();
        if (!(await waitMainPlayer())) return;
        previewStopAt = null;
        player.pauseVideo();
        player.seekTo(0, true);
      } catch (e) {
        alert(e.message);
      }
    });
    $('playPreview').addEventListener('click', async () => {
      try {
        if (!currentVideoId) await loadInfo();
        if (!(await waitMainPlayer())) return;
        const s = parseInt(($('previewSecs').value||'30'), 10);
        if (Number.isNaN(s) || s < 5 || s > 600) { alert('Preview detik harus 5-600'); return; }
        previewStopAt = s;
        player.seekTo(0, true);
        player.playVideo();
      } catch (e) {
        alert(e.message);
      }
    });

    $('segEnabled').addEventListener('change', () => {
      if (activeSegIdx === null) return;
      if (!segments[activeSegIdx]) return;
      segments[activeSegIdx].enabled = !!$('segEnabled').checked;
      renderSegs();
      persistCfg();
    });

    $('segSetStartNow').addEventListener('click', () => {
      if (!segPlayer || !segPlayer.getCurrentTime) return;
      try {
        const ct = Math.floor(segPlayer.getCurrentTime() || 0);
        $('segEditStart').value = fmt(ct);
      } catch {}
    });

    $('segSetEndNow').addEventListener('click', () => {
      if (!segPlayer || !segPlayer.getCurrentTime) return;
      try {
        const ct = Math.floor(segPlayer.getCurrentTime() || 0);
        $('segEditEnd').value = fmt(ct);
      } catch {}
    });

    $('segApply').addEventListener('click', applySegEdit);

    $('segUse').addEventListener('click', () => {
      if (activeSegIdx === null) return;
      const s = segments[activeSegIdx];
      if (!s) return;
      $('sStart').value = String(Math.max(0, parseInt(s.start||0, 10)));
      $('sEnd').value = String(Math.max(0, parseInt(s.end||0, 10)));
      closeSegModal();
      destroySegPlayer();
    });

    $('segClose').addEventListener('click', () => {
      closeSegModal();
      destroySegPlayer();
    });

    window.onYouTubeIframeAPIReady = function() {
      playerReady = true;
    };

    const loadPlayer = (videoId) => {
      ensureYTApi().then(() => {
        if (player && player.getVideoData && player.loadVideoById) {
          const curId = player.getVideoData()?.video_id;
          if (String(curId) !== String(videoId)) {
            try { player.loadVideoById(videoId); } catch {}
          }
          return;
        }

        try { if (player && player.destroy) player.destroy(); } catch {}
        const holder = $('player');
        if (holder) holder.innerHTML = '';

        player = new YT.Player('player', {
          height: '100%',
          width: '100%',
          videoId: videoId,
          playerVars: { controls: 1, rel: 0, modestbranding: 1, fs: 1 },
          events: {
            onReady: (e) => {
              playerReady = true;
              try { e.target.setPlaybackQuality('large'); } catch {}
              const tick = () => {
                try {
                  if (!player) return;
                  const ct = player.getCurrentTime ? player.getCurrentTime() : 0;
                  $('timeline').value = String(Math.floor(ct));
                  syncRangeFill($('timeline'));
                  $('tCur').textContent = fmt(ct);
                  if (previewStopAt !== null && ct >= previewStopAt) {
                    player.pauseVideo();
                    previewStopAt = null;
                  }
                } catch {}
                requestAnimationFrame(tick);
              };
              requestAnimationFrame(tick);
            }
          }
        });
      });
    };

    (async () => {
      const serverCfg = await fetch('/api/config').then(r=>r.json()).catch(()=>({}));
      const localCfg = loadLocalCfg();
      applyCfg(Object.assign({}, serverCfg, localCfg, { output_dir: localCfg.output_dir || serverCfg.output_dir || '{{ default_output_dir }}' }));
      if (!$('previewSecs').value) $('previewSecs').value = '30';
      $('url').value = '';
      syncRangeFill($('timeline'));
      renderSegs();
    })();
  </script>
</body>
</html>
"""


@app.get("/")
def home():
    return render_template_string(HTML, default_output_dir=_default_output_dir())


@app.get("/api/config")
def api_get_config():
    cfg = _load_config()
    if "output_dir" not in cfg:
        cfg["output_dir"] = _default_output_dir()
    if "output_mode" not in cfg:
        cfg["output_mode"] = "default"
    if "preview_seconds" not in cfg:
        cfg["preview_seconds"] = 30
    if "subtitle_position" not in cfg:
        cfg["subtitle_position"] = "middle"
    return jsonify(cfg)


@app.post("/api/config")
def api_set_config():
    data = request.get_json(silent=True) or {}
    cfg = _load_config()
    for k in ("output_mode", "output_dir", "crop_mode", "use_subtitle", "whisper_model", "subtitle_position", "preview_seconds"):
        if k in data:
            cfg[k] = data[k]
    _save_config(cfg)
    return jsonify({"ok": True})


@app.post("/api/video_info")
def api_video_info():
    data = request.get_json(silent=True) or {}
    url = str(data.get("url", "")).strip()
    video_id = extract_video_id(url)
    if not video_id:
        return jsonify({"ok": False, "error": "Link YouTube tidak valid."})
    try:
        duration_seconds = int(get_duration(video_id))
        return jsonify({"ok": True, "video_id": video_id, "duration_seconds": duration_seconds})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.post("/api/heatmap")
def api_heatmap():
    data = request.get_json(silent=True) or {}
    url = str(data.get("url", "")).strip()
    video_id = extract_video_id(url)
    if not video_id:
        return jsonify({"ok": False, "error": "Link YouTube tidak valid."})
    try:
        heatmap = ambil_most_replayed(video_id)
        segs = []
        for it in heatmap:
            s = int(float(it.get("start", 0)))
            d = int(float(it.get("duration", 0)))
            if d <= 0:
                continue
            segs.append({"enabled": True, "start": s, "end": s + d, "score": float(it.get("score", 0))})
        if not segs:
            return jsonify({
                "ok": False,
                "error": "Heatmap tidak ditemukan untuk video ini. Bisa jadi videonya memang tidak punya Most Replayed, atau YouTube lagi ganti format halaman.",
            })
        return jsonify({"ok": True, "segments": segs})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.post("/api/start")
def api_start():
    data = request.get_json(silent=True) or {}
    url = str(data.get("url", "")).strip()
    crop_mode = str(data.get("crop_mode", "default")).strip() or "default"
    use_subtitle = bool(data.get("use_subtitle", False))
    whisper_model = str(data.get("whisper_model", WHISPER_MODEL)).strip() or WHISPER_MODEL
    subtitle_position = str(data.get("subtitle_position", "middle")).strip().lower() or "middle"
    if subtitle_position not in ("bottom", "middle", "top"):
        subtitle_position = "middle"
    output_dir = data.get("output_dir")
    if output_dir is None or str(output_dir).strip() == "":
        output_dir = _default_output_dir()
    else:
        output_dir = str(output_dir).strip()

    segments = data.get("segments", [])
    if not isinstance(segments, list):
        return jsonify({"ok": False, "error": "segments harus array."})

    cleaned = []
    for s in segments:
        if not isinstance(s, dict):
            continue
        enabled = bool(s.get("enabled", True))
        try:
            start = float(s.get("start", 0))
            end = float(s.get("end", 0))
        except Exception:
            return jsonify({"ok": False, "error": "start/end harus angka."})
        cleaned.append({"enabled": enabled, "start": start, "end": end})

    enabled_segments = [s for s in cleaned if s.get("enabled", True)]
    if not enabled_segments:
        return jsonify({"ok": False, "error": "Minimal 1 segmen harus aktif."})

    total_sec = 0
    for s in enabled_segments:
        if s["start"] < 0 or s["end"] < 0:
            return jsonify({"ok": False, "error": "Durasi tidak boleh negatif."})
        if s["end"] <= s["start"]:
            return jsonify({"ok": False, "error": "End harus lebih besar dari Start."})
        total_sec += int(max(0, s["end"] - s["start"]))
    est_bytes = _estimate_total_size_bytes(total_sec)

    job_id = uuid.uuid4().hex
    job = {
        "id": job_id,
        "running": False,
        "done": False,
        "percent": 0.0,
        "stage": "queued",
        "status": "Queued",
        "eta": "",
        "error": None,
        "logs": [],
        "created_at": time.time(),
        "output_dir": output_dir,
        "success_count": 0
    }

    with _JOBS_LOCK:
        _JOBS[job_id] = job

    payload = {
        "url": url,
        "segments": cleaned,
        "crop_mode": crop_mode if crop_mode in ("default", "split_left", "split_right") else "default",
        "use_subtitle": use_subtitle,
        "whisper_model": whisper_model,
        "subtitle_position": subtitle_position,
        "output_dir": output_dir,
        "apply_padding": False,
        "total_clips": len(enabled_segments)
    }

    t = threading.Thread(target=_run_job, args=(job_id, payload), daemon=True)
    t.start()

    cfg = _load_config()
    cfg["output_dir"] = output_dir
    cfg["output_mode"] = "custom" if data.get("output_dir") else "default"
    cfg["crop_mode"] = payload["crop_mode"]
    cfg["use_subtitle"] = use_subtitle
    cfg["whisper_model"] = whisper_model
    cfg["subtitle_position"] = subtitle_position
    _save_config(cfg)

    return jsonify({"ok": True, "job_id": job_id, "estimated_bytes": est_bytes})


@app.get("/api/status/<job_id>")
def api_status(job_id):
    job = _get_job(job_id)
    if not job:
        return jsonify({"ok": False})
    logs = "".join(job.get("logs", [])[-2500:])
    return jsonify({
        "ok": True,
        "running": bool(job.get("running", False)),
        "done": bool(job.get("done", False)),
        "percent": float(job.get("percent", 0.0)),
        "status": str(job.get("status", "")),
        "stage": str(job.get("stage", "")),
        "eta": str(job.get("eta", "")),
        "error": job.get("error"),
        "output_dir": job.get("output_dir"),
        "success_count": int(job.get("success_count", 0)),
        "logs": logs
    })


if __name__ == "__main__":
    # Default debug=True untuk hot reload saat development
    debug = str(os.environ.get("FLASK_DEBUG", "1")).lower() not in ("0", "false", "no", "off")
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    print(f"🚀 Server running at http://{host}:{port}")
    print(f"🔥 Hot reload: {'ON' if debug else 'OFF'} (set FLASK_DEBUG=0 to disable)")
    app.run(host=host, port=port, debug=debug, use_reloader=debug)

