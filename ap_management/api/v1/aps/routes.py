from fastapi import APIRouter, status

from .create import create_ap

router = APIRouter(
    prefix="/aps",
    tags=["aps"],
)


router.add_api_route(
    "/", create_ap, methods=["POST"], status_code=status.HTTP_201_CREATED)


@router.get("")
def list_tasks():
    return []
