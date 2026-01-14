from logging import getLogger

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel

from ap_management.di import get_ap_service
from ap_management.domain import AnalyticalPattern, CrudFailure
from ap_management.services.analytical_pattern import AnalyticalPatternService

logger = getLogger(__name__)


class CreatePayload(BaseModel):
    id: str


async def create_ap(ap: AnalyticalPattern, svc: AnalyticalPatternService = Depends(get_ap_service)) -> CreatePayload:
    """
    Registers a new Analytical Pattern
    """
    try:
        id = await svc.create(ap=ap)

        return CreatePayload(id=id)

    except CrudFailure as e:
        logger.error("Database connection failed", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create the AP"
        ) from e
