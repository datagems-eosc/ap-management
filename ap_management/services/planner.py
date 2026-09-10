import asyncio
from typing import Dict, List, Optional

import structlog
from moma_management.domain.analytical_pattern import AnalyticalPattern
from moma_management.domain.generated.nodes.node_schema import Node
from pydantic import BaseModel

from ap_management.internal.dataset_compat import (
    compatible_dataset_ids,
    describe_requirements,
)
from ap_management.internal.graph_utils import (
    find_terminal_operator,
    iter_operators,
    wired_input_names,
)
from ap_management.services.ap_catalog.catalog import APCatalog, OperatorPort
from ap_management.services.dataset_catalog.catalog import (
    DatasetCatalog,
    DatasetSummary,
)
from ap_management.services.magic_operator import (
    INSTRUCTION_INPUT,
    MagicOperatorBuilder,
)

from .composer import Composer
from .composer.exceptions import (
    CompositionImpossibleError,
    CompositionInputError,
    CompositionInternalError,
)
from .matchmaker import MAGIC_STEP_SENTINEL, Matchmaker, TaskResolution
from .planner_exceptions import (
    ApFetchError,
    DatasetFetchError,
    DatasetNotFoundError,
    MagicOperatorError,
    MatchmakerError,
    NoApFoundError,
    NoCompatibleDatasetError,
    PlannerCompositionError,
)
from .value_suggester import SuggestedParameter, ValueSuggester

logger = structlog.get_logger(__name__)


class DatasetRef(BaseModel):
    """A dataset the plan was built against, trimmed for the API response.

    Deliberately narrower than `DatasetSummary`: the plan response must not carry the
    summary's `access_urls` (which can hold DB connection strings) or table schemas.
    """

    id: str
    name: str
    kinds: List[str] = []


class PlanResult(BaseModel):
    """The AP produced by the planner, plus the parameters needed to instantiate it."""

    ap: AnalyticalPattern
    instantiation_parameters: List[SuggestedParameter]
    datasets: List[DatasetRef] = []
    used_magic_operator: bool = False


