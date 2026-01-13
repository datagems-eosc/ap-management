from logging import getLogger

from fastapi import Depends, HTTPException, status

from ap_management.di import get_ap_service
from ap_management.domain import AnalyticalPattern, ApCRUDFailure
from ap_management.services.analytical_pattern import AnalyticalPatternService

logger = getLogger(__name__)


async def create_ap(ap: AnalyticalPattern, svc: AnalyticalPatternService = Depends(get_ap_service)):
    try:
        id = await svc.create(ap=ap)

        return {"id": id}

    except ApCRUDFailure as e:
        logger.error("Database connection failed", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create the AP"
        ) from e
