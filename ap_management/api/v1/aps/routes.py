from fastapi import APIRouter, status

from .create import create_ap
from .retrieve import retrieve_ap

router = APIRouter(
    prefix="/aps",
    tags=["aps"],
)


router.add_api_route(
    "/", create_ap, methods=["POST"], status_code=status.HTTP_201_CREATED)
router.add_api_route("/{id}", retrieve_ap, methods=["GET"])
