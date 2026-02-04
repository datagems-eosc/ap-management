from logging import getLogger
from typing import Any, List

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from ap_management.di import get_ap_service
from ap_management.domain import PgJson
from ap_management.domain.exceptions import SchemaNotFoundError, SchemaUnavailableError
from ap_management.services.analytical_pattern import AnalyticalPatternService

logger = getLogger(__name__)


class ValidationPayload(BaseModel):
    # Whether the model is a valid AP
    valid: bool
    # List of errors if any
    errors: List[Any]


async def validate_ap(ap: PgJson, schema_path: str = "ap/ap-common.schema.json", svc: AnalyticalPatternService = Depends(get_ap_service)) -> ValidationPayload:
    """
    Ensure the provided PG-JSON is a valid Analytical Pattern. Return the list of errors if validation fails.
    The input must first be a valid PG-JSON.
    If the payload is not a valid PG-JSON, a 422 error will be returned, and no Analytical Pattern validation will be performed.
    """
    try:
        errors = await svc.validate(schema_path, ap)
        return ValidationPayload(
            valid=len(errors) == 0,
            errors=errors
        )
    except SchemaNotFoundError as e:
        logger.error(f"Schema not found: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Validation schema not found: {schema_path}"
        )
    except SchemaUnavailableError as e:
        logger.error(f"Schema service unavailable: {e}")
        raise HTTPException(
            status_code=503,
            detail="Schema validation service is currently unavailable. Please try again later."
        )
