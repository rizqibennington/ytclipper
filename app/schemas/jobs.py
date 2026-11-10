from typing import Any
from pydantic import BaseModel, Field

from app.schemas.ai import StartJobRequest, StartJobResponse
from app.schemas.base import OkResponse


class SubtitleReviewRequest(BaseModel):
    review_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    srt: str = Field(max_length=100_000)


class SubtitleReviewDraft(SubtitleReviewRequest):
    clip_index: int


class JobStatusResponse(BaseModel):
    ok: bool
    running: bool | None = None
    done: bool | None = None
    percent: float | None = None
    status: str | None = None
    stage: str | None = None
    eta: str | None = None
    error: str | None = None
    output_dir: str | None = None
    output_dir_ok: bool | None = None
    output_dir_error: str | None = None
    success_count: int | None = None
    logs: str | None = None
    files: list[str] = []
    segments: list[dict] | None = None
    ai_metadata: dict[str, Any] | None = None
    subtitle_review: SubtitleReviewDraft | None = None


__all__ = [
    "StartJobRequest",
    "StartJobResponse",
    "JobStatusResponse",
]
