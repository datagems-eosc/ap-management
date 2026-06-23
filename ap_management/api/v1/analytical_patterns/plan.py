from logging import getLogger
from typing import Never

from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse
from moma_management.domain.analytical_pattern import AnalyticalPattern
from pydantic import BaseModel

from ap_management.di import get_planner
from ap_management.middlewares.auth import require_authentication
from ap_management.services.planner import Planner
from ap_management.services.planner_exceptions import (
    ApFetchError,
    MatchmakerError,
    NoApFoundError,
    PlannerCompositionError,
)

logger = getLogger(__name__)


class PlanPayload(BaseModel):
    task: str


async def plan_ap(
    body: PlanPayload,
    planner: Planner = Depends(get_planner),
    _auth: Never = Depends(require_authentication()),
) -> AnalyticalPattern:
    try:
        result = await planner.plan(body.task)
        return JSONResponse(content=result.model_dump(mode="json", by_alias=True))
    except NoApFoundError as e:
        raise HTTPException(status_code=404, detail=e.reason)
    except (MatchmakerError, ApFetchError) as e:
        logger.error("Upstream failure during planning: %s", e)
        raise HTTPException(status_code=502, detail=str(e))
    except PlannerCompositionError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error during planning: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Unexpected error during planning. Check logs for details.",
        )
