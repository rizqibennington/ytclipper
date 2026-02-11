import os
import subprocess
import sys
import uuid
from datetime import datetime

from config_store import default_output_dir
from core_constants import BOTTOM_HEIGHT, MAX_DURATION, PADDING, TOP_HEIGHT
from ffmpeg_deps import cek_dependensi
from subtitle_ai import generate_subtitle, set_whisper_model
from yt_info import extract_video_id, get_duration


def unique_path(folder, stem, ext):
    base = f"{stem}{ext}"
    path = os.path.join(folder, base)
    if not os.path.exists(path):
        return path
    for i in range(2, 10000):
        path = os.path.join(folder, f"{stem}_{i}{ext}")
        if not os.path.exists(path):
            return path
    raise RuntimeError("Gagal membuat nama file output unik.")


def format_hhmmss(seconds):
    seconds = max(0, int(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def estimate_total_size_bytes(total_seconds):
    bitrate_bps = 2_600_000
    return int(max(0, total_seconds) * (bitrate_bps / 8))


def _fmt_time(s):
    m = int(s // 60)
    sec = int(s % 60)
    return f"{m}:{sec:02d}"


def proses_satu_clip(
    video_id,
    item,
    index,
    total_duration,
    crop_mode="default",
    use_subtitle=False,
    subtitle_position="middle",
    output_dir=None,
    apply_padding=True,
    event_cb=None,
):
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

    max_end = start + float(MAX_DURATION)
    if end > max_end:
        end = max_end

    duration = end - start
    print(f"\n{'='*40}")
    print(f"🎬 Clip #{index}: {_fmt_time(start)} → {_fmt_time(end)} ({duration:.0f}s)")

    if duration < 1:
        print(f"⚠️ Skip - durasi terlalu pendek ({duration:.1f}s)")
        return False

    if output_dir is None:
        output_dir = default_output_dir()
    os.makedirs(output_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = uuid.uuid4().hex[:8]
    stem = f"clip_{index}_{ts}_{tag}"
    temp_file = unique_path(output_dir, f"temp_{index}_{ts}_{tag}", ".mp4")
    cropped_file = unique_path(output_dir, f"temp_cropped_{index}_{ts}_{tag}", ".mp4")
    subtitle_file = unique_path(output_dir, f"temp_{index}_{ts}_{tag}", ".srt")
    output_file = unique_path(output_dir, stem, ".mp4")

    cmd_download = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--force-ipv4",
        "--quiet",
        "--no-warnings",
        "--downloader",
        "ffmpeg",
        "--downloader-args",
        f"ffmpeg_i:-ss {start} -to {end} -hide_banner -loglevel error",
        "-f",
        "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "-o",
        temp_file,
        f"https://youtu.be/{video_id}",
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
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                temp_file,
                "-vf",
                "scale=-2:1280,pad=max(iw\\,720):ih:(ow-iw)/2:0,crop=720:1280:(iw-720)/2:(ih-1280)/2",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "26",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                cropped_file,
            ]
        elif crop_mode == "split_left":
            vf = (
                f"scale='max(720,iw*1280/ih)':1280[scaled];"
                f"[scaled]split=2[s1][s2];"
                f"[s1]crop=720:{TOP_HEIGHT}:(iw-720)/2:0[top];"
                f"[s2]crop=720:{BOTTOM_HEIGHT}:0:{TOP_HEIGHT}[bottom];"
                f"[top][bottom]vstack=inputs=2[out]"
            )
            cmd_crop = [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "warning",
                "-i",
                temp_file,
                "-filter_complex",
                vf,
                "-map",
                "[out]",
                "-map",
                "0:a?",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "26",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                cropped_file,
            ]
        else:
            vf = (
                f"scale='max(720,iw*1280/ih)':1280[scaled];"
                f"[scaled]split=2[s1][s2];"
                f"[s1]crop=720:{TOP_HEIGHT}:(iw-720)/2:0[top];"
                f"[s2]crop=720:{BOTTOM_HEIGHT}:iw-720:{TOP_HEIGHT}[bottom];"
                f"[top][bottom]vstack=inputs=2[out]"
            )
            cmd_crop = [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "warning",
                "-i",
                temp_file,
                "-filter_complex",
                vf,
                "-map",
                "[out]",
                "-map",
                "0:a?",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "26",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                cropped_file,
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
                    "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    cropped_file,
                    "-vf",
                    f"subtitles='{subtitle_path}':force_style='{force_style}'",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-crf",
                    "26",
                    "-c:a",
                    "copy",
                    output_file,
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
    except subprocess.CalledProcessError:
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


def proses_dengan_segmen(
    link,
    segments,
    crop_mode="default",
    use_subtitle=False,
    whisper_model=None,
    subtitle_position="middle",
    output_dir=None,
    apply_padding=False,
    event_cb=None,
):
    if whisper_model:
        set_whisper_model(whisper_model)

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
        output_dir = default_output_dir()
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
        max_end = start + float(MAX_DURATION)
        if end > max_end:
            end = max_end
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
            event_cb=event_cb,
        )
        if ok:
            success += 1

    if success == 0:
        raise RuntimeError("Semua segmen gagal diproses.")

    return {"success_count": success, "output_dir": output_dir}

