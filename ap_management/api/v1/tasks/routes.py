from fastapi import APIRouter, status

from .create import create_task

router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
)

router.add_api_route(
    "/", create_task,
    methods=["POST"],
    status_code=status.HTTP_201_CREATED,
    responses={
        500: {"description": "Database error or unexpected server error"},
    }
)
