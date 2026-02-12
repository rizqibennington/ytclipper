from fastapi import APIRouter, HTTPException

from app.jobs import get_job
from app.schemas import JobStatusResponse, OpenOutputResponse, StartJobRequest, StartJobResponse
from app.services.clip_service import open_output_folder, start_clip_job


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
    return {
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
        "logs": logs,
    }


@router.post("/open_output/{job_id}", response_model=OpenOutputResponse)
def open_output(job_id: str):
    try:
        return open_output_folder(job_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