class Planner:
    """The planner creates a composition of APs answering a given task."""

    def __init__(
        self,
        matchmaker: Matchmaker,
        composer: Composer,
        ap_catalog: APCatalog,
        value_suggester: ValueSuggester,
        dataset_catalog: DatasetCatalog,
        magic_operator_builder: MagicOperatorBuilder,
    ):
        self.matchmaker = matchmaker
        self.composer = composer
        self.ap_catalog = ap_catalog
        self.value_suggester = value_suggester
        self.dataset_catalog = dataset_catalog
        self.magic_operator_builder = magic_operator_builder

    async def plan(
        self,
        task: str,
        dataset_ids: Optional[List[str]] = None,
        *,
        allow_magic_operator: bool = False,
    ) -> PlanResult:
        dataset_ids = dataset_ids or []
        logger.info("Planning AP composition", task=task,
                    dataset_count=len(dataset_ids))

        datasets = await self._fetch_datasets(dataset_ids)
        steps = await self._resolve_steps(task, datasets, allow_magic_operator)

        # Left-fold the steps into one AP. Magic steps are built on the fly; the
        # instructions they generate are collected to hand back as parameters.
        magic_instructions: Dict[str, str] = {}
        ap: Optional[AnalyticalPattern] = None

        for step in steps:
            if step.analytical_pattern_id == MAGIC_STEP_SENTINEL:
                upstream = _terminal_outputs(ap) if ap else []
                next_ap, instruction = await self._build_magic_ap(
                    task, step.role, upstream, datasets
                )
                # Composition never rewrites operator ids, so this key still addresses
                # the same operator once the chain is stitched together.
                magic_instructions[str(
                    next(iter_operators(next_ap)).id)] = instruction
            else:
                try:
                    next_ap = await self.ap_catalog.get(step.analytical_pattern_id)
                except Exception as e:
                    logger.error("Failed to fetch AP",
                                 ap_id=step.analytical_pattern_id, error=str(e))
                    raise ApFetchError(step.analytical_pattern_id, e) from e

            if ap is None:
                ap = next_ap
                continue

            logger.info("Composing APs")
            try:
                ap = await self.composer.compose(ap, next_ap)
            except (CompositionInputError, CompositionImpossibleError, CompositionInternalError) as e:
                logger.error("AP composition failed", error=str(e))
                raise PlannerCompositionError(
                    f"Failed to compose APs: {e}") from e

        # An AP whose operators cannot touch the caller's data would only fail later,
        # in the executor, where the reason is much harder to see.
        if datasets and not compatible_dataset_ids(ap, datasets):
            raise NoCompatibleDatasetError(
                describe_requirements(
                    ap), [k for d in datasets for k in d.kinds]
            )

        return PlanResult(
            ap=ap,
            instantiation_parameters=self._suggest_parameters(
                task, ap, datasets, magic_instructions),
            datasets=[DatasetRef(id=d.id, name=d.name, kinds=d.kinds)
                      for d in datasets],
            used_magic_operator=bool(magic_instructions),
        )

    async def _resolve_steps(
        self, task: str, datasets: List[DatasetSummary], allow_magic_operator: bool
    ) -> List[TaskResolution]:
        """Ask the matchmaker for an ordered list of AP steps.

        When it finds nothing: a lone magic step if the caller allowed one, otherwise
        `NoApFoundError`.
        """
        try:
            ap_list = await self.matchmaker.resolve(
                task, datasets, allow_magic_operator=allow_magic_operator
            )
        except Exception as e:
            logger.error("Matchmaker failed", error=str(e))
            raise MatchmakerError(
                f"Matchmaker failed to process task: {e}") from e

        if ap_list.steps:
            logger.info(
                "Matchmaker resolved steps", step_count=len(ap_list.steps)
            )
            return ap_list.steps

        if not allow_magic_operator:
            logger.info("No APs found for task", reasoning=ap_list.reasoning)
            raise NoApFoundError(ap_list.reasoning)

        logger.info("No APs found, falling back to a magic operator",
                    reasoning=ap_list.reasoning)
        return [TaskResolution(role=task, analytical_pattern_id=MAGIC_STEP_SENTINEL)]

    async def _fetch_datasets(self, dataset_ids: List[str]) -> List[DatasetSummary]:
        """Fetch every requested dataset concurrently and project it for the LLM."""
        if not dataset_ids:
            return []

        results = await asyncio.gather(
            *(self.dataset_catalog.get(id) for id in dataset_ids),
            return_exceptions=True,
        )

        summaries: List[DatasetSummary] = []
        for dataset_id, result in zip(dataset_ids, results):
            if isinstance(result, ValueError):
                # The catalogs raise ValueError for "no such id", which is the caller's
                # mistake, not an upstream failure.
                logger.error("Dataset not found", dataset_id=dataset_id)
                raise DatasetNotFoundError(dataset_id) from result
            elif isinstance(result, BaseException):
                logger.error("Failed to fetch dataset",
                             dataset_id=dataset_id, error=str(result))
                raise DatasetFetchError(dataset_id, result) from result
            summaries.append(DatasetSummary.from_dataset(result))

        logger.info("Fetched datasets", kinds=[
                    k for s in summaries for k in s.kinds])
        return summaries

    async def _build_magic_ap(
        self,
        task: str,
        role: Optional[str],
        upstream_outputs: List[OperatorPort],
        datasets: List[DatasetSummary],
    ):
        try:
            return await self.magic_operator_builder.build(
                task, role=role, upstream_outputs=upstream_outputs, datasets=datasets
            )
        except Exception as e:
            logger.error("Magic operator build failed", error=str(e))
            raise MagicOperatorError(
                f"Failed to build a magic operator: {e}") from e

    def _suggest_parameters(
        self,
        task: str,
        ap: AnalyticalPattern,
        datasets: List[DatasetSummary],
        magic_instructions: Dict[str, str],
    ) -> List[SuggestedParameter]:
        """One suggested value per operator input the AP does not already receive from
        an upstream operator."""
        logger.info(
            "Planning complete. Suggesting parameters for AP instantiation",
            ap_id=str(ap.root.id),
        )

        parameters: List[SuggestedParameter] = []
        for operator in iter_operators(ap):
            ports = _unsatisfied_inputs(ap, operator)
            if not ports:
                continue

            operator_id = str(operator.id)
            operator_name = operator.properties.get("name", "")
            instruction = magic_instructions.get(operator_id)

            if instruction is not None:
                # The instruction was written by the magic operator builder for this exact
                # step; asking the value suggester to re-invent it would only lose it.
                parameters.extend(_instruction_parameters(
                    ports, instruction, operator_id, operator_name))
            else:
                parameters.extend(self.value_suggester.suggest(
                    task, ports,
                    datasets=datasets,
                    operator_id=operator_id,
                    operator_name=operator_name,
                ))

        return parameters


def _unsatisfied_inputs(ap: AnalyticalPattern, operator: Node) -> List[OperatorPort]:
    """The operator's inputs that still need a caller-supplied value.

    Inputs already fed by an `input` edge are excluded: the executor resolves those from
    the upstream operator at run time, and that value overrides anything suggested here.
    """
    wired = wired_input_names(ap, str(operator.id))
    return [
        port for port in OperatorPort.from_properties(
            operator.properties.get("inputs", []))
        if port.name not in wired
    ]


def _terminal_outputs(ap: AnalyticalPattern) -> List[OperatorPort]:
    """The outputs a following step would consume, used to name a magic step's input."""
    terminal = find_terminal_operator(ap)
    return OperatorPort.from_properties(terminal.properties.get("outputs", []))


def _instruction_parameters(
    ports: List[OperatorPort],
    instruction: str,
    operator_id: str,
    operator_name: str,
) -> List[SuggestedParameter]:
    """
    Bind a magic operator's `instruction` input to the generated instruction, and leave its
    payload input for the caller (or, mid-chain, for the upstream operator that feeds it).
    """
    return [
        SuggestedParameter(
            **port.model_dump(),
            suggested_value=instruction if port.name == INSTRUCTION_INPUT else port.default,
            operator_id=operator_id,
            operator_name=operator_name,
        )
        for port in ports
    ]
