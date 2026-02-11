import contextlib
import threading
import time

from clipper import format_hhmmss, proses_dengan_segmen


_JOBS_LOCK = threading.Lock()
_JOBS = {}


class JobWriter:
    def __init__(self, job_id):
        self.job_id = job_id

    def write(self, s):
        if not s:
            return
        append_job_log(self.job_id, s)

    def flush(self):
        return


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
        if not job:
            return
        job.update(kwargs)


def get_job(job_id):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return None
        return dict(job)


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
            eta = format_hhmmss(int(remaining))
        else:
            eta = ""

        status_msg = stage_text.get(stage, stage)
        if stage in ("download", "clip", "subtitle", "subtitle_burn"):
            status_msg = f"[Clip {clip_i}/{total_clips}] {status_msg}"

        update_job(job_id, percent=percent, stage=stage, status=status_msg, eta=eta)
        print(f"📍 {status_msg}")

    def event_cb(evt):
        try:
            push(evt.get("stage", ""), clip_index=evt.get("clip_index"))
        except Exception:
            return

    update_job(job_id, running=True, percent=0.0, stage="dependency", status="🚀 Memulai...", eta="", error=None)

    writer = JobWriter(job_id)
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
                event_cb=event_cb,
                gemini_api_key=payload.get("gemini_api_key"),
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
            )
        except Exception as e:
            import traceback

            error_detail = f"{type(e).__name__}: {str(e)}"
            print(f"\n[FATAL ERROR] {error_detail}")
            print(traceback.format_exc())
            update_job(job_id, running=False, done=True, percent=0.0, stage="error", status="Error", eta="", error=error_detail)


def start_job(job_id, payload):
    t = threading.Thread(target=run_job, args=(job_id, payload), daemon=True)
    t.start()
    return t
