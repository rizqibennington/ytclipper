import os
import subprocess
import sys
import uuid
import json
import tempfile
import glob
from datetime import datetime

from app.config_store import default_output_dir
from app.core_constants import BOTTOM_HEIGHT, MAX_DURATION, PADDING, TOP_HEIGHT
from app.ffmpeg_deps import cek_dependensi
from app.subtitle_ai import generate_subtitle
from app.yt_info import extract_video_id, get_duration
from app.services.gemini_service import generate_clip_metadata
from app.yt_utils import get_yt_dlp_cookies_args, get_yt_dlp_proxy_args, normalize_youtube_url


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


def _hex_to_ass_color(hex_color: str) -> str:
    """Konversi format hex RGB (#RRGGBB) ke format warna ASS FFmpeg (&H00BBGGRR)."""
    if not hex_color or not isinstance(hex_color, str):
        return "&H00FFFFFF"
    c = hex_color.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        return "&H00FFFFFF"
    try:
        r = c[0:2]
        g = c[2:4]
        b = c[4:6]
        return f"&H00{b}{g}{r}".upper()
    except Exception:
        return "&H00FFFFFF"


def _escape_filter_value(value):
    # Escape the filter's option value first, then the filter graph.
    for special in ("\\':", "\\'[],;"):
        value = "".join("\\" + ch if ch in special else ch for ch in value)
    return value


def _append_video_filter(cmd, video_filter):
    cmd = cmd.copy()
    if "-vf" in cmd:
        index = cmd.index("-vf") + 1
        cmd[index] += "," + video_filter
    else:
        index = cmd.index("-filter_complex") + 1
        cmd[index] += f";[out]{video_filter}[filtered]"
        cmd[cmd.index("[out]")] = "[filtered]"
    return cmd


def _render_with_progress(cmd, on_progress):
    cmd = [cmd[0], "-nostats", "-progress", "pipe:1", *cmd[1:]]
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8", errors="replace") as stderr:
        with subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=stderr, text=True, encoding="utf-8", errors="replace",
        ) as process:
            try:
                for line in process.stdout:
                    key, _, value = line.strip().partition("=")
                    if key == "out_time_us" and value.lstrip("-").isdigit():
                        on_progress(max(0, int(value)) / 1_000_000)
            except BaseException:
                process.kill()
                raise
            returncode = process.wait()
        if returncode:
            stderr.seek(0)
            raise subprocess.CalledProcessError(returncode, cmd, stderr=stderr.read())


class SubtitleReviewAborted(RuntimeError):
    pass


