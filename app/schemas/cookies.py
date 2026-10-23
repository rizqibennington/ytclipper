from typing import Optional
from pydantic import BaseModel


class CookieStatus(BaseModel):
    installed: bool
    path: Optional[str] = None
    size_bytes: int = 0
    line_count: int = 0
    has_youtube_cookies: bool = False
    error: Optional[str] = None


class CookiesStatusResponse(BaseModel):
    ok: bool = True
    status: CookieStatus


class UploadCookiesRequest(BaseModel):
    cookies: str


class UploadCookiesResponse(BaseModel):
    ok: bool = True
    message: str
    status: CookieStatus
