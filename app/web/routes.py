from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from app.config_store import default_output_dir


router = APIRouter()

base_dir = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(base_dir / "templates"))


@router.get("/")
def home(request: Request):
    return templates.TemplateResponse(request, "index.html", {"default_output_dir": default_output_dir()})

