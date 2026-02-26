from fastapi import APIRouter, status

from .create import create_ap
from .display import display_ap
from .retrieve import retrieve_ap
from .search import search_aps
from .validate import validate_ap

router = APIRouter(
    prefix="/aps",
    tags=["aps"],
)


router.add_api_route(
    "/", create_ap,
    methods=["POST"],
    status_code=status.HTTP_201_CREATED,
    responses={
        500: {"description": "Database error or unexpected server error"},
    }
)

router.add_api_route(
    "/", search_aps,
    methods=["GET"],
    responses={
        500: {"description": "Database error or unexpected server error"},
    }
)

router.add_api_route(
    "/{id}", retrieve_ap,
    methods=["GET"],
    responses={
        404: {"description": "Analytical Pattern not found"},
        500: {"description": "Database error or unexpected server error"},
    }
)

router.add_api_route(
    "/display", display_ap,
    methods=["POST"],
    responses={
        200: {
            "content": {"image/svg+xml": {}},
            "description": "SVG representation of the Analytical Pattern",
        }
    }
)

router.add_api_route(
    "/validate", validate_ap,
    methods=["POST"],
    responses={
        404: {"description": "Validation schema not found"},
        503: {"description": "Schema validation service is currently unavailable"},
    }
)
