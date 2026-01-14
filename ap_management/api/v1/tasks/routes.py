from fastapi import APIRouter, status

from .create import create_task
from .retrieve_aps import retrieve_aps

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

router.add_api_route(
    "/{id}/aps", retrieve_aps,
    methods=["GET"],
    responses={
        404: {"description": "Task not found"},
        500: {"description": "Database error or unexpected server error"},
    }
)
