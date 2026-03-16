from fastapi import APIRouter

from .aps.routes import router as aps_routes
from .health import health_check
from .tasks.routes import router as tasks_routes

router = APIRouter(
    prefix="/api/v1"
)
router.include_router(aps_routes)
router.include_router(tasks_routes)
router.add_api_route("/health", health_check, methods=["GET"])
