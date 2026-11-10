import io
import os
import zipfile
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.jobs import cancel_job, get_job, submit_subtitle_review
from app.schemas import JobStatusResponse, StartJobRequest, StartJobResponse
from app.schemas.jobs import SubtitleReviewRequest
from app.services.clip_service import inspect_output_dir, start_clip_job
from app.subtitle_ai import normalize_review_srt


router = APIRouter()


@router.post("/start", response_model=StartJobResponse)
def start(data: StartJobRequest):
    try:
        return start_clip_job(data.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status/{job_id}", response_model=JobStatusResponse)
def status(job_id: str):
    job = get_job(job_id)
    if not job:
        return {"ok": False}
    logs = "".join(job.get("logs", [])[-2500:])

    done = bool(job.get("done", False))
    output_dir = job.get("output_dir")
    out_ok = None
    out_err = None
    review = job.get("subtitle_review")
    if done and output_dir:
        inspected = inspect_output_dir(str(output_dir))
        output_dir = inspected.get("path")
        out_ok = bool(inspected.get("ok"))
        out_err = inspected.get("error")

    return {
        "ok": True,
        "running": bool(job.get("running", False)),
        "done": done,
        "percent": float(job.get("percent", 0.0)),
        "status": str(job.get("status", "")),
        "stage": str(job.get("stage", "")),
        "eta": str(job.get("eta", "")),
        "error": job.get("error"),
        "output_dir": output_dir,
        "output_dir_ok": out_ok,
        "output_dir_error": out_err,
        "success_count": int(job.get("success_count", 0)),
        "logs": logs,
        "files": job.get("files", []),
        "segments": job.get("segments", []),
        "ai_metadata": job.get("ai_metadata", {}),
        "subtitle_review": {
            "review_id": review["id"],
            "clip_index": review["clip_index"],
            "srt": review["srt"],
        } if review and "edited" not in review else None,
    }


@router.get("/subtitle-review/{job_id}/{review_id}/video")
def subtitle_review_video(job_id: str, review_id: str):
    job = get_job(job_id)
    review = job.get("subtitle_review") if job else None
    if not review or review["id"] != review_id or "edited" in review:
        raise HTTPException(status_code=404, detail="Preview caption sudah tidak tersedia.")
    return FileResponse(review["video_path"], media_type="video/mp4", headers={"Cache-Control": "no-store"})


@router.post("/subtitle-review/{job_id}")
def save_subtitle_review(job_id: str, data: SubtitleReviewRequest):
    try:
        srt = normalize_review_srt(data.srt)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not submit_subtitle_review(job_id, data.review_id, srt):
        raise HTTPException(status_code=409, detail="Sesi review caption sudah berakhir.")
    return {"ok": True}


@router.post("/cancel/{job_id}")
def cancel(job_id: str):
    ok = cancel_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan")
    return {"ok": True, "message": "Job berhasil dibatalkan"}


@router.get("/download/{job_id}/{filename}")
def download_file(job_id: str, filename: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan")
    
    files = job.get("files", [])
    if filename not in files:
        raise HTTPException(status_code=404, detail="File tidak ditemukan atau tidak diizinkan")
    
    output_dir = job.get("output_dir")
    if not output_dir:
        raise HTTPException(status_code=400, detail="Output directory tidak ada")
        
    file_path = os.path.join(output_dir, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File fisik tidak ditemukan di server")
        
    return FileResponse(path=file_path, filename=filename, media_type="video/mp4")


@router.get("/download-zip/{job_id}")
def download_zip(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan")
    
    output_dir = job.get("output_dir")
    if not output_dir or not os.path.exists(output_dir):
        raise HTTPException(status_code=404, detail="Output directory tidak ditemukan")
    
    files = job.get("files", [])
    if not files:
        raise HTTPException(status_code=400, detail="Tidak ada file hasil untuk diunduh")
    
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            f_path = os.path.join(output_dir, f)
            if os.path.exists(f_path):
                zf.write(f_path, arcname=f)
                
                # Sertain file _ai.txt jika ada
                base_stem = os.path.splitext(f)[0]
                ai_txt = base_stem + "_ai.txt"
                ai_path = os.path.join(output_dir, ai_txt)
                if os.path.exists(ai_path):
                    zf.write(ai_path, arcname=ai_txt)
                    
    mem_zip.seek(0)
    zip_name = f"ytclips_{job_id[:8]}.zip"
    return StreamingResponse(
        mem_zip,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_name}"'}
    )
