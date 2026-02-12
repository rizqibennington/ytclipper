from fastapi import APIRouter, HTTPException

from app.schemas import AiSegmentsRequest, AiSegmentsResponse, GeminiSuggestionRequest, GeminiSuggestionResponse
from app.services.ai_service import generate_ai_suggestions, get_ai_segments


router = APIRouter()


@router.post("/ai_segments", response_model=AiSegmentsResponse)
def ai_segments(data: AiSegmentsRequest):
    try:
        return get_ai_segments(data.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/gemini_suggestions", response_model=GeminiSuggestionResponse)
def gemini_suggestions(data: GeminiSuggestionRequest):
    try:
        return generate_ai_suggestions(data.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

