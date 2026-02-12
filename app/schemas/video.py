from pydantic import BaseModel, Field

from app.schemas.base import OkResponse


class VideoInfoRequest(BaseModel):
    url: str = Field(min_length=1)


class VideoInfoResponse(OkResponse):
    video_id: str
    duration_seconds: int

