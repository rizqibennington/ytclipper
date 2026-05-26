import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.jobs import get_job
from app.schemas import JobStatusResponse, StartJobRequest, StartJobResponse
from app.services.clip_service import inspect_output_dir, start_clip_job


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
    }


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
