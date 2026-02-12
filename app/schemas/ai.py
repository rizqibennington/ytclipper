from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.base import OkResponse
from app.schemas.heatmap import ScoredSegment, Segment


class AiSegmentsRequest(BaseModel):
    url: str = Field(min_length=1)
    duration_seconds: int | None = None
    language: str = "id"
    whisper_model: str | None = None
    limit: int = Field(default=10, ge=1, le=20)


class AiSegmentsResponse(OkResponse):
    segments: list[ScoredSegment]


class StartJobRequest(BaseModel):
    url: str = Field(min_length=1)
    segments: list[Segment]
    crop_mode: Literal["default", "fit", "split_left", "split_right"] = "default"
    use_subtitle: bool = False
    whisper_model: str | None = None
    subtitle_language: str | None = None
    subtitle_position: Literal["bottom", "middle", "top"] = "middle"
    output_dir: str | None = None
    gemini_api_key: str | None = None


class StartJobResponse(OkResponse):
    job_id: str
    estimated_bytes: int


class GeminiSuggestionRequest(BaseModel):
    text: str = Field(min_length=1)
    gemini_api_key: str | None = None


class ClipMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")


class GeminiSuggestionResponse(OkResponse):
    data: ClipMetadata
