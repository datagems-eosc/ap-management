from logging import getLogger

from fastapi import Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from ap_management.di import get_ap_service
from ap_management.domain import AnalyticalPattern, CrudError
from ap_management.services.analytical_pattern import AnalyticalPatternService

logger = getLogger(__name__)


class ResolveApRequest(BaseModel):
    query: str = Field(...,
                       description="Natural language description of the desired Analytical Pattern")
    threshold: float = Field(
        0.85, ge=0.0, le=1.0, description="Minimum cosine similarity to consider an AP a match")
    top_k: int = Field(
        5, ge=1, le=100, description="Number of candidates to retrieve before applying the threshold")


class ResolveApResponse(BaseModel):
    ap: AnalyticalPattern
    score: float | None = Field(
        None, description="Cosine similarity score; None when the AP was generated")
    source: str = Field(
        ..., description='"found" if an existing AP matched, "generated" if a new one was created')


async def resolve_ap(
    body: ResolveApRequest,
    response: Response,
    svc: AnalyticalPatternService = Depends(get_ap_service),
) -> ResolveApResponse:
    """
    Resolve an Analytical Pattern from a natural language query.

    Searches for an existing AP whose description is semantically close to the
    query (cosine similarity >= threshold). If none is found, generates a new AP
    from the query and persists it.

    Returns HTTP 200 when an existing AP was matched, HTTP 201 when a new one was created.
    """
    try:
        ap, score, created = await svc.resolve(body.query, threshold=body.threshold, top_k=body.top_k)
        if created:
            response.status_code = status.HTTP_201_CREATED
        return ResolveApResponse(
            ap=ap,
            score=score,
            source="generated" if created else "found",
        )
    except CrudError as e:
        logger.error("Error while resolving AP", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to resolve Analytical Pattern",
        ) from e
