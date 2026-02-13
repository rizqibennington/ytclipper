from pydantic import BaseModel

from app.schemas.ai import StartJobRequest, StartJobResponse
from app.schemas.base import OkResponse


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


class OpenOutputResponse(OkResponse):
    output_dir: str
    method: str


__all__ = [
    "StartJobRequest",
    "StartJobResponse",
    "JobStatusResponse",
    "OpenOutputResponse",
]
