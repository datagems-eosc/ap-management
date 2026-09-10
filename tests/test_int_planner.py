from pathlib import Path

import pytest
from moma_management.domain.analytical_pattern import AnalyticalPattern

from ap_management.di import get_composer, get_moma_svc
from ap_management.internal.graph_utils import iter_operators
from ap_management.internal.llm import LLM
from ap_management.services.dataset_catalog import LocalDatasetCatalog
from ap_management.services.magic_operator import (
    INSTRUCTION_INPUT,
    MagicOperatorBuilder,
)
from ap_management.services.matchmaker import LocalAPCatalog, Matchmaker
from ap_management.services.planner import Planner
from ap_management.services.planner_exceptions import (
    NoApFoundError,
    NoCompatibleDatasetError,
)
from ap_management.services.value_suggester import ValueSuggester
from tests.ap_test_cases import AP_TEST_CASES, ApTestCase

_ASSETS_PATH = Path(__file__).parent.parent / "assets"
_DATASETS_PATH = _ASSETS_PATH / "datasets"

RELATIONAL_DATASET_ID = "d1000000-0000-4000-8000-000000000001"
PDF_DATASET_ID = "d2000000-0000-4000-8000-000000000001"


@pytest.fixture
def planner(llm: LLM) -> Planner:
    moma_svc = get_moma_svc()
    catalog = LocalAPCatalog(_ASSETS_PATH)
    return Planner(
        matchmaker=Matchmaker(llm, catalog),
        composer=get_composer(moma_svc),
        ap_catalog=catalog,
        value_suggester=ValueSuggester(llm),
        dataset_catalog=LocalDatasetCatalog(_DATASETS_PATH),
        magic_operator_builder=MagicOperatorBuilder(llm, moma_svc),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tc",
    [tc for tc in AP_TEST_CASES if tc.task],
    ids=[tc.name for tc in AP_TEST_CASES if tc.task],
)
async def test_plan_task(planner: Planner, tc: ApTestCase):
    result = await planner.plan(tc.task)
    assert isinstance(result.ap, AnalyticalPattern)


@pytest.mark.asyncio
async def test_plan_three_steps(planner: Planner):
    result = await planner.plan(
        "Translate the natural-language query 'list all users older than 30' to SQL, "
        "explain the query with provenance information, and produce a structured provenance report."
    )
    assert isinstance(result.ap, AnalyticalPattern)
    nl_param = next(
        p for p in result.instantiation_parameters if p.name == "nl")
    assert "30" in nl_param.suggested_value


@pytest.mark.asyncio
async def test_plan_no_result(planner: Planner):
    with pytest.raises(NoApFoundError):
        await planner.plan("Pinpoint a satellite location")


# --- datasets ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_plan_with_a_compatible_dataset(planner: Planner):
    result = await planner.plan(
        "List all students older than 30", [RELATIONAL_DATASET_ID]
    )

    assert isinstance(result.ap, AnalyticalPattern)
    assert [d.id for d in result.datasets] == [RELATIONAL_DATASET_ID]
    assert "RelationalDatabase" in result.datasets[0].kinds


@pytest.mark.asyncio
async def test_sql_task_over_a_pdf_dataset_is_rejected(planner: Planner):
    """A SQL operator cannot run over a document corpus, however well the task's wording
    matches the AP's description."""
    with pytest.raises((NoCompatibleDatasetError, NoApFoundError)):
        await planner.plan(
            "List all students older than 30 using SQL", [PDF_DATASET_ID]
        )


# --- magic operator ---------------------------------------------------------


@pytest.mark.asyncio
async def test_magic_operator_answers_an_uncovered_task(planner: Planner):
    result = await planner.plan(
        "Summarize the main arguments of a climate policy report",
        allow_magic_operator=True,
    )

    assert result.used_magic_operator
    magic_ops = [
        op for op in iter_operators(result.ap) if "Magic_Operator" in op.labels]
    assert len(magic_ops) == 1

    instruction = next(
        p for p in result.instantiation_parameters if p.name == INSTRUCTION_INPUT)
    assert instruction.operator_id == str(magic_ops[0].id)
    assert instruction.suggested_value


@pytest.mark.asyncio
async def test_magic_operator_fills_a_mid_chain_gap(planner: Planner):
    """'text to sql' is catalogued, explaining the result in plain English is not: the
    planner should chain the real AP with a magic step rather than give up."""
    result = await planner.plan(
        "Translate 'list all users older than 30' to SQL, then rewrite the resulting "
        "query as a haiku.",
        allow_magic_operator=True,
    )

    assert result.used_magic_operator
    operators = list(iter_operators(result.ap))
    assert len(operators) >= 2
    assert any("Magic_Operator" in op.labels for op in operators)
