import pytest

from ap_management.services.composer import SimpleComposition
from tests.conftest import ApTestCase


@pytest.fixture
def strat() -> SimpleComposition:
    return SimpleComposition()


def test_simple_strategy(case: ApTestCase, strat: SimpleComposition):
    is_possible, reason = strat.is_possible(case.ap1, case.ap2)
    assert is_possible == case.simple.applicable, f"Expected applicable={case.simple.applicable} but got {is_possible}. Reason: {reason}"
    if not is_possible:
        return

    success, mapping = strat.generate_mapping(case.ap1, case.ap2)
    assert success == case.simple.succeeds, f"Expected succeeds={case.simple.succeeds} but got {success}. Mapping: {mapping}"
    assert mapping == case.expected_mappings
