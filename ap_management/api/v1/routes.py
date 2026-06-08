from fastapi import APIRouter

from .analytical_patterns.routes import router as ap_router

router = APIRouter()
router.include_router(ap_router, prefix="/analytical-patterns")
