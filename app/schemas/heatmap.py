from typing import Any

from pydantic import BaseModel, Field

from app.schemas.base import OkResponse


class HeatmapRequest(BaseModel):
    url: str = Field(min_length=1)
    duration_seconds: int | None = None
    debug: bool = False


class Segment(BaseModel):
    enabled: bool = True
    start: float
    end: float


class ScoredSegment(Segment):
    score: float | None = None


class HeatmapResponse(OkResponse):
    segments: list[ScoredSegment]
    _meta: dict[str, Any] | None = None

