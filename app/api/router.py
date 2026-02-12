from fastapi import APIRouter

from app.api.routes.ai import router as ai_router
from app.api.routes.config import router as config_router
from app.api.routes.heatmap import router as heatmap_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.video import router as video_router


router = APIRouter(prefix="/api")

router.include_router(config_router)
router.include_router(video_router)
router.include_router(heatmap_router)
router.include_router(ai_router)
router.include_router(jobs_router)

