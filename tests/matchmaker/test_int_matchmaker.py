from pathlib import Path

import pytest

from ap_management.di import get_llm
from ap_management.services.matchmaker import LocalAPCatalog, Matchmaker
from tests.ap_test_cases import AP_TEST_CASES, ApTestCase

_ASSETS_PATH = Path(__file__).parent.parent.parent / "assets"


class ApName:
    TEXT_TO_SQL = "0a79a9c7-76f3-4f96-be42-e6818793f182"
    EXPLAIN = "0c2052db-1274-4fd8-b428-1538ce7bfe6f"
    PROVENANCE_REPORT = "a8a80000-0000-4000-8000-000000000001"


@pytest.fixture
def matchmaker():
    return Matchmaker(get_llm(), LocalAPCatalog(_ASSETS_PATH))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tc",
    [tc for tc in AP_TEST_CASES if tc.task],
    ids=[tc.name for tc in AP_TEST_CASES if tc.task],
)
async def test_matchmaker_task(matchmaker: Matchmaker, tc: ApTestCase):
    response = await matchmaker.resolve(tc.task)
    expected = [str(tc.ap1.root.id), str(tc.ap2.root.id)]
    actual = [step.analytical_pattern_id for step in response.steps]
    assert actual == expected, f"Expected {expected}: {response.reasoning}"


@pytest.mark.asyncio
async def test_decomposition_three_steps(matchmaker: Matchmaker):
    response = await matchmaker.resolve("Translate a natural-language query to SQL, explain the query with provenance information, and produce a structured provenance report.")
    assert len(response.steps) == 3, f"Failed: {response.reasoning}"
    assert response.steps[
        0].analytical_pattern_id == ApName.TEXT_TO_SQL, f"Expected Text to SQL AP first: {response.reasoning}"
    assert response.steps[
        1].analytical_pattern_id == ApName.EXPLAIN, f"Expected Explain AP second: {response.reasoning}"
    assert response.steps[
        2].analytical_pattern_id == ApName.PROVENANCE_REPORT, f"Expected Provenance Report AP third: {response.reasoning}"


@pytest.mark.asyncio
async def test_decomposition_no_result(matchmaker: Matchmaker):
    response = await matchmaker.resolve("Pinpoint a satellite location")
    assert len(response.steps) == 0, f"Failed: {response.reasoning}"