def proses_satu_clip(
    video_id,
    item,
    index,
    total_duration,
    video_url=None,
    crop_mode="default",
    use_subtitle=False,
    subtitle_language=None,
    subtitle_position="middle",
    subtitle_font_name="Arial Black",
    subtitle_font_size=22,
    subtitle_font_color="#FFFFFF",
    output_dir=None,
    apply_padding=False,
    event_cb=None,
    gemini_api_key=None,
    subtitle_review_cb=None,
    whisper_model=None,
):
    video_id = str(video_id or "").strip().strip("` \t\r\n\"'")
    video_url = normalize_youtube_url(video_url or f"https://youtu.be/{video_id}")

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

    if total_duration is not None:
        start = min(start, total_duration)

    max_end = start + float(MAX_DURATION)
    if end > max_end:
        end = max_end

    duration = end - start
    print(f"\n{'='*40}")
    print(f"🎬 Clip #{index}: {_fmt_time(start)} → {_fmt_time(end)} ({duration:.0f}s)")

    if duration < 1:
        print(f"⚠️ Skip - durasi terlalu pendek ({duration:.1f}s)")
        return False, "Durasi terlalu pendek"

    if output_dir is None:
        output_dir = default_output_dir()
    os.makedirs(output_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = uuid.uuid4().hex[:8]
    stem = f"clip_{index}_{ts}_{tag}"
    temp_base = os.path.join(output_dir, f"temp_{index}_{ts}_{tag}")
    out_tpl = temp_base + ".%(ext)s"
    temp_file = temp_base + ".mp4"
    cropped_file = unique_path(output_dir, f"temp_cropped_{index}_{ts}_{tag}", ".mp4")
    subtitle_file = unique_path(output_dir, f"temp_{index}_{ts}_{tag}", ".srt")
    output_file = unique_path(output_dir, stem, ".mp4")

    format_candidates = [
        "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b/best",
        "bv*+ba/b",
        "bestvideo+bestaudio/best",
        "b/best",
        "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    ]

    player_client_candidates = [
        "ios",
        "android",
        "web_creator,tv_embedded,mweb",
        "tv_simply,mweb",
        "web_safari,mweb",
        "tv,mweb",
    ]

    completed = False
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
                safe_cmd = []
                skip_next = False
                for arg in cmd:
                    if skip_next:
                        skip_next = False
                        continue
                    if arg == "--cookies":
                        safe_cmd.extend(["--cookies", "<cookies-file>"])
                        skip_next = True
                    elif arg == "--cookies-from-browser":
                        safe_cmd.extend(["--cookies-from-browser", "<browser>"])
                        skip_next = True
                    else:
                        safe_cmd.append(str(arg))
                cmd_text = " ".join(safe_cmd)
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
        last_error = None
        downloaded = False
        for player_client in player_client_candidates:
            for fmt in format_candidates:
                cmd_download = [
                    sys.executable,
                    "-m",
                    "yt_dlp",
                    "--quiet",
                    "--no-warnings",
                    "--no-playlist",
                    "--extractor-args",
                    f"youtube:player_client={player_client}",
                    "--downloader",
                    "ffmpeg",
                    "--downloader-args",
                    f"ffmpeg_i:-ss {start} -to {end} -hide_banner -loglevel error",
                    "-f",
                    fmt,
                    "--restrict-filenames",
                    "--js-runtimes",
                    "node",
                ] + get_yt_dlp_cookies_args() + get_yt_dlp_proxy_args() + [
                    "-o",
                    out_tpl,
                    video_url,
                ]
                try:
                    _run(cmd_download, f"download[client={player_client},fmt={fmt}]")
                    last_error = None
                    downloaded = True
                    break
                except subprocess.CalledProcessError as e:
                    last_error = e
            if downloaded:
                break
        if last_error and not downloaded:
            cmd_download = [
                sys.executable,
                "-m",
                "yt_dlp",
                "--quiet",
                "--no-warnings",
                "--no-playlist",
                "--extractor-args",
                "youtube:player_client=ios,android,web_creator",
                "--download-sections",
                f"*{start}-{end}",
                "-f",
                "bv*+ba/b/best",
                "--restrict-filenames",
                "--js-runtimes",
                "node",
            ] + get_yt_dlp_cookies_args() + get_yt_dlp_proxy_args() + [
                "-o",
                out_tpl,
                video_url,
            ]
            try:
                _run(cmd_download, "download[sections]")
                last_error = None
                downloaded = True
            except subprocess.CalledProcessError as e:
                last_error = e
        if last_error and not downloaded:
            raise last_error

        cand = sorted(glob.glob(temp_base + ".*"), key=lambda p: os.path.getmtime(p), reverse=True)
        if cand:
            temp_file = cand[0]
        if not os.path.exists(temp_file):
            return False, "File temp tidak ditemukan setelah download"

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
                "veryfast",
                "-crf",
                "23",
                "-af",
                "loudnorm=I=-14:LRA=7:tp=-1",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                cropped_file,
            ]
        elif crop_mode == "fit":
            vf = (
                "[0:v]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,boxblur=25:5[bg];"
                "[0:v]scale=720:1280:force_original_aspect_ratio=decrease[fg];"
                "[bg][fg]overlay=(W-w)/2:(H-h)/2[out]"
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
                "veryfast",
                "-crf",
                "23",
                "-af",
                "loudnorm=I=-14:LRA=7:tp=-1",
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
                "veryfast",
                "-crf",
                "23",
                "-af",
                "loudnorm=I=-14:LRA=7:tp=-1",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                cropped_file,
            ]
        elif crop_mode == "split_right":
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
                "veryfast",
                "-crf",
                "23",
                "-af",
                "loudnorm=I=-14:LRA=7:tp=-1",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                cropped_file,
            ]
        elif crop_mode == "split_podcast":
            try:
                from app.speaker_tracker import analyze_video_speakers, build_split_podcast_filter
                spk_analysis = analyze_video_speakers(temp_file)
                vf = build_split_podcast_filter(spk_analysis)
            except Exception as e:
                print(f"⚠️ [split_podcast] Gagal analisis wajah ({e}), menggunakan layout default 50:50")
                from app.speaker_tracker import build_split_podcast_filter
                vf = build_split_podcast_filter({"left_cx": 0.25, "right_cx": 0.75})
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
                "veryfast",
                "-crf",
                "23",
                "-af",
                "loudnorm=I=-14:LRA=7:tp=-1",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                cropped_file,
            ]
        elif crop_mode == "podcast_speaker":
            try:
                from app.speaker_tracker import analyze_video_speakers, build_dynamic_speaker_crop_filter
                spk_analysis = analyze_video_speakers(temp_file)
                vf = build_dynamic_speaker_crop_filter(spk_analysis)
            except Exception as e:
                print(f"⚠️ [podcast_speaker] Gagal deteksi active speaker ({e}), menggunakan crop tengah")
                from app.speaker_tracker import build_dynamic_speaker_crop_filter
                vf = build_dynamic_speaker_crop_filter({})
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
                "veryfast",
                "-crf",
                "23",
                "-af",
                "loudnorm=I=-14:LRA=7:tp=-1",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                cropped_file,
            ]
        else:
            raise ValueError(f"crop_mode tidak dikenal: {crop_mode}")

        if event_cb:
            event_cb({"stage": "clip", "clip_index": index})
        prepared_audio = False
        if not use_subtitle:
            _run(cmd_crop, "ffmpeg")
        elif subtitle_review_cb:
            # The preview keeps the final layout and normalized audio.
            preview_cmd = _append_video_filter(cmd_crop, "scale=iw/2:ih/2")
            preview_cmd[preview_cmd.index("-preset") + 1] = "ultrafast"
            _run(preview_cmd, "ffmpeg")
            prepared_audio = True
        else:
            audio_map = ["-map", "0:a?"] if "-map" in cmd_crop else []
            audio_cmd = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", temp_file, "-vn", *audio_map, *cmd_crop[cmd_crop.index("-af"):],
            ]
            try:
                _run(audio_cmd, "audio")
                prepared_audio = True
            except subprocess.CalledProcessError:
                print("⚠️ Audio transkripsi tidak tersedia. Melanjutkan render video.")

        if use_subtitle:
            if prepared_audio and event_cb:
                event_cb({"stage": "subtitle", "clip_index": index})
            ok = prepared_audio and generate_subtitle(
                cropped_file, subtitle_file, language=subtitle_language, model_name=whisper_model,
            )
            if subtitle_review_cb:
                if not ok:
                    print(f"⚠️ Transkripsi Clip #{index} gagal. Caption bisa diisi manual.")
                draft = ""
                if ok:
                    with open(subtitle_file, encoding="utf-8") as f:
                        draft = f.read()
                edited = subtitle_review_cb(cropped_file, draft, index)
                with open(subtitle_file, "w", encoding="utf-8") as f:
                    f.write(edited)
                ok = bool(edited)
            final_cmd = cmd_crop
            if ok:
                subtitle_path = _escape_filter_value(os.path.abspath(subtitle_file).replace(os.sep, "/"))
                pos = str(subtitle_position or "middle").strip().lower()
                # libass force_style uses SSA alignment values. FFmpeg converts
                # SRT to a 288-unit-high canvas, so match the preview's 14%/15% insets.
                if pos in ("bottom", "bawah"):
                    alignment = 2
                    margin_v = 43
                elif pos in ("top", "atas"):
                    alignment = 6
                    margin_v = 40
                else:
                    alignment = 10
                    margin_v = 0
                font_name = str(subtitle_font_name or "Arial Black").strip() or "Arial Black"
                try:
                    font_size = int(subtitle_font_size or 22)
                except Exception:
                    font_size = 22
                primary_color = _hex_to_ass_color(subtitle_font_color or "#FFFFFF")

                force_style = (
                    f"FontName={font_name},"
                    f"FontSize={font_size},"
                    "Bold=1,"
                    f"PrimaryColour={primary_color},"
                    "OutlineColour=&H00000000,"
                    "BorderStyle=1,"
                    "Outline=3,"
                    "Shadow=1.5,"
                    f"Alignment={alignment},"
                    f"MarginV={margin_v}"
                )
                final_cmd = _append_video_filter(
                    final_cmd,
                    f"subtitles=filename={subtitle_path}:force_style='{force_style}'",
                )
            if prepared_audio:
                # Reuse the normalized audio and render video from the source.
                filter_index = final_cmd.index("-vf" if "-vf" in final_cmd else "-filter_complex")
                final_cmd = [*final_cmd[:filter_index], "-i", cropped_file, *final_cmd[filter_index:]]
                if "-map" in final_cmd:
                    final_cmd[final_cmd.index("0:a?")] = "1:a?"
                else:
                    map_index = final_cmd.index("-c:v")
                    final_cmd[map_index:map_index] = ["-map", "0:v:0", "-map", "1:a?"]
                final_cmd[final_cmd.index("-af"):] = ["-c:a", "copy", output_file]
            else:
                final_cmd[-1] = output_file
            stage = "subtitle_burn" if ok else "clip_render"
            if event_cb:
                event_cb({"stage": stage, "clip_index": index})
                _render_with_progress(final_cmd, lambda seconds: event_cb({
                    "stage": stage, "clip_index": index, "render_fraction": seconds / duration,
                }))
            else:
                _run(final_cmd, "render")
        else:
            try:
                os.replace(cropped_file, output_file)
            except Exception:
                return False, "Gagal replace file output"

        ai_meta_obj = None
        if gemini_api_key:
            if event_cb:
                event_cb({"stage": "metadata", "clip_index": index})
            try:
                print(f"✨ [AI] Menggenerate judul & caption untuk Clip #{index}...")
                transcript_text = ""

                sub_source = subtitle_file if (use_subtitle and os.path.exists(subtitle_file)) else None
                temp_sub = None

                if not sub_source:
                    temp_sub = unique_path(tempfile.gettempdir(), f"sub_temp_{uuid.uuid4().hex}", ".srt")
                    if generate_subtitle(output_file, temp_sub, model_name=whisper_model):
                        sub_source = temp_sub

                if sub_source and os.path.exists(sub_source):
                    with open(sub_source, "r", encoding="utf-8") as f:
                        lines = f.read().splitlines()
                        text_parts = []
                        for line in lines:
                            l = line.strip()
                            if "-->" in l or l.isdigit() or not l:
                                continue
                            text_parts.append(l)
                        transcript_text = " ".join(text_parts)

                if temp_sub and os.path.exists(temp_sub):
                    try:
                        os.remove(temp_sub)
                    except Exception:
                        pass

                if transcript_text.strip():
                    meta = generate_clip_metadata(transcript_text, gemini_api_key)
                    ai_meta_obj = meta
                    meta_file = os.path.splitext(output_file)[0] + "_ai.txt"
                    with open(meta_file, "w", encoding="utf-8") as f:
                        f.write("JUDUL:\n")
                        for t in meta.get("titles", []):
                            f.write(f"- {t}\n")
                        f.write(f"\nCAPTION:\n{meta.get('caption', '')}\n")
                        f.write(f"\nHASHTAGS:\n{' '.join(meta.get('hashtags', []))}\n")

                    print(f"✅ [AI] Saran judul & caption tersimpan di {os.path.basename(meta_file)}")
                    print(f"__AI_JSON__{json.dumps(meta)}")
                else:
                    print("⚠️ [AI Warning] Tidak ada suara/transkrip terdeteksi untuk AI.")
            except Exception as e:
                print(f"⚠️ [AI Error] {str(e)}")

        completed = True
        print(f"✅ Clip #{index} selesai → {os.path.basename(output_file)}")
        return True, output_file, ai_meta_obj
    except SubtitleReviewAborted:
        raise
    except subprocess.CalledProcessError as e:
        print(f"❌ [ERROR] Clip #{index} gagal (crop_mode={crop_mode})")
        err_msg = str(e)
        if e.stderr:
             err_msg += "\nStderr: " + str(e.stderr).strip()[-200:]
        
        return False, err_msg
    except Exception as e:
        print(f"❌ [ERROR] Clip #{index} exception: {e}")
        return False, str(e)
    finally:
        cleanup = [temp_file, cropped_file, subtitle_file]
        if not completed:
            cleanup.append(output_file)
        for f in cleanup:
            try:
                os.remove(f)
            except OSError:
                pass


