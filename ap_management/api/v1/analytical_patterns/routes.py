from typing import Any, Dict

from fastapi import APIRouter

from .compose import ErrorResponse, compose_aps
from .plan import plan_ap

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
router.add_api_route(
    "/plan",
    plan_ap,
    methods=["POST"],
    responses={
        200: {
            "description": (
                "Planned AnalyticalPattern returned successfully, together with the "
                "instantiation parameters required to run its entry operator"
            ),
            "model": Dict[str, Any],
        },
        404: {"description": "No AP found for the task", "model": ErrorResponse},
        422: {"description": "APs found but cannot be composed", "model": ErrorResponse},
        502: {"description": "Upstream service failure (LLM or MOMA)", "model": ErrorResponse},
        500: {"description": "Unexpected internal error during planning", "model": ErrorResponse},
    },
)
