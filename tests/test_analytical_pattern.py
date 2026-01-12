import pytest

from ap_management.domain import AnalyticalPattern
from ap_management.services.analytical_pattern import AnalyticalPatternService
from tests.conftest import load_asset


def test_validate_ap():
    """
    Basic validation for an Ap
    """
    sql_ap_plain = load_asset("ap_sql_select")
    AnalyticalPattern.model_validate_json(sql_ap_plain)


@pytest.mark.asyncio
async def test_store_ap(ap_svc: AnalyticalPatternService):
    sql_ap_plain = load_asset("ap_sql_select")
    sql_ap = AnalyticalPattern.model_validate_json(sql_ap_plain)
    await ap_svc.create(sql_ap)