def proses_dengan_segmen(
    link,
    segments,
    crop_mode="default",
    use_subtitle=False,
    whisper_model=None,
    subtitle_language=None,
    subtitle_position="middle",
    subtitle_font_name="Arial Black",
    subtitle_font_size=22,
    subtitle_font_color="#FFFFFF",
    output_dir=None,
    apply_padding=False,
    event_cb=None,
    gemini_api_key=None,
    subtitle_review_cb=None,
):
    link = normalize_youtube_url(link)

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
    skipped = 0
    for s in enabled_segments:
        start = float(s.get("start", 0))
        end = float(s.get("end", 0))
        if start < 0 or end < 0:
            skipped += 1
            continue
        if total_duration is not None:
            if start >= total_duration:
                skipped += 1
                continue
            end = min(end, total_duration)
        if end <= start:
            skipped += 1
            continue
        max_end = start + float(MAX_DURATION)
        if end > max_end:
            end = max_end
        if end <= start:
            skipped += 1
            continue
        cleaned.append({"start": start, "end": end, "enabled": True})

    success = 0
    errors = []
    generated_files = []
    ai_metadata = {}
    for index, seg in enumerate(cleaned, start=1):
        item = {"start": seg["start"], "end": seg["end"]}
        res_tuple = proses_satu_clip(
            video_id=video_id,
            item=item,
            index=index,
            total_duration=total_duration,
            video_url=link,
            crop_mode=crop_mode,
            use_subtitle=use_subtitle,
            subtitle_language=subtitle_language,
            subtitle_position=subtitle_position,
            subtitle_font_name=subtitle_font_name,
            subtitle_font_size=subtitle_font_size,
            subtitle_font_color=subtitle_font_color,
            output_dir=output_dir,
            apply_padding=apply_padding,
            event_cb=event_cb,
            gemini_api_key=gemini_api_key,
            subtitle_review_cb=subtitle_review_cb,
            whisper_model=whisper_model,
        )
        ok = res_tuple[0]
        res = res_tuple[1]
        meta = res_tuple[2] if len(res_tuple) > 2 else None
        if ok:
            success += 1
            if res:
                generated_files.append(res)
                if meta:
                    ai_metadata[os.path.basename(res)] = meta
        elif res:
            errors.append(res)

    if success == 0:
        if skipped > 0 and not errors:
            raise RuntimeError("Semua segmen gagal diproses. Segmen berada di luar durasi video.")
        
        msg = "Semua segmen gagal diproses."
        if errors:
            # Ambil error terakhir atau yang paling unik
            unique_errors = sorted(list(set(errors)))
            msg += f"\nDetail error: {'; '.join(unique_errors)}"
        raise RuntimeError(msg)

    return {"success_count": success, "output_dir": output_dir, "files": generated_files, "ai_metadata": ai_metadata}
