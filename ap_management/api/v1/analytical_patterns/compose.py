from logging import getLogger
from typing import Never

from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse
from moma_management.domain.analytical_pattern import AnalyticalPattern
from pydantic import BaseModel

from ap_management.di import get_composer
from ap_management.middlewares.auth import require_authentication
from ap_management.services.composer.composer import Composer
from ap_management.services.composer.exceptions import (
    CompositionImpossibleError,
    CompositionInputError,
)

logger = getLogger(__name__)


class ComposePayload(BaseModel):
    ap1: AnalyticalPattern
    ap2: AnalyticalPattern


class ErrorResponse(BaseModel):
    detail: str


async def compose_aps(
    body: ComposePayload,
    svc: Composer = Depends(get_composer),
    _auth: Never = Depends(require_authentication())
) -> AnalyticalPattern:
    """
    Create a new AnalyticalPattern in the MoMa graph repository.
d
    The ``input`` edges of the AP **must** reference Data nodes that belong
    to an existing dataset, and the caller must be able to **browse** those
    datasets.  The AP cannot create Dataset nodes itself.
    """
    try:
        composed_ap = await svc.compose(body.ap1, body.ap2)
        return JSONResponse(content=composed_ap.model_dump(mode="json", by_alias=True))
    except (CompositionInputError, CompositionImpossibleError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error composing APs: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unexpected error during AP composition. Check logs for details."
        )
