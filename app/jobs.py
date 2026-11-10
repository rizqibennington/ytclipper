import contextlib
import sys
import threading
import time
import uuid

import os
from app.clipper import SubtitleReviewAborted, format_hhmmss, proses_dengan_segmen


_JOBS_LOCK = threading.Condition()
_JOBS = {}
_LOG_LOCK = threading.Lock()
_LOG_WRITER = threading.local()
_LOG_USERS = 0


def cancel_job(job_id):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return False
        if job["done"]:
            return True
        job["cancelled"] = True
        job["running"] = False
        job["done"] = True
        job["stage"] = "cancelled"
        job["status"] = "Dibatalkan oleh user"
        job["error"] = "Dibatalkan oleh pengguna"
        job.pop("subtitle_review", None)
        _JOBS_LOCK.notify_all()
        return True


def is_job_cancelled(job_id):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        return bool(job and job.get("cancelled", False))


class JobWriter:
    def __init__(self, job_id):
        self.job_id = job_id

    def write(self, s):
        if not s:
            return
        append_job_log(self.job_id, s)

    def flush(self):
        return


class _JobLogStream:
    def __init__(self, stream):
        self.stream = stream

    def write(self, text):
        return getattr(_LOG_WRITER, "writer", self.stream).write(text)

    def flush(self):
        return getattr(_LOG_WRITER, "writer", self.stream).flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)


@contextlib.contextmanager
def _job_logs(job_id):
    global _LOG_USERS
    with _LOG_LOCK:
        if _LOG_USERS == 0:
            sys.stdout = _JobLogStream(sys.stdout)
            sys.stderr = _JobLogStream(sys.stderr)
        _LOG_USERS += 1
    _LOG_WRITER.writer = JobWriter(job_id)
    try:
        yield
    finally:
        del _LOG_WRITER.writer
        with _LOG_LOCK:
            _LOG_USERS -= 1
            if _LOG_USERS == 0:
                if isinstance(sys.stdout, _JobLogStream):
                    sys.stdout = sys.stdout.stream
                if isinstance(sys.stderr, _JobLogStream):
                    sys.stderr = sys.stderr.stream


def append_job_log(job_id, text):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        job["logs"].append(text)
        if len(job["logs"]) > 6000:
            job["logs"] = job["logs"][-4000:]


def update_job(job_id, **kwargs):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job or job["cancelled"]:
            return
        job.update(kwargs)


def get_job(job_id):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return None
        return dict(job)


def wait_for_subtitle_review(job_id, video_path, draft, clip_index, timeout=1800):
    review = {
        "id": uuid.uuid4().hex,
        "video_path": video_path,
        "srt": draft,
        "clip_index": clip_index,
    }
    with _JOBS_LOCK:
        job = _JOBS[job_id]
        if job["cancelled"]:
            raise SubtitleReviewAborted("Job dibatalkan oleh pengguna.")
        job.update(stage="subtitle_review", status=f"Tinjau caption Clip #{clip_index}", eta="", subtitle_review=review)
        try:
            if not _JOBS_LOCK.wait_for(lambda: job["cancelled"] or "edited" in review, timeout):
                raise SubtitleReviewAborted("Waktu untuk meninjau caption habis.")
            if job["cancelled"]:
                raise SubtitleReviewAborted("Job dibatalkan oleh pengguna.")
            return review["edited"]
        finally:
            job.pop("subtitle_review", None)
            if not job["cancelled"]:
                job.update(stage="clip", status=f"Melanjutkan Clip #{clip_index}...")


def submit_subtitle_review(job_id, review_id, srt):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        review = job.get("subtitle_review") if job else None
        if not review or review["id"] != review_id or "edited" in review:
            return False
        review["edited"] = srt
        _JOBS_LOCK.notify_all()
        return True


def create_job(job_id, output_dir):
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
        "success_count": 0,
        "files": [],
        "segments": [],
        "ai_metadata": {},
        "cancelled": False,
    }

    with _JOBS_LOCK:
        _JOBS[job_id] = job
    return job


