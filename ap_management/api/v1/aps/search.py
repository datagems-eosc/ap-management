from logging import getLogger
from typing import List

from fastapi import Depends, HTTPException, Query, status
from pydantic import BaseModel

from ap_management.di import get_ap_service
from ap_management.domain import AnalyticalPattern, CrudError
from ap_management.services.analytical_pattern import AnalyticalPatternService

logger = getLogger(__name__)


class ApSearchResult(BaseModel):
    ap: AnalyticalPattern
    score: float


async def search_aps(
    q: str = Query(..., description="Natural language query matched against AP descriptions via vector similarity"),
    top_k: int = Query(
        10, ge=1, le=100, description="Maximum number of results to return"),
    svc: AnalyticalPatternService = Depends(get_ap_service),
) -> List[ApSearchResult]:
    """
    Search Analytical Patterns using semantic similarity
    """
    try:
        results = await svc.search(q, top_k=top_k)
        return [ApSearchResult(ap=ap, score=score) for ap, score in results]

    except CrudError as e:
        logger.error("Database error while searching APs", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to search Analytical Patterns (Database error)",
        ) from e
