from logging import getLogger
from typing import Any, Dict

from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ap_management.di import get_composer
from ap_management.services.composer.composer import Composer
from ap_management.services.composer.exceptions import CompositionInputError, CompositionInternalError

logger = getLogger(__name__)


class ComposePayload(BaseModel):
    ap1: Dict[str, Any]
    ap2: Dict[str, Any]


async def compose_aps(
    body: ComposePayload,
    svc: Composer = Depends(get_composer),
) -> Dict[str, Any]:
    """
    Create a new AnalyticalPattern in the MoMa graph repository.

    The ``input`` edges of the AP **must** reference Data nodes that belong
    to an existing dataset, and the caller must be able to **browse** those
    datasets.  The AP cannot create Dataset nodes itself.
    """
    try:
        composed_ap = await svc.compose(body.ap1, body.ap2)
        return JSONResponse(content=composed_ap)
    except CompositionInputError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except CompositionInternalError as e:
        logger.error(f"Composition produced an invalid AP: {e}")
        raise HTTPException(
            status_code=500,
            detail="Composition failed. Check logs for details."
        )
    except Exception as e:
        logger.error(f"Unexpected error composing APs: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unexpected error during AP composition. Check logs for details."
        )
