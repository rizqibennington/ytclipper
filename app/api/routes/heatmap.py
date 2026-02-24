from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import settings_dep
from app.core.settings import Settings
from app.schemas import HeatmapRequest, HeatmapResponse
from app.services.heatmap_service import get_heatmap_segments


router = APIRouter()


@router.post("/heatmap", response_model=HeatmapResponse)
def heatmap(data: HeatmapRequest, settings: Settings = Depends(settings_dep)):
    try:
        return get_heatmap_segments(data.model_dump(exclude_none=True), settings=settings)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

