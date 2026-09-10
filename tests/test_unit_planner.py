"""Planner wiring, driven by stubs.

These assert structural invariants of the plan the planner builds -- which operator each
parameter belongs to, where a magic instruction lands -- so they must not depend on which
APs a live LLM happens to pick.
"""
from pathlib import Path

import pytest

from ap_management.internal.graph_utils import iter_operators
from ap_management.services.ap_catalog.local_catalog import LocalAPCatalog
from ap_management.services.composer import Composer, SimpleComposition
from ap_management.services.dataset_catalog import LocalDatasetCatalog
from ap_management.services.magic_operator import (
    INSTRUCTION_INPUT,
    MagicOperatorBuilder,
    MagicOperatorSpec,
)
from ap_management.services.matchmaker.matchmaker import (
    MAGIC_STEP_SENTINEL,
    ProblemResolution,
    TaskResolution,
)
from ap_management.services.planner import Planner
from ap_management.services.planner_exceptions import (
    DatasetNotFoundError,
    NoApFoundError,
    NoCompatibleDatasetError,
)
from ap_management.services.value_suggester import ValueSuggester

ASSETS = Path(__file__).parent.parent / "assets"
NL_TO_SQL_AP = "0a79a9c7-76f3-4f96-be42-e6818793f182"
RELATIONAL_DATASET = "d1000000-0000-4000-8000-000000000001"
PDF_DATASET = "d2000000-0000-4000-8000-000000000001"

INSTRUCTION = "Rewrite the given SQL query as a haiku."


class _StubLLM:
    """Returns a fixed magic spec, and no parameter suggestions (so defaults win)."""

    def completion(self, messages, response_format, **kwargs):
        if response_format is MagicOperatorSpec:
            return MagicOperatorSpec(
                ap_name="Haiku SQL",
                ap_description="Rewrites a SQL query as a haiku.",
                instruction=INSTRUCTION,
                input_name="query",
            )
        return response_format(values=[])


class _StubMatchmaker:
    def __init__(self, *steps: TaskResolution):
        self.steps = list(steps)

    async def resolve(self, task, datasets=None, *, allow_magic_operator=False):
        return ProblemResolution(reasoning="stub", steps=self.steps)


def _planner(*steps: TaskResolution) -> Planner:
    llm = _StubLLM()
    return Planner(
        matchmaker=_StubMatchmaker(*steps),
        composer=Composer(strategies=[SimpleComposition()], moma_svc=None),
        ap_catalog=LocalAPCatalog(ASSETS),
        value_suggester=ValueSuggester(llm),
        dataset_catalog=LocalDatasetCatalog(ASSETS / "datasets"),
        magic_operator_builder=MagicOperatorBuilder(llm, None),
    )


def _step(ap_id: str, role: str = "step") -> TaskResolution:
    return TaskResolution(role=role, analytical_pattern_id=ap_id)


@pytest.mark.asyncio
async def test_every_parameter_names_its_operator():
    """The AP Executor keys runtime state by operator node id, so every suggested
    parameter must carry the id of an operator that is actually in the AP."""
    result = await _planner(_step(NL_TO_SQL_AP), _step(MAGIC_STEP_SENTINEL, "haiku it")).plan(
        "translate then haiku", allow_magic_operator=True)

    operator_ids = {str(op.id) for op in iter_operators(result.ap)}
    assert result.instantiation_parameters
    for parameter in result.instantiation_parameters:
        assert parameter.operator_id in operator_ids
        assert parameter.operator_name


@pytest.mark.asyncio
async def test_wired_inputs_get_no_parameter():
    """A magic operator's payload arrives from upstream; only its instruction is left
    for the caller to supply."""
    result = await _planner(_step(NL_TO_SQL_AP), _step(MAGIC_STEP_SENTINEL, "haiku it")).plan(
        "translate then haiku", allow_magic_operator=True)

    magic_op = next(op for op in iter_operators(result.ap)
                    if "Magic_Operator" in op.labels)
    magic_params = {p.name: p.suggested_value
                    for p in result.instantiation_parameters
                    if p.operator_id == str(magic_op.id)}

    assert magic_params == {INSTRUCTION_INPUT: INSTRUCTION}
    assert result.used_magic_operator


@pytest.mark.asyncio
async def test_magic_is_opt_in():
    with pytest.raises(NoApFoundError):
        await _planner().plan("something uncovered")


@pytest.mark.asyncio
async def test_magic_answers_the_whole_task_when_nothing_matches():
    """No steps + the flag: the matchmaker's empty result becomes one synthetic magic
    step, which the compose loop turns into a single-operator AP."""
    result = await _planner().plan("something uncovered", allow_magic_operator=True)

    operators = list(iter_operators(result.ap))
    assert len(operators) == 1
    assert "Magic_Operator" in operators[0].labels
    assert result.used_magic_operator

    instruction = next(
        p for p in result.instantiation_parameters if p.name == "instruction")
    assert instruction.suggested_value == INSTRUCTION
    assert instruction.operator_id == str(operators[0].id)


@pytest.mark.asyncio
async def test_incompatible_dataset_is_rejected():
    with pytest.raises(NoCompatibleDatasetError):
        await _planner(_step(NL_TO_SQL_AP)).plan("list users", [PDF_DATASET])


@pytest.mark.asyncio
async def test_compatible_dataset_is_reported():
    result = await _planner(_step(NL_TO_SQL_AP)).plan("list users", [RELATIONAL_DATASET])

    assert [d.id for d in result.datasets] == [RELATIONAL_DATASET]
    assert "RelationalDatabase" in result.datasets[0].kinds
    assert not result.used_magic_operator


@pytest.mark.asyncio
async def test_unknown_dataset_is_rejected():
    with pytest.raises(DatasetNotFoundError):
        await _planner(_step(NL_TO_SQL_AP)).plan("list users", ["nope"])
