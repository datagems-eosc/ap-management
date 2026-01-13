from logging import getLogger

from fastapi import Depends, HTTPException, status

from ap_management.di import get_ap_service
from ap_management.domain import ApCRUDFailure
from ap_management.services.analytical_pattern import AnalyticalPatternService

logger = getLogger(__name__)


async def retrieve_ap(id: str, svc: AnalyticalPatternService = Depends(get_ap_service)):
    try:
        ap = await svc.get(id)

        if ap is None:
            raise HTTPException(
                status_code=404, detail="Analytical Pattern not found")

        return ap

    except ApCRUDFailure as e:
        logger.error("Database connection failed", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve the AP (Datanase error)"
        ) from e
