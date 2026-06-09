from typing import Any, Dict

from fastapi import APIRouter

from .compose import ErrorResponse, compose_aps

router = APIRouter(tags=["analytical patterns"])
router.add_api_route(
    "/compose",
    compose_aps,
    methods=["POST"],
    responses={
        200: {"description": "Composed AnalyticalPattern returned successfully", "model": Dict[str, Any]},
        400: {"description": "Invalid input or composition is not possible", "model": ErrorResponse},
        500: {"description": "Unexpected internal error during composition", "model": ErrorResponse},
    },
)