def run_job(job_id, payload):
    stage_text = {
        "dependency": "⚙️ Cek dependensi...",
        "duration": "📊 Ambil info video...",
        "download": "⬇️ Download video...",
        "clip": "✂️ Proses clipping...",
        "subtitle": "🤖 AI generating subtitle...",
        "subtitle_burn": "🔥 Burning subtitle...",
        "clip_render": "🎞️ Render video...",
        "metadata": "✨ Menyiapkan judul dan deskripsi...",
    }

    total_clips = max(1, int(payload.get("total_clips", 1)))
    base_percent = 7.0
    per_clip = (100.0 - base_percent) / float(total_clips)
    render_start, render_end = 0.85, 0.99
    clip_stage = {
        "download": 0.0, "clip": 0.40, "subtitle": 0.60,
        "subtitle_burn": render_start, "clip_render": render_start, "metadata": render_end,
    }
    if not payload.get("use_subtitle", False):
        clip_stage = {"download": 0.0, "clip": 0.60, "metadata": render_end}

    state = {"clip_index": 1, "render_started": None}

    def push(stage, clip_index=None, render_fraction=None):
        if clip_index is not None:
            state["clip_index"] = int(clip_index)
        clip_i = max(1, int(state["clip_index"]))
        stage_part = clip_stage.get(stage, 0.0)
        eta = ""
        if stage in ("subtitle_burn", "clip_render"):
            if render_fraction is None:
                state["render_started"] = time.perf_counter()
            else:
                fraction = min(1.0, max(0.0, render_fraction))
                stage_part += (render_end - render_start) * fraction
                if clip_i == total_clips and state["render_started"] is not None and 0.05 <= fraction < 1.0:
                    elapsed = time.perf_counter() - state["render_started"]
                    remaining = elapsed * (1.0 - fraction) / fraction
                    if remaining >= 1.0:
                        eta = format_hhmmss(round(remaining))
        percent = min(100.0, base_percent + (clip_i - 1 + stage_part) * per_clip)
        status_msg = stage_text.get(stage, stage)
        if stage in clip_stage:
            status_msg = f"[Clip {clip_i}/{total_clips}] {status_msg}"

        update_job(job_id, percent=percent, stage=stage, status=status_msg, eta=eta)
        if render_fraction is None:
            print(f"📍 {status_msg}")

    def event_cb(evt):
        if is_job_cancelled(job_id):
            raise RuntimeError("Job dibatalkan oleh pengguna.")
        try:
            push(evt.get("stage", ""), clip_index=evt.get("clip_index"), render_fraction=evt.get("render_fraction"))
        except Exception:
            return

    update_job(job_id, running=True, percent=0.0, stage="dependency", status="🚀 Memulai...", eta="", error=None)

    def review_cb(video_path, draft, clip_index):
        return wait_for_subtitle_review(job_id, video_path, draft, clip_index)

    with _job_logs(job_id):
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
                subtitle_language=payload.get("subtitle_language"),
                subtitle_position=payload.get("subtitle_position", "middle"),
                subtitle_font_name=payload.get("subtitle_font_name", "Arial Black"),
                subtitle_font_size=payload.get("subtitle_font_size", 22),
                subtitle_font_color=payload.get("subtitle_font_color", "#FFFFFF"),
                output_dir=payload.get("output_dir"),
                apply_padding=payload.get("apply_padding", False),
                event_cb=event_cb,
                gemini_api_key=payload.get("gemini_api_key"),
                subtitle_review_cb=review_cb if payload.get("review_subtitles") else None,
            )
            update_job(
                job_id,
                running=False,
                done=True,
                percent=100.0,
                stage="done",
                status="Selesai",
                eta="",
                output_dir=result.get("output_dir"),
                success_count=result.get("success_count", 0),
                files=[os.path.basename(f) for f in result.get("files", [])],
                ai_metadata=result.get("ai_metadata", {}),
            )
        except Exception as e:
            import traceback

            if is_job_cancelled(job_id):
                print(f"\n[JOB CANCELLED] Job dibatalkan oleh pengguna.")
                update_job(job_id, running=False, done=True, percent=0.0, stage="cancelled", status="Dibatalkan", eta="", error="Job dibatalkan oleh pengguna.")
                return

            error_detail = f"{type(e).__name__}: {str(e)}"
            print(f"\n[FATAL ERROR] {error_detail}")
            print(traceback.format_exc())
            update_job(job_id, running=False, done=True, percent=0.0, stage="error", status="Error", eta="", error=error_detail)


def start_job(job_id, payload):
    t = threading.Thread(target=run_job, args=(job_id, payload), daemon=True)
    t.start()
    return t


def run_ai_job(job_id, payload):
    from app.services.ai_service import get_ai_segments
    
    update_job(job_id, running=True, percent=10.0, stage="init", status="🤖 Menyiapkan analisis AI...", eta="", error=None)

    def on_ai_progress(percent, status, stage="process"):
        update_job(job_id, percent=float(percent), status=str(status), stage=str(stage))

    with _job_logs(job_id):
        print(f"🤖 Memulai analisis AI segments...")
        try:
            result = get_ai_segments(payload, on_progress=on_ai_progress)
            if not result.get("ok"):
                raise ValueError(result.get("error", "Gagal mendapatkan AI segments"))
            
            segs = result.get("segments", [])
            update_job(
                job_id,
                running=False,
                done=True,
                percent=100.0,
                stage="done",
                status="Selesai",
                eta="",
                segments=segs,
            )
            print(f"✅ Selesai. Mendapatkan {len(segs)} segmen.")
        except Exception as e:
            import traceback
            error_detail = f"{type(e).__name__}: {str(e)}"
            print(f"\n[FATAL ERROR] {error_detail}")
            print(traceback.format_exc())
            update_job(job_id, running=False, done=True, percent=0.0, stage="error", status="Error", eta="", error=error_detail)


def start_ai_job(job_id, payload):
    t = threading.Thread(target=run_ai_job, args=(job_id, payload), daemon=True)
    t.start()
    return t
