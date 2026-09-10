from logging import getLogger
from typing import List, Never

from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ap_management.di import get_planner
from ap_management.middlewares.auth import require_authentication
from ap_management.services.planner import Planner, PlanResult
from ap_management.services.planner_exceptions import (
    ApFetchError,
    DatasetFetchError,
    DatasetNotFoundError,
    MagicOperatorError,
    MatchmakerError,
    NoApFoundError,
    NoCompatibleDatasetError,
    PlannerCompositionError,
)

logger = getLogger(__name__)


class PlanPayload(BaseModel):
    task: str = Field(description="The natural-language task to plan an AP for.")
    dataset_ids: List[str] = Field(
        default=[],
        description=(
            "IDs of the datasets the plan must run against, as returned by "
            "cross-dataset-discovery. Their types constrain which operators can apply "
            "and ground the suggested instantiation parameters. The planned AP contains "
            "no dataset nodes; it is only guaranteed to be compatible with them."
        ),
    )
    allow_magic_operator: bool = Field(
        default=False,
        description=(
            "Allow steps no catalogued AP covers to be filled by a generic LLM-backed "
            "'magic' operator, instead of failing with 404. Off by default."
        ),
    )


async def plan_ap(
    body: PlanPayload,
    planner: Planner = Depends(get_planner),
    _auth: Never = Depends(require_authentication()),
) -> PlanResult:
    try:
        result = await planner.plan(
            body.task,
            body.dataset_ids,
            allow_magic_operator=body.allow_magic_operator,
        )
        return JSONResponse(content=result.model_dump(mode="json", by_alias=True))
    except NoApFoundError as e:
        raise HTTPException(status_code=404, detail=e.reason)
    except DatasetNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (MatchmakerError, ApFetchError, DatasetFetchError) as e:
        logger.error("Upstream failure during planning: %s", e)
        raise HTTPException(status_code=502, detail=str(e))
    except (PlannerCompositionError, NoCompatibleDatasetError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    except MagicOperatorError as e:
        logger.error("Magic operator failure during planning: %s", e)
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error during planning: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Unexpected error during planning. Check logs for details.",
        )
