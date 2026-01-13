from logging import getLogger

from fastapi import Depends, HTTPException, Path, status

from ap_management.di import get_ap_service
from ap_management.domain import AnalyticalPattern, ApCRUDFailure
from ap_management.services.analytical_pattern import AnalyticalPatternService

logger = getLogger(__name__)


async def retrieve_ap(id: str = Path(..., description="The Analytical Pattern Node UUID to look for"), svc: AnalyticalPatternService = Depends(get_ap_service)) -> AnalyticalPattern:
    """
    Retrieves an Analytical Pattern whole graph by the UUID of the Analytical Pattern Node.
    """
    try:
        ap = await svc.get(id)

        if ap is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Analytical Pattern not found")

        return ap

    except ApCRUDFailure as e:
        logger.error("Database connection failed", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve the AP (Datanase error)"
        ) from e
