from pathlib import Path

import pytest
from moma_management.domain.analytical_pattern import AnalyticalPattern

from ap_management.di import get_composer, get_moma_svc
from ap_management.internal.llm import LLM
from ap_management.services.matchmaker import LocalAPCatalog, Matchmaker
from ap_management.services.planner import Planner
from ap_management.services.planner_exceptions import NoApFoundError
from ap_management.services.value_suggester import ValueSuggester
from tests.ap_test_cases import AP_TEST_CASES, ApTestCase

_ASSETS_PATH = Path(__file__).parent.parent / "assets"


@pytest.fixture
def planner(llm: LLM) -> Planner:
    moma_svc = get_moma_svc()
    catalog = LocalAPCatalog(_ASSETS_PATH)
    return Planner(
        matchmaker=Matchmaker(llm, catalog),
        composer=get_composer(moma_svc),
        ap_catalog=catalog,
        value_suggester=ValueSuggester(llm),
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
