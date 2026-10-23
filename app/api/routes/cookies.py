from fastapi import APIRouter, HTTPException
from app.schemas.cookies import (
    CookiesStatusResponse,
    UploadCookiesRequest,
    UploadCookiesResponse,
)
from app.schemas.base import OkResponse
from app.yt_utils import delete_cookies, get_cookies_status, save_cookies

router = APIRouter(prefix="/cookies", tags=["Cookies"])


@router.get("", response_model=CookiesStatusResponse)
def get_status():
    status = get_cookies_status()
    return {"ok": True, "status": status}


@router.post("", response_model=UploadCookiesResponse)
def upload_cookies(data: UploadCookiesRequest):
    content = str(data.cookies or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Isi file cookies tidak boleh kosong.")
    
    # Simple validation for Netscape cookie format or valid lines
    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")]
    if not lines:
        raise HTTPException(
            status_code=400,
            detail="File cookies tidak memiliki baris data cookie yang valid (format Netscape HTTP Cookie File diperlukan)."
        )

    try:
        saved_path = save_cookies(content)
        status = get_cookies_status()
        return {
            "ok": True,
            "message": f"Cookies berhasil disimpan ke {saved_path} ({status['line_count']} baris cookie).",
            "status": status,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan cookies: {str(e)}")


@router.delete("", response_model=OkResponse)
def remove_cookies():
    try:
        deleted = delete_cookies()
        if not deleted:
            return {"ok": True}
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menghapus cookies: {str(e)}")
