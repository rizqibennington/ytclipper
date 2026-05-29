from fastapi import APIRouter, HTTPException

from app.schemas import AiSegmentsRequest, AiSegmentsResponse, GeminiSuggestionRequest, GeminiSuggestionResponse, StartJobResponse
from app.services.ai_service import generate_ai_suggestions, get_ai_segments
from app.jobs import create_job, start_ai_job
import uuid


router = APIRouter()


@router.post("/ai_segments", response_model=StartJobResponse)
def ai_segments(data: AiSegmentsRequest):
    try:
        job_id = uuid.uuid4().hex[:12]
        create_job(job_id, output_dir=None)
        start_ai_job(job_id, data.model_dump(exclude_none=True))
        return {"ok": True, "job_id": job_id, "estimated_bytes": 0}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/gemini_suggestions", response_model=GeminiSuggestionResponse)
def gemini_suggestions(data: GeminiSuggestionRequest):
    try:
        return generate_ai_suggestions(data.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

