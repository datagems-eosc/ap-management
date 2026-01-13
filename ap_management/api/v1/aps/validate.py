from logging import getLogger
from typing import List

from fastapi import Depends
from pydantic import BaseModel

from ap_management.di import get_ap_service
from ap_management.domain import PgJson
from ap_management.services.analytical_pattern import AnalyticalPatternService

logger = getLogger(__name__)


class ValidationPayload(BaseModel):
    # Whether the model is a valid AP
    valid: bool
    # List of errors if any
    errors: List[str]


async def validate_ap(ap: PgJson, svc: AnalyticalPatternService = Depends(get_ap_service)) -> ValidationPayload:
    """
    Ensure the provided PG-JSON is a valid Analytical Pattern. Return the list of errors if validation fails.
    The input must first be a valid PG-JSON.
    If the payload is not a valid PG-JSON, a 422 error will be returned, and no Analytical Pattern validation will be performed.
    """
    # There is no db fetch, no need for special exception handling, any generic exception will be mapped to a 500
    errors = svc.validate(ap)
    return ValidationPayload(
        valid=len(errors) == 0,
        errors=errors
    )
