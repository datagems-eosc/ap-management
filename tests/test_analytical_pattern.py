import pytest
from pydantic import BaseModel

from ap_management.domain import AnalyticalPattern
from ap_management.services.analytical_pattern import AnalyticalPatternService
from tests.conftest import load_asset


class ApTestCase(BaseModel):
    # File name on disk
    asset_name: str
    # Why bother with this case
    reason: str


test_cases = [
    ApTestCase(asset_name="ap_sql_select_with_task", reason="with a task"),
    ApTestCase(
        asset_name="ap_sql_select_without_task", reason="without a task"
    ),
]


@pytest.mark.parametrize("case", test_cases, ids=[tc.reason for tc in test_cases])
def test_validate_ap(case: ApTestCase):
    """
    Basic validation for an Ap
    """
    sql_ap_plain = load_asset(case.asset_name)
    AnalyticalPattern.model_validate_json(sql_ap_plain)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", test_cases, ids=[tc.reason for tc in test_cases])
async def test_store_ap(case: ApTestCase, ap_svc: AnalyticalPatternService):
    sql_ap_plain = load_asset(case.asset_name)
    sql_ap = AnalyticalPattern.model_validate_json(sql_ap_plain)
    await ap_svc.create(sql_ap)
