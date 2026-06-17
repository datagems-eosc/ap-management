from fastapi import APIRouter

from .analytical_patterns.routes import router as ap_router
from .health import health_check

router = APIRouter()
router.add_api_route(
    "/health",
    health_check,
    methods=["GET"],
    tags=["health"],
    summary="Health check",
    responses={
        200: {"description": "Service is healthy"},
    },
)
router.include_router(ap_router, prefix="/analytical-patterns")
