from uuid import uuid4

import structlog
from moma_management.domain.analytical_pattern import AnalyticalPattern

from ap_management.generated.moma_management.moma_management_client import (
    MomaManagementClient,
)
from ap_management.services.ap_catalog.catalog import APCatalog

from .composer import Composer
from .composer.exceptions import (
    CompositionImpossibleError,
    CompositionInputError,
    CompositionInternalError,
)
from .matchmaker import Matchmaker
from .planner_exceptions import (
    ApFetchError,
    MatchmakerError,
    NoApFoundError,
    PlannerCompositionError,
)

logger = structlog.get_logger(__name__)


class Planner:
    """The planner creates a composition of APs answering a given task."""

    def __init__(self, matchmaker: Matchmaker, composer: Composer, ap_catalog: APCatalog):
        self.matchmaker = matchmaker
        self.composer = composer
        self.ap_catalog = ap_catalog

    async def plan(self, task: str) -> AnalyticalPattern:
        logger.info("Planning AP composition", task=task)

        try:
            ap_list = await self.matchmaker.resolve(task)
        except Exception as e:
            logger.error("Matchmaker failed", error=str(e))
            raise MatchmakerError(
                f"Matchmaker failed to process task: {e}") from e

        if not ap_list.steps:
            logger.info("No APs found for task", reasoning=ap_list.reasoning)
            raise NoApFoundError(ap_list.reasoning)

        logger.info("Matchmaker resolved steps", step_count=len(ap_list.steps))

        aps = []
        for step in ap_list.steps:
            try:
                ap = await self.ap_catalog.get(step.analytical_pattern_id)
                aps.append(ap)
            except Exception as e:
                logger.error(
                    "Failed to fetch AP", ap_id=step.analytical_pattern_id, error=str(e)
                )
                raise ApFetchError(step.analytical_pattern_id, e) from e

        if not aps:
            logger.info(
                "No APs resolved from catalog", reasoning=ap_list.reasoning
            )
            raise NoApFoundError(ap_list.reasoning)

        if len(aps) == 1:
            logger.info(
                "Single AP resolved, no composition needed", ap_id=str(aps[0].root.id)
            )
            return aps[0]

        logger.info("Composing APs", ap_count=len(aps))
        try:
            composed: AnalyticalPattern = aps[0]
            for i in range(1, len(aps)):
                composed = await self.composer.compose(composed, aps[i])
        except (CompositionInputError, CompositionImpossibleError, CompositionInternalError) as e:
            logger.error("AP composition failed", error=str(e))
            raise PlannerCompositionError(f"Failed to compose APs: {e}") from e

        logger.info("Planning complete")
        return composed
