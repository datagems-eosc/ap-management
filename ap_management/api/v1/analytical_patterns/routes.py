from fastapi import APIRouter

from .compose import compose_aps

router = APIRouter(tags=["analytical patterns"])
router.add_api_route("/compose", compose_aps, methods=["POST"])
