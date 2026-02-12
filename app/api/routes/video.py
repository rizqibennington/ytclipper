from fastapi import APIRouter, HTTPException

from app.schemas import VideoInfoRequest, VideoInfoResponse
from app.services.video_service import get_video_info


router = APIRouter()


@router.post("/video_info", response_model=VideoInfoResponse)
def video_info(data: VideoInfoRequest):
    try:
        return get_video_info(data.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

