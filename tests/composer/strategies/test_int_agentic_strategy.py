from json import dumps

import pytest

from ap_management.di import get_llm
from ap_management.services.composer.strategies.agentic import AgenticComposition
from tests.conftest import ApTestCase


@pytest.fixture
def strat() -> AgenticComposition:
    try:
        return AgenticComposition(get_llm())
    except ValueError:
        pytest.skip(
            "LLM configuration is not set, skipping agentic composition tests.")


# @pytest.mark.repeat(10)
def test_agentic_strategy(case: ApTestCase, strat: AgenticComposition):
    if not case.agentic.applicable:
        pytest.skip("Agentic strategy is not applicable for this test case.")

    success, mapping = strat.generate_mapping(case.ap1, case.ap2)

    assert success == case.agentic.succeeds, dumps(mapping, indent=2)
    if case.agentic.succeeds:
        assert mapping == case.expected_mappings


@pytest.mark.skip(reason="Benchmarking test, not meant for regular test runs.")
def test_bench_agentic_strategy(case: ApTestCase, strat: AgenticComposition, benchmark):
    if not case.agentic.applicable:
        pytest.skip("Agentic strategy is not applicable for this test case.")

    success, mapping = benchmark(strat.generate_mapping, case.ap1, case.ap2)
    assert success == case.agentic.succeeds, dumps(mapping, indent=2)

    if case.agentic.succeeds:
        assert mapping == case.expected_mappings
