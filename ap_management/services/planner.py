from typing import List
from uuid import uuid4

import structlog
from moma_management.domain.analytical_pattern import AnalyticalPattern
from pydantic import BaseModel

from ap_management.generated.moma_management.moma_management_client import (
    MomaManagementClient,
)
from ap_management.internal.graph_utils import find_entry_operator
from ap_management.services.ap_catalog.catalog import APCatalog, OperatorPort

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
from .value_suggester import SuggestedParameter, ValueSuggester

logger = structlog.get_logger(__name__)


class PlanResult(BaseModel):
    """The AP produced by the planner, plus the parameters needed to instantiate it."""
    ap: AnalyticalPattern
    instantiation_parameters: List[SuggestedParameter]


class Planner:
    """The planner creates a composition of APs answering a given task."""

    def __init__(self, matchmaker: Matchmaker, composer: Composer, ap_catalog: APCatalog, value_suggester: ValueSuggester):
        self.matchmaker = matchmaker
        self.composer = composer
        self.ap_catalog = ap_catalog
        self.value_suggester = value_suggester

    async def plan(self, task: str) -> PlanResult:
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
            ap = aps[0]
        else:
            logger.info("Composing APs", ap_count=len(aps))
            try:
                composed: AnalyticalPattern = aps[0]
                for i in range(1, len(aps)):
                    composed = await self.composer.compose(composed, aps[i])
            except (CompositionInputError, CompositionImpossibleError, CompositionInternalError) as e:
                logger.error("AP composition failed", error=str(e))
                raise PlannerCompositionError(
                    f"Failed to compose APs: {e}") from e
            ap = composed

        logger.info(
            "Planning complete. Suggesting parameters for AP instantiation", ap_id=str(ap.root.id))

        entry_op = find_entry_operator(ap)
        entry_op_inputs = entry_op.properties.get("inputs", [])
        parameters = OperatorPort.from_properties(entry_op_inputs)
        runtime_params = self.value_suggester.suggest(task, parameters)

        return PlanResult(ap=ap, instantiation_parameters=runtime_params)
